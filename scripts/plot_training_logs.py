import json
import argparse
import matplotlib.pyplot as plt
import os
from pathlib import Path

def plot_training(log_history, output_path):
    # Extract rewards and steps
    # GRPOTrainer logs 'reward' in the history
    steps = []
    rewards = []
    
    for entry in log_history:
        if "reward" in entry and "step" in entry:
            steps.append(entry["step"])
            rewards.append(entry["reward"])
    
    if not steps:
        print("No reward data found in logs.")
        return

    plt.figure(figsize=(10, 5))
    plt.plot(steps, rewards, label='Mean Reward (per step)', color='#2ecc71', alpha=0.4)
    
    # Simple moving average for trend
    if len(rewards) > 5:
        window = 5
        sma = [sum(rewards[i:i+window])/window for i in range(len(rewards)-window+1)]
        plt.plot(steps[window-1:], sma, label=f'{window}-step Moving Avg', color='#e74c3c', linewidth=2)

    plt.title("CommitGuard — GRPO Training Reward Curve", fontsize=14)
    plt.xlabel("Training Step", fontsize=12)
    plt.ylabel("Mean Reward", fontsize=12)
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    
    plt.savefig(output_path, dpi=180)
    print(f"Training plot saved to {output_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-file", type=str, default="outputs/commitguard-llama-3b-grpo/final/trainer_state.json")
    parser.add_argument("--output", type=str, default="plots/training_reward_curve.png")
    args = parser.parse_args()

    log_path = Path(args.log_file)
    if not log_path.exists():
        print(f"Log file {log_path} not found yet. Training might still be in progress.")
        return

    with open(log_path, "r") as f:
        data = json.load(f)
    
    plot_training(data.get("log_history", []), args.output)

if __name__ == "__main__":
    main()
