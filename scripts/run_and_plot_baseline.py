from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main() -> None:
    ap = argparse.ArgumentParser(description="Run a tiny baseline and save a reward-curve PNG.")
    ap.add_argument("--episodes", type=int, default=200)
    ap.add_argument("--out-dir", type=Path, default=Path("plots"))
    args = ap.parse_args()

    # Allow running from a fresh clone without `pip install -e .`.
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root))

    # Local, in-process baseline (no server needed).
    from commitguard_env.environment import CommitGuardEnvironment
    from commitguard_env.models import CommitGuardAction

    data_path = repo_root / "data" / "devign_filtered.jsonl"
    env = CommitGuardEnvironment(data_path=data_path)

    rewards: list[float] = []
    for _ in range(args.episodes):
        _ = env.reset()
        # Naive always-vulnerable verdict baseline (intentionally dumb).
        action = CommitGuardAction(
            action_type="verdict",
            is_vulnerable=True,
            vuln_type="CWE-89",
            exploit_sketch="sql select where concat injection",
        )
        _obs, reward, _done = env.step(action)
        rewards.append(float(reward))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "baseline_rewards.json").write_text(json.dumps(rewards), encoding="utf-8")

    import matplotlib.pyplot as plt

    plt.figure(figsize=(8, 4))
    plt.plot(rewards, linewidth=1)
    plt.title("CommitGuard baseline reward curve (naive always-vulnerable)")
    plt.xlabel("Episode")
    plt.ylabel("Reward")
    plt.tight_layout()
    plt.savefig(args.out_dir / "baseline_reward_curve.png", dpi=180)


if __name__ == "__main__":
    main()

