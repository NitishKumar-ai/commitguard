from __future__ import annotations

from .models import CommitGuardAction


def compute_reward(*, action: CommitGuardAction) -> float:
    """
    Phase-1 stub: always returns 0.0.

    Real reward (tiered RLVR) is implemented by Deepak per PRD.
    """
    _ = action
    return 0.0

