import os
import sys
import json
import argparse
from pathlib import Path

from unsloth import FastLanguageModel
import torch
from datasets import Dataset, load_dataset
from trl import SFTTrainer, SFTConfig

# --- Embedded Prompts ---
SYSTEM_PROMPT = """\
You are a senior security auditor reviewing code commits for exploitable vulnerabilities.

You operate in a multi-step environment (up to 5 steps). Each turn you must output exactly ONE action in XML tags.

## Actions

**1. Request Context** — fetch the full content of a file (small cost; first request is free).
<action>
<action_type>request_context</action_type>
<file_path>filename.c</file_path>
</action>

**2. Analyze** — record your chain-of-thought reasoning before deciding.
<action>
<action_type>analyze</action_type>
<reasoning>
1. Identify what the diff changes (added/removed lines, control flow).
2. Check for common vulnerability patterns (see CWE list below).
3. Consider whether surrounding context could mitigate the issue.
</reasoning>
</action>

**3. Verdict** — issue your final judgment (terminates the episode).
<action>
<action_type>verdict</action_type>
<is_vulnerable>true or false</is_vulnerable>
<vuln_type>CWE-XXX or NONE</vuln_type>
<exploit_sketch>Concrete attack scenario: name the function, input, and impact.</exploit_sketch>
</action>

## Strategy
- Start by reading the diff carefully. If the diff is short and self-contained, go straight to a verdict.
- Request context only when the diff references functions, macros, or types whose safety you cannot judge from the diff alone.
- Use an analyze step when the vulnerability pattern is ambiguous — lay out your reasoning before committing.
- Be specific in exploit_sketch: name the vulnerable function, the attacker-controlled input, and the impact (crash, code exec, data leak).

## Common CWE patterns in C/C++ diffs
- **CWE-119/120/787** (Buffer overflow): unchecked memcpy/strcpy, missing bounds on array index, off-by-one in loop.
- **CWE-476** (Null dereference): pointer used without NULL check after allocation or lookup.
- **CWE-189/190** (Integer issues): arithmetic on user-controlled size, signed/unsigned comparison, truncating cast.
- **CWE-20** (Input validation): missing length/range check on external input before use.
- **CWE-22** (Path traversal): unsanitized file path from user input, no chroot/canonicalization.
- **CWE-78** (Command injection): user input passed to system()/popen() without escaping.
- **CWE-89** (SQL injection): string concatenation into SQL query.

## Rules
- If the code is safe, set is_vulnerable to false and vuln_type to NONE.
- You have a maximum of 5 steps. Budget wisely.
- Do NOT guess randomly — false positives are penalized more heavily than false negatives.
"""

# --- Configuration ---
MODEL_NAME = os.getenv("MODEL_NAME", "Divyank1607/commitguard-llama-3b-lora")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs/commitguard-llama-3b-sft")

def get_formatting_func(tokenizer):
    def formatting_prompts_func(examples):
        instructions = examples["diff"]
        is_vulnerable_list = examples["is_vulnerable"]
        cwe_list = examples["cwe"]
        
        texts = []
        for diff, is_vulnerable, cwe in zip(instructions, is_vulnerable_list, cwe_list):
            vuln_str = "true" if is_vulnerable else "false"
            cwe_str = cwe if cwe and is_vulnerable else "NONE"
            
            if is_vulnerable:
                sketch = f"Attacker targets the vulnerable pattern in the code diff ({cwe_str})."
            else:
                sketch = "No vulnerability identified in the provided code diff."

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Analyze this commit and submit your verdict.\n\nCode diff:\n```diff\n{diff}\n```"},
                {"role": "assistant", "content": f"<action>\n<action_type>verdict</action_type>\n<fields>\n<is_vulnerable>{vuln_str}</is_vulnerable>\n<vuln_type>{cwe_str}</vuln_type>\n<exploit_sketch>{sketch}</exploit_sketch>\n</fields>\n</action>"}
            ]
            
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
            texts.append(text)
        return { "text" : texts }
    return formatting_prompts_func

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=5000)
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--batch-size", type=int, default=2)
    ap.add_argument("--grad-accum", type=int, default=4)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--max-seq-length", type=int, default=2048)
    ap.add_argument("--push-to-hub", action="store_true")
    ap.add_argument("--hub-model-id", type=str, default="Divyank1607/commitguard-llama-3b-sft-v2")
    args = ap.parse_args()

    # 1. Load Model & Tokenizer
    print(f"Loading {MODEL_NAME} with Unsloth...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=args.max_seq_length,
        load_in_4bit=True,
        token=os.getenv("HF_TOKEN", "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"),
    )

    # Only add PEFT adapters if not already present
    if not hasattr(model, "peft_config"):
        print("Adding new LoRA adapters...")
        model = FastLanguageModel.get_peft_model(
            model,
            r=16,
            target_modules=[
                "q_proj", "k_proj", "v_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj",
            ],
            lora_alpha=32,
            lora_dropout=0,
            bias="none",
            use_gradient_checkpointing="unsloth",
            random_state=3407,
        )
    else:
        print("Using existing LoRA adapters from the loaded model.")
        # Ensure gradient checkpointing is enabled for training
        model.gradient_checkpointing_enable()

    # 2. Prepare Dataset
    # Load from HF Hub for remote execution
    dataset_id = os.getenv("DATASET_ID", "Divyank1607/commitguard-data")
    # Use the token provided by the user for private access
    hf_token = os.getenv("HF_TOKEN", "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")
    
    print(f"Loading SFT samples from Hub: {dataset_id}...")
    
    try:
        # Load the jsonl file directly from the dataset repo with token
        dataset = load_dataset(dataset_id, data_files="devign_train.jsonl", split="train", token=hf_token)
    except Exception as e:
        print(f"Failed to load dataset from Hub: {e}")
        print("Falling back to local data/devign_train.jsonl if available...")
        data_path = Path.cwd() / "data" / "devign_train.jsonl"
        if not data_path.exists():
            data_path = Path.cwd() / "devign_train.jsonl"
        
        if data_path.exists():
            dataset = load_dataset("json", data_files=str(data_path), split="train")
        else:
            print("Dataset not found on Hub or locally. Exiting.")
            return

    dataset = dataset.select(range(min(args.samples, len(dataset))))
    
    formatting_func = get_formatting_func(tokenizer)
    dataset = dataset.map(formatting_func, batched=True)

    # 3. SFT Config
    training_args = SFTConfig(
        output_dir=OUTPUT_DIR,
        dataset_text_field="text",
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        num_train_epochs=args.epochs,
        logging_steps=10,
        save_steps=100,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=3407,
    )

    # 4. Train
    print("Starting Supervised Fine-Tuning...")
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        max_seq_length=args.max_seq_length,
        args=training_args,
    )
    
    trainer.train()

    # 5. Save
    final_dir = f"{OUTPUT_DIR}/final"
    model.save_pretrained_merged(final_dir, tokenizer, save_method="lora")
    print(f"SFT complete. LoRA adapter saved to {final_dir}")

    if args.push_to_hub:
        print(f"Pushing to HF Hub: {args.hub_model_id}")
        model.push_to_hub(args.hub_model_id, token=True)
        tokenizer.push_to_hub(args.hub_model_id, token=True)

if __name__ == "__main__":
    main()
