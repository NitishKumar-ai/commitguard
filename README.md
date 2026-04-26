---
title: CommitGuard
emoji: 🛡️
colorFrom: indigo
colorTo: red
sdk: docker
pinned: false
---

# CommitGuard (OpenEnv Hackathon)

CommitGuard is a **Meta OpenEnv** RL environment that trains LLM agents to detect exploitable vulnerabilities in **code commits** (single-file diffs). Its **RLVR**: rewards come from ground truth (dataset labels), **not** an LLM judge.

## 30-second pitch (verbatim)

> "AI is now writing production code at AI speed. Security review still runs on a 6-month human cycle. The same LLMs that write the code can attack it  defense is on human time, offense is on AI time, and that asymmetry breaks the security model.
>
> CommitGuard is an OpenEnv where an agent learns to flag exploitable diffs at commit time. We trained Llama-3.2-3B on it via GRPO and the detection rate climbs measurably. It's RLVR  verifiable rewards from ground truth, not LLM judges. The thesis: continuous AI red-teaming at the velocity code is being shipped. This is the environment to train it."

## Whats in this repo (today)

- **Env server**: `commitguard_env/` (FastAPI + Docker)
- **Dataset placeholders**: `data/devign_filtered.jsonl`, `data/cwe_keywords.json`
- **Agent constraints**: `.agent/` + `AGENT.md` (scope freeze, architecture contract, tests)

## Non-negotiable safety rule (no-leak)

The agent must **never** see ground truth. Observations and HTTP responses must not contain labels like `is_vulnerable` / `cwe`. See `.agent/architecture.md` and the merge-blocking `tests/test_no_leak.py` contract in `.agent/test_contracts.md`.

## Quickstart (local)

Prereqs: Python 3.10+

```bash
python -m pip install -e .
server
```

Health check:

```bash
powershell -NoProfile -Command "Invoke-RestMethod http://localhost:8000/health | ConvertTo-Json -Compress"
```

## Generate required plot artifacts (P0)

Baseline curve (commits a PNG under `plots/`):

```bash
python -m pip install matplotlib
python scripts/run_and_plot_baseline.py --episodes 200
```

## Quickstart (Docker)

```bash
docker build -t commitguard .
docker run -p 8000:8000 commitguard
```

## API endpoints (P0)

- `GET /health`  `{"status":"healthy"}`
- `POST /reset`  returns an `observation` (diff + available_files)
- `POST /step`  submit action; returns `{observation, reward, done, info}`
- `GET /state`  episode metadata (no ground truth)
- `GET /docs`  OpenAPI docs

## Action format (agent output contract)

Model actions are **XML-tagged free text** (robust to small-model variance). Spec lives in `.agent/architecture.md`.

## How to work on this repo (hackathon mode)

- Start here: `AGENT.md`
- Rules + contracts: `.agent/`
- Locked PRD: `prd.md` (scope freeze at midnight Saturday)
- Task lists: `tasks_niti.md`, `tasks_deepak.md`, `tasks_divyank.md`

## Links (fill before submission)

- **HF Space**: [commitguard-env](https://huggingface.co/spaces/Nitishkumar-ai/commitguard-env)
- **Trained Model**: [commitguard-llama-3b](https://huggingface.co/inmodel-labs/commitguard-llama-3b)
- **W&B run**: [Check your dashboard](https://wandb.ai/home)
- **Demo video**: `<TODO>`

## Baseline Results (Pre-training)
We established a baseline using a naive "always-vulnerable" strategy on 50 episodes:
- **Mean Reward**: ~0.95 (due to high prevalence of vulnerabilities in the filtered set)
- **Baseline Plot**: See `plots/baseline_reward_curve.png`

## Training Configuration (A10G)
- **Model**: Llama-3.2-3B-Instruct (4-bit quantized via Unsloth)
- **Method**: GRPO (Group Relative Policy Optimization)
- **Steps**: 300
- **Generations per step**: 8
- **Hardware**: A10G Small (24GB VRAM)

## Google Cloud (GCE) runbook

See `scripts/gce_vm_runbook.md`.
