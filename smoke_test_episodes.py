import random
from pathlib import Path
from commitguard_env.environment import CommitGuardEnvironment
from commitguard_env.models import CommitGuardAction

def run_random_episodes(n=100):
    env = CommitGuardEnvironment(data_path=Path("data/devign_filtered.jsonl"))
    
    rewards = []
    episode_lengths = []
    
    for i in range(n):
        obs = env.reset()
        done = False
        total_reward = 0
        steps = 0
        
        while not done:
            # Randomly choose an action
            action_type = random.choice(["request_context", "analyze", "verdict"])
            
            if action_type == "request_context":
                action = CommitGuardAction(action_type="request_context", file_path="random_file.c")
            elif action_type == "analyze":
                action = CommitGuardAction(action_type="analyze", reasoning="Thinking...")
            else:
                action = CommitGuardAction(
                    action_type="verdict", 
                    is_vulnerable=random.choice([True, False]),
                    vuln_type="CWE-119",
                    exploit_sketch="Random exploit attempt"
                )
            
            obs, reward, done = env.step(action)
            total_reward += reward
            steps += 1
            
            if steps > 10: # Safety break
                break
        
        rewards.append(total_reward)
        episode_lengths.append(steps)
    
    print(f"Finished {n} episodes.")
    print(f"Average reward: {sum(rewards)/n:.4f}")
    print(f"Max reward: {max(rewards):.4f}")
    print(f"Min reward: {min(rewards):.4f}")
    print(f"Average episode length: {sum(episode_lengths)/n:.2f}")
    print(f"Max episode length: {max(episode_lengths)}")
    
    # Check distribution
    unique_rewards = set(rewards)
    print(f"Unique rewards: {len(unique_rewards)}")
    if len(unique_rewards) > 1:
        print("Reward distribution looks healthy (not all zeros).")
    else:
        print("Warning: Only one reward value found.")

if __name__ == "__main__":
    run_random_episodes(100)
