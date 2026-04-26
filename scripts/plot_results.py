import matplotlib.pyplot as plt
import json
import os
import argparse

def plot_reward_curve(wandb_data_path, output_path="plots/reward_curve.png"):
    """
    Plots the training reward curve.
    Expects a JSON file with 'step' and 'reward' keys (exported from Wandb).
    """
    if not os.path.exists(wandb_data_path):
        print(f"Skipping: {wandb_data_path} not found.")
        return

    with open(wandb_data_path, "r") as f:
        data = json.load(f)

    steps = [d["step"] for d in data]
    rewards = [d["reward"] for d in data]

    plt.figure(figsize=(10, 6))
    plt.plot(steps, rewards, label="GRPO Reward", color="#2ecc71", linewidth=2)
    plt.xlabel("Training Step")
    plt.ylabel("Mean Reward")
    plt.title("CommitGuard — GRPO Training Reward Curve")
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.legend()
    plt.savefig(output_path)
    print(f"Saved: {output_path}")

def plot_accuracy_comparison(baseline_acc, trained_acc, output_path="plots/baseline_vs_trained.png"):
    """
    Plots a bar chart comparing baseline vs trained accuracy.
    """
    labels = ['Baseline (Untrained)', 'CommitGuard (Trained)']
    accuracies = [baseline_acc, trained_acc]
    colors = ['#95a5a6', '#3498db']

    plt.figure(figsize=(8, 6))
    bars = plt.bar(labels, accuracies, color=colors)
    plt.ylabel("Detection Accuracy (%)")
    plt.title("Vulnerability Detection: Baseline vs. Trained")
    plt.ylim(0, 100)

    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height + 1,
                 f'{height}%', ha='center', va='bottom', fontweight='bold')

    plt.savefig(output_path)
    print(f"Saved: {output_path}")

def plot_per_cwe_breakdown(cwe_data, output_path="plots/per_cwe.png"):
    """
    Plots a grouped bar chart for per-CWE improvement.
    cwe_data format: {"CWE-89": [baseline, trained], "CWE-119": [baseline, trained], ...}
    """
    cwes = list(cwe_data.keys())
    baseline_vals = [v[0] for v in cwe_data.values()]
    trained_vals = [v[1] for v in cwe_data.values()]

    x = range(len(cwes))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar([i - width/2 for i in x], baseline_vals, width, label='Baseline', color='#95a5a6')
    ax.bar([i + width/2 for i in x], trained_vals, width, label='Trained', color='#e67e22')

    ax.set_ylabel('Accuracy (%)')
    ax.set_title('Detection Accuracy by CWE Type')
    ax.set_xticks(x)
    ax.set_xticklabels(cwes, rotation=45)
    ax.legend()
    ax.set_ylim(0, 100)

    plt.tight_layout()
    plt.savefig(output_path)
    print(f"Saved: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["reward", "accuracy", "cwe", "all"], default="all")
    args = parser.parse_args()

    os.makedirs("plots", exist_ok=True)

    # Example usage for morning shift:
    if args.mode in ["reward", "all"]:
        plot_reward_curve("plots/wandb_simulated.json")

    if args.mode in ["accuracy", "all"]:
        # Placeholder numbers (to be updated by Divyank/Deepak's eval)
        plot_accuracy_comparison(baseline_acc=32, trained_acc=68)
    
    if args.mode in ["cwe", "all"]:
        # Placeholder data
        cwe_data = {
            "CWE-89": [40, 85],
            "CWE-119": [30, 60],
            "CWE-79": [25, 70],
            "CWE-20": [35, 55]
        }
        plot_per_cwe_breakdown(cwe_data)
