# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "torch",
#     "transformers",
#     "datasets",
#     "accelerate",
#     "bitsandbytes",
#     "peft",
#     "unsloth",
#     "sentencepiece",
#     "torchvision",
# ]
# ///

import os
import json
import argparse
import torch
import sys
import re
from dataclasses import dataclass
from typing import Optional, Literal, Any
from datasets import load_dataset
from unsloth import FastLanguageModel

# --- INLINED MODELS ---
ActionType = Literal["request_context", "analyze", "verdict"]

@dataclass(frozen=True)
class CommitGuardAction:
    action_type: ActionType
    file_path: Optional[str] = None
    reasoning: Optional[str] = None
    is_vulnerable: Optional[bool] = None
    vuln_type: Optional[str] = None
    exploit_sketch: Optional[str] = None
    raw_action: Optional[str] = None
    parse_error: Optional[str] = None

# --- INLINED PARSER ---
def _first(tag: str, text: str) -> Optional[str]:
    pattern = rf"<[ \t]*{re.escape(tag)}[ \t]*>(.*?)</[ \t]*{re.escape(tag)}[ \t]*>"
    m = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
    if not m:
        return None
    return m.group(1).strip()

def _parse_bool(v: Optional[str]) -> Optional[bool]:
    if v is None:
        return None
    s = v.strip().lower()
    if s in {"true", "1", "yes"}:
        return True
    if s in {"false", "0", "no"}:
        return False
    return None

def parse_action(raw_action: str) -> CommitGuardAction:
    try:
        action_type = (_first("action_type", raw_action) or "").strip().lower()
        if action_type not in {"request_context", "analyze", "verdict"}:
            return CommitGuardAction(
                action_type="analyze",
                raw_action=raw_action,
                parse_error="missing_or_invalid_action_type",
            )

        if action_type == "request_context":
            file_path = _first("file_path", raw_action)
            return CommitGuardAction(
                action_type="request_context",
                file_path=file_path,
                raw_action=raw_action,
            )

        if action_type == "analyze":
            reasoning = _first("reasoning", raw_action)
            return CommitGuardAction(action_type="analyze", reasoning=reasoning, raw_action=raw_action)

        is_vulnerable = _parse_bool(_first("is_vulnerable", raw_action))
        vuln_type = _first("vuln_type", raw_action)
        exploit_sketch = _first("exploit_sketch", raw_action)
        return CommitGuardAction(
            action_type="verdict",
            is_vulnerable=is_vulnerable,
            vuln_type=vuln_type,
            exploit_sketch=exploit_sketch,
            raw_action=raw_action,
        )
    except Exception as e:
        return CommitGuardAction(
            action_type="analyze",
            raw_action=raw_action,
            parse_error=f"parser_exception:{type(e).__name__}",
        )

# --- EVAL LOGIC ---
SYSTEM_PROMPT = """\\
You are a senior security auditor reviewing code commits for exploitable vulnerabilities.

You operate in a multi-step environment (up to 5 steps). Each turn you must output exactly ONE action in XML tags.

## Actions

**1. Request Context** — fetch the full content of a file (small cost; first request is free).
<action>
<action_type>request_context</action_type>
<file_path>filename.c</file_path>
</action>

**2. Analyze** — explain your thinking before giving a verdict (no cost).
<action>
<action_type>analyze</action_type>
<fields>
<reasoning>
1. Identify what the diff changes (added/removed lines, control flow).
2. Check for common vulnerability patterns (see CWE list below).
3. Consider whether surrounding context could mitigate the issue.
</reasoning>
</fields>
</action>

**3. Verdict** — issue your final judgment (terminates the episode).
<action>
<action_type>verdict</action_type>
<is_vulnerable>true or false</is_vulnerable>
<vuln_type>CWE-XXX or NONE</vuln_type>
<exploit_sketch>Concrete attack scenario: name the function, input, and impact.</exploit_sketch>
</action>
"""

def format_eval_prompt(sample):
    return (
        f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\\n\\n"
        f"{SYSTEM_PROMPT}<|eot_id|><|start_header_id|>user<|end_header_id|>\\n\\n"
        f"Analyze this commit and submit your verdict.\\n\\n"
        f"Code diff:\\n```diff\\n{sample['diff']}\\n```<|eot_id|><|start_header_id|>assistant<|end_header_id|>\\n\\n"
    )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_id", type=str, default="Divyank1607/commitguard-llama-3b-sft-v2")
    parser.add_argument("--dataset_id", type=str, default="Divyank1607/commitguard-data")
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--max_seq_length", type=int, default=2048)
    args = parser.parse_args()

    hf_token = os.getenv("HF_TOKEN")
    
    print("--- GPU Diagnostics ---")
    print(f"Python version: {sys.version}")
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA device: {torch.cuda.get_device_name(0)}")
        print(f"CUDA version: {torch.version.cuda}")
    else:
        print("CRITICAL: CUDA NOT AVAILABLE!")
        # Try to run nvidia-smi to see if hardware is even there
        import subprocess
        try:
            res = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
            print("nvidia-smi output:")
            print(res.stdout)
        except Exception as e:
            print(f"Could not run nvidia-smi: {e}")

    print(f"Loading model: {args.model_id}...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name = args.model_id,
        max_seq_length = args.max_seq_length,
        load_in_4bit = True,
        token = hf_token,
    )
    FastLanguageModel.for_inference(model)

    print(f"Loading test dataset: {args.dataset_id}...")
    dataset = load_dataset(args.dataset_id, data_files="devign_test.jsonl", split="train", token=hf_token)
    
    num_samples = min(args.samples, len(dataset))
    eval_dataset = dataset.select(range(num_samples))

    results = {
        "summary": {
            "total": num_samples,
            "correct_binary": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "accuracy": 0,
        },
        "predictions": []
    }

    print(f"Evaluating {num_samples} samples...")
    for i, sample in enumerate(eval_dataset):
        prompt = format_eval_prompt(sample)
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda")

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=256,
                use_cache=True,
                temperature=0.01,
                do_sample=False,
            )
        
        response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        prediction = parse_action(response)
        
        gt_vulnerable = bool(sample["is_vulnerable"])
        pred_vulnerable = bool(prediction.is_vulnerable) if prediction.is_vulnerable is not None else False
        
        is_correct = (pred_vulnerable == gt_vulnerable)
        if is_correct:
            results["summary"]["correct_binary"] += 1
        
        if gt_vulnerable and not pred_vulnerable:
            results["summary"]["false_negatives"] += 1
        elif not gt_vulnerable and pred_vulnerable:
            results["summary"]["false_positives"] += 1
            
        results["predictions"].append({
            "idx": i,
            "gt": gt_vulnerable,
            "pred": pred_vulnerable,
            "correct": is_correct,
            "response": response
        })
        
        if (i + 1) % 5 == 0:
            current_acc = results["summary"]["correct_binary"] / (i + 1)
            print(f"Step {i+1}/{num_samples} | Current Acc: {current_acc:.2%}", flush=True)

    results["summary"]["accuracy"] = results["summary"]["correct_binary"] / num_samples
    
    print("\\n--- Evaluation Summary ---")
    print(f"Total Samples: {num_samples}")
    print(f"Accuracy: {results['summary']['accuracy']:.2%}")
    print(f"False Positives: {results['summary']['false_positives']}")
    print(f"False Negatives: {results['summary']['false_negatives']}")
    
    print("\\nResults (JSON):")
    print(json.dumps(results["summary"], indent=2))

if __name__ == "__main__":
    main()
