import json
import argparse
import matplotlib.pyplot as plt
import os

def main():
    parser = argparse.ArgumentParser(description="Plot accuracy per CWE type.")
    parser.add_argument("--input", type=str, default="eval_results.json", help="Path to evaluation results JSON")
    parser.add_argument("--output", type=str, default="plots/per_cwe.png", help="Path to save the plot")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file {args.input} not found.")
        return

    with open(args.input, "r") as f:
        data = json.load(f)

    cwe_breakdown = data.get("summary", {}).get("cwe_breakdown", {})
    if not cwe_breakdown:
        print("No CWE breakdown found in the results.")
        return

    cwes = list(cwe_breakdown.keys())
    accuracies = [stats["accuracy"] for stats in cwe_breakdown.values()]
    counts = [stats["count"] for stats in cwe_breakdown.values()]

    plt.figure(figsize=(12, 6))
    bars = plt.bar(cwes, accuracies, color='skyblue', edgecolor='navy')
    
    # Add counts on top of bars
    for i, bar in enumerate(bars):
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval + 0.01, f'n={counts[i]}', ha='center', va='bottom')

    plt.xlabel('CWE Type')
    plt.ylabel('Accuracy')
    plt.title('CommitGuard — Accuracy per CWE Type')
    plt.ylim(0, 1.1)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.xticks(rotation=45)
    plt.tight_layout()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    plt.savefig(args.output)
    print(f"Plot saved to {args.output}")

if __name__ == "__main__":
    main()
