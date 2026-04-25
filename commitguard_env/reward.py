from __future__ import annotations
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import CommitGuardAction

def compute_reward(
    *, 
    action: CommitGuardAction, 
    ground_truth: dict, 
    cwe_keywords: dict, 
    step_count: int
) -> float:
    """
    Computes the scalar reward for an agent's action in the CommitGuard environment.
    
    Args:
        action: The action object taken by the agent.
        ground_truth: Dictionary containing 'is_vulnerable' and 'cwe_type'.
        cwe_keywords: Dictionary mapping CWE IDs to keyword patterns.
        step_count: The current step number in the episode.
    """
    reward = 0.0

    # Per-step efficiency penalty for context requests
    if action.action_type == "request_context":
        return -0.05

    # Analyze action — no reward, just logged
    if action.action_type == "analyze":
        return 0.0

    # Verdict action — main reward signal
    if action.action_type == "verdict":
        # Correctness of binary classification
        if action.is_vulnerable == ground_truth["is_vulnerable"]:
            reward += 1.0
            
            # Bonus: correct CWE classification (only if vulnerable)
            if ground_truth["is_vulnerable"]:
                if action.vuln_type == ground_truth["cwe_type"]:
                    reward += 0.5
                
                # Bonus: plausible exploit sketch
                sketch = action.exploit_sketch or ""
                if sketch:
                    patterns = cwe_keywords.get(ground_truth["cwe_type"], [])
                    sketch_lower = sketch.lower()
                    if any(p.lower() in sketch_lower for p in patterns):
                        reward += 0.5
        else:
            # Wrong classification
            if action.is_vulnerable and not ground_truth["is_vulnerable"]:
                reward -= 1.0  # False positive
            else:
                reward -= 0.5  # False negative

    return reward
