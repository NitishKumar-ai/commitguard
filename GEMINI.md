# CommitGuard v3 - Project Context & Instructions

This file is the **foundational mandate** for the CommitGuard project. It defines the technical standards, security protocols, and operational workflows that must be followed by all agents.

## 🚀 Project Overview
CommitGuard v3 is an autonomous security scanning and **self-improving verification system**. It monitors public GitHub repositories, detects vulnerabilities, verifies them via sandboxed exploits, and uses the verified findings to automatically retrain itself.

- **Model:** Gemma 4 E4B fine-tuned via LoRA on the Devign dataset (and self-improving via v3 pipeline).
- **Agent Architecture:** Jules-inspired async design with a 4-layer loop: L1 Scanner, L2 Verifier, L3 Pipeline, and L4 Self-Trainer.
- **Output:** Structured GitHub Issues with CWE IDs, severity badges, exploit sketches, and fix suggestions, backed by verified exploits.

## 📐 Engineering Standards (Non-Negotiable)

### 1. The "No-Leak" Rule (Highest Priority)
The agent must **NEVER** see ground truth labels (`is_vulnerable`, `cwe`, etc.) during an episode.
- **Constraint:** `CommitGuardObservation` and all reward calculations must be stripped of label fields before being presented to the model.
- **Validation:** `tests/test_no_leak.py` must remain green. Any change that causes a leak is a blocking failure.

### 2. Python Architecture
- **Typed Dataclasses:** Use `@dataclass(frozen=True, slots=True)` for all API shapes (Actions, Observations, State, Findings).
- **Strict Typing:** Every function and variable must be type-annotated end-to-end.
- **No Untyped Dicts:** Dicts are for internal parsing only; convert to dataclasses at all boundaries.
- **Defensive Parsing:** JSON/XML parsers must handle malformed model output without crashing, returning safe defaults and structured errors.

### 3. Structured JSON Output Format (v2)
The Gemma 4 E4B model outputs structured JSON for each finding:
```json
{
  "is_vulnerable": true,
  "cwe_id": "CWE-89",
  "cwe_name": "SQL Injection",
  "severity": "HIGH",
  "confidence": 0.91,
  "exploit_sketch": "...",
  "suggested_fix": "...",
  "line_start": 42,
  "line_end": 58
}
```

## 🛠️ Operational Workflows

### 1. Training Pipeline (`scripts/train_gemma.py`)
- **Base model:** `google/gemma-4-4b-it` with 4-bit NF4 quantization
- **LoRA config:** r=16, alpha=32, dropout=0.05, target modules: q_proj, v_proj, k_proj, o_proj
- **Data:** Instruction-tuning pairs from `scripts/data_prep.py`
- **Hardware:** GCP L4 GPU (us-central1)

### 2. Data Pipeline (`scripts/data_prep.py`)
- Downloads Devign from HuggingFace
- Synthetic augmentation: variable renaming, decoy injection
- Outputs: `data/gemma_train.jsonl`, `data/gemma_val.jsonl`, `data/gemma_test.jsonl`

### 3. 4-Layer Scan & Train Loop (`commitguard_env/repo_agent.py`)
1. **L1 Scanner** — Plan + Execute + Review (Gemma 4 inference on repo code)
2. **L2 Verifier** — Sandboxed exploit generation to prove vulnerabilities
3. **L3 Pipeline** — Documents verified exploits as LoRA training pairs to GCS
4. **L4 Self-Trainer** — Monitors new examples and triggers hot-swap LoRA retraining

### 4. Server (`commitguard_env/server_v2.py`)
- `POST /scan` — Enqueue a repo scan
- `GET /status/{job_id}` — Poll job status
- `GET /findings/{job_id}` — Get findings
- `GET /training/status` — Get L3 pipeline status
- `POST /retrain/trigger` — Trigger L4 retraining
- `GET /adapter/current` — Check current hot-swapped adapter

## 📁 Critical Files

### v3 Components
- `commitguard_env/verifier.py` — L2 Exploit sandbox verification
- `commitguard_env/training_pipeline.py` — L3 GCS documentation pipeline
- `commitguard_env/self_trainer.py` — L4 Adapter retraining and hot-swapping
- `commitguard_env/scanner_v2.py` — L1 Scanner
- `commitguard_env/repo_agent.py` — Async job queue + orchestration
- `commitguard_env/server_v2.py` — v2/v3 FastAPI endpoints
- `Dockerfile.sandbox` — Minimal isolated image for L2 verifier

### v1 Components (preserved)
- `commitguard_env/environment.py` — RL environment
- `commitguard_env/reward.py` — Reward computation
- `commitguard_env/models.py` — Dataclasses (v1 + v2)
- `commitguard_env/parse_action.py` — XML action parser
- `commitguard_env/scanner.py` — v1 single-diff scanner
- `commitguard_env/server.py` — v1 FastAPI endpoints
- `data/` — Devign datasets
- `scripts/train_grpo.py` — v1 GRPO training (reference)

## ⏳ Hackathon Mandate
- **Scope Freeze:** No new features after midnight Saturday IST. Focus strictly on reliability, documentation, and evaluation.
- **Fallback Triggers:** If OOM or performance blockers occur, pivot immediately to documented fallbacks (e.g., Gemma 3 4B) and log in `.agent/decision_log.md`.
