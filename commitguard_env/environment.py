from __future__ import annotations

import json
import random
import uuid
from collections import OrderedDict
from dataclasses import replace
from pathlib import Path

from .models import CommitGuardAction, CommitGuardObservation, CommitGuardState, ContextSnippet, DevignSample
from .reward import compute_reward


class CommitGuardEnvironment:
    _MAX_SESSIONS = 64

    def __init__(self, *, data_path: Path) -> None:
        self._data_path = data_path
        self._samples: list[DevignSample] = []
        self._sessions: OrderedDict[str, CommitGuardState] = OrderedDict()
        self._latest_episode_id: str | None = None
        self._rng = random.Random(0)
        self._cwe_keywords: dict[str, list[str]] = {}

    def _resolve_session(self, episode_id: str | None) -> CommitGuardState:
        eid = episode_id or self._latest_episode_id
        if eid and eid in self._sessions:
            return self._sessions[eid]
        raise ValueError("no_active_session")

    def _evict_if_needed(self) -> None:
        while len(self._sessions) > self._MAX_SESSIONS:
            self._sessions.popitem(last=False)

    def load(self) -> None:
        if self._samples:
            return
        # Load CWE keywords from data directory (matching instructions)
        try:
            kw_path = self._data_path.parent / "cwe_keywords.json"
            if not kw_path.exists():
                # Fallback to current directory or data subfolder if needed
                kw_path = self._data_path.parent / "data" / "cwe_keywords.json"
            
            self._cwe_keywords = json.loads(kw_path.read_text(encoding="utf-8"))
        except Exception:
            self._cwe_keywords = {}

        raw = self._data_path.read_text(encoding="utf-8").strip().splitlines()
        for line in raw:
            obj = json.loads(line)
            # Support both original and mvd schemas
            sample_id = str(obj.get("commit_id") or obj.get("sample_id", "unknown"))
            
            # Synthesize diff if missing (mvd branch data schema)
            diff = obj.get("diff")
            if not diff and "code_before" in obj and "code_after" in obj:
                diff = f"--- code_before\n+++ code_after\n{obj['code_before']}\n{obj['code_after']}"
            
            self._samples.append(
                DevignSample(
                    sample_id=sample_id,
                    diff=str(diff or ""),
                    available_files=list(obj.get("available_files") or []),
                    is_vulnerable=obj.get("is_vulnerable"),
                    cwe=obj.get("cwe") or obj.get("cwe_type"),
                    target_file=obj.get("target_file"),
                    files=obj.get("files"),
                )
            )
        if not self._samples:
            raise RuntimeError("no_samples_loaded")

    def reset(self, sample_id: str | None = None) -> CommitGuardObservation:
        self.load()
        if sample_id:
            sample = next((s for s in self._samples if s.sample_id == sample_id), None)
            if not sample:
                raise ValueError(f"sample_id {sample_id} not found")
        else:
            sample = self._rng.choice(self._samples)
        
        episode_id = str(uuid.uuid4())
        state = CommitGuardState(
            episode_id=episode_id,
            current_sample_id=sample.sample_id,
            step_count=0,
            context_requests=0,
            history=[],
        )
        self._sessions[episode_id] = state
        self._latest_episode_id = episode_id
        self._evict_if_needed()

        return CommitGuardObservation(
            episode_id=episode_id,
            diff=sample.diff,
            available_files=sample.available_files,
            step_idx=0,
            budget_remaining=5,
        )

    def step(self, action: CommitGuardAction, episode_id: str | None = None) -> tuple[CommitGuardObservation, float, bool]:
        try:
            state = self._resolve_session(episode_id)
        except ValueError:
            # Auto-reset if no active session, matching previous behavior
            obs = self.reset()
            state = self._sessions[obs.episode_id]

        next_step = state.step_count + 1
        sample = next(s for s in self._samples if s.sample_id == state.current_sample_id)

        context_snippets: list[ContextSnippet] = []
        context_requests = state.context_requests
        if action.action_type == "request_context":
            context_requests += 1
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

        new_state = replace(
            state,
            step_count=next_step,
            context_requests=context_requests,
            history=[
                *state.history,
                {
                    "step": next_step,
                    "action_type": action.action_type,
                    "parse_error": action.parse_error,
                },
            ],
        )
        self._sessions[new_state.episode_id] = new_state

        obs = CommitGuardObservation(
            episode_id=new_state.episode_id,
            diff=sample.diff,
            available_files=sample.available_files,
            context_snippets=context_snippets,
            step_idx=next_step,
            budget_remaining=max(0, 5 - next_step),
            error=action.parse_error or (None if context_snippets else ("context_unavailable" if action.action_type == "request_context" else None)),
        )
        return obs, reward, done

    def state(self, episode_id: str | None = None) -> CommitGuardState:
        try:
            return self._resolve_session(episode_id)
        except ValueError:
            return CommitGuardState(episode_id="", current_sample_id="", step_count=0, context_requests=0, history=[])
