from __future__ import annotations

import unittest
from scripts.train_grpo import commitguard_reward_func, format_reward_func, MockCommitGuardEnv

class TestGRPOWiring(unittest.TestCase):
    def test_mock_env(self):
        env = MockCommitGuardEnv()
        obs = env.reset()
        self.assertEqual(obs.step_count, 0)
        self.assertIn("auth.c", obs.available_files)
        
        step_obs = env.step("<action>test</action>")
        self.assertTrue(step_obs.done)
        self.assertGreaterEqual(step_obs.reward, -1.0)
        self.assertLessEqual(step_obs.reward, 2.0)

    def test_format_reward_func(self):
        completions = [
            "<action><action_type>analyze</action_type></action>",
            "no action here",
            "just text <action>something</action> more text"
        ]
        rewards = format_reward_func(completions)
        self.assertEqual(rewards[0], 0.5)
        self.assertEqual(rewards[1], 0.0)
        self.assertEqual(rewards[2], 0.5)

    def test_commitguard_reward_func(self):
        prompts = ["p1", "p2"]
        completions = [
            "<action><action_type>verdict</action_type></action>",
            "invalid"
        ]
        # commitguard_reward_func returns deterministic penalties (e.g., -0.5) 
        # for invalid completions, while valid completions receive mocked/random rewards.
        rewards = commitguard_reward_func(prompts, completions)
        self.assertEqual(len(rewards), 2)
        self.assertIsInstance(rewards[0], float) # Reward from mock random behavior
        self.assertEqual(rewards[1], -0.5) # Penalty for invalid

if __name__ == "__main__":
    unittest.main()
