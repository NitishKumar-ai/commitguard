from __future__ import annotations

import json
import random
import uuid
from dataclasses import replace
from pathlib import Path

from .models import CommitGuardAction, CommitGuardObservation, CommitGuardState, ContextSnippet, DevignSample
from .reward import compute_reward


class CommitGuardEnvironment:
    def __init__(self, *, data_path: Path) -> None:
        self._data_path = data_path
        self._samples: list[DevignSample] = []
        self._state: CommitGuardState | None = None
        self._rng = random.Random(0)
        self._cwe_keywords: dict[str, list[str]] = {}

    def load(self) -> None:
        if self._samples:
            return
        # Load CWE keywords opportunistically (reward uses them). Safe if missing.
        try:
            kw_path = self._data_path.parent / "cwe_keywords.json"
            self._cwe_keywords = json.loads(kw_path.read_text(encoding="utf-8"))
        except Exception:
            self._cwe_keywords = {}

        raw = self._data_path.read_text(encoding="utf-8").strip().splitlines()
        for line in raw:
            obj = json.loads(line)
            self._samples.append(
                DevignSample(
                    sample_id=str(obj["sample_id"]),
                    diff=str(obj["diff"]),
                    available_files=list(obj.get("available_files") or []),
                    is_vulnerable=obj.get("is_vulnerable"),
                    cwe=obj.get("cwe") or obj.get("cwe_type"),
                    target_file=obj.get("target_file"),
                    files=obj.get("files"),
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
            context_requests=0,
            history=[],
        )
        return CommitGuardObservation(
            episode_id=episode_id,
            diff=sample.diff,
            available_files=sample.available_files,
            step_idx=0,
            budget_remaining=5,
        )

    def step(self, action: CommitGuardAction) -> tuple[CommitGuardObservation, float, bool]:
        if self._state is None:
            # permissive: auto-reset if step called first
            _ = self.reset()

        assert self._state is not None
        next_step = self._state.step_count + 1

        sample = next(s for s in self._samples if s.sample_id == self._state.current_sample_id)

        context_snippets: list[ContextSnippet] = []
        context_requests = self._state.context_requests
        if action.action_type == "request_context":
            context_requests += 1
            # Best-effort: if dataset provides per-file content, return a small snippet; otherwise return an error.
            if action.file_path and sample.files and action.file_path in sample.files:
                content = sample.files[action.file_path]
                lines = content.splitlines()
                start = 1
                end = min(len(lines), 80)
                context_snippets = [
                    ContextSnippet(
                        file_path=action.file_path,
                        start_line=start,
                        end_line=end,
                        content="\n".join(lines[start - 1 : end]),
                    )
                ]

        reward = compute_reward(
            action=action,
            is_vulnerable=sample.is_vulnerable,
            cwe=sample.cwe,
            target_file=sample.target_file,
            cwe_keywords=self._cwe_keywords,
            context_requests=context_requests,
        )

        done = bool(action.action_type == "verdict" or next_step >= 5)

        self._state = replace(
            self._state,
            step_count=next_step,
            context_requests=context_requests,
            history=[
                *self._state.history,
                {
                    "step": next_step,
                    "action_type": action.action_type,
                    "parse_error": action.parse_error,
                },
            ],
        )

        obs = CommitGuardObservation(
            episode_id=self._state.episode_id,
            diff=sample.diff,
            available_files=sample.available_files,
            context_snippets=context_snippets,
            step_idx=next_step,
            budget_remaining=max(0, 5 - next_step),
            error=action.parse_error or (None if context_snippets else ("context_unavailable" if action.action_type == "request_context" else None)),
        )
        return obs, reward, done

    def state(self) -> CommitGuardState:
        if self._state is None:
            # state() must not leak labels; returning empty is fine
            return CommitGuardState(episode_id="", current_sample_id="", step_count=0, context_requests=0, history=[])
        return self._state

