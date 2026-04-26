import json
import argparse
import os
import re
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from pathlib import Path
import sys

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.agent_prompt import SYSTEM_PROMPT

def parse_xml_action(text):
    """Extract action fields from XML-tagged model output."""
    def extract(tag, default=None):
        match = re.search(f"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
        return match.group(1).strip() if match else default

    is_vuln_str = extract("is_vulnerable", "false")
    return {
        "action_type": "verdict",
        "is_vulnerable": is_vuln_str.lower() == "true",
        "vuln_type": extract("vuln_type", "unknown"),
        "exploit_sketch": extract("exploit_sketch", ""),
    }

def format_eval_prompt(sample):
    return (
        f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
        f"{SYSTEM_PROMPT}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
        f"Analyze this commit and submit your verdict.\n\n"
        f"Code diff:\n```diff\n{sample['diff']}\n```<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
    )

def evaluate(model_path, test_file, is_lora=False, base_model=None, output_file="eval_results.json"):
    """
    Run model on test samples, compute accuracy metrics.
    """
    print(f"Loading model from {model_path}...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # Load model
    if is_lora:
        if not base_model:
            raise ValueError("base_model is required if is_lora=True")
        print(f"Loading LoRA adapter from {model_path} with base model {base_model}")
        from unsloth import FastLanguageModel
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name = base_model,
            max_seq_length = 2048,
            load_in_4bit = True,
        )
        model = PeftModel.from_pretrained(model, model_path)
        FastLanguageModel.for_inference(model)
    else:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        model = AutoModelForCausalLM.from_pretrained(model_path, torch_dtype=torch.float16, device_map="auto")
        tokenizer = AutoTokenizer.from_pretrained(model_path)

    # Load test data
    print(f"Loading test data from {test_file}...")
    with open(test_file, "r", encoding="utf-8") as f:
        samples = [json.loads(line) for line in f if line.strip()]

    results = {
        "summary": {
            "total": len(samples),
            "correct_binary": 0,
            "correct_cwe": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "binary_accuracy": 0,
            "cwe_accuracy": 0,
            "false_positive_rate": 0,
            "false_negative_rate": 0,
            "cwe_breakdown": {},
        },
        "predictions": [],
    }

    print(f"Starting evaluation on {len(samples)} samples...")
    for i, sample in enumerate(samples):
        prompt = format_eval_prompt(sample)
        inputs = tokenizer(prompt, return_tensors="pt").to(device)

        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=256,
                temperature=0.1,
                do_sample=False,
            )

        response = tokenizer.decode(output[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        prediction = parse_xml_action(response)

        gt_vulnerable = bool(sample["is_vulnerable"])
        pred_vulnerable = prediction.get("is_vulnerable", False)

        correct = pred_vulnerable == gt_vulnerable
        if correct:
            results["summary"]["correct_binary"] += 1

        if gt_vulnerable and not pred_vulnerable:
            results["summary"]["false_negatives"] += 1
        elif not gt_vulnerable and pred_vulnerable:
            results["summary"]["false_positives"] += 1

        cwe = sample.get("cwe") or "CWE-OTHER"
        if cwe not in results["summary"]["cwe_breakdown"]:
            results["summary"]["cwe_breakdown"][cwe] = {"total": 0, "correct": 0, "accuracy": 0}
        
        results["summary"]["cwe_breakdown"][cwe]["total"] += 1
        if correct:
            results["summary"]["cwe_breakdown"][cwe]["correct"] += 1

        if gt_vulnerable and correct and prediction.get("vuln_type") == cwe:
            results["summary"]["correct_cwe"] += 1

        results["predictions"].append({
            "sample_id": sample["sample_id"],
            "ground_truth": gt_vulnerable,
            "predicted": pred_vulnerable,
            "predicted_cwe": prediction.get("vuln_type"),
            "actual_cwe": cwe,
            "response": response,
        })
        
        if (i + 1) % 10 == 0:
            print(f"  Processed {i+1}/{len(samples)} samples...")

    # Final summary stats
    summary = results["summary"]
    total = summary["total"]
    vuln_count = sum(1 for s in samples if s["is_vulnerable"])
    safe_count = total - vuln_count

    summary["binary_accuracy"] = summary["correct_binary"] / total if total > 0 else 0
    summary["cwe_accuracy"] = summary["correct_cwe"] / vuln_count if vuln_count > 0 else 0
    summary["false_positive_rate"] = summary["false_positives"] / safe_count if safe_count > 0 else 0
    summary["false_negative_rate"] = summary["false_negatives"] / vuln_count if vuln_count > 0 else 0
    
    for cwe in summary["cwe_breakdown"]:
        stats = summary["cwe_breakdown"][cwe]
        stats["accuracy"] = stats["correct"] / stats["total"] if stats["total"] > 0 else 0

    print(f"\nEvaluation Complete:")
    print(f"  Binary Accuracy: {summary['binary_accuracy']:.2%}")
    print(f"  CWE Accuracy:    {summary['cwe_accuracy']:.2%}")
    print(f"  False Positives: {summary['false_positives']}")
    print(f"  False Negatives: {summary['false_negatives']}")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {output_file}")
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", default="meta-llama/Llama-3.2-3B-Instruct")
    parser.add_argument("--test-file", default="data/devign_test.jsonl")
    parser.add_argument("--is-lora", action="store_true")
    parser.add_argument("--base-model", default="meta-llama/Llama-3.2-3B-Instruct")
    parser.add_argument("--output", default="eval_results.json")
    args = parser.parse_args()
    
    evaluate(args.model_path, args.test_file, args.is_lora, args.base_model, args.output)
