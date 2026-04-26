# CommitGuard - Project Context & Instructions

This file is the **foundational mandate** for the CommitGuard project. It defines the technical standards, security protocols, and operational workflows that must be followed by all agents.

## 🚀 Project Overview
CommitGuard is a specialized RL environment built on **Meta OpenEnv** for commit-time vulnerability detection. It trains LLM agents (primarily **Llama-3.2-3B-Instruct**) to identify exploitable vulnerabilities in single-file code commits using **Reinforcement Learning from Verifiable Rewards (RLVR)**.

- **Objective:** Bridge the gap between AI-speed code generation and human-paced security review.
- **Framework:** Meta OpenEnv (v0.2.3+).
- **Incentive:** Tiered rewards grounded in dataset truth (Devign), not LLM judgment.

## 📐 Engineering Standards (Non-Negotiable)

### 1. The "No-Leak" Rule (Highest Priority)
The agent must **NEVER** see ground truth labels (`is_vulnerable`, `cwe`, etc.) during an episode.
- **Constraint:** `CommitGuardObservation` and all reward calculations must be stripped of label fields before being presented to the model.
- **Validation:** `tests/test_no_leak.py` must remain green. Any change that causes a leak is a blocking failure.

### 2. Python Architecture
- **Typed Dataclasses:** Use `@dataclass(frozen=True, slots=True)` for all API shapes (Actions, Observations, State).
- **Strict Typing:** Every function and variable must be type-annotated end-to-end.
- **No Untyped Dicts:** Dicts are for internal parsing only; convert to dataclasses at all boundaries.
- **Defensive Parsing:** XML parsers must handle malformed model output without crashing, returning safe defaults and structured errors.

### 3. XML Action Format
Models must emit exactly one top-level `<action>` block to ensure robust parsing.
- **Structure:** `<action><action_type>...</action_type><fields>...</fields></action>`
- **Types:** `request_context`, `analyze`, `verdict`.

## 🛠️ Operational Workflows

### 1. Evaluation Pipeline (`scripts/evaluate.py`)
This script executes local inference on test samples to compute accuracy metrics.
- **Deterministic Selection:** It iterates through `data/devign_test.jsonl`.
- **Strict Scoring:** `is_correct` requires both a correct binary verdict AND a correct CWE type match (if vulnerable).
- **Inference:** Uses Unsloth/FastLanguageModel for accelerated evaluation.

### 2. Training Pipeline (`scripts/train_grpo.py`)
- **Framework:** Uses TRL's `GRPOTrainer` with Unsloth 4-bit quantization.
- **Local Rewards:** Reward functions are computed in-process (`get_reward_local`) to eliminate latency.

### 3. Visualization (`plots/`)
- `plot_reward_curve.py`: Visualizes reward trends from `eval_results.json`.
- `plot_per_cwe.py`: Generates bar charts showing accuracy breakdown by CWE category.
- `plot_baseline_vs_trained.py`: Compares untrained vs. trained model performance.

## 📁 Critical Files
- `commitguard_env/`: Core logic (environment, reward model, XML parser).
- `data/`: `devign_filtered.jsonl` (training) and `devign_test.jsonl` (testing).
- `scripts/`: Training, evaluation, and environment setup runbooks (GCP/Lightning).
- `.agent/`: Internal state, technical contracts, and hackathon milestones.

## ⏳ Hackathon Mandate
- **Scope Freeze:** No new features after midnight Saturday IST. Focus strictly on reliability, documentation, and evaluation.
- **Fallback Triggers:** If OOM or performance blockers occur, pivot immediately to documented fallbacks (e.g., Qwen-1.5B) and log in `.agent/decision_log.md`.
