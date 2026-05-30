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


# ---------------------------------------------------------------------------
# v2 models — repo-level scanning agent
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Finding:
    """A single vulnerability finding from the v2 scanner."""

    file: str
    line_start: int
    line_end: int
    cwe_id: str
    cwe_name: str
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
    confidence: float
    exploit_sketch: str
    suggested_fix: str
    code_snippet: str


@dataclass(frozen=True, slots=True)
class ScanJob:
    """A queued repository scan job."""

    job_id: str
    repo_url: str
    status: Literal[
        "queued", "cloning", "planning", "scanning",
        "reviewing", "verifying", "filing", "documenting",
        "complete", "failed",
    ]
    findings: list[Finding] = field(default_factory=list)
    error: Optional[str] = None
    created_at: Optional[str] = None


@dataclass(frozen=True, slots=True)
class CodeChunk:
    """A chunk of code for memory / embedding."""

    file_path: str
    start_line: int
    end_line: int
    content: str
    token_count: int


# ---------------------------------------------------------------------------
# v3 models — closed-loop verification & self-training
# ---------------------------------------------------------------------------

VerificationVerdict = Literal["CONFIRMED", "UNVERIFIABLE", "FALSE_POSITIVE"]


@dataclass(frozen=True, slots=True)
class VerifiedFinding:
    """A finding that has been through the L2 verification sandbox."""

    finding: Finding
    verdict: VerificationVerdict
    exploit_code: str
    exploit_output: str
    execution_time_ms: int
    sandbox_exit_code: int
    verified_at: str


@dataclass(frozen=True, slots=True)
class TrainingPair:
    """A structured training example from a verified scan."""

    code: str
    cwe_id: str
    cwe_name: str
    verdict: VerificationVerdict
    exploit_code: str
    exploit_output: str
    suggested_fix: str
    repo_url: str
    commit_sha: str
    file_path: str
    line_start: int
    line_end: int
    created_at: str


@dataclass(frozen=True, slots=True)
class SandboxConfig:
    """Configuration for the L2 verification sandbox."""

    image: str = "commitguard-sandbox:latest"
    cpu_limit: str = "2"
    memory_limit: str = "2g"
    timeout_seconds: int = 30
    network_disabled: bool = True
    read_only_rootfs: bool = True


@dataclass(frozen=True, slots=True)
class RetrainJob:
    """Tracks a self-training LoRA rerun."""

    job_id: str
    status: Literal["pending", "training", "swapping", "complete", "failed"]
    new_examples_count: int
    adapter_path: str
    started_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None

