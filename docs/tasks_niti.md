## Tasks  Niti (Lead / Env / Pitch)

**Project:** CommitGuard  OpenEnv Hackathon Submission  
**Submission deadline:** Sunday 5:00 PM IST  
**Your role:** Lead. Own the env code, the HF Space deployment, the pitch, and the final submission.

---

## Why you own these

You have the most context on the existing Code Security Review env, you're the most senior engineer on the team, and you're the face of the project. The env code and the pitch are the two highest-leverage artifacts in the submission  both are yours.

---

## Phase 1  Foundation (9:30 PM Saturday  12:30 AM Sunday)

### Task 1.1  Env scaffolding (3 hours)

**Goal:** CommitGuard env runs locally and responds correctly to all 3 actions with a stub reward.

- [x] Copy existing Code Security Review env folder, rename to `commitguard`
- [x] Update `pyproject.toml`  change project name, description, package name
- [x] Update `openenv.yaml`  new env name, port stays 8000
- [x] Update `Dockerfile` if any path references need fixing
- [x] Rewrite `models.py`:
  - `CommitGuardAction`  fields: `action_type: str` (one of `request_context`, `analyze`, `verdict`), `file_path: Optional[str]`, `reasoning: Optional[str]`, `is_vulnerable: Optional[bool]`, `vuln_type: Optional[str]`, `exploit_sketch: Optional[str]`
  - `CommitGuardObservation`  fields: `diff: str`, `available_files: List[str]`, `step_count: int`, `reward: float`, `done: bool`. **DO NOT** include `is_vulnerable` or `cwe_type` here  that's the leak.
  - `CommitGuardState`  fields: `episode_id: str`, `current_sample_id: str`, `step_count: int`, `history: List[dict]`
- [x] Rewrite `environment.py`:
  - `reset()`  load random sample from `data/devign_filtered.jsonl` (Deepak's output), return observation
  - `step(action)`  parse action_type, dispatch to correct handler, call `compute_reward()` (stub returns 0.0 for now), increment step_count, terminate after 5 steps or on verdict
  - `state()`  return current state metadata
- [x] Verify locally:
  - `uv run server` starts cleanly
  - `curl http://localhost:8000/health` returns `{"status": "healthy"}`
  - `curl -X POST http://localhost:8000/reset` returns observation with diff
  - `curl -X POST http://localhost:8000/step -d '{...}'` works for each of the 3 action types

**Hard checkpoint at midnight:** env responds correctly to all 3 action types.

**If RED at midnight:** drop `request_context` action, env becomes 2-action (analyze + verdict only). Do not negotiate this  cut and move on.

### Task 1.2  Mentor Round 2 (8:00 PM, 15 minutes max)

- [ ] Walk to Mentor Round 2 with the pitch markdown
- [ ] Find Sanyam Bhutani, Yash Khare, or Nilesh Pandey (Meta partner engineers)
- [ ] Deliver the 30-second pitch verbatim from the pitch doc
- [ ] Ask exactly one question: *"What's the weakest part of this framing?"*
- [ ] Capture feedback in a note. Don't argue, don't expand scope, just listen.
- [ ] **15 minutes max.** Walk back. Code.

---

## Phase 2  Sleep (12:30 AM  5:00 AM Sunday)

**This is a task. It is not optional.**

- [x] Phone in another room
- [x] Alarm set for 5:00 AM
- [x] Sleep 4.5 hours minimum
- [x] Do not respond to team messages during this window unless the building is on fire

You are the pitcher. Your fatigue degrades the 30% storytelling score more than any other team member's. This is a CTO mandate. If you skip this, you lose more than you gain.

---

## Phase 3  Early shift & polish (5:00 AM  11:30 AM Sunday)

### Task 3.1  Training watch & morning prep (5:00 AM  7:00 AM, 2 hours, sole-on-deck)

- [x] Check on training run started by Divyank  is it alive? Take screenshots of Wandb dashboard.
- [x] If training crashed: pull logs, post in team channel, decide fallback (smaller model? salvage partial run?). Don't block waiting for others to wake up  make the call.
- [x] If training healthy: start drafting README skeleton from `commitguard_pitch.md`
- [x] Write the matplotlib plot scripts so they're ready to ingest training logs the moment they finish:
  - `plot_reward_curve.py`  training step on x, reward on y, both axes labeled
  - `plot_baseline_vs_trained.py`  bar chart, accuracy comparison
  - `plot_per_cwe.py`  heatmap or grouped bar, CWE on x, accuracy on y
- [x] Save all scripts to `plots/` directory

### Task 3.2  Breakfast (7:00 AM  8:00 AM)

- [x] Eat. Hydrate. You will think clearer with food.

### Task 3.3  README finalization (8:00 AM  10:00 AM, 2 hours)

- [ ] Open `commitguard_pitch.md` as base
- [ ] Fill in actual numbers from Deepak's evaluation (baseline accuracy, trained accuracy, training steps)
- [ ] Embed PNG plots inline in README (not links  actual images)
- [ ] Write captions under each plot  one line, what does it show
- [ ] Verify all links work: HF Space URL, training notebook URL, demo video URL, GitHub URL
- [ ] Run a 3-minute self-read  can a stranger understand the project?

### Task 3.4  Mentor Round 3 (10:00 AM  10:20 AM, ~20 minutes)

- [ ] Walk in with: live env demo on laptop, training curve plot, baseline vs trained numbers
- [ ] Ask: *"What's the one thing about our submission that's underselling itself?"*
- [ ] Take feedback into README polish only. **No new features after Mentor Round 3.**

---

## Phase 4  Submission (11:30 AM  5:00 PM Sunday)

### Task 4.1  Smoke test (12:00 PM  1:00 PM, 1 hour)

- [x] From a fresh machine (use phone hotspot, simulate judge experience):
  - HF Space URL loads
  - Env's `/health` endpoint responds
  - Training notebook in Colab opens and first cell runs
  - Demo video plays
- [ ] Fix anything broken. Don't add features.

### Task 4.2  Lunch (1:00 PM  2:00 PM)

- [ ] Eat. The afternoon is high-stakes packaging  don't do it hungry.

### Task 4.3  Stretch goals if Tier 1 done (2:00 PM  3:00 PM, 1 hour)

- [ ] Bonus screen recording of the env's web UI being interacted with  this hits the page-26 submission requirement softly
- [ ] Coordinate with Divyank on HF blog post if they're drafting one

### Task 4.4  Final submission packaging (3:30 PM  4:30 PM, 1 hour)

- [ ] Final README check  every link clicks, every plot renders
- [ ] HF Space URL is in the README at the top
- [ ] Training notebook URL works
- [ ] Demo video URL works
- [ ] GitHub repo is public and clean
- [ ] Submit per Scaler dashboard instructions
- [ ] **Stop touching anything after 4:30 PM.**

### Task 4.5  Buffer (4:30 PM  5:00 PM)

- [ ] Hands off keyboard. Watch the clock. Final 30 min is for disasters only.

---

## Sync points (non-negotiable, your job to lead)

- [x] **8:00 PM**  Mentor Round 2 (you go alone, 15 min)
- [x] **12:00 AM Midnight**  Team sync, 15 min. Each person reports green/yellow/red. Cut scope if anyone is red.
- [x] **9:00 AM Sunday**  Team sync, 15 min. Confirm training run health, plot status, README progress.
- [ ] **3:00 PM Sunday**  Final sync. 2-hour reminder hits at 3 PM. Stop adding features.

---

## CTO commitments you signed

1. [x] Sleep 12:30 AM  5:00 AM. Non-negotiable.
2. [x] Scope locked at midnight. No new reward components, actions, or data sources after 12 AM.
3. [x] Status check to mentor (Claude) at midnight and 9 AM. Format: green/yellow/red on each role. No essays.

---

## Fallback rules (if things break)

- **Env doesn't run by midnight:** drop to 2-action env (analyze + verdict). Cut `request_context`.
- **HF Space deployment fails:** ship as Docker image with instructions, judges can pull and run locally.
- **Training crashes overnight:** wake up, diagnose, drop to Qwen2.5-1.5B if Llama OOMs. Don't reinvent  fall back fast.
- **Demo video can't be recorded:** ship a side-by-side text comparison in the README with full reasoning traces. Less visceral but still tells the story.
- **Mentor Round 3 surfaces a major flaw:** patch the README narrative around it, don't try to fix the underlying issue. You're 6 hours from submission.
