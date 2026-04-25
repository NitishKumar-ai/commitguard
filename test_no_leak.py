from dataclasses import asdict
# Placeholder imports - these will be replaced by Niti's env code
# from environment import CommitGuardEnvironment, CommitGuardAction

def test_observation_does_not_leak_ground_truth(env_class, action_class):
    """
    Goal: A test that fails loudly if Niti accidentally leaks ground truth 
    into the observation returned to the agent.
    """
    env = env_class()
    obs = env.reset()
    
    # Check reset observation
    obs_dict = asdict(obs)
    forbidden_keys = ["is_vulnerable", "cwe_type", "ground_truth", "label"]
    for key in forbidden_keys:
        assert key not in str(obs_dict).lower(), f"Leak detected in reset(): {key}"
        
    # Check after a step
    # Action type 'analyze' should be safe
    action = action_class(action_type="analyze", reasoning="test")
    obs, _, _, _ = env.step(action)
    obs_dict = asdict(obs)
    for key in forbidden_keys:
        assert key not in str(obs_dict).lower(), f"Leak detected in step(): {key}"
    
    print("No-leak test passed! No ground truth keys found in observations.")

if __name__ == "__main__":
    # This script will be called by Task 2.1 integration
    print("test_no_leak.py ready. Awaiting Niti's environment.py integration.")
