"""
Standalone utility for parsing XML-tagged model actions.
Wraps the core logic in commitguard_env.
"""

import sys
import os
import json

# Ensure parent directory is in path to find commitguard_env
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from commitguard_env.models import CommitGuardAction
from commitguard_env.parse_action import parse_action as core_parse

def parse_action_to_dict(raw_text: str) -> CommitGuardAction:
    """
    Parses an XML action string and returns a CommitGuardAction object.
    Handles malformed responses gracefully.
    """
    return core_parse(raw_text)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_input = " ".join(sys.argv[1:])
        action = parse_action_to_dict(test_input)
        # Convert to dict for printing
        res = {
            "action_type": action.action_type,
            "file_path": action.file_path,
            "reasoning": action.reasoning,
            "is_vulnerable": action.is_vulnerable,
            "vuln_type": action.vuln_type,
            "exploit_sketch": action.exploit_sketch,
            "parse_error": action.parse_error
        }
        print(json.dumps({k: v for k, v in res.items() if v is not None}, indent=2))
    else:
        print("Usage: python parse_action.py '<action>...</action>'")
