import json

def compute_reward(action: dict, ground_truth: dict, cwe_keywords: dict, step_count: int) -> float:
    """
    Computes the scalar reward for an agent's action in the CommitGuard environment.
    """
    reward = 0.0

    # Per-step efficiency penalty for context requests
    if action["action_type"] == "request_context":
        return -0.05

    # Analyze action — no reward, just logged
    if action["action_type"] == "analyze":
        return 0.0

    # Verdict action — main reward signal
    if action["action_type"] == "verdict":
        # Correctness of binary classification
        if action["is_vulnerable"] == ground_truth["is_vulnerable"]:
            reward += 1.0
            
            # Bonus: correct CWE classification (only if vulnerable)
            if ground_truth["is_vulnerable"]:
                if action.get("vuln_type") == ground_truth["cwe_type"]:
                    reward += 0.5
                
                # Bonus: plausible exploit sketch
                sketch = action.get("exploit_sketch", "")
                if sketch:
                    patterns = cwe_keywords.get(ground_truth["cwe_type"], [])
                    sketch_lower = sketch.lower()
                    if any(p.lower() in sketch_lower for p in patterns):
                        reward += 0.5
        else:
            # Wrong classification
            if action["is_vulnerable"] and not ground_truth["is_vulnerable"]:
                reward -= 1.0  # False positive
            else:
                reward -= 0.5  # False negative

    return reward

if __name__ == "__main__":
    # Test cases
    with open('cwe_keywords.json') as f:
        keywords = json.load(f)
        
    gt = {"is_vulnerable": True, "cwe_type": "CWE-89"}
    
    # Test 1: Perfect verdict
    a1 = {
        "action_type": "verdict", 
        "is_vulnerable": True, 
        "vuln_type": "CWE-89", 
        "exploit_sketch": "Use ' union select ' to bypass auth"
    }
    r1 = compute_reward(a1, gt, keywords, 1)
    print(f"Perfect Verdict Reward: {r1} (Expected: 2.0)")
