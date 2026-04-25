from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict
from typing import Any

import requests
import torch
import traceback
from peft import PeftModel
from tqdm import tqdm
from transformers import AutoModelForCausalLM, AutoTokenizer


SYSTEM_PROMPT = """You are a security analyst reviewing code commits for vulnerabilities.
...
You have at most 5 steps per commit. Be efficient.
"""

def parse_xml_action(text: str) -> str | None:
...
    return tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate CommitGuard agentic loop.")
    parser.add_argument("--model_path", type=str, default="meta-llama/Llama-3.2-3B-Instruct", help="Base model path")
    parser.add_argument("--adapter_path", type=str, default=None, help="Path to LoRA adapter")
    parser.add_argument("--data_path", type=str, default="data/devign_test.jsonl", help="Test data path")
    parser.add_argument("--env_url", type=str, default="http://127.0.0.1:8000", help="Environment server URL")
    parser.add_argument("--output", type=str, default="eval_results.json", help="Output results file")
    parser.add_argument("--limit", type=int, default=10, help="Limit number of samples to evaluate")
    parser.add_argument("--timeout", type=int, default=10, help="Timeout for server requests")
    parser.add_argument("--max_failures", type=int, default=5, help="Max allowed consecutive failures")
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading model on {device}...")
    
    # Load model and tokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.model_path)
    model = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        device_map="auto" if device == "cuda" else None
    )
    if args.adapter_path:
        print(f"Loading adapter from {args.adapter_path}...")
        model = PeftModel.from_pretrained(model, args.adapter_path)
    
    if device == "cpu":
        model = model.to(device)

    # Load ground truth for metric breakdown
    test_samples = []
    with open(args.data_path, "r", encoding="utf-8") as f:
        for line in f:
            test_samples.append(json.loads(line))
    
    if args.limit:
        test_samples = test_samples[:args.limit]

    results = []
    cwe_stats = {}
    failure_count = 0

    for sample in tqdm(test_samples, desc="Evaluating"):
        sample_id = sample["sample_id"]
        gt_vulnerable = sample["is_vulnerable"]
        gt_cwe = sample.get("cwe")
        
        # Reset environment with deterministic sample_id
        try:
            resp_raw = requests.post(
                f"{args.env_url}/reset", 
                json={"sample_id": sample_id}, 
                timeout=args.timeout
            )
            resp_raw.raise_for_status()
            resp = resp_raw.json()
            
            if "error" in resp:
                print(f"Server error for sample {sample_id}: {resp['error']}")
                continue

            obs = resp["observation"]
            episode_id = obs["episode_id"]
            
            history = []
            done = False
            total_reward = 0.0
            
            prompt = f"{SYSTEM_PROMPT}\n\nDiff:\n{obs['diff']}\n\nAvailable files: {obs['available_files']}\n"
            
            final_vuln_type = None
            for step_idx in range(5):
                model_output = get_model_response(model, tokenizer, prompt, device)
                action_xml = parse_xml_action(model_output)
                
                try:
                    if not action_xml:
                        step_resp_raw = requests.post(
                            f"{args.env_url}/step", 
                            json={"action": model_output}, 
                            timeout=args.timeout
                        )
                    else:
                        step_resp_raw = requests.post(
                            f"{args.env_url}/step", 
                            json={"action": action_xml}, 
                            timeout=args.timeout
                        )
                    step_resp_raw.raise_for_status()
                    step_resp = step_resp_raw.json()
                except (requests.Timeout, requests.RequestException):
                    print(f"\nStep request failed for {sample_id} at step {step_idx}")
                    raise

                obs = step_resp["observation"]
                reward = step_resp["reward"]
                done = step_resp["done"]
                total_reward += reward
                
                history.append({
                    "step": step_idx,
                    "model_output": model_output,
                    "parsed_action": action_xml,
                    "reward": reward,
                    "observation": obs
                })
                
                if done:
                    # Capture vuln_type from the final verdict if available
                    if action_xml and "<action_type>verdict</action_type>" in action_xml:
                        match = re.search(r"<vuln_type>(.*?)</vuln_type>", action_xml)
                        if match:
                            final_vuln_type = match.group(1).strip()
                    break
                
                # Update prompt for next step
                prompt += f"\nObservation: {obs}\nAction:"

            # Extract final verdict
            final_verdict = None
            last_action = history[-1]["parsed_action"]
            if last_action and "<action_type>verdict</action_type>" in last_action:
                is_vuln_match = re.search(r"<is_vulnerable>(.*?)</is_vulnerable>", last_action)
                if is_vuln_match:
                    final_verdict = is_vuln_match.group(1).lower() in ["true", "1", "yes"]

            # Strict scoring: verdict must match AND CWE must match if vulnerable
            is_correct = (final_verdict == gt_vulnerable) if final_verdict is not None else False
            if is_correct and gt_vulnerable:
                # Check CWE match
                if not (gt_cwe and final_vuln_type and final_vuln_type.upper() == gt_cwe.upper()):
                    is_correct = False

            results.append({
                "sample_id": sample_id,
                "gt_vulnerable": gt_vulnerable,
                "gt_cwe": gt_cwe,
                "final_verdict": final_verdict,
                "final_vuln_type": final_vuln_type,
                "is_correct": is_correct,
                "total_reward": total_reward,
                "history": history
            })
            
            # Update CWE stats
            cwe = gt_cwe or "UNKNOWN"
            if cwe not in cwe_stats:
                cwe_stats[cwe] = {"correct": 0, "total": 0}
            cwe_stats[cwe]["total"] += 1
            if is_correct:
                cwe_stats[cwe]["correct"] += 1
            
            failure_count = 0 # reset on success

        except Exception:
            failure_count += 1
            print(f"\nError evaluating sample {sample_id}:")
            traceback.print_exc()
            if failure_count >= args.max_failures:
                print(f"Reached max consecutive failures ({args.max_failures}). Aborting.")
                break
            continue

    # Final report
    summary = {
        "total_samples": len(results),
        "overall_accuracy": sum(1 for r in results if r["is_correct"]) / len(results) if results else 0,
        "cwe_breakdown": {
            cwe: {
                "accuracy": stats["correct"] / stats["total"],
                "count": stats["total"]
            } for cwe, stats in cwe_stats.items()
        }
    }
    
    output_data = {
        "summary": summary,
        "results": results
    }
    
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\nEvaluation complete. Results saved to {args.output}")
    print(f"Overall Accuracy: {summary['overall_accuracy']:.2%}")

if __name__ == "__main__":
    main()
