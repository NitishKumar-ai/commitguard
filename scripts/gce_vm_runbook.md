## GCE VM Runbook — CommitGuard GRPO Training

### Step 1: Create VM

Run from your local machine (or use GCP Console):

```bash
# Option A: L4 (24 GB VRAM, ~$0.70/hr) — RECOMMENDED
gcloud compute instances create commitguard-train \
  --zone=us-central1-a \
  --machine-type=g2-standard-8 \
  --accelerator=type=nvidia-l4,count=1 \
  --boot-disk-size=100GB \
  --image-family=pytorch-latest-gpu \
  --image-project=deeplearning-platform-release \
  --maintenance-policy=TERMINATE \
  --metadata="install-nvidia-driver=True"

# Option B: A100 (40 GB VRAM, ~$2.50/hr) — if L4 unavailable
gcloud compute instances create commitguard-train \
  --zone=us-central1-a \
  --machine-type=a2-highgpu-1g \
  --accelerator=type=nvidia-tesla-a100,count=1 \
  --boot-disk-size=100GB \
  --image-family=pytorch-latest-gpu \
  --image-project=deeplearning-platform-release \
  --maintenance-policy=TERMINATE \
  --metadata="install-nvidia-driver=True"

# Option C: T4 (16 GB VRAM, ~$0.35/hr) — budget fallback
gcloud compute instances create commitguard-train \
  --zone=us-central1-b \
  --machine-type=n1-standard-8 \
  --accelerator=type=nvidia-tesla-t4,count=1 \
  --boot-disk-size=100GB \
  --image-family=pytorch-latest-gpu \
  --image-project=deeplearning-platform-release \
  --maintenance-policy=TERMINATE \
  --metadata="install-nvidia-driver=True"
```

### Step 2: SSH into VM

```bash
gcloud compute ssh commitguard-train --zone=us-central1-a
```

### Step 3: One-command setup

```bash
curl -sSL https://raw.githubusercontent.com/NitishKumar-ai/commitguard/main/scripts/gcp_setup.sh | bash
```

Or manually:

```bash
git clone https://github.com/NitishKumar-ai/commitguard.git
cd commitguard
bash scripts/gcp_setup.sh
```

### Step 4: Start env server (in tmux)

```bash
cd ~/commitguard && source .venv/bin/activate
tmux new -s server
server
# Ctrl-B D to detach
```

Verify:

```bash
curl -s http://localhost:8000/health
# → {"status":"healthy"}
```

### Step 5: Login to HuggingFace + Wandb

```bash
source ~/commitguard/.venv/bin/activate
huggingface-cli login          # paste your HF token (needed for Llama gated model)
wandb login                    # paste your wandb API key
```

### Step 6: Start training

```bash
cd ~/commitguard && source .venv/bin/activate
export WANDB_PROJECT=commitguard

# Full run (~2-3 hours on L4)
python scripts/train_grpo.py \
  --samples 200 \
  --max-steps 300 \
  --save-steps 50 \
  --num-generations 4 \
  --batch-size 1 \
  --grad-accum 4

# Quick smoke test first (5 min)
python scripts/train_grpo.py \
  --samples 20 \
  --max-steps 10 \
  --no-wandb
```

### Step 7: Monitor

```bash
# In another tmux pane:
watch -n 30 nvidia-smi          # GPU memory
# Wandb dashboard: https://wandb.ai/<your-user>/commitguard
```

### Step 8: Copy results back

```bash
# From your LOCAL machine:
gcloud compute scp --recurse \
  commitguard-train:~/commitguard/outputs/commitguard-llama-3b/final \
  ./outputs/commitguard-llama-3b/final \
  --zone=us-central1-a
```

### Step 9: Shut down VM

```bash
gcloud compute instances stop commitguard-train --zone=us-central1-a
# or delete to stop billing entirely:
gcloud compute instances delete commitguard-train --zone=us-central1-a
```

### Cost estimate

| GPU | VRAM | $/hr | 300 steps (~3hr) |
|-----|------|------|-------------------|
| T4  | 16GB | $0.35 | ~$1.05 |
| L4  | 24GB | $0.70 | ~$2.10 |
| A100| 40GB | $2.50 | ~$7.50 |

### Troubleshooting

- **OOM on T4**: reduce `--num-generations 2` and `--batch-size 1`
- **Llama access denied**: make sure you accepted the license at https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct
- **Env server not responding**: check `tmux attach -t server` for errors
- **Wandb not logging**: verify `wandb login` succeeded, or use `--no-wandb`
- **GPU quota error**: request GPU quota increase at https://console.cloud.google.com/iam-admin/quotas

