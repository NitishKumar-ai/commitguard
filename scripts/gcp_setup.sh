#!/usr/bin/env bash
# =============================================================================
# CommitGuard — GCP VM Setup Script
# Target: GCE VM with NVIDIA L4 (24 GB) or A100 (40/80 GB)
# =============================================================================
set -euo pipefail

echo "============================================"
echo "  CommitGuard GCP Training VM Setup"
echo "============================================"

# --- 1. System packages ---
sudo apt-get update -qq
sudo apt-get install -y -qq git python3-venv python3-pip tmux htop

# --- 2. NVIDIA driver check ---
if ! command -v nvidia-smi &>/dev/null; then
    echo "ERROR: nvidia-smi not found. Use a GCP image with pre-installed GPU drivers:"
    echo "  - Deep Learning VM (recommended)"
    echo "  - Or install manually: sudo apt install nvidia-driver-535"
    exit 1
fi
echo "GPU detected:"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

# --- 3. Clone repo ---
REPO_DIR="$HOME/commitguard"
if [ ! -d "$REPO_DIR" ]; then
    echo "Cloning repo..."
    git clone https://github.com/NitishKumar-ai/commitguard.git "$REPO_DIR"
else
    echo "Repo exists, pulling latest..."
    cd "$REPO_DIR" && git pull
fi
cd "$REPO_DIR"

# --- 4. Python venv ---
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -U pip setuptools wheel -q

# --- 5. Install training dependencies ---
echo "Installing training dependencies..."
pip install -e . -q

pip install \
    "torch>=2.4" \
    "unsloth[cu124-torch240]" \
    "trl>=0.12" \
    "peft>=0.13" \
    "bitsandbytes>=0.44" \
    "transformers>=4.46" \
    "datasets>=3.0" \
    "accelerate>=1.0" \
    "wandb" \
    "requests" \
    "matplotlib" \
    "jupyter" \
    "ipywidgets" \
    -q

echo "Verifying installs..."
python -c "
import torch, trl, unsloth, peft, wandb, bitsandbytes
print(f'PyTorch:  {torch.__version__}')
print(f'CUDA:     {torch.cuda.is_available()} — {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')
print(f'TRL:      {trl.__version__}')
print(f'PEFT:     {peft.__version__}')
print(f'Wandb:    {wandb.__version__}')
print('All training deps OK.')
"

echo ""
echo "============================================"
echo "  Setup complete. Two options to train:"
echo "============================================"
echo ""
echo "  ── OPTION A: Jupyter Notebook (recommended) ──"
echo ""
echo "  # On the VM:"
echo "  cd $REPO_DIR && source .venv/bin/activate"
echo "  tmux new -s server -d 'source .venv/bin/activate && server'"
echo "  jupyter notebook --no-browser --port=8888 --ip=0.0.0.0"
echo ""
echo "  # On your LOCAL machine (new terminal):"
echo "  gcloud compute ssh commitguard-train --zone=us-central1-a -- -NL 8888:localhost:8888"
echo ""
echo "  # Then open in browser:"
echo "  # http://localhost:8888  →  notebooks/train_commitguard.ipynb"
echo ""
echo "  ── OPTION B: CLI ──"
echo ""
echo "  cd $REPO_DIR && source .venv/bin/activate"
echo "  tmux new -s server -d 'source .venv/bin/activate && server'"
echo "  huggingface-cli login"
echo "  python scripts/train_grpo.py --samples 200 --max-steps 300"
echo ""
