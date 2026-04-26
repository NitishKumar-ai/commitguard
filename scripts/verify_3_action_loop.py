import requests
import json
import sys

def test_loop():
    base_url = "http://localhost:8000"
    
    print("--- Phase 1: Reset ---")
    r = requests.post(f"{base_url}/reset")
    if r.status_code != 200:
        print(f"FAILED: Reset returned {r.status_code}")
        return
    data = r.json()
    print(f"Full response keys: {list(data.keys())}")
    obs = data["observation"]
    print(f"Observation value: {obs}")
    episode_id = obs["episode_id"]
    print(f"Observation keys: {list(obs.keys())}")
    print(f"Episode ID: {episode_id}")
    print(f"Diff length: {len(obs['diff'])}")
    
    # Verify no leak
    forbidden = ["is_vulnerable", "cwe", "cwe_type", "label"]
    for f in forbidden:
        if f in obs:
            print(f"CRITICAL LEAK: '{f}' found in observation!")
            sys.exit(1)

    print("\n--- Phase 2: Action 'request_context' ---")
    # Using the first available file if any
    file_to_req = obs["available_files"][0] if obs["available_files"] else "unknown.c"
    action = {
        "action": f"<action><action_type>request_context</action_type><file_path>{file_to_req}</file_path></action>"
    }
    r = requests.post(f"{base_url}/step", json=action)
    res = r.json()
    print(f"Status: {r.status_code}, Reward: {res['reward']}, Done: {res['done']}")
    print(f"Context snippets returned: {len(res['observation'].get('context_snippets', []))}")

    print("\n--- Phase 3: Action 'analyze' ---")
    action = {
        "action": "<action><action_type>analyze</action_type><reasoning>Thinking about the pointer arithmetic in the diff...</reasoning></action>"
    }
    r = requests.post(f"{base_url}/step", json=action)
    res = r.json()
    print(f"Status: {r.status_code}, Reward: {res['reward']}, Done: {res['done']}")

    print("\n--- Phase 4: Action 'verdict' ---")
    action = {
        "action": "<action><action_type>verdict</action_type><is_vulnerable>true</is_vulnerable><vuln_type>CWE-119</vuln_type><exploit_sketch>buffer overflow via unchecked memcpy</exploit_sketch></action>"
    }
    r = requests.post(f"{base_url}/step", json=action)
    res = r.json()
    print(f"Status: {r.status_code}, Reward: {res['reward']}, Done: {res['done']}")
    print(f"Final Info: {res.get('info', 'No info')}")

    print("\n--- Phase 5: Verify State (No Leaks) ---")
    r = requests.get(f"{base_url}/state")
    data = r.json()
    state = data["state"]
    print(f"State Episode ID: {state['episode_id']}")
    print(f"Step Count: {state['step_count']}")
    for f in forbidden:
        if f in state:
             # state() is allowed internal metadata, but the PRD says it shouldn't leak to agent.
             # environment.py says: "state() must not leak labels; returning empty is fine"
             print(f"LEAK WARNING: '{f}' found in state output!")

if __name__ == "__main__":
    test_loop()
