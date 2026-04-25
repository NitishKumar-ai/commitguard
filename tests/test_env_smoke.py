from __future__ import annotations

import random

from commitguard_env.environment import CommitGuardEnvironment
from commitguard_env.models import CommitGuardAction
from pathlib import Path


def test_env_100_random_episodes_no_crash() -> None:
    data_path = Path(__file__).resolve().parent.parent / "data" / "devign_filtered.jsonl"
    env = CommitGuardEnvironment(data_path=data_path)
    rng = random.Random(0)

    for _ in range(100):
        obs = env.reset()
        assert obs.budget_remaining == 5
        done = False
        steps = 0

        while not done:
            steps += 1
            # Mix in malformed actions to ensure robustness.
            if rng.random() < 0.2:
                action = CommitGuardAction(action_type="analyze", raw_action="<<<", parse_error="synthetic")
            else:
                action = CommitGuardAction(action_type=rng.choice(["analyze", "request_context", "verdict"]))  # type: ignore[arg-type]
            obs, reward, done = env.step(action)
            assert isinstance(reward, float)
            assert obs.step_idx == steps
            assert obs.budget_remaining == max(0, 5 - steps)

        assert steps <= 5

