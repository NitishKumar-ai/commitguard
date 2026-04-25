import json
from commitguard_env.reward import compute_reward
from commitguard_env.models import CommitGuardAction

def test_reward():
    with open('cwe_keywords.json') as f:
        keywords = json.load(f)
        
    # Ground Truth: Vulnerable SQL Injection (CWE-89)
    gt_vuln = {"is_vulnerable": True, "cwe_type": "CWE-89"}
    
    # 1. Correct vulnerable verdict (Binary only) -> reward = 1.0
    a1 = CommitGuardAction(action_type="verdict", is_vulnerable=True, vuln_type="CWE-119", exploit_sketch="")
    r1 = compute_reward(action=a1, ground_truth=gt_vuln, cwe_keywords=keywords, step_count=1)
    assert r1 == 1.0, f"Expected 1.0, got {r1}"
    
    # 2. Correct vulnerable + correct CWE + good sketch -> reward = 2.0
    a2 = CommitGuardAction(
        action_type="verdict", 
        is_vulnerable=True, 
        vuln_type="CWE-89", 
        exploit_sketch="Inject ' or 1=1 -- to bypass login"
    )
    r2 = compute_reward(action=a2, ground_truth=gt_vuln, cwe_keywords=keywords, step_count=1)
    assert r2 == 2.0, f"Expected 2.0, got {r2}"
    
    # 3. False positive (flagged safe as vulnerable) -> reward = -1.0
    gt_safe = {"is_vulnerable": False, "cwe_type": "N/A"}
    a3 = CommitGuardAction(action_type="verdict", is_vulnerable=True, vuln_type="CWE-89", exploit_sketch="")
    r3 = compute_reward(action=a3, ground_truth=gt_safe, cwe_keywords=keywords, step_count=1)
    assert r3 == -1.0, f"Expected -1.0, got {r3}"
    
    # 4. False negative (missed real vuln) -> reward = -0.5
    a4 = CommitGuardAction(action_type="verdict", is_vulnerable=False, vuln_type="", exploit_sketch="")
    r4 = compute_reward(action=a4, ground_truth=gt_vuln, cwe_keywords=keywords, step_count=1)
    assert r4 == -0.5, f"Expected -0.5, got {r4}"
    
    # 5. Context request -> reward = -0.05
    a5 = CommitGuardAction(action_type="request_context", file_path="main.c")
    r5 = compute_reward(action=a5, ground_truth=gt_vuln, cwe_keywords=keywords, step_count=1)
    assert r5 == -0.05, f"Expected -0.05, got {r5}"
    
    print("All 5 hand-crafted unit tests passed!")

if __name__ == "__main__":
    test_reward()
