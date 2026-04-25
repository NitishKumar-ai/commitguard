## CommitGuard: project context (load this first)

This file is the **single source of truth for agents**. It compresses `../prd.md` into must-know facts so you can make correct decisions at 3 AM.

If you’re unsure: re-read `../prd.md` and then update this file to match.

## What we’re building

**CommitGuard** is a **Meta OpenEnv** reinforcement learning environment where an LLM agent learns to detect exploitable vulnerabilities in **code commits** (single-file diffs) and output a vulnerability verdict + CWE type + exploit sketch.

The environment runs as an **HTTP server (FastAPI in Docker)**, hosted on **Hugging Face Spaces**. Training runs with **TRL GRPO + Unsloth** on **Llama‑3.2‑3B‑Instruct**, using verifiable rewards from dataset ground truth (RLVR).

## Why this matters (the thesis)

AI writes code at AI speed. Security review still runs on human cycles. Offense can now scale with the same LLM tooling. **We’re building the RL environment that trains AI-paced commit-time security review.**

## Who it’s for

- **Hackathon judges / Meta partner engineers**: want innovation + evidence (learning curve) + clean story.
- **Meta researchers**: want RLVR framing, cheating-prevention, and extensibility.
- **HF community**: wants a runnable Space + reproducible training notebook.

## 30-second pitch (verbatim; memorize)

> "AI is now writing production code at AI speed. Security review still runs on a 6-month human cycle. The same LLMs that write the code can attack it — defense is on human time, offense is on AI time, and that asymmetry breaks the security model.
>
> CommitGuard is an OpenEnv where an agent learns to flag exploitable diffs at commit time. We trained Llama-3.2-3B on it via GRPO and the detection rate climbs measurably. It's RLVR — verifiable rewards from ground truth, not LLM judges. The thesis: continuous AI red-teaming at the velocity code is being shipped. This is the environment to train it."

## Locked stack (do not change)

- **Env framework**: Meta OpenEnv **0.2.3+**
- **Server**: **FastAPI** in **Docker**
- **Hosting**: **Hugging Face Space**
- **Data**: **Devign** (Devign/DetectBERT subset); filtered to single-file commits <80 LOC; ~balanced
- **Model**: **Llama‑3.2‑3B‑Instruct**
- **Training**: **TRL** with **GRPO**
- **Optimization**: **Unsloth** 4‑bit + **LoRA r=8**
- **Infra**: **HF Jobs A10G** for training; **GCP VM with T4** for dev/stability
- **Action serialization**: **XML-tag free-text** (not JSON-mode)
- **Logging**: **Weights & Biases**

Operational preference: **use CLI** for HF + GCP actions (repeatable, copy/paste-able, no UI-clicking).

## Submission deliverables (P0)

- **HF Space** deployed; `/health` returns 200; `/docs` works
- **Training notebook / script** produces a measurable learning curve (or triggers fallback)
- **Plots** committed (reward curve + baseline vs trained)
- **Demo video** (60–90s) showing before/after behavior on one example
- **README** with all required links (Space, notebook, video, repo, wandb)

## Hard constraints (time + scope)

- **Deadline**: Sunday **5:00 PM IST** (non-negotiable)
- **Scope freeze**: **midnight Saturday (00:00 IST)** — after this, no new features
- **Episode constraints**: max **5 steps** per episode; context requests cost reward

## Explicit non-goals (do not drift)

- Not a production CI security tool; **research environment only**
- No real exploit execution sandbox in v1 (pattern match only)
- No multi-file / repo-level reasoning in v1 (single-file commits, <=80 LOC)
- No multi-agent self-play in v1
- No network/runtime attacks, no social engineering
- No “cover all CWEs”: v1 focuses on **top 10 CWEs** in Devign
- No fancy frontend: HF Space default UI is enough

## If something breaks: pre-approved fallbacks (no debate)

These are legal pivots from `../prd.md` §7.2. If trigger happens, switch immediately and log it in `decision_log.md`.

- **OOM on Llama‑3.2‑3B on A10G** → use **Qwen2.5‑1.5B‑Instruct** (trigger: first test step crashes)
- **HF Jobs queue > 30 min** → use **GCP A10G on-demand**
- **3-action env not shipped by midnight** → ship **2-action env** (analyze + verdict)
- **Tiered reward buggy** → ship **binary reward only**
- **Training curve still flat at 10 AM Sunday** → ship **qualitative comparison narrative**
- **Demo video recording fails twice** → ship **side-by-side text trace in README**

## Next file to read

Read `architecture.md` next. Then read your per-person task list (e.g. `../tasks_niti.md`) if present.

