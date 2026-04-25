# CommitGuard — Product Requirements Document

**Project:** CommitGuard
**Owner:** Niti (Inmodel Labs)
**Team:** Niti, Deepak, Divyank
**Submission deadline:** Sunday 5:00 PM IST
**Hackathon:** Meta OpenEnv Hackathon (PyTorch + Hugging Face + Scaler)
**Document status:** Locked. Scope freeze at midnight Saturday.

---

## 1. Executive Summary

CommitGuard is a Reinforcement Learning environment built on Meta OpenEnv that trains LLM agents to detect exploitable vulnerabilities in code commits. The submission demonstrates that AI-paced security review is feasible — that an agent trained on commit-level reasoning can match the velocity at which AI coding agents are now shipping production code.

The deliverable is a runnable HF Space hosting the env, a training notebook that produces a measurable learning curve on Llama-3.2-3B-Instruct, a demo video showing the qualitative shift from untrained to trained behavior, and a README that tells the story.

---

## 2. Problem Statement

### 2.1 The shift in software development

Until recently, code was written by humans at human velocity. Security review processes were designed around this assumption — periodic pentests every 3 to 6 months, with manual code review at PR time. The cycle worked because the codebase changed slowly enough that periodic deep review caught most issues before they reached production.

This assumption has broken. Code is now being written and shipped by AI coding agents — Claude Code, Cursor, autonomous coding agents — at 10 to 100 times human velocity. Companies push to production daily, sometimes hourly. A pentest report from six months ago describes a codebase that no longer exists.

### 2.2 The asymmetry

The same class of LLM that writes the code can be weaponized to attack it. An adversary equipped with autonomous coding tooling, given repository access or even just leaked commits, can pentest at the same velocity defenders ship. Defense runs on human time. Offense runs on AI time. **This asymmetry is unsustainable for any organization shipping AI-generated code at scale.**

### 2.3 Why this is a frontier problem

AI red-teaming today is overwhelmingly a manual, human-bottlenecked discipline. Researchers at Anthropic, OpenAI, and Meta craft attacks one at a time. There is no automated equivalent of Metasploit for AI-generated code. Closing that gap is an open research problem that frontier labs are actively investing in.

---

## 3. Goals and Non-Goals

### 3.1 Goals (in scope for this submission)

- Deliver a working OpenEnv environment that takes a code commit as input and rewards an agent for correctly identifying vulnerabilities, the CWE class, and a plausible exploit
- Train a small Llama variant (Llama-3.2-3B-Instruct) on the env using GRPO via TRL + Unsloth
- Demonstrate measurable learning — baseline vs. trained accuracy with reward curves
- Ship a complete submission package: HF Space, training notebook, README, demo video, optional HF blog post
- Frame the work in language a Meta researcher recognizes: RLVR (Reinforcement Learning from Verifiable Rewards), commit-time security, AI-paced defense

### 3.2 Non-goals (explicitly out of scope)

- Production-ready security tool — this is a research environment, not a CI plugin
- Real-time exploit execution against arbitrary code — the v1 reward uses pattern matching, not sandboxed execution
- Multi-file / repo-level reasoning — v1 operates on single-file commits up to 80 lines
- Multi-agent self-play — listed in Future Work
- Pentesting beyond static code analysis — no network attacks, social engineering, or runtime probing
- Coverage of all CWEs — v1 focuses on the top 10 CWEs in Devign

### 3.3 Non-goals from the rubric perspective

The rubric rewards ambition and storytelling more heavily than engineering polish. Therefore: not pursuing exhaustive test coverage, not optimizing for inference latency, not building a fancy frontend. The HF Space's default web UI is sufficient.

---

## 4. Target Users and Stakeholders

| Stakeholder | Role | What they care about |
|---|---|---|
| Hackathon judges (Meta partner engineers) | Primary audience | Innovation, story, training evidence, reward design |
| Meta Superintelligence Labs researchers | Aspirational audience | Frontier framing, RLVR alignment, paper-worthiness |
| HF community | Discovery audience | Reproducibility, runnable Space, clean README |
| Future contributors | Builder audience | Code clarity, extensibility hooks for v2 |

---

## 5. Solution Overview

### 5.1 The environment

CommitGuard is an OpenEnv environment where an agent investigates code commits and decides whether they introduce exploitable vulnerabilities. The agent has limited investigation budget (5 steps maximum per episode), forcing it to reason efficiently rather than brute-forcing context.

### 5.2 The agent loop

1. `reset()` — env loads a commit (a `code_before`/`code_after` pair plus metadata) from a preprocessed Devign-derived dataset, returns the diff and the list of available files in the repo
2. `step(action)` — agent emits one of three action types:
   - `request_context(file_path)` — pull surrounding code (small reward penalty, encourages efficiency)
   - `analyze(reasoning)` — write chain-of-thought, no reward effect, logged for traces
   - `verdict(is_vulnerable, vuln_type, exploit_sketch)` — terminate the episode with a judgment
3. Reward fires on verdict, computed server-side against ground truth the agent never sees

### 5.3 Reward design (RLVR philosophy)

The reward is tiered and grounded in dataset truth, not in another LLM's opinion. This is deliberate — it follows the RLVR tradition (verifiable rewards from ground truth or executable checks) and prevents the reward hacking that plagues LLM-as-judge setups.

| Signal | Reward |
|---|---|
| Correct binary verdict (vulnerable vs. safe) | +1.0 |
| Correct CWE classification (when vulnerable) | +0.5 |
| Plausible exploit sketch (CWE-keyword match) | +0.5 |
| False positive (safe flagged as vulnerable) | -1.0 |
| False negative (real vuln missed) | -0.5 |
| Per-step context request | -0.05 |
| Episode step cap | 5 steps |

The shape is hard to game — flagging everything is punished by false positives, never investigating means no exploit sketch bonus.

---

## 6. Technical Architecture

### 6.1 System diagram

```
┌─────────────────────┐     HTTP/JSON      ┌────────────────────┐
│   TRL + Unsloth     │ ◄──────────────►  │   HF Space         │
│   Llama-3.2-3B      │   reset/step      │   FastAPI server   │
│   GRPO trainer      │   /state          │   (Docker)         │
│   (HF Jobs A10G)    │                    │                    │
└─────────────────────┘                    │   ┌────────────┐   │
                                            │   │ Devign     │   │
                                            │   │ JSONL      │   │
                                            │   └────────────┘   │
                                            │   ┌────────────┐   │
                                            │   │ Reward     │   │
                                            │   │ function   │   │
                                            │   └────────────┘   │
                                            └────────────────────┘
```

### 6.2 Component breakdown

**Env server** (Python, FastAPI, Docker, OpenEnv 0.2.3+)
- `models.py` — Action, Observation, State dataclasses (extends OpenEnv base classes)
- `environment.py` — `reset()`, `step()`, `state()` methods on the `CommitGuardEnvironment` class
- `reward.py` — pure function `compute_reward(action, ground_truth, cwe_keywords) -> float`
- `parse_action.py` — XML-tag parser, robust to malformed model output
- `data/devign_filtered.jsonl` — preprocessed dataset, shipped in image
- `data/cwe_keywords.json` — top-10 CWE → exploit-pattern keyword map

**Env client** (auto-generated by OpenEnv CLI)
- `client.py` — `HTTPEnvClient` subclass, used by training notebook
- Installable via `pip install git+https://huggingface.co/spaces/<user>/commitguard`

**Training pipeline** (Python, TRL, Unsloth, PEFT, Wandb)
- `train_grpo.py` — GRPOTrainer config + main loop
- `agent_prompt.py` — system prompt template with XML-tag action format
- `evaluate.py` — runs N samples through a model, returns accuracy stats

**Storytelling artifacts**
- `README.md` — pitch + results + links
- `demo_video.mp4` — 60-90 second before/after, hosted on YouTube unlisted
- `commitguard_hf_blog.md` — optional HF Hub blog post (page 26 bonus)
- `plots/` — reward_curve.png, baseline_vs_trained.png, per_cwe.png

### 6.3 Data flow

1. Preprocess Devign once at build time → `data/devign_filtered.jsonl` (~5000 samples, balanced, filtered to <80 LOC)
2. Build Docker image with JSONL embedded
3. `openenv push` deploys to HF Space
4. Training notebook connects to HF Space URL via the OpenEnv HTTP client
5. Each training step: GRPO generates 4 completions per prompt → each runs a full episode in the env → rewards collected → policy updated via LoRA
6. Wandb logs reward curves, training loss, checkpoints saved every 50 steps
7. Final LoRA adapter saved to HF Hub for evaluation and demo

### 6.4 Cheating prevention

The agent must never see ground truth. Enforced by architecture:

- Ground truth lives only on the server, in the JSONL file the env loads from
- The Observation dataclass schema explicitly excludes `is_vulnerable`, `cwe_type`, and `target_file_with_label`
- A unit test (`test_no_leak.py`) asserts no observation contains forbidden fields
- The server returns only `reward` (a scalar) on each step, never the label that produced it

---

## 7. Stack and Dependencies

### 7.1 Locked technical decisions

| Decision | Choice | Rationale |
|---|---|---|
| Env framework | Meta OpenEnv 0.2.3+ | Mandatory per submission rules |
| Server runtime | FastAPI in Docker | OpenEnv default, lowest friction |
| Hosting | HF Space | Mandatory per submission rules, three-in-one (server + repo + registry) |
| Data source | Devign (DetectBERT subset) | Already on disk, real CWE labels, manageable size |
| Model | Llama-3.2-3B-Instruct | Meta-branded for the Meta hackathon, fits A10G with GRPO |
| Training framework | TRL with GRPO | Native OpenEnv integration via `reward_funcs` callback |
| Training optimization | Unsloth 4-bit + LoRA r=8 | 70% memory reduction, 2x speed (page 75 of opening deck) |
| Training infra | HF Jobs A10G | $0.40-1.50/hr, runs unattended, integrates with HF ecosystem |
| Dev infra | GCP VM with T4 | Stable, no Colab disconnects, leverages ₹24,000 GCP credit |
| Action serialization | XML-tag free-text | Robust to small-model output variance, easier than JSON-mode |
| Logging | Wandb | TRL native, judges can view runs |

### 7.2 Fallback decisions (pre-approved, no debate when triggered)

| If this fails | Fall back to | Trigger |
|---|---|---|
| Llama-3.2-3B OOM on A10G | Qwen2.5-1.5B-Instruct | First test step crashes |
| HF Jobs queue full | GCP A10G on-demand | Job queues for >30 min |
| 3-action env doesn't ship by midnight | 2-action env (analyze + verdict) | Niti's checkpoint red |
| Tiered reward buggy | Binary correct/incorrect reward | Deepak's checkpoint red |
| Training curve flat | Ship with qualitative comparison only | Curve still flat at 10 AM Sunday |
| Demo video can't be cleanly recorded | Side-by-side text trace in README | Recording fails twice |

---

## 8. Functional Requirements

### 8.1 Environment functional requirements

| ID | Requirement | Priority |
|---|---|---|
| F-1 | Env exposes `/health`, `/reset`, `/step`, `/state`, `/docs` endpoints | P0 |
| F-2 | `reset()` returns a random commit observation, never the same one twice in a single episode | P0 |
| F-3 | `step()` accepts XML-tagged action strings and parses them robustly | P0 |
| F-4 | `step()` returns reward, observation, and done flag | P0 |
| F-5 | Episode terminates on `verdict` action OR after 5 steps | P0 |
| F-6 | Observation never contains ground-truth labels | P0 |
| F-7 | Env handles malformed actions gracefully (returns -0.5 reward, doesn't crash) | P1 |
| F-8 | Env supports concurrent episodes (multiple training generations in parallel) | P1 |
| F-9 | Web UI on HF Space allows manual interaction for demo recording | P2 |

### 8.2 Training functional requirements

| ID | Requirement | Priority |
|---|---|---|
| T-1 | Training notebook runs end-to-end on a single A10G | P0 |
| T-2 | Reward curve, training loss, and completions logged to Wandb | P0 |
| T-3 | LoRA adapter saved every 50 steps for resumability | P0 |
| T-4 | Baseline (untrained) evaluation on 100 held-out samples completes in <10 min | P0 |
| T-5 | Trained model evaluation produces per-CWE accuracy breakdown | P1 |
| T-6 | Notebook runnable from Colab via "Open in Colab" badge in README | P1 |

### 8.3 Storytelling functional requirements

| ID | Requirement | Priority |
|---|---|---|
| S-1 | README explains problem, env, results, and motivation in <5 min read | P0 |
| S-2 | All plot PNGs committed to repo (not Wandb-only) | P0 |
| S-3 | Demo video 60-90 sec, before/after on a single SQL injection example | P0 |
| S-4 | Wandb run URL linked in README | P1 |
| S-5 | HF Hub blog post published and linked | P2 |

---

## 9. Non-Functional Requirements

| Aspect | Requirement |
|---|---|
| Performance | Single `step()` call returns in <2 seconds on HF Space free tier |
| Reliability | Env survives 100 random episodes without crash |
| Reproducibility | Training notebook produces a measurable learning curve when re-run with same seed |
| Discoverability | HF Space tagged with `openenv`, `rl`, `security`, `code` |
| Documentation | README is self-contained — judge can understand without reading source |
| Licensing | Code MIT-licensed, dataset attribution to Devign authors |

---

## 10. Success Metrics

### 10.1 Submission completeness (binary, must-pass)

- [ ] HF Space deployed and `/health` returns 200 OK
- [ ] Training notebook runs without crashes on a fresh Colab/VM
- [ ] README has all required links (HF Space, notebook, video, GitHub)
- [ ] At least one reward curve plot committed
- [ ] Demo video accessible via public URL

### 10.2 Quality metrics (graded by rubric)

| Metric | Target | Stretch |
|---|---|---|
| Innovation framing recognized by mentor | "this is an interesting angle" feedback | "this is paper-worthy" feedback |
| Baseline accuracy (untrained Llama-3.2-3B) | Establishes a floor (likely 30-45%) | — |
| Trained accuracy (after 300 GRPO steps) | Beats baseline by ≥10pp absolute | Beats baseline by ≥20pp |
| Reward curve | Bends upward visibly | Smooth monotonic increase |
| Per-CWE breakdown | At least 3 CWEs show improvement | All top-5 CWEs show improvement |
| Storytelling | Mentor at Round 3 can repeat the pitch back | Mentor offers to share with Meta team |

### 10.3 Anti-metrics (things we explicitly don't optimize for)

- Number of features
- Number of CWEs covered (more is not better — depth beats breadth here)
- Lines of code
- Model size (going larger doesn't make a stronger submission, just slower training)

---

## 11. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Training run produces flat curve | Medium | High | Pre-approved pivot to qualitative-comparison narrative; baseline already establishes a contrast |
| HF Space deployment fails at 4 AM | Low | High | Fallback to Docker image with `docker run` instructions in README |
| Llama-3.2 license approval delayed | Low | Medium | Submit license request immediately at GCP setup; Qwen-1.5B fallback ready |
| Devign data has bad CWE labels | Medium | Medium | Filter aggressively; if too noisy, drop to top-5 cleanest CWEs only |
| One teammate falls behind their phase | Medium | High | Sync points at midnight, 9 AM, 3 PM allow scope cuts; mock-env pattern means training isn't blocked |
| Niti exhausted at Mentor Round 3 | High if no sleep | High | Mandatory sleep schedule 12:30 AM–5:00 AM, non-negotiable |
| Demo video can't be cleanly recorded | Medium | Medium | Cherry-pick the best example; fall back to text trace if recording fails twice |
| HF Space rate limits during training | Low | Medium | Run training on local Docker if HF Space hits limits |

---

## 12. Timeline and Milestones

| Time (IST) | Milestone | Owner |
|---|---|---|
| Sat 9:30 PM | Phase 1 starts — env scaffolding, data prep, training scaffolding in parallel | All |
| Sat 8:00 PM | Mentor Round 2 — pitch validation | Niti |
| Sat 11:59 PM | Phase 1 checkpoint — env runs, data ready, mock training works | All |
| Sun 12:00 AM | **Scope freeze** — no new features after this point | All |
| Sun 12:30 AM | Niti sleep starts | Niti |
| Sun 3:00 AM | HF Space live, Deepak sleep starts | Deepak |
| Sun 5:30 AM | Real training run launched on HF Jobs, Divyank sleep starts | Divyank |
| Sun 5:00 AM | Niti wakes, watches training | Niti |
| Sun 9:00 AM | Team sync — training results, plot status | All |
| Sun 10:00 AM | Mentor Round 3 — final sharpening | Niti |
| Sun 11:30 AM | Demo video recorded and uploaded | Divyank |
| Sun 1:00 PM | README finalized | Niti |
| Sun 3:00 PM | **Feature freeze** — 2-hour reminder, no more changes | All |
| Sun 4:30 PM | Submission packaged | Niti |
| Sun 5:00 PM | **Submission deadline** | — |

---

## 13. Open Questions and Assumptions

### 13.1 Assumptions

- Devign dataset is on disk locally (or downloadable in <30 min) — to be verified by Deepak at Phase 1 start
- HF Space free tier is sufficient for env hosting during the hackathon — backup plan: $9/mo upgrade if rate limited
- Llama-3.2-3B-Instruct license approval lands within 1 hour of request — Qwen fallback ready if not
- HF Jobs A10G availability at 5 AM Sunday — GCP A10G fallback if queued

### 13.2 Open questions (to resolve during execution)

- Exact number of training steps to maximize curve visibility within budget — answered empirically by 9 AM Sunday based on observed loss
- Whether to ship a Colab-runnable notebook AND an HF Jobs notebook, or just one — defer to Divyank's call at Phase 2
- Whether to include a comparison against a non-RL baseline (pure SFT or zero-shot) — stretch only

---

## 14. Future Work (Post-Hackathon)

This section becomes part of the README's "What's Next" pitch — explicitly signals to judges that we understand the limitations and have a roadmap.

- **Sandboxed exploit execution** — replace pattern-match reward with actual exploit runs against compiled code in a Docker sandbox
- **Multi-file commit reasoning** — extend the env to support diffs spanning multiple files, with a context budget
- **Self-play loop** — pair CommitGuard with a code-generation agent; defender and attacker train against each other (the AlphaGo pattern for security)
- **Agentic harness integration** — wire into real CI pipelines via the OpenEnv MCP layer, enabling commit-time security review at PR open
- **Real CVE corpus** — extend beyond Devign to recent CVE-tagged commits from major open-source repos
- **Multi-language support** — current env is C-focused via Devign; extend to Python, JavaScript, Go
- **Reward shape ablations** — formal study of how reward composition affects which vulnerability types the model learns fastest

---

## 15. Appendix

### 15.1 Key reference URLs (for the team to bookmark)

- OpenEnv repo: https://github.com/meta-pytorch/OpenEnv
- OpenEnv Scaler intro: https://tinyurl.com/openenv-scaler
- TRL OpenEnv docs: https://huggingface.co/docs/trl/en/openenv
- TRL Sudoku GRPO example: https://github.com/huggingface/trl/blob/main/examples/notebooks/openenv_sudoku_grpo.ipynb
- TRL Wordle GRPO example: https://github.com/huggingface/trl/blob/main/examples/notebooks/openenv_wordle_grpo.ipynb
- Unsloth 2048 example: https://github.com/meta-pytorch/OpenEnv/blob/main/tutorial/examples/unsloth_2048.ipynb
- Llama-3.2-3B model card: https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct
- HF Jobs docs: https://huggingface.co/docs/hub/jobs
- Cursor credits: https://tinyurl.com/sclr-openenv-dashboard
- HF $30 credits: https://huggingface.co/coupons/claim/hf-openenv-community

### 15.2 Document version

- v1.0 — Saturday evening, Bangalore venue. Locked at midnight Saturday.
- Changes after lock require explicit team-wide sign-off and a documented rationale.

---

## 16. The 30-Second Pitch (For Mentor Rounds, Memorize This)

> "AI is now writing production code at AI speed. Security review still runs on a 6-month human cycle. The same LLMs that write the code can attack it — defense is on human time, offense is on AI time, and that asymmetry breaks the security model.
>
> CommitGuard is an OpenEnv where an agent learns to flag exploitable diffs at commit time. We trained Llama-3.2-3B on it via GRPO and the detection rate climbs measurably. It's RLVR — verifiable rewards from ground truth, not LLM judges. The thesis: continuous AI red-teaming at the velocity code is being shipped. This is the environment to train it."