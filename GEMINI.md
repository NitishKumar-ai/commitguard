# CommitGuard - Project Context & Instructions

This file provides the foundational context and operational mandates for the **CommitGuard** project, a Meta OpenEnv RL environment for commit-time vulnerability detection.

## 🚀 Project Overview
CommitGuard is a specialized RL environment designed to train LLM agents (primarily **Llama-3.2-3B-Instruct**) to identify exploitable vulnerabilities in single-file code commits. It uses **Reinforcement Learning from Verifiable Rewards (RLVR)**, where rewards are grounded in dataset truth (Devign) rather than LLM judgment.

- **Goal:** Close the asymmetry between AI-paced code generation and human-paced security review.
- **Core Framework:** Meta OpenEnv (v0.2.3+).
- **Training Algorithm:** GRPO via TRL + Unsloth.
- **Dataset:** Preprocessed Devign (C-based commits, <80 LOC).

## 🛠️ Building and Running

### Environment Server
The server is built with FastAPI and can be run locally or via Docker.
- **Install:** `pip install -e .`
- **Run Local:** `server` (Runs on `http://localhost:8000`)
- **Run Docker:** `docker build -t commitguard . && docker run -p 8000:8000 commitguard`
- **Health Check:** `curl http://localhost:8000/health`

### Training & Evaluation
- **Train (GRPO):** `python scripts/train_grpo.py`
- **Baseline Curve:** `python scripts/run_and_plot_baseline.py --episodes 200`
- **Test:** `pytest` (Standard Python testing)

## 📐 Development Conventions & Mandates

### 1. The "No-Leak" Rule (Critical)
The agent must **NEVER** see ground truth labels (`is_vulnerable`, `cwe`, etc.).
- **Constraint:** Observations and HTTP responses must never contain label fields.
- **Verification:** `tests/test_no_leak.py` must remain green at all times.

### 2. Action Format (XML-Tagged)
Models must emit actions in XML format to ensure robust parsing.
- **Structure:** `<action><action_type>...</action_type>...</action>`
- **Types:** `request_context`, `analyze`, `verdict`.

### 3. Systematic Documentation (`.agent/`)
This project uses a structured `.agent/` directory for internal state and contracts. Always consult these before changes:
- `.agent/project_context.md`: Single source of truth for project state.
- `.agent/architecture.md`: Technical contracts and schemas.
- `.agent/test_contracts.md`: Merge-blocking requirements.

### 4. Deadline Operations (Hackathon Mode)
- **Scope Freeze:** Midnight Saturday IST. No new features after this point.
- **Pivots:** If technical blockers arise (e.g., OOM, slow queues), immediately use the pre-approved fallbacks documented in `prd.md` and `.agent/project_context.md`.

## 📁 Directory Structure
- `commitguard_env/`: Core environment logic, FastAPI server, and reward modeling.
- `scripts/`: Training entrypoints, preprocessing scripts, and GCE runbooks.
- `data/`: Dataset placeholders (`devign_filtered.jsonl`) and CWE mapping.
- `plots/`: Generated reward curves and performance artifacts.
- `tests/`: Smoke tests, reward validation, and leak detection.
- `.agent/`: High-priority architectural and process documentation.

## 🔗 Key Endpoints
- `POST /reset`: Initialize episode, returns diff + available files.
- `POST /step`: Submit XML action, returns `{observation, reward, done, info}`.
- `GET /health`: Server status.
- `GET /state`: Episode metadata (safe for agent logs).
