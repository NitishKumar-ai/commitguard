# Tasks — Divyank (Training + Storytelling)

**Project:** CommitGuard — OpenEnv Hackathon Submission
**Submission deadline:** Sunday 5:00 PM IST
**Your role:** Own the training pipeline (TRL + Unsloth + Llama-3.2-3B + GRPO) and the storytelling assets (demo video, HF blog post). You produce both the technical proof and the emotional hook.

---

## Why you own these

Training and storytelling sit at opposite ends of the rubric — 20% (training proof) and 30% (storytelling). Together that's half your grade. They share one trait: both require deep focus blocks with no interruptions. You take both because they parallelize cleanly with Niti and Deepak's work, and because the demo video should be made by someone who watched the training curves bend with their own eyes.

You can start immediately on training infra — your work doesn't depend on the env being ready. Use a mock env first.

---

## Phase 1 — Foundation (9:30 PM Saturday → 12:30 AM Sunday)

### Task 1.1 — GCP VM provisioning (30 min)

**Goal:** A stable dev box for training development that won't disconnect like Colab.

- [ ] Spin up GCP VM:
  - Region: `us-central1-b` (Niti has used this before, low latency)
  - Machine: `n1-standard-4` (4 vCPU, 15GB RAM)
  - GPU: 1x NVIDIA T4 (for dev work, ~$0.35/hr on-demand)
  - OS: Ubuntu 22.04
  - Disk: 100GB SSD
- [ ] SSH in, install dependencies:
  ```bash
  sudo apt update && sudo apt install -y python3.11 python3.11-venv git
  curl -LsSf https://astral.sh/uv/install.sh | sh
  uv venv --python 3.11
  source .venv/bin/activate
  uv pip install torch transformers trl unsloth accelerate peft datasets wandb huggingface_hub
  ```
- [ ] `huggingface-cli login` — paste your HF token
- [ ] Accept Llama-3.2 license at https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct (do this NOW, license approval can take time)
- [ ] `wandb login` — for training run logging

### Task 1.2 — Training notebook with mock env (2 hours)

**Goal:** TRL + GRPO + Llama-3.2-3B running 5 training steps cleanly on a mock env that returns random rewards.

- [ ] Clone the TRL Sudoku notebook from https://github.com/huggingface/trl/blob/main/examples/notebooks/openenv_sudoku_grpo.ipynb as your starting template
- [ ] Replace Sudoku env imports with a mock CommitGuard client:
  ```python
  class MockCommitGuardEnv:
      def reset(self):
          return MockObservation(diff="dummy diff", available_files=[], step_count=0, reward=0.0, done=False)
      
      def step(self, action_str):
          import random
          # Parse XML-tagged action from string
          # Return random reward between -1.0 and 2.0
          return MockObservation(..., reward=random.uniform(-1.0, 2.0), done=True)
  ```
- [ ] Configure GRPO:
  ```python
  config = GRPOConfig(
      output_dir="./commitguard-llama-3b",
      num_generations=4,
      max_completion_length=512,
      per_device_train_batch_size=1,
      gradient_accumulation_steps=4,
      learning_rate=5e-6,
      logging_steps=1,
      save_steps=50,
      report_to="wandb",
  )
  ```
- [ ] Configure Unsloth + LoRA:
  ```python
  model, tokenizer = FastLanguageModel.from_pretrained(
      model_name="meta-llama/Llama-3.2-3B-Instruct",
      max_seq_length=2048,
      load_in_4bit=True,
  )
  model = FastLanguageModel.get_peft_model(
      model, r=8, lora_alpha=16,
      target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
  )
  ```
- [ ] Run 5 training steps. Verify:
  - No OOM
  - Gradient flows (loss is non-zero, changes step to step)
  - Reward gets logged to Wandb
  - LoRA weights save correctly

**Hard checkpoint at midnight:** training step runs cleanly on mock env, ready to swap in real client.

**If RED at midnight:** drop to Qwen2.5-1.5B-Instruct. Keep everything else identical. Don't debate, switch.

### Task 1.3 — Prompt template for the agent (30 min)

**Goal:** A clear prompt template that tells Llama how to respond with XML-tagged actions.

- [ ] Write `agent_prompt.py`:
  ```python
  SYSTEM_PROMPT = """You are a security analyst reviewing code commits for vulnerabilities.

  You see a code diff and must determine if it introduces an exploitable vulnerability.

  Respond with one of three action types, wrapped in XML tags:

  <action_type>request_context</action_type>
  <file_path>filename.c</file_path>
  
  OR
  
  <action_type>analyze</action_type>
  <reasoning>your reasoning here</reasoning>
  
  OR
  
  <action_type>verdict</action_type>
  <is_vulnerable>true</is_vulnerable>
  <vuln_type>CWE-89</vuln_type>
  <exploit_sketch>brief description of how to exploit this</exploit_sketch>
  
  You have at most 5 steps per commit. Be efficient.
  """
  ```
- [ ] Write `parse_action.py` — robust XML-tag parser. Returns dict with action_type and relevant fields. Handle malformed responses gracefully (return invalid action, server gives -0.5 reward).

---

## Phase 2 — Integration & Sleep (12:30 AM → 9:30 AM Sunday)

### Task 2.1 — Wait for HF Space (12:30 AM → 3:00 AM)

Deepak is wiring the data + reward into Niti's env and pushing to HF Space during this window. While you wait:

- [ ] Continue mock-env training: run 50 steps, verify checkpointing works, verify Wandb logs everything
- [ ] Write the evaluation script `evaluate.py` that runs N samples through a model and returns accuracy stats. Will be reused for baseline and trained eval. Hand to Deepak.

### Task 2.2 — Swap to real env + launch real training (3:00 AM → 5:30 AM, 2.5 hours)

- [ ] Pull the live HF Space URL from Deepak: `https://<deepak-or-niti-username>-commitguard.hf.space`
- [ ] Replace `MockCommitGuardEnv` with real OpenEnv HTTP client pointing to the HF Space URL
- [ ] Run 10 training steps against real env. Verify:
  - Real rewards arrive (not all zeros)
  - Reward distribution looks reasonable
  - Episode lengths are bounded
- [ ] **Baseline measurement:** before training, run untrained Llama-3.2-3B on 100 held-out samples (Deepak's `data/devign_test.jsonl`). Save `eval_baseline.json`.
- [ ] **Launch real training run on HF Jobs:**
  ```bash
  hf jobs uv run --flavor a10g-large \
    --model_name_or_path meta-llama/Llama-3.2-3B-Instruct \
    train_grpo.py
  ```
  - 300 steps target
  - Wandb logging enabled
  - Save checkpoint every 50 steps
  - Total budget: ~$5 for one 2-hour run
- [ ] Verify the job started, dashboard URL captured, then go to sleep

### Task 2.3 — Sleep (5:30 AM → 9:30 AM, 4 hours)

- [ ] Training runs unattended on HF Jobs while you sleep
- [ ] Phone alarm 9:30 AM
- [ ] Niti is on watch from 5 AM, will wake you if training crashes

---

## Phase 3 — Demo + Storytelling (9:30 AM → 1:30 PM Sunday)

### Task 3.1 — Pull trained model & verify (9:30 AM → 10:00 AM)

- [ ] Wake up, check Wandb dashboard — did training complete? Did the curve bend?
- [ ] Download LoRA adapter weights from HF Jobs output
- [ ] Hand off model location to Deepak so he can run trained-model evaluation

### Task 3.2 — Demo video recording (10:00 AM → 11:30 AM, 1.5 hours)

**The single most important storytelling artifact in your submission. Don't rush, don't over-polish.**

- [ ] Pick ONE great example commit from Devign — preferably a SQL injection (CWE-89), the visceral one
- [ ] Set up screen recording: OBS or QuickTime, full screen, 1080p, no music
- [ ] Recording structure (90 seconds total):
  - **Seconds 0-10:** Title card + one-line problem statement ("AI now writes code at AI speed. Security review can't keep up.")
  - **Seconds 10-35:** Show the diff. Show the untrained model's response — random verdict, no reasoning, fails. Caption: "Untrained Llama-3.2-3B"
  - **Seconds 35-70:** Same diff. Trained model: requests context, identifies CWE-89, sketches exploit (`' OR 1=1--`), correct verdict. Caption: "Trained on CommitGuard, 300 GRPO steps"
  - **Seconds 70-90:** Reward curve plot, single line: "Detection accuracy: 23% → 67%" (whatever the actual numbers are). End card with HF Space URL.
- [ ] Record. Re-record if any verbal slip. Get it right.
- [ ] Edit only if necessary — trim, no transitions, no music, no zoom effects. The contrast IS the production value.
- [ ] Export as MP4, 1080p
- [ ] Upload to YouTube as **Unlisted** (not Private — judges need the link to work without auth)
- [ ] Send link to Niti for README

### Task 3.3 — HF Hub blog post (11:30 AM → 1:00 PM, 1.5 hours)

Page 26 of the deck explicitly mentions "a mini-blog on Hugging Face" as a submission requirement option. Do it. Costs 90 minutes, hits a rubric checkbox.

- [ ] Go to https://huggingface.co/blog
- [ ] Title: *"CommitGuard: Training LLMs to Pentest Code at AI Speed"*
- [ ] Structure (use Niti's pitch markdown as base, expand):
  - The Problem (the asymmetry between AI-coding velocity and human security review)
  - The Insight (commit-time security is the right unit of analysis)
  - The Environment (3-action design, tiered rewards, RLVR philosophy)
  - The Results (your plots, embedded)
  - What's Next (sandbox exploit execution, multi-file diffs, self-play)
  - Try it yourself (HF Space URL, training notebook URL)
- [ ] Embed all three plots
- [ ] Embed the demo video
- [ ] Publish. Link to Niti for README.

### Task 3.4 — Lunch (1:00 PM → 1:30 PM)

- [ ] Eat. You've earned it.

---

## Phase 4 — Buffer & support (1:30 PM → 5:00 PM Sunday)

### Task 4.1 — Re-runs if needed (1:30 PM → 3:00 PM)

- [ ] If Deepak's evaluation surfaces an issue (e.g., trained model performs worse than baseline on a specific subset) — diagnose, decide if a quick re-eval is worth it
- [ ] If demo video has any issue — re-record once more, no more
- [ ] Help Niti smoke test from different networks

### Task 4.2 — Stretch: ablation training run (1:30 PM → 3:00 PM, optional)

Only if Tier 1 fully shipped:

- [ ] Launch a second short training run with a different reward weight configuration on HF Jobs
- [ ] Compare curves on the same axes
- [ ] Adds depth to the results section, shows you understand the reward design space
- [ ] Skip if anything in Tier 1 is wobbling

### Task 4.3 — Final support (3:00 PM → 5:00 PM)

- [ ] Stand by Niti during submission packaging
- [ ] If a link breaks, fix it
- [ ] After 4:30 PM, hands off keyboard

---

## Sync points

- **12:00 AM Midnight** — Team sync. Report: GCP VM ✅/⚠️/❌, mock training ✅/⚠️/❌, prompt template ✅/⚠️/❌
- **9:00 AM Sunday** — Team sync. Report: training run status, plot data availability
- **3:00 PM Sunday** — Final sync. Stop adding features.

---

## Fallback rules

- **HF Jobs queue is congested at 3 AM:** fall back to GCP VM with on-demand A10G (`a2-highgpu-1g` or `g2-standard-8`). Slightly more expensive (~$1/hr) but you have ₹24,000 of GCP credit. Budget allows.
- **Llama-3.2-3B OOMs on A10G with GRPO:** drop to Qwen2.5-1.5B-Instruct. Same notebook, swap one line. Don't debate.
- **Training curve is flat (model not learning):** check first if reward distribution is too sparse — if everything is around zero, agent has no signal. Coordinate with Deepak to tighten reward shape. Worst case, ship with a flat curve and a qualitative comparison — page 26 says "evidence that you trained," not "evidence that training was successful."
- **Demo video can't get the trained model to behave well in the recording:** cherry-pick the example. Find a commit where trained model nails it and untrained model fumbles. This is fine — judges expect curated demos.
- **HF blog post hits a publishing issue:** ship as a Markdown file in the GitHub repo, link from README. Same content, different surface. Doesn't matter for the rubric.