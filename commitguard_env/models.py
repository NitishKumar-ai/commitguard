from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


ActionType = Literal["request_context", "analyze", "verdict"]


@dataclass(frozen=True, slots=True)
class CommitGuardAction:
    action_type: ActionType
    file_path: Optional[str] = None
    reasoning: Optional[str] = None
    is_vulnerable: Optional[bool] = None
    vuln_type: Optional[str] = None
    exploit_sketch: Optional[str] = None
    raw_action: Optional[str] = None
    parse_error: Optional[str] = None


@dataclass(frozen=True, slots=True)
class CommitGuardObservation:
    diff: str
    available_files: list[str]
    step_count: int
    reward: float
    done: bool
    error: Optional[str] = None


@dataclass(frozen=True, slots=True)
class CommitGuardState:
    episode_id: str
    current_sample_id: str
    step_count: int
    ground_truth: dict = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class DevignSample:
    sample_id: str
    diff: str
    available_files: list[str]
    is_vulnerable: bool
    cwe_type: str

