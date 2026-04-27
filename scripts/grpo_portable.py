# /// script
# dependencies = [
#   "torch>=2.4,<2.5",
#   "trl==0.12.1",
#   "unsloth @ git+https://github.com/unslothai/unsloth.git",
#   "datasets",
#   "transformers==4.47.1",
#   "setuptools",
#   "xformers==0.0.28.post2",
# ]
# ///
import os
import sys
import traceback
import json
import re

print("Python Version:", sys.version)
print("Current Working Directory:", os.getcwd())

try:
    print("Checking torch...")
    import torch
    print(f"Torch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA device: {torch.cuda.get_device_name(0)}")
except Exception:
    print("CRITICAL: Torch check failed")
    traceback.print_exc()

try:
    print("Importing unsloth...")
    import unsloth
    from unsloth import FastLanguageModel, PatchFastRL
    print("Patching GRPO...")
    PatchFastRL("GRPO", FastLanguageModel)
except Exception:
    print("CRITICAL: Failed to import/patch unsloth")
    traceback.print_exc()
    sys.exit(1)

from pathlib import Path
from dataclasses import dataclass
from typing import Any, Optional
try:
    from datasets import load_dataset
    from trl import GRPOConfig, GRPOTrainer
except Exception:
    print("CRITICAL: Failed to import datasets/trl")
    traceback.print_exc()
    sys.exit(1)

# --- Patch for TRANSFORMERS_CACHE (removed in recent transformers) ---
try:
    import transformers.utils.hub as hub
    if not hasattr(hub, "TRANSFORMERS_CACHE"):
        hub.TRANSFORMERS_CACHE = os.getenv("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
except ImportError:
    pass

# --- 1. Environment Logic (Inlined for Portability) ---

@dataclass(frozen=True, slots=True)
class CommitGuardAction:
    action_type: str  # request_context | analyze | verdict
    file_path: Optional[str] = None
    reasoning: Optional[str] = None
    is_vulnerable: Optional[bool] = None
    vuln_type: Optional[str] = None
    exploit_sketch: Optional[str] = None
    raw_action: Optional[str] = None
    parse_error: Optional[str] = None

def _first(tag: str, text: str) -> Optional[str]:
    pattern = rf"<[ \t]*{re.escape(tag)}[ \t]*>(.*?)</[ \t]*{re.escape(tag)}[ \t]*>"
    m = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else None

def _parse_bool(v: Optional[str]) -> Optional[bool]:
    if v is None: return None
    s = v.strip().lower()
    if s in {"true", "1", "yes"}: return True
    if s in {"false", "0", "no"}: return False
    return None

def parse_action(raw_action: str) -> CommitGuardAction:
    try:
        action_type = (_first("action_type", raw_action) or "").strip().lower()
        if action_type not in {"request_context", "analyze", "verdict"}:
            return CommitGuardAction(action_type="analyze", raw_action=raw_action, parse_error="missing_or_invalid_action_type")
        if action_type == "request_context":
            return CommitGuardAction(action_type="request_context", file_path=_first("file_path", raw_action), raw_action=raw_action)
        if action_type == "analyze":
            return CommitGuardAction(action_type="analyze", reasoning=_first("reasoning", raw_action), raw_action=raw_action)
        return CommitGuardAction(
            action_type="verdict",
            is_vulnerable=_parse_bool(_first("is_vulnerable", raw_action)),
            vuln_type=_first("vuln_type", raw_action),
            exploit_sketch=_first("exploit_sketch", raw_action),
            raw_action=raw_action,
        )
    except Exception as e:
        return CommitGuardAction(action_type="analyze", raw_action=raw_action, parse_error=f"parser_exception:{type(e).__name__}")

def compute_reward(action: CommitGuardAction, is_vulnerable: bool, cwe: str) -> float:
    if action.parse_error: return -0.5
    if action.action_type != "verdict": return 0.0 # Reward for analysis/context is neutral here
    pred = action.is_vulnerable
    if pred is None: return -0.5
    
    # Correctness
    if pred == is_vulnerable:
        reward = 1.0
        # CWE bonus
        if is_vulnerable and action.vuln_type and cwe:
            if action.vuln_type.strip().upper() == cwe.strip().upper():
                reward += 0.5
        return reward
    else:
        # False positive is penalized more than false negative
        return -1.0 if pred else -0.5

# --- 2. GRPO Reward Function ---

SAMPLE_LABELS = {}

def reward_func(prompts, completions, sample_id, **kwargs) -> list[float]:
    rewards = []
    for sid, completion in zip(sample_id, completions):
        text = completion[-1]["content"] if isinstance(completion, list) else str(completion)
        action = parse_action(text)
        labels = SAMPLE_LABELS.get(sid, {})
        reward = compute_reward(
            action=action,
            is_vulnerable=labels.get("is_vulnerable", False),
            cwe=labels.get("cwe", "NONE")
        )
        rewards.append(reward)
    return rewards

# --- 3. Prompt Template ---

SYSTEM_PROMPT = """You are a senior security auditor reviewing code commits for exploitable vulnerabilities.
You operate in a multi-step environment. Each turn you must output exactly ONE action in XML tags:
<action>
<action_type>verdict</action_type>
<fields>
<is_vulnerable>true or false</is_vulnerable>
<vuln_type>CWE-XXX or NONE</vuln_type>
<exploit_sketch>Concrete attack scenario...</exploit_sketch>
</fields>
</action>"""

def format_prompt(sample):
    return {
        "prompt": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze this commit and submit your verdict.\n\nCode diff:\n```diff\n{sample['diff']}\n```"},
        ],
        "sample_id": sample["sample_id"],
    }

# --- 4. Main Training Logic ---

def main():
    print("Initializing Unsloth GRPO...")
    
    MODEL_NAME = "Divyank1607/commitguard-llama-3b-lora"
    DATASET_ID = "Divyank1607/commitguard-data"
    HF_TOKEN = os.getenv("HF_TOKEN")
    
    # 1. Load Model
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=2048,
        load_in_4bit=True,
        fast_inference=False, # Disable to avoid vllm issues in this env
        token=HF_TOKEN,
    )
    
    # Check if we need to add adapters
    if not hasattr(model, "peft_config"):
        model = FastLanguageModel.get_peft_model(
            model,
            r=8,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            lora_alpha=16,
            lora_dropout=0,
            bias="none",
            use_gradient_checkpointing="unsloth",
            random_state=3407,
        )
    else:
        model.gradient_checkpointing_enable()

    # 2. Build Dataset
    print(f"Loading dataset {DATASET_ID}...")
    raw_dataset = load_dataset(DATASET_ID, data_files="devign_train.jsonl", split="train", token=HF_TOKEN)
    # Filter for samples with labels
    raw_dataset = raw_dataset.select(range(min(200, len(raw_dataset))))
    
    for row in raw_dataset:
        SAMPLE_LABELS[row["sample_id"]] = {
            "is_vulnerable": row["is_vulnerable"],
            "cwe": row.get("cwe", "NONE")
        }
        
    dataset = raw_dataset.map(format_prompt)

    # 3. Training Config
    training_args = GRPOConfig(
        output_dir="outputs/commitguard-grpo",
        num_generations=8,
        max_completion_length=256,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=5e-6,
        max_steps=100, # Quick run for demonstration
        logging_steps=1,
        save_steps=50,
        bf16=torch.cuda.is_bf16_supported(),
        fp16=not torch.cuda.is_bf16_supported(),
        report_to="none"
    )

    # 4. Train
    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        reward_funcs=[reward_func],
        args=training_args,
        train_dataset=dataset,
    )
    
    print("Starting GRPO Training...")
    trainer.train()

    # 5. Push to Hub
    PUSH_ID = "Divyank1607/commitguard-llama-3b-grpo"
    print(f"Pushing to {PUSH_ID}...")
    model.push_to_hub(PUSH_ID, token=HF_TOKEN)
    tokenizer.push_to_hub(PUSH_ID, token=HF_TOKEN)
    print("Done!")

if __name__ == "__main__":
    import traceback
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
