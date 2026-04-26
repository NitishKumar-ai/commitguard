# HF Training Checklist — CommitGuard

**Print this. Tick every box in order. Do NOT skip steps.**
**If any box fails: STOP. Fix before proceeding.**

---

## PHASE 0 — Account Setup (Do Once, Do NOW)

- [ ] `huggingface-cli login` → authenticated
- [ ] `huggingface-cli whoami` → shows your username
- [ ] HF credits visible at https://huggingface.co/settings/billing → $30 showing
- [ ] Claim HF credits if not done: https://huggingface.co/coupons/claim/hf-openenv-community
- [ ] Llama-3.2-3B license accepted at https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct
- [ ] License status: "You have been granted access" (NOT "pending")
- [ ] If pending after 30 min → **SWITCH TO Qwen2.5-1.5B-Instruct. No waiting.**
- [ ] `wandb login` → authenticated
- [ ] Wandb project created: `commitguard`

---

## PHASE 1 — Environment Health (Before ANY Training)

### 1A. HF Space is alive

```bash
curl https://<username>-commitguard.hf.space/health
```

- [ ] Returns `{"status": "healthy"}` with HTTP 200
- [ ] Response time < 3 seconds

### 1B. Env accepts actions

```bash
# Reset
curl -X POST https://<username>-commitguard.hf.space/reset
```

- [ ] Returns JSON with `diff` field (non-empty string)
- [ ] Returns JSON with `done: false`
- [ ] Returns JSON with `reward: 0.0`

```bash
# Step with verdict
curl -X POST https://<username>-commitguard.hf.space/step \
  -H "Content-Type: application/json" \
  -d '{"action_type":"verdict","is_vulnerable":true,"vuln_type":"CWE-89","exploit_sketch":"sql injection"}'
```

- [ ] Returns JSON with `reward` field (NOT 0.0 — should be +1.0 or -1.0)
- [ ] Returns JSON with `done: true`

### 1C. Env handles load

- [ ] Run 10 sequential reset→step cycles → zero crashes
- [ ] Run 5 concurrent reset→step cycles → zero crashes, no race conditions
- [ ] No request takes longer than 10 seconds

### 1D. Reward sanity

- [ ] Correct vulnerable verdict → reward > 0 (expected: +1.0)
- [ ] False positive (safe code flagged) → reward < 0 (expected: -1.0)
- [ ] False negative (vuln missed) → reward < 0 (expected: -0.5)
- [ ] Rewards are NOT all identical across different samples

---

## PHASE 2 — Data Verification

- [ ] `data/devign_train.jsonl` exists
- [ ] `wc -l data/devign_train.jsonl` → >1000 samples
- [ ] `data/devign_test.jsonl` exists
- [ ] `wc -l data/devign_test.jsonl` → exactly 100 samples
- [ ] Train and test commit_ids are disjoint (no overlap)
- [ ] Spot check 3 samples: `code_after` is non-empty, `is_vulnerable` is boolean
- [ ] No sample exceeds 80 lines of code
- [ ] Approximate 50/50 split between vulnerable and safe samples

---

## PHASE 3 — GPU & Dependencies

### 3A. Hardware

```bash
nvidia-smi
```

- [ ] GPU visible with ≥16GB VRAM
- [ ] GPU name matches expected (T4 / A10G / L4)
- [ ] Free VRAM ≥ 14GB (kill other processes if needed)

### 3B. Python environment

```bash
python --version
```

- [ ] Python 3.10 or 3.11 (NOT 3.12 — Unsloth compatibility issues)

### 3C. Critical libraries

```bash
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
python -c "from unsloth import FastLanguageModel; print('OK')"
python -c "from trl import GRPOTrainer; print('OK')"
python -c "from peft import PeftModel; print('OK')"
python -c "import wandb; print('OK')"
```

- [ ] torch ≥ 2.3.0, CUDA = True
- [ ] unsloth imports without error
- [ ] trl ≥ 0.12.0 imports without error
- [ ] peft imports without error
- [ ] wandb imports without error

---

## PHASE 4 — Model Loading Test

```python
from unsloth import FastLanguageModel
model, tokenizer = FastLanguageModel.from_pretrained(
    "meta-llama/Llama-3.2-3B-Instruct",
    max_seq_length=2048,
    load_in_4bit=True,
)
print("Model loaded successfully")
print(f"GPU memory: {torch.cuda.memory_allocated()/1e9:.1f}GB")
```

- [ ] Model loads without OOM
- [ ] GPU memory after load < 6GB (leaves room for GRPO overhead)
- [ ] No warnings about missing tokenizer files

### LoRA application

```python
model = FastLanguageModel.get_peft_model(
    model, r=8, lora_alpha=16,
    target_modules=["q_proj","k_proj","v_proj","o_proj"],
)
print(f"Trainable params: {sum(p.numel() for p in model.parameters() if p.requires_grad)}")
```

- [ ] LoRA applies without error
- [ ] Trainable params ~3-8M (NOT the full 3B)

---

## PHASE 5 — Dry Run (2 Steps)

**THE MOST CRITICAL CHECK. DO NOT SKIP.**

```bash
python train_grpo.py --max_steps 2
```

### 5A. Generation

- [ ] First prompt formatted correctly (print it — does it contain a code diff?)
- [ ] 4 completions generated for first prompt
- [ ] At least 2 of 4 completions contain `<action_type>` XML tags
- [ ] Completions are different from each other (not all identical)

### 5B. Reward collection

- [ ] All 4 completions submitted to env
- [ ] All 4 rewards received (no timeouts)
- [ ] Rewards have variance (NOT all the same value)
- [ ] Rewards in expected range [-1.0, +2.0]
- [ ] Print rewards: `[_____, _____, _____, _____]` (write them down)

### 5C. Training step

- [ ] GRPO loss computed (finite number, not NaN, not inf, not 0.0)
- [ ] Loss value: _____ (write it down)
- [ ] Wandb shows run with 2 logged steps
- [ ] No OOM during backward pass
- [ ] Peak GPU memory: _____GB (must be < 22GB on A10G or < 14GB on T4)

### 5D. Checkpointing

- [ ] Output directory created: `./commitguard-llama-3b-grpo/`
- [ ] Checkpoint files present (or will be at step 50)

### 5E. Timing estimate

- [ ] 2 steps took _____ seconds
- [ ] Estimated time for 300 steps: _____ minutes (= 2-step-time × 150)
- [ ] Estimated cost: _____ dollars (hours × GPU hourly rate)
- [ ] Cost within budget? (must be under $8)

---

## PHASE 6 — Baseline Eval (Before Training)

**MUST run baseline BEFORE training. Cannot run after — you need the contrast.**

```bash
python evaluate.py \
  --model_path meta-llama/Llama-3.2-3B-Instruct \
  --test_file data/devign_test.jsonl \
  --output eval_baseline.json
```

- [ ] Eval completes on all 100 test samples
- [ ] Binary accuracy: _____% (write it down, expected: 30-50%)
- [ ] CWE accuracy: _____% (expected: low, maybe 5-15%)
- [ ] False positive rate: _____%
- [ ] False negative rate: _____%
- [ ] Results saved to `eval_baseline.json`
- [ ] File committed to repo

---

## PHASE 7 — Launch Real Training

### Pre-launch final checks

- [ ] All phases 0-6 are GREEN
- [ ] Budget approved by Niti (team lead)
- [ ] Config confirmed:
  - [ ] `max_steps = 300`
  - [ ] `save_steps = 50`
  - [ ] `logging_steps = 1`
  - [ ] `num_generations = 4`
  - [ ] `learning_rate = 5e-6`
  - [ ] `report_to = "wandb"`
- [ ] HF Space is still healthy (re-check `/health`)
- [ ] Screenshot this checklist with all boxes ticked → post in team channel

### Launch

```bash
# Option A: HF Jobs (preferred)
hf jobs uv run --flavor a10g-large train_grpo.py

# Option B: GCP (fallback)
nohup python train_grpo.py > training.log 2>&1 &
```

- [ ] Job started successfully
- [ ] Job ID / Dashboard URL captured: _______________________
- [ ] Wandb run URL captured: _______________________
- [ ] Posted both URLs in team channel
- [ ] Set alarm to check in 30 minutes

---

## PHASE 8 — During Training Monitoring

**Check every 30 minutes while awake. Check immediately on waking up.**

### Quick health check (< 2 min each time)

| Time | reward/mean | reward/std | loss | GPU mem | Status |
|------|-------------|------------|------|---------|--------|
| +30m | _____ | _____ | _____ | _____ | ✅/⚠️/❌ |
| +1h  | _____ | _____ | _____ | _____ | ✅/⚠️/❌ |
| +1.5h | _____ | _____ | _____ | _____ | ✅/⚠️/❌ |
| +2h  | _____ | _____ | _____ | _____ | ✅/⚠️/❌ |
| Final | _____ | _____ | _____ | _____ | ✅/⚠️/❌ |

### Red flags → immediate action

| Red flag | Action |
|---|---|
| reward/mean trending DOWN | Check env `/health`. If healthy, lower LR to 2e-6 and relaunch from latest checkpoint. |
| loss = NaN | Kill run. Add `max_grad_norm=1.0` to config. Relaunch from checkpoint. |
| GPU memory > 23GB | Will OOM soon. Kill run. Reduce `num_generations` to 2. Relaunch. |
| Env returning errors in Wandb logs | HF Space is sleeping. Hit `/health` to wake. If down, Niti restarts. |
| Steps/second dropped to 0 | Job hung. Kill and relaunch from checkpoint. |
| All rewards identical for 50+ steps | Reward function bug. Ping Deepak. |

---

## PHASE 9 — Post-Training

### Immediately after training completes

- [ ] Training finished without crash
- [ ] Wandb run status: "finished"
- [ ] Final reward/mean: _____ (higher than step-1 reward? That's the curve.)
- [ ] Screenshot reward curve from Wandb → save as `plots/reward_curve.png`
- [ ] Final checkpoint exists in output directory
- [ ] Total training time: _____ hours
- [ ] Total cost: $_____

### Save the model

```bash
# Push LoRA adapter to HF Hub
huggingface-cli upload inmodel-labs/commitguard-llama-3b \
  ./commitguard-llama-3b-grpo/final
```

- [ ] Upload successful
- [ ] Model page visible at https://huggingface.co/inmodel-labs/commitguard-llama-3b

### Verify the saved model loads

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM
base = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-3.2-3B-Instruct")
model = PeftModel.from_pretrained(base, "inmodel-labs/commitguard-llama-3b")
print("Trained model loads correctly")
```

- [ ] Model loads without error
- [ ] Quick inference produces XML-tagged output (not garbage)

---

## PHASE 10 — Trained Model Eval

```bash
python evaluate.py \
  --model_path ./commitguard-llama-3b-grpo/final \
  --test_file data/devign_test.jsonl \
  --is_lora \
  --base_model meta-llama/Llama-3.2-3B-Instruct \
  --output eval_trained.json
```

- [ ] Eval completes on all 100 test samples
- [ ] Binary accuracy: _____% (compare to baseline: _____%)
- [ ] CWE accuracy: _____% (compare to baseline: _____%)
- [ ] False positive rate: _____% (compare to baseline: _____%)
- [ ] False negative rate: _____% (compare to baseline: _____%)
- [ ] Results saved to `eval_trained.json`
- [ ] File committed to repo

### The verdict

- [ ] Trained accuracy > baseline accuracy? **YES / NO**
- [ ] If YES: by how many percentage points? _____pp
- [ ] If NO: check if qualitative outputs improved (reasoning traces better even if accuracy similar)

### Hand off to team

- [ ] Post in team channel:
  ```
  TRAINING COMPLETE
  Baseline accuracy: X%
  Trained accuracy: Y%
  Improvement: +Zpp
  Wandb: [url]
  Reward curve: [screenshot]
  Model on Hub: inmodel-labs/commitguard-llama-3b
  Ready for plots and README.
  ```
- [ ] Hand `eval_baseline.json` and `eval_trained.json` to Deepak for plot generation
- [ ] Kill GCP VM if running (`gcloud compute instances stop ...`)
- [ ] Update budget tracker in team channel

---

## PHASE 11 — Inference for Demo Video

**Divyank runs this to get the before/after examples for the demo recording.**

### Pick the demo sample

- [ ] Find ONE sample from test set where:
  - Ground truth: vulnerable (preferably CWE-89 SQL injection)
  - Baseline model gets it WRONG
  - Trained model gets it RIGHT
- [ ] Sample commit_id: _______________________

### Generate baseline output

```python
# Load untrained model, generate response for the demo sample
# Save full text output to demo_baseline_output.txt
```

- [ ] Baseline output saved
- [ ] Output shows: wrong verdict / no reasoning / random guess

### Generate trained output

```python
# Load trained model, generate response for the demo sample
# Save full text output to demo_trained_output.txt
```

- [ ] Trained output saved
- [ ] Output shows: correct verdict / identifies CWE / sketches exploit
- [ ] The contrast between baseline and trained is VISIBLE and OBVIOUS

### Ready for recording

- [ ] Both outputs saved as text files for screen capture
- [ ] The diff for this sample is readable (not 80 lines of dense C)
- [ ] Proceed to demo video recording (see tasks_divyank.md)

---

## Emergency Fallback Reference Card

**Tape this next to your screen. Read it at 3 AM when your brain is mush.**

```
CRASHED? → Check Wandb → Is it OOM?
  YES OOM → num_generations=2, retry from checkpoint
  STILL OOM → Switch to Qwen2.5-1.5B, retry from scratch
  NOT OOM → Check error message → Screenshot → Post in team channel

REWARDS ALL ZERO? → Env bug, not model bug
  → curl /health on HF Space
  → If dead: ping Niti
  → If alive: curl /step manually, check reward value
  → If reward from curl is also 0: Deepak's reward function bug

LLAMA ACCESS DENIED? → Switch to Qwen2.5-1.5B immediately
  → Change ONE line: model_name="Qwen/Qwen2.5-1.5B-Instruct"
  → Everything else stays the same

CURVE IS FLAT? → Ship it anyway with honest narrative
  → "Training evidence shows optimization attempted;
     reward signal needs richer shaping in future work"
  → A flat curve + honest story > no submission
```