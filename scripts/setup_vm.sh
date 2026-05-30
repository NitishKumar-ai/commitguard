#!/usr/bin/env bash
# =============================================================================
# CommitGuard v2 — GCP L4 VM Setup Script
# Target: GCE VM with NVIDIA L4 (24 GB), Python 3.11
# Model:  Gemma 4 E4B (LoRA fine-tune)
# =============================================================================
set -euo pipefail

echo "============================================"
echo "  CommitGuard v2 — GCP Training VM Setup"
echo "  Model: Gemma 4 E4B (LoRA)"
echo "============================================"

# --- 1. System packages ---
sudo apt-get update -qq
sudo apt-get install -y -qq git python3.11 python3.11-venv python3-pip tmux htop

# --- 2. NVIDIA driver check ---
if ! command -v nvidia-smi &>/dev/null; then
    echo "ERROR: nvidia-smi not found. Use a GCP image with pre-installed GPU drivers:"
    echo "  - Deep Learning VM (recommended)"
    echo "  - Or install manually: sudo apt install nvidia-driver-550"
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
    python3.11 -m venv .venv
fi
source .venv/bin/activate
pip install -U pip setuptools wheel -q

# --- 5. Install base + training dependencies ---
echo "Installing core dependencies..."
pip install -e ".[scan,v2]" -q

echo "Installing training dependencies..."
pip install \
    "torch>=2.4" \
    "transformers>=4.46" \
    "peft>=0.13" \
    "bitsandbytes>=0.44" \
    "datasets>=3.0" \
    "accelerate>=1.0" \
    "wandb" \
    "requests" \
    "matplotlib" \
    "sentence-transformers>=2.2" \
    "faiss-cpu>=1.7" \
    "PyGithub>=2.0" \
    "gitpython>=3.1" \
    -q

# --- 6. Verify installs ---
echo "Verifying installs..."
python -c "
import torch, transformers, peft, bitsandbytes, accelerate
print(f'PyTorch:       {torch.__version__}')
print(f'CUDA:          {torch.cuda.is_available()} — {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')
print(f'Transformers:  {transformers.__version__}')
print(f'PEFT:          {peft.__version__}')
print(f'BnB:           {bitsandbytes.__version__}')
print(f'Accelerate:    {accelerate.__version__}')
print()
print('All training deps OK.')
"

# --- 7. Configure HuggingFace ---
echo ""
echo "============================================"
echo "  Setup complete."
echo "============================================"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Authenticate with HuggingFace:"
echo "     huggingface-cli login"
echo ""
echo "  2. Prepare training data:"
echo "     python scripts/data_prep.py --limit 5000"
echo ""
echo "  3. Start training:"
echo "     python scripts/train_gemma.py --samples 200 --max-steps 500"
echo ""
echo "  4. Evaluate:"
echo "     python scripts/evaluate.py --model-path outputs/commitguard-gemma-4b/final"
echo ""
echo "  5. Run the server:"
echo "     uvicorn server.app:app --port 8000"
echo ""
