from __future__ import annotations

# Canonical location is commitguard_env.agent_prompt; re-exported here
# so that scripts/ and notebooks/ that do `from agent_prompt import ...` still work.
from commitguard_env.agent_prompt import SYSTEM_PROMPT, get_agent_prompt

__all__ = ["SYSTEM_PROMPT", "get_agent_prompt"]
