import json
import argparse
import matplotlib.pyplot as plt
import os

def main():
    parser = argparse.ArgumentParser(description="Plot reward curve from training/eval history.")
    parser.add_argument("--input", type=str, default="eval_results.json", help="Path to evaluation results JSON")
    parser.add_argument("--output", type=str, default="plots/reward_curve.png", help="Path to save the plot")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file {args.input} not found.")
        return

    with open(args.input, "r") as f:
        data = json.load(f)

    results = data.get("results", [])
    if not results:
        print("No results found to plot.")
        return

    rewards = [r["total_reward"] for r in results]
    
    plt.figure(figsize=(10, 6))
    plt.plot(rewards, marker='o', linestyle='-', color='green', markersize=4, alpha=0.6)
    
    # Calculate moving average
    window = 10
    if len(rewards) >= window:
        moving_avg = [sum(rewards[i:i+window])/window for i in range(len(rewards)-window+1)]
        plt.plot(range(window-1, len(rewards)), moving_avg, color='red', linewidth=2, label=f'{window}-sample Moving Avg')

    plt.xlabel('Sample Index')
    plt.ylabel('Total Reward')
    plt.title('CommitGuard — Evaluation Reward Distribution')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    plt.savefig(args.output)
    print(f"Plot saved to {args.output}")

if __name__ == "__main__":
    main()
