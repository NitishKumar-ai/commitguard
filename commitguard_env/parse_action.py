from __future__ import annotations

import re
from typing import Any, Optional

from .models import CommitGuardAction


_TAG_RE = re.compile(r"<(?P<tag>[a-zA-Z_]+)>(?P<val>.*?)</(?P=tag)>", re.DOTALL)


def _first(tag: str, text: str) -> Optional[str]:
    m = re.search(rf"<{re.escape(tag)}>(.*?)</{re.escape(tag)}>", text, flags=re.DOTALL)
    if not m:
        return None
    return m.group(1).strip()


def _parse_bool(v: Optional[str]) -> Optional[bool]:
    if v is None:
        return None
    s = v.strip().lower()
    if s in {"true", "1", "yes"}:
        return True
    if s in {"false", "0", "no"}:
        return False
    return None


def parse_action(raw_action: str) -> CommitGuardAction:
    """
    Parse XML-tag free-text action. Never raises.

    Expected shape:
    <action><action_type>...</action_type><fields>...</fields></action>
    """
    try:
        action_type = (_first("action_type", raw_action) or "").strip().lower()
        if action_type not in {"request_context", "analyze", "verdict"}:
            return CommitGuardAction(
                action_type="analyze",
                raw_action=raw_action,
                parse_error="missing_or_invalid_action_type",
            )

        if action_type == "request_context":
            file_path = _first("file_path", raw_action)
            return CommitGuardAction(
                action_type="request_context",
                file_path=file_path,
                raw_action=raw_action,
            )

        if action_type == "analyze":
            reasoning = _first("reasoning", raw_action)
            return CommitGuardAction(action_type="analyze", reasoning=reasoning, raw_action=raw_action)

        is_vulnerable = _parse_bool(_first("is_vulnerable", raw_action))
        vuln_type = _first("vuln_type", raw_action)
        exploit_sketch = _first("exploit_sketch", raw_action)
        return CommitGuardAction(
            action_type="verdict",
            is_vulnerable=is_vulnerable,
            vuln_type=vuln_type,
            exploit_sketch=exploit_sketch,
            raw_action=raw_action,
        )
    except Exception as e:  # defensive: model output must never crash server
        return CommitGuardAction(
            action_type="analyze",
            raw_action=raw_action,
            parse_error=f"parser_exception:{type(e).__name__}",
        )


def action_from_json(payload: dict[str, Any]) -> CommitGuardAction:
    """
    Convenience for curl/json clients: accept either {action: "<xml>"} or
    direct fields matching CommitGuardAction.
    """
    if isinstance(payload.get("action"), str):
        return parse_action(payload["action"])

    action_type = (payload.get("action_type") or "analyze").strip().lower()
    if action_type not in {"request_context", "analyze", "verdict"}:
        action_type = "analyze"

    return CommitGuardAction(
        action_type=action_type,  # type: ignore[arg-type]
        file_path=payload.get("file_path"),
        reasoning=payload.get("reasoning"),
        is_vulnerable=payload.get("is_vulnerable"),
        vuln_type=payload.get("vuln_type"),
        exploit_sketch=payload.get("exploit_sketch"),
        raw_action=None,
        parse_error=None,
    )

