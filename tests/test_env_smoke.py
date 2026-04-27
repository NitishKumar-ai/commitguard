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


def test_concurrent_sessions() -> None:
    data_path = Path(__file__).resolve().parent.parent / "data" / "devign_filtered.jsonl"
    env = CommitGuardEnvironment(data_path=data_path)
    
    # Create two sessions
    obs1 = env.reset()
    obs2 = env.reset()
    
    assert obs1.episode_id != obs2.episode_id
    
    # Step in session 1
    env.step(CommitGuardAction(action_type="analyze"), episode_id=obs1.episode_id)
    state1 = env.state(episode_id=obs1.episode_id)
    state2 = env.state(episode_id=obs2.episode_id)
    
    assert state1.step_count == 1
    assert state2.step_count == 0
    
    # Step in session 2
    env.step(CommitGuardAction(action_type="analyze"), episode_id=obs2.episode_id)
    state1 = env.state(episode_id=obs1.episode_id)
    state2 = env.state(episode_id=obs2.episode_id)
    
    assert state1.step_count == 1
    assert state2.step_count == 1
    
    # Backward compat: default to latest if no ID provided
    env.step(CommitGuardAction(action_type="analyze")) # should step obs2
    assert env.state(episode_id=obs2.episode_id).step_count == 2
    assert env.state(episode_id=obs1.episode_id).step_count == 1

