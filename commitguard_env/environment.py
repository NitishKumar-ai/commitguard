from __future__ import annotations

import json
import random
import uuid
from dataclasses import replace
from pathlib import Path

from .models import CommitGuardAction, CommitGuardObservation, CommitGuardState, DevignSample
from .reward import compute_reward


class CommitGuardEnvironment:
    def __init__(self, *, data_path: Path) -> None:
        self._data_path = data_path
        self._samples: list[DevignSample] = []
        self._state: CommitGuardState | None = None
        self._rng = random.Random(0)

    def load(self) -> None:
        if self._samples:
            return
        raw = self._data_path.read_text(encoding="utf-8").strip().splitlines()
        for line in raw:
            obj = json.loads(line)
            self._samples.append(
                DevignSample(
                    sample_id=str(obj["commit_id"]),
                    diff=f"--- code_before\n+++ code_after\n{obj['code_before']}\n{obj['code_after']}",
                    available_files=list(obj.get("available_files") or []),
                )
            )
        if not self._samples:
            raise RuntimeError("no_samples_loaded")

    def reset(self) -> CommitGuardObservation:
        self.load()
        sample = self._rng.choice(self._samples)
        episode_id = str(uuid.uuid4())
        self._state = CommitGuardState(
            episode_id=episode_id,
            current_sample_id=sample.sample_id,
            step_count=0,
            history=[],
        )
        return CommitGuardObservation(
            diff=sample.diff,
            available_files=sample.available_files,
            step_count=0,
            reward=0.0,
            done=False,
        )

    def step(self, action: CommitGuardAction) -> CommitGuardObservation:
        if self._state is None:
            # permissive: auto-reset if step called first
            _ = self.reset()

        assert self._state is not None
        next_step = self._state.step_count + 1

        reward = compute_reward(action=action)
        done = bool(action.action_type == "verdict" or next_step >= 5)

        self._state = replace(
            self._state,
            step_count=next_step,
            history=[
                *self._state.history,
                {
                    "step": next_step,
                    "action_type": action.action_type,
                    "parse_error": action.parse_error,
                },
            ],
        )

        sample = next(s for s in self._samples if s.sample_id == self._state.current_sample_id)
        return CommitGuardObservation(
            diff=sample.diff,
            available_files=sample.available_files,
            step_count=next_step,
            reward=reward,
            done=done,
            error=action.parse_error,
        )

    def state(self) -> CommitGuardState:
        if self._state is None:
            # state() must not leak labels; returning empty is fine
            return CommitGuardState(episode_id="", current_sample_id="", step_count=0, history=[])
        return self._state
