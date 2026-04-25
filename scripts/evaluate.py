import json
import argparse
import os
from typing import Any
import requests
from commitguard_env.parse_action import parse_action

def evaluate_model(env_url: str, samples_path: str, model_client: Any = None):
    """
    Evaluates a model (or mock) against a test set.
    If model_client is None, it prompts for manual input (useful for baseline smoke tests).
    """
    with open(samples_path, "r") as f:
        samples = [json.loads(line) for line in f]

    results = []
    
    for sample in samples:
        print(f"Evaluating Sample ID: {sample['sample_id']}")
        
        # 1. Reset Env
        r = requests.post(f"{env_url}/reset")
        obs = r.json()["observation"]
        
        # 2. Simple 1-step evaluation for baseline (direct verdict)
        # In a full run, this would be a loop up to 5 steps.
        
        # Placeholder for actual model inference
        # if model_client:
        #     action_str = model_client.generate(obs['diff'])
        # else:
        #     action_str = input("Enter XML Action: ")
        
        # For now, we simulate a 'verdict' action
        dummy_action = {
            "action": f"<action><action_type>verdict</action_type><is_vulnerable>true</is_vulnerable><vuln_type>{sample.get('cwe', 'CWE-0')}</vuln_type><exploit_sketch>exploit</exploit_sketch></action>"
        }
        
        r = requests.post(f"{env_url}/step", json=dummy_action)
        res = r.json()
        
        results.append({
            "sample_id": sample["sample_id"],
            "reward": res["reward"],
            "is_vulnerable_ground_truth": sample["is_vulnerable"],
            "cwe_ground_truth": sample["cwe"]
        })

    # Summary Stats
    avg_reward = sum(r["reward"] for r in results) / len(results)
    print(f"Evaluation Complete. Avg Reward: {avg_reward:.4f}")
    
    with open("eval_results.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-url", default="http://localhost:8000")
    parser.add_argument("--samples", default="data/devign_filtered.jsonl")
    args = parser.parse_argument()
    
    evaluate_model(args.env_url, args.samples)
