## GCE VM runbook (₹2400 free credit friendly)

### 1) Create VM
- **Machine**: `n1-standard-4` (or similar)
- **GPU**: start with **T4** (cheapest widely available) or **L4** if available
- **Disk**: 50–100GB
- **OS**: Ubuntu 22.04

### 2) Install CUDA drivers (one-time)
Use GCP’s recommended NVIDIA driver install for your image/GPU.

### 3) Setup python + install

```bash
sudo apt-get update
sudo apt-get install -y python3-venv git
git clone <YOUR_REPO_URL>
cd commitguard
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[train]"
```

### 4) Start the env server

```bash
server
```

Health check:

```bash
curl -s http://127.0.0.1:8000/health
```

### 5) Run baseline training driver (placeholder)

```bash
python scripts/train_grpo.py --episodes 200
```

Optional W&B:

```bash
export WANDB_PROJECT=commitguard
python scripts/train_grpo.py --episodes 200
```

### 6) Next step
Replace the placeholder baseline driver with the full **TRL GRPO** loop once deps are installed and the env is stable.

