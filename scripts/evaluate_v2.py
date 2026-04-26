import json
import argparse
import os
import requests
import torch
import sys
from pathlib import Path
from unsloth import FastLanguageModel

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from commitguard_env.grpo_prompt import get_agent_prompt, SYSTEM_PROMPT

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", default="outputs/commitguard-llama-3b/final")
    parser.add_argument("--test_file", default="data/devign_test.jsonl")
    parser.add_argument("--env_url", default="http://localhost:8000")
    parser.add_argument("--max_samples", type=int, default=100)
    args = parser.parse_args()

    print(f"Loading merged model from {args.model_path}...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model_path,
        max_seq_length=2048,
        load_in_4bit=True,
        fast_inference=False,
    )
    FastLanguageModel.for_inference(model)

    with open(args.test_file, "r") as f:
        test_samples = [json.loads(line) for line in f]
    
    test_samples = test_samples[:args.max_samples]
    
    results = []
    correct_binary = 0
    total_reward = 0.0

    print(f"Starting evaluation on {len(test_samples)} samples...")

    for i, sample in enumerate(test_samples):
        sample_id = sample["sample_id"]
        # Reset environment for specific sample
        r = requests.post(f"{args.env_url}/reset", json={"sample_id": sample_id})
        if r.status_code != 200:
            print(f"Failed to reset for {sample_id}")
            continue
            
        obs = r.json()["observation"]
        done = False
        step_idx = 0
        episode_reward = 0.0
        
        print(f"[{i+1}/{len(test_samples)}] Evaluating {sample_id}...", end="\r")
        
        while not done and step_idx < 5:
            prompt = get_agent_prompt(obs["diff"], obs["available_files"], obs["step_idx"])
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
            inputs = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt").to("cuda")
            
            with torch.no_grad():
                outputs = model.generate(input_ids=inputs, max_new_tokens=512, use_cache=True)
            
            generated_text = tokenizer.decode(outputs[0][len(inputs[0]):], skip_special_tokens=True)
            
            # Step in environment
            r = requests.post(f"{args.env_url}/step", json={"action": generated_text})
            if r.status_code != 200:
                print(f"\nError at step {step_idx}: {r.text}")
                break
                
            res = r.json()
            obs = res["observation"]
            episode_reward = res["reward"]
            done = res["done"]
            step_idx += 1

        total_reward += episode_reward
        # is_correct info is passed in 'info' field by environment
        is_correct = res.get("info", {}).get("is_correct", False)
        if is_correct:
            correct_binary += 1
            
        results.append({
            "sample_id": sample_id,
            "reward": episode_reward,
            "is_correct": is_correct,
            "ground_truth": sample.get("is_vulnerable")
        })

    avg_reward = total_reward / len(test_samples)
    accuracy = (correct_binary / len(test_samples)) * 100
    
    print(f"\nEvaluation Complete!")
    print(f"Average Reward: {avg_reward:.4f}")
    print(f"Accuracy: {accuracy:.2f}%")

    with open("eval_results_trained.json", "w") as f:
        json.dump({
            "average_reward": avg_reward,
            "accuracy": accuracy,
            "detailed_results": results
        }, f, indent=2)

if __name__ == "__main__":
    main()
