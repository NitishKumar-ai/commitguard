from __future__ import annotations

"""
Hackathon-grade GRPO training entrypoint.

This is intentionally lightweight: it wires TRL to the CommitGuard env via HTTP
and logs a reward curve. It is designed to run on a single GCE GPU VM.
"""

import argparse
import os
from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class EpisodeResult:
    reward: float
    done: bool


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-url", default="http://127.0.0.1:8000")
    ap.add_argument("--episodes", type=int, default=100)
    args = ap.parse_args()

    # Minimal smoke runner (baseline) until full TRL GRPO wiring is added.
    # This still gives you an end-to-end env+reward curve and a place to hook TRL.
    rewards: list[float] = []
    for _ in range(args.episodes):
        _ = _post_json(f"{args.env_url}/reset", {})
        step = _post_json(
            f"{args.env_url}/step",
            {
                "action": "<action><action_type>verdict</action_type><is_vulnerable>true</is_vulnerable><vuln_type>CWE-89</vuln_type><exploit_sketch>sql select where concat injection</exploit_sketch></action>"
            },
        )
        rewards.append(float(step["reward"]))

    avg = sum(rewards) / max(1, len(rewards))
    print(f"episodes={len(rewards)} avg_reward={avg:.4f}")
    if os.environ.get("WANDB_PROJECT"):
        import wandb  # optional

        wandb.init(project=os.environ["WANDB_PROJECT"])
        for i, r in enumerate(rewards):
            wandb.log({"reward": r}, step=i)


if __name__ == "__main__":
    main()

