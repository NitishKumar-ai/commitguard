"""
Lightweight offline evaluation of baseline strategies against CommitGuard env.

No GPU or model required — runs locally with deterministic strategies.
Reports precision, recall, F1, accuracy, mean reward, and per-CWE breakdown.

Usage:
    python scripts/eval_baselines.py --episodes 500
    python scripts/eval_baselines.py --episodes 1000 --strategy always_vuln
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from commitguard_env.environment import CommitGuardEnvironment
from commitguard_env.models import CommitGuardAction


@dataclass
class EvalResult:
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    total_reward: float = 0.0
    episodes: int = 0
    rewards: list[float] = field(default_factory=list)
    per_cwe: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) > 0 else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    @property
    def accuracy(self) -> float:
        total = self.tp + self.fp + self.tn + self.fn
        return (self.tp + self.tn) / total if total > 0 else 0.0

    @property
    def mean_reward(self) -> float:
        return self.total_reward / self.episodes if self.episodes > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "episodes": self.episodes,
            "confusion": {"tp": self.tp, "fp": self.fp, "tn": self.tn, "fn": self.fn},
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "accuracy": round(self.accuracy, 4),
            "mean_reward": round(self.mean_reward, 4),
            "per_cwe": self.per_cwe,
        }


def make_action(strategy: str) -> CommitGuardAction:
    if strategy == "always_vuln":
        return CommitGuardAction(
            action_type="verdict",
            is_vulnerable=True,
            vuln_type="CWE-119",
            exploit_sketch="buffer overflow via unchecked memcpy",
        )
    if strategy == "always_safe":
        return CommitGuardAction(
            action_type="verdict",
            is_vulnerable=False,
            vuln_type="NONE",
        )
    if strategy == "random":
        vuln = random.choice([True, False])
        return CommitGuardAction(
            action_type="verdict",
            is_vulnerable=vuln,
            vuln_type="CWE-119" if vuln else "NONE",
            exploit_sketch="buffer overflow" if vuln else None,
        )
    raise ValueError(f"unknown strategy: {strategy}")


def run_eval(env: CommitGuardEnvironment, episodes: int, strategy: str) -> EvalResult:
    result = EvalResult()
    for _ in range(episodes):
        env.reset()
        action = make_action(strategy)
        _obs, reward, _done = env.step(action)

        sample = next(s for s in env._samples if s.sample_id == env._state.current_sample_id)
        pred = action.is_vulnerable
        gt = sample.is_vulnerable
        cwe = sample.cwe or "None"

        if cwe not in result.per_cwe:
            result.per_cwe[cwe] = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}

        if pred and gt:
            result.tp += 1
            result.per_cwe[cwe]["tp"] += 1
        elif pred and not gt:
            result.fp += 1
            result.per_cwe[cwe]["fp"] += 1
        elif not pred and gt:
            result.fn += 1
            result.per_cwe[cwe]["fn"] += 1
        else:
            result.tn += 1
            result.per_cwe[cwe]["tn"] += 1

        result.total_reward += reward
        result.rewards.append(reward)
        result.episodes += 1

    return result


def plot_results(results: dict[str, EvalResult], out_dir: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    ax = axes[0]
    for name, res in results.items():
        cumulative = []
        s = 0.0
        for i, r in enumerate(res.rewards):
            s += r
            cumulative.append(s / (i + 1))
        ax.plot(cumulative, label=f"{name} (mean={res.mean_reward:.2f})", linewidth=1.2)
    ax.set_title("Cumulative Mean Reward")
    ax.set_xlabel("Episode")
    ax.set_ylabel("Mean Reward")
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    metrics = ["precision", "recall", "f1", "accuracy"]
    x = range(len(metrics))
    width = 0.8 / len(results)
    for i, (name, res) in enumerate(results.items()):
        vals = [getattr(res, m) for m in metrics]
        offset = (i - len(results) / 2 + 0.5) * width
        bars = ax.bar([xi + offset for xi in x], vals, width, label=name)
    ax.set_xticks(list(x))
    ax.set_xticklabels([m.upper() for m in metrics])
    ax.set_ylim(0, 1.05)
    ax.set_title("Classification Metrics by Strategy")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    plt.savefig(out_dir / "eval_baselines.png", dpi=180)
    print(f"Plot saved to {out_dir / 'eval_baselines.png'}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate CommitGuard baseline strategies")
    ap.add_argument("--episodes", type=int, default=500)
    ap.add_argument("--strategy", type=str, default="all",
                    choices=["always_vuln", "always_safe", "random", "all"])
    ap.add_argument("--out-dir", type=Path, default=Path("plots"))
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    data_path = REPO_ROOT / "data" / "devign_filtered.jsonl"
    env = CommitGuardEnvironment(data_path=data_path)

    strategies = (
        ["always_vuln", "always_safe", "random"]
        if args.strategy == "all"
        else [args.strategy]
    )

    results: dict[str, EvalResult] = {}
    for strat in strategies:
        random.seed(args.seed)
        env._rng = random.Random(args.seed)
        res = run_eval(env, args.episodes, strat)
        results[strat] = res
        d = res.to_dict()
        print(f"\n{'='*50}")
        print(f"  Strategy: {strat} ({args.episodes} episodes)")
        print(f"{'='*50}")
        print(f"  Accuracy:    {d['accuracy']:.2%}")
        print(f"  Precision:   {d['precision']:.2%}")
        print(f"  Recall:      {d['recall']:.2%}")
        print(f"  F1:          {d['f1']:.2%}")
        print(f"  Mean Reward: {d['mean_reward']:.4f}")
        print(f"  Confusion:   TP={d['confusion']['tp']} FP={d['confusion']['fp']} "
              f"TN={d['confusion']['tn']} FN={d['confusion']['fn']}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    all_results = {name: res.to_dict() for name, res in results.items()}
    out_path = args.out_dir / "eval_baselines.json"
    out_path.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"\nResults saved to {out_path}")

    try:
        plot_results(results, args.out_dir)
    except ImportError:
        print("matplotlib not available — skipping plot")


if __name__ == "__main__":
    main()
