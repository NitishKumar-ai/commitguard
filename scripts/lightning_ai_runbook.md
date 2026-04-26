# Training on Lightning AI

This guide explains how to run CommitGuard GRPO training on a Lightning AI GPU Studio.

## Recommended Instance
- **GPU:** NVIDIA L4 (24GB) or A10G (24GB) is sufficient for Llama-3.2-3B with Unsloth 4-bit.
- **Image:** Default Linux / PyTorch images are fine; the setup script handles dependencies.

## Setup & Train in One Step

1. Open a terminal in your Lightning AI Studio.
2. Run the setup script:
   ```bash
   bash scripts/lightning_setup.sh
   ```

## What the script does:
1. Installs `uv` for fast dependency management.
2. Creates a virtual environment and installs all requirements (Unsloth, TRL, etc.).
3. Starts the `commitguard_env` server in the background (via `tmux` if available).
4. Runs `scripts/train_grpo.py`.

## Manual Steps (Optional)

### 1. View Training Logs
If you want to see the environment server logs:
```bash
tmux attach -t env_server
```
(Press `Ctrl+B`, then `D` to detach).

### 2. Hugging Face Integration
To save your model to the Hugging Face Hub, login before training:
```bash
huggingface-cli login
```

### 3. Checkpoints
Checkpoints and the final merged LoRA adapter will be saved to:
`outputs/commitguard-llama-3b/final`

## Troubleshooting
- **OOM Error:** If you hit Out-Of-Memory, try reducing `--batch-size` or `--num-generations` in `scripts/train_grpo.py`.
- **Server Connection:** If training fails with connection errors, ensure the server started correctly by checking `curl http://localhost:8000/health`.
