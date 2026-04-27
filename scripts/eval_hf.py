import os
import json
import argparse
import torch
from datasets import load_dataset
from unsloth import FastLanguageModel
from peft import PeftModel
from pathlib import Path
import sys

# Add current directory and parent to path for imports
sys.path.insert(0, os.getcwd())
sys.path.insert(0, str(Path(os.getcwd()) / "scripts"))

# Try to import project components
try:
    from commitguard_env.parse_action import parse_action
    print("Successfully imported commitguard_env.parse_action")
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Directory contents: {os.listdir(os.getcwd())}")
    # Last ditch effort: try relative import if possible
    try:
        from commitguard_env.parse_action import parse_action
    except:
        raise e

SYSTEM_PROMPT = """\
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
        f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
        f"{SYSTEM_PROMPT}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
        f"Analyze this commit and submit your verdict.\n\n"
        f"Code diff:\n```diff\n{sample['diff']}\n```<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
    )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_id", type=str, default="Divyank1607/commitguard-llama-3b-sft-v2")
    parser.add_argument("--dataset_id", type=str, default="Divyank1607/commitguard-data")
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--max_seq_length", type=int, default=2048)
    args = parser.parse_args()

    hf_token = os.getenv("HF_TOKEN")
    
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
    
    # Limit samples for quick evaluation
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
        
        if (i + 1) % 10 == 0:
            current_acc = results["summary"]["correct_binary"] / (i + 1)
            print(f"Step {i+1}/{num_samples} | Current Acc: {current_acc:.2%}")

    results["summary"]["accuracy"] = results["summary"]["correct_binary"] / num_samples
    
    print("\n--- Evaluation Summary ---")
    print(f"Total Samples: {num_samples}")
    print(f"Accuracy: {results['summary']['accuracy']:.2%}")
    print(f"False Positives: {results['summary']['false_positives']}")
    print(f"False Negatives: {results['summary']['false_negatives']}")
    
    with open("eval_results_remote.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nResults saved to eval_results_remote.json")

if __name__ == "__main__":
    main()
