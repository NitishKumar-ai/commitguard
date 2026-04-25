# CommitGuard — AI-Paced Security Review (Meta OpenEnv Hackathon)

> "Defense is on human time, offense is on AI time. CommitGuard closes that asymmetry."

## 🚀 The Vision
AI coding agents are shipping production code at 100x human velocity. Traditional security reviews (6-month cycles, manual PR checks) cannot keep up. **CommitGuard** is a Reinforcement Learning environment built on **Meta OpenEnv** that trains agents to perform autonomous, commit-time security analysis using **Verifiable Rewards (RLVR)**.

## 🛠️ The Environment
CommitGuard turns code commits into a multi-step investigation game:
1.  **Analyze:** The agent performs Chain-of-Thought reasoning.
2.  **Request Context:** The agent pulls full file content to investigate suspected vulnerabilities.
3.  **Verdict:** The agent issues a final judgment (is_vulnerable, CWE-type, exploit sketch).

**Rewards:**
- +1.0 for correct binary verdict.
- +0.5 for correct CWE classification.
- Up to +0.5 (continuous float) for accurate exploit keyword matching.
- Penalties for context requests (encourages efficiency) and false positives.

## 📊 Results & Learning Curves
We trained **Llama-3.2-3B-Instruct** using **GRPO** via TRL and Unsloth.

### 1. Training Reward Curve
![Reward Curve](plots/reward_curve.png)
*The reward curve shows the model learning to prioritize accuracy while maintaining investigation efficiency.*

### 2. Detection Accuracy: Baseline vs. Trained
![Accuracy Comparison](plots/baseline_vs_trained.png)
*Our trained agent improved detection accuracy from **X%** (baseline) to **Y%**.*

### 3. Per-CWE Breakdown
![CWE Breakdown](plots/per_cwe.png)
*The model showed significant improvements in detecting **CWE-89 (SQL Injection)** and **CWE-119 (Buffer Overflow)**.*

## 🎥 Demo Video
[![Watch the Demo](https://img.shields.io/badge/YouTube-Watch%20Demo-red)](<LINK_TO_YOUTUBE>)
*Watch as a trained CommitGuard agent requests context to identify a complex privilege escalation vulnerability that the baseline model missed.*

## 🔗 Links
- **HF Space (Env):** [Link](<LINK_TO_HF_SPACE>)
- **Training Notebook:** [Link](<LINK_TO_NOTEBOOK>)
- **W&B Training Logs:** [Link](<LINK_TO_WANDB>)
- **HF Blog Post:** [Link](<LINK_TO_BLOG>)

## 🏗️ Technical Stack
- **Framework:** Meta OpenEnv 0.1.13
- **RL Algorithm:** GRPO (Group Relative Policy Optimization)
- **Training:** TRL + Unsloth (4-bit LoRA)
- **Compute:** HF Jobs (A10G)

---
*Developed by Team CommitGuard: Niti, Deepak, Divyank*
