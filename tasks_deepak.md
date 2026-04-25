# Tasks — Deepak (Data + Reward + Evaluation)

**Project:** CommitGuard — OpenEnv Hackathon Submission
**Submission deadline:** Sunday 5:00 PM IST
**Your role:** Own the data pipeline, the reward function, and the evaluation that produces the plots judges will see.

---

## Why you own these

The reward function is the soul of the env — it determines whether the agent learns anything at all. The data pipeline determines whether the env can scale. The evaluation produces the plots that drive 20% of the rubric score directly. Three things, all surgical, all yours.

You can start immediately — your work doesn't depend on Niti's env code being ready.

---

## Phase 1 — Foundation (9:30 PM Saturday → 12:30 AM Sunday)

### Task 1.1 — Devign data preprocessing (1.5 hours)

**Goal:** A single JSONL file with clean, balanced, filtered samples ready for the env.

- [x] Verify Devign dataset is on disk locally. If not, download from HuggingFace: `DetectBERT/devign` or the original Devign release
- [x] Write `preprocess_devign.py`:
  - Load all samples
  - Filter: drop samples where `len(code.split('\n')) > 80` (keeps context windows manageable for Qwen-0.5B / Llama-3.2-3B)
  - Filter: drop samples without a clear CWE label
  - Balance: roughly 50/50 split between vulnerable and safe
  - Output schema per row:
    ```json
    {
      "commit_id": "synthetic_0001",
      "code_before": "...",
      "code_after": "...",
      "is_vulnerable": true,
      "cwe_type": "CWE-89",
      "target_file": "auth.c",
      "available_files": ["auth.c", "db.c", "utils.c"]
    }
    ```
  - Note: Devign doesn't have real "before/after" diffs — synthesize by treating each function as `code_after` and using a slightly mutated version (or just an empty string + `code_after`) as `code_before`. Don't overthink this; the diff representation is what matters.
- [x] Save to `data/devign_filtered.jsonl`
- [x] Aim for ~5000 samples post-filter. If you have fewer, that's fine — quality over quantity.
- [x] Smoke test: `wc -l data/devign_filtered.jsonl` and spot-check 5 random samples manually for sanity

### Task 1.2 — CWE keyword dictionary (30 min)

**Goal:** Map each top-10 CWE to a list of exploit-pattern keywords for reward computation.

- [x] Identify the top 10 CWEs by frequency in your filtered dataset
- [x] For each CWE, list 5-10 keywords/phrases that would appear in a plausible exploit description
- [x] Save to `cwe_keywords.json`:
  ```json
  {
    "CWE-89": ["sql injection", "drop table", "union select", "or 1=1", "concat", "unsanitized input"],
    "CWE-79": ["xss", "script tag", "innerhtml", "eval", "javascript:", "onerror"],
    "CWE-78": ["command injection", "os.system", "subprocess", "shell=true", "exec", "popen"],
    ...
  }
  ```
- [x] Source from MITRE CWE pages (mitre.org/data/definitions/89.html etc.) — copy the exploit examples, extract phrases

### Task 1.3 — Reward function (1 hour)

**Goal:** Pure function that takes an action + ground truth and returns a scalar reward. Tested.

- [x] Write `reward.py`:
  ```python
  def compute_reward(action: dict, ground_truth: dict, cwe_keywords: dict, step_count: int) -> float:
      reward = 0.0

      # Per-step efficiency penalty
      if action["action_type"] == "request_context":
          return -0.05

      # Analyze action — no reward, just logged
      if action["action_type"] == "analyze":
          return 0.0

      # Verdict action — main reward signal
      if action["action_type"] == "verdict":
          # Correctness of binary classification
          if action["is_vulnerable"] == ground_truth["is_vulnerable"]:
              reward += 1.0
              # Bonus: correct CWE classification
              if ground_truth["is_vulnerable"] and action["vuln_type"] == ground_truth["cwe_type"]:
                  reward += 0.5
              # Bonus: plausible exploit sketch
              if ground_truth["is_vulnerable"] and action["exploit_sketch"]:
                  patterns = cwe_keywords.get(ground_truth["cwe_type"], [])
                  sketch_lower = action["exploit_sketch"].lower()
                  if any(p in sketch_lower for p in patterns):
                      reward += 0.5
          else:
              # Wrong classification
              if action["is_vulnerable"] and not ground_truth["is_vulnerable"]:
                  reward -= 1.0  # False positive
              else:
                  reward -= 0.5  # False negative

      return reward
  ```
- [x] Write 5 hand-crafted unit tests in `test_reward.py`:
  - Correct vulnerable verdict → reward = 1.0
  - Correct vulnerable + correct CWE + good sketch → reward = 2.0
  - False positive (flagged safe as vulnerable) → reward = -1.0
  - False negative (missed real vuln) → reward = -0.5
  - Context request → reward = -0.05
- [x] All tests pass

### Task 1.4 — No-leak unit test (30 min)

**Goal:** A test that fails loudly if Niti accidentally leaks ground truth into the observation.

- [x] Write `test_no_leak.py`:
  ```python
  def test_observation_does_not_leak_ground_truth():
      env = CommitGuardEnvironment()
      obs = env.reset()
      obs_dict = asdict(obs)
      forbidden_keys = ["is_vulnerable", "cwe_type", "ground_truth", "label"]
      for key in forbidden_keys:
          assert key not in str(obs_dict).lower(), f"Leak detected: {key}"
      # Also check after a step
      obs = env.step(CommitGuardAction(action_type="analyze", reasoning="test"))
      for key in forbidden_keys:
          assert key not in str(asdict(obs)).lower()
  ```
- [x] Run against Niti's env once it's ready. Test must pass.

**Hard checkpoint at midnight:** JSONL exists, reward function passes 5 unit tests, no-leak test passes against Niti's env.

**If RED at midnight:** ship with binary correct/incorrect reward only. Drop CWE bonus and exploit-sketch bonus. Tier the reward later if time allows.

---

## Phase 2 — Integration & Sleep (12:30 AM → 7:00 AM Sunday)

### Task 2.1 — Wire data + reward into Niti's env (12:30 AM → 3:00 AM, 2.5 hours)

- [ ] Sync with Niti — pull his latest `environment.py` 
- [ ] Wire `reset()` to actually load from your JSONL: random sample, return diff + available_files
- [ ] Wire `step()` to call your `compute_reward()` with the loaded ground truth (server-side, never returned to client)
- [ ] Run 100 random episodes locally with a dummy random-action client:
  - No crashes
  - Reward distribution looks reasonable (not all zeros, not all -1.0)
  - Episode lengths bounded by step cap
- [ ] Run `test_no_leak.py` — must pass
- [ ] Push env to HF Space: `cd commitguard && openenv push`
- [ ] Verify deployment: `curl https://<your-username>-commitguard.hf.space/health`
- [ ] Hand off to Divyank in team channel: "HF Space live at [URL], ready for training integration"

### Task 2.2 — Sleep (3:00 AM → 7:00 AM, 4 hours)

- [ ] Sleep. Alarm at 7:00 AM. Phone away.
- [ ] You wake up, you do evaluation. Need clear head for plotting.

---

## Phase 3 — Evaluation & Plots (7:00 AM → 10:00 AM Sunday)

### Task 3.1 — Held-out test set (7:00 AM → 7:30 AM)

- [ ] Carve out 100 samples from the JSONL that were NOT used in training
- [ ] Save as `data/devign_test.jsonl`
- [ ] These 100 samples will be your evaluation set for both baseline and trained model

### Task 3.2 — Baseline measurement (7:30 AM → 8:30 AM, 1 hour)

- [ ] Coordinate with Divyank — get the baseline (untrained) Llama-3.2-3B model loaded
- [ ] Run all 100 test samples through baseline:
  - For each sample, prompt the model with the diff, parse its verdict from XML tags
  - Compute: vulnerability detection accuracy, per-CWE accuracy
- [ ] Save raw results to `eval_baseline.json`

### Task 3.3 — Trained model measurement (8:30 AM → 9:30 AM, 1 hour)

- [ ] Once Divyank's training run completes (should be done by ~5:30 AM, results in Wandb)
- [ ] Load LoRA-adapted Llama-3.2-3B
- [ ] Run same 100 test samples through trained model
- [ ] Compute same metrics
- [ ] Save raw results to `eval_trained.json`

### Task 3.4 — Generate plots (9:30 AM → 10:00 AM, 30 min)

Use Niti's plot scripts in `plots/` (he writes them in his early shift). You feed them data, they produce PNGs.

- [ ] Reward curve plot — from Wandb training logs, save as `plots/reward_curve.png`
  - X-axis: training step
  - Y-axis: mean reward
  - Title: "CommitGuard — GRPO Training Reward Curve"
- [ ] Baseline vs Trained accuracy bar chart, save as `plots/baseline_vs_trained.png`
  - Two bars: baseline accuracy, trained accuracy
  - Both numbers labeled on the bars
- [ ] Per-CWE breakdown, save as `plots/per_cwe.png`
  - Grouped bar: each CWE has baseline + trained bar
  - Shows which vuln types the model learned fastest
- [ ] All plots: axes labeled with units, title, readable from 5 feet away (page 28 reminder)
- [ ] Commit all PNGs to repo

---

## Phase 4 — Submission support (10:00 AM → 5:00 PM Sunday)

### Task 4.1 — Numbers handoff to Niti (10:00 AM → 10:30 AM)

- [ ] Send Niti the headline numbers in plain text:
  - "Baseline accuracy: X%"
  - "Trained accuracy: Y%"
  - "Best CWE improvement: CWE-XX, +Z%"
  - "Total training steps: N"
- [ ] He drops these into the README

### Task 4.2 — Stretch: ablation (10:30 AM → 1:00 PM, optional, only if Tier 1 done)

- [ ] If time allows, run a second eval comparing trained model on samples it saw during training vs held-out samples
- [ ] This shows generalization, strengthens results section
- [ ] Skip if Niti or Divyank need help instead

### Task 4.3 — Lunch + buffer (1:00 PM → 5:00 PM)

- [ ] Eat
- [ ] Be available for last-minute eval re-runs if something breaks
- [ ] Help with smoke testing the HF Space from a different network

---

## Sync points

- **12:00 AM Midnight** — Team sync. Report: data ✅/⚠️/❌, reward ✅/⚠️/❌, leak test ✅/⚠️/❌
- **9:00 AM Sunday** — Team sync. Report: baseline numbers, trained numbers, plot status
- **3:00 PM Sunday** — Final sync. Stop adding features.

---

## Fallback rules

- **Devign is too messy / inconsistent:** drop to a smaller, cleaner subset. 1000 high-quality samples beat 5000 noisy ones.
- **CWE keyword matching is too brittle:** drop the exploit-sketch bonus. Reward becomes 1.0 (correct) / 0.5 (correct + CWE) / penalties unchanged. Simpler, still tiered.
- **Training run produces no learning curve:** that's not your problem to fix — Divyank owns it. You produce evaluation honestly. If trained ≈ baseline, that's the truth, ship it. The pitch can pivot to "we built the env, training is future work" — page 26 says "evidence that you trained" not "evidence that training worked perfectly."
- **You can't get the trained model to load:** ask Divyank for raw outputs from the training run, evaluate from those instead.