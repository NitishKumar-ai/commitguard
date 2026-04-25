import json
from pathlib import Path
from dataclasses import asdict
from commitguard_env.environment import CommitGuardEnvironment
from commitguard_env.models import CommitGuardAction

def test_observation_does_not_leak_ground_truth():
    """
    Goal: A test that fails loudly if ground truth 
    leaks into the observation returned to the agent.
    """
    data_path = Path("data/devign_filtered.jsonl")
    if not data_path.exists():
        # Fallback for testing environment if real data isn't available
        # But in this workspace it should be there.
        print("Warning: data/devign_filtered.jsonl not found. Skipping test.")
        return

    env = CommitGuardEnvironment(data_path=data_path)
    obs = env.reset()
    
    # Check reset observation
    obs_dict = asdict(obs)
    forbidden_keys = ["is_vulnerable", "cwe_type", "ground_truth", "label"]
    
    # Check both keys and the string representation for leaks
    obs_str = str(obs_dict).lower()
    for key in forbidden_keys:
        assert key not in obs_dict, f"Leak detected: Forbidden key '{key}' found in observation dict keys."
        assert key not in obs_str, f"Leak detected: Forbidden string '{key}' found in observation data."
        
    # Check after a step
    action = CommitGuardAction(action_type="analyze", reasoning="Verifying no leaks.")
    obs = env.step(action)
    
    obs_dict = asdict(obs)
    obs_str = str(obs_dict).lower()
    for key in forbidden_keys:
        assert key not in obs_dict, f"Leak detected in step(): Forbidden key '{key}' found."
        assert key not in obs_str, f"Leak detected in step(): Forbidden string '{key}' found."
    
    print("No-leak test passed! No ground truth keys found in observations.")

if __name__ == "__main__":
    test_observation_does_not_leak_ground_truth()
