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
class ContextSnippet:
    file_path: str
    start_line: int
    end_line: int
    content: str


@dataclass(frozen=True, slots=True)
class CommitGuardObservation:
    # Cheating-prevention critical: this shape must never include ground truth.
    episode_id: str
    step_idx: int
    diff: str
    available_files: list[str]
    context_snippets: list[ContextSnippet] = field(default_factory=list)
    budget_remaining: int = 0
    error: Optional[str] = None


@dataclass(frozen=True, slots=True)
class CommitGuardState:
    episode_id: str
    current_sample_id: str
    step_count: int
    context_requests: int = 0
    history: list[dict] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class DevignSample:
    sample_id: str
    diff: str
    available_files: list[str]
    # Server-only fields (must never be surfaced in Observation)
    is_vulnerable: Optional[bool] = None
    cwe: Optional[str] = None
    target_file: Optional[str] = None
    files: Optional[dict[str, str]] = None


@dataclass(frozen=True, slots=True)
class ScanResult:
    is_vulnerable: bool
    cwe: Optional[str]
    exploit_sketch: Optional[str]
    raw_response: str
    parse_error: Optional[str] = None

