from __future__ import annotations

from .models import CommitGuardAction


def compute_reward(
    *,
    action: CommitGuardAction,
    is_vulnerable: bool | None,
    cwe: str | None,
    target_file: str | None,
    cwe_keywords: dict[str, list[str]] | None,
    context_requests: int,
) -> float:
    """
    Tiered RLVR reward (PRD 5.3, architecture contract).

    Notes:
    - Ground truth must remain server-only; caller passes it in.
    - Reward is a scalar only; no label debug info.
    """
    # Per-context-request penalty applies regardless of verdict.
    reward = -0.05 * float(max(0, context_requests))

    if action.parse_error:
        return reward - 0.5

    # Small CoT bonus: reward 'analyze' steps that provide substantial reasoning.
    # This provides a tiny positive float signal to encourage thinking.
    if action.action_type == "analyze":
        reasoning_len = len(action.reasoning or "")
        if reasoning_len > 50:
            reward += min(0.05, 0.001 * (reasoning_len // 10))
        return reward

    if action.action_type != "verdict":
        return reward

    if is_vulnerable is None:
        return reward

    pred = bool(action.is_vulnerable) if action.is_vulnerable is not None else None
    if pred is None:
        return reward - 0.5

    if pred is True and is_vulnerable is True:
        reward += 1.0
        # Correct CWE (Discrete 0.5)
        if cwe and action.vuln_type and action.vuln_type.strip().upper() == cwe.strip().upper():
            reward += 0.5

        # Proportional Keyword Match (Continuous Float up to 0.5)
        kws = (cwe_keywords or {}).get(cwe or "", []) if cwe else []
        if kws:
            sketch = (action.exploit_sketch or "").lower()
            matches = sum(1 for k in kws if k.lower() in sketch)
            # Continuous signal: reward is proportional to percentage of keywords found.
            reward += 0.5 * (matches / len(kws))
        return reward

    if pred is True and is_vulnerable is False:
        return reward - 1.0

    if pred is False and is_vulnerable is True:
        return reward - 0.5

    if pred is False and is_vulnerable is False:
        return reward + 1.0

    return reward

