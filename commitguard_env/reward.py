from __future__ import annotations

from .models import CommitGuardAction

_CWE_FAMILIES: dict[str, str] = {
    # Memory and Buffer issues
    "CWE-119": "memory-safety", "CWE-120": "memory-safety", "CWE-121": "memory-safety",
    "CWE-122": "memory-safety", "CWE-125": "memory-safety", "CWE-787": "memory-safety",
    # Input and Validation issues (often overlap with memory safety)
    "CWE-20": "input-validation", "CWE-190": "input-validation", "CWE-189": "input-validation",
    "CWE-191": "input-validation",
    # Pointers
    "CWE-476": "null-pointer",
    # Logic and Traversal
    "CWE-22": "traversal",
    # Injections
    "CWE-78": "injection", "CWE-89": "injection", "CWE-79": "injection",
}


def _cwe_partial_score(predicted: str | None, actual: str | None) -> float:
    if not predicted or not actual:
        return 0.0
    p, a = predicted.strip().upper(), actual.strip().upper()
    if p == a:
        return 1.0
    pf = _CWE_FAMILIES.get(p, "")
    af = _CWE_FAMILIES.get(a, "")
    if pf and pf == af:
        return 0.5
    return 0.0


def compute_reward(
    *,
    action: CommitGuardAction,
    is_vulnerable: bool | None,
    cwe: str | None,
    target_file: str | None,
    cwe_keywords: dict[str, list[str]] | None,
    context_requests: int,
) -> float:
    # Graduated context penalty: first request is free, then escalating
    if context_requests <= 1:
        reward = 0.0
    else:
        reward = -0.05 * (context_requests - 1)

    if action.parse_error:
        return reward - 0.5

    if action.action_type == "analyze":
        reasoning_len = len(action.reasoning or "")
        if reasoning_len > 50:
            reward += min(0.05, 0.001 * (reasoning_len // 10))
        return reward

    if action.action_type == "request_context":
        return reward

    if action.action_type != "verdict":
        return reward

    if is_vulnerable is None:
        return reward

    pred = bool(action.is_vulnerable) if action.is_vulnerable is not None else None
    if pred is None:
        return reward - 0.5

    # True positive
    if pred is True and is_vulnerable is True:
        reward += 1.0

        # CWE scoring: exact match = 0.5, same family = 0.25
        cwe_score = _cwe_partial_score(action.vuln_type, cwe)
        reward += 0.5 * cwe_score

        # Keyword match (continuous, up to 0.5)
        kws = (cwe_keywords or {}).get(cwe or "", []) if cwe else []
        if kws:
            sketch = (action.exploit_sketch or "").lower()
            matches = sum(1 for k in kws if k.lower() in sketch)
            reward += 0.5 * (matches / len(kws))

        return reward

    # False positive
    if pred is True and is_vulnerable is False:
        return reward - 1.0

    # False negative
    if pred is False and is_vulnerable is True:
        return reward - 0.5

    # True negative
    if pred is False and is_vulnerable is False:
        return reward + 1.0

    return reward
