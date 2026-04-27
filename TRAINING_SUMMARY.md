# CommitGuard: Technical Training Summary

This document provides a comprehensive overview of the training procedure used for the CommitGuard model during the hackathon.

---

## 🚀 Objective
To train a specialized LLM (**Llama-3.2-3B-Instruct**) to autonomously identify security vulnerabilities in code commits and provide structured, reasoning-based exploit sketches using Reinforcement Learning.

## 🛠️ Technical Stack & Optimization
- **Base Model:** `Llama-3.2-3B-Instruct`
- **Optimization:** **Unsloth 4-bit Quantization** (PEFT/LoRA)
- **Infrastructure:** Google Colab (NVIDIA T4 GPU)
- **RL Framework:** Meta OpenEnv (v0.2.3+)

## 🧠 Training Methodology: GRPO
We utilized **Group Relative Policy Optimization (GRPO)**, an advanced reinforcement learning algorithm that optimizes the model based on relative performance within a group of generated responses. 

- **Group Size:** 4 completions per prompt.
- **Advantage:** No separate Reward Model (RM) is required; the model learns by comparing its own variations against the environment's verifiable reward.

## 🌍 The Environment (CommitGuard Env)
A custom RL environment was built to simulate a security audit workflow:
1. **Observation:** The model receives a code diff and file context.
2. **Action Space:** Structured XML actions (`<request_context>`, `<analyze>`, `<verdict>`).
3. **Internal State:** Managed by a FastAPI server that tracks episode progress and calculates rewards.

## 🏆 Verifiable Reward System
Rewards are grounded in the **Devign** dataset's ground-truth labels:
- **Binary Verdict (+1.0):** Correctly identifying `is_vulnerable`.
- **CWE Accuracy (+0.5):** Correctly matching the vulnerability type (e.g., CWE-119).
- **Exploit Sketch Bonus (up to +0.5):** Verification of security keywords in the model's reasoning.
- **Efficiency Penalty (-0.05 per request):** Encourages the model to find vulnerabilities with minimal context requests.

## 📈 Training Configuration
- **Dataset:** Filtered Devign (C-language single-file commits).
- **Learning Rate:** $2.0 \times 10^{-5}$
- **Sequence Length:** 2048 tokens.
- **Training Duration:** ~3 hours (300 steps).

## 🏁 Final Artifact
The training produces a **LoRA Adapter** (~50MB) that can be seamlessly integrated into CI/CD pipelines to provide "AI-speed" code security reviews with "human-level" reasoning.
