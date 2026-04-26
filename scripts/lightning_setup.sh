#!/usr/bin/env bash
# CommitGuard - Lightning AI Setup & Train
# This script prepares the environment and starts GRPO training.

set -e

echo "--- 1. Installing uv ---"
curl -LsSf https://astral.sh/uv/install.sh | sh
if [ -f "$HOME/.local/bin/env" ]; then
    source "$HOME/.local/bin/env"
elif [ -f "$HOME/.cargo/env" ]; then
    source "$HOME/.cargo/env"
fi
export PATH="$HOME/.local/bin:$PATH"

echo "--- 2. Setting up Workspace ---"
REPO_DIR="$HOME/commitguard"
if [ ! -d "$REPO_DIR" ]; then
    echo "Cloning repo..."
    git clone https://github.com/NitishKumar-ai/commitguard "$REPO_DIR"
fi
cd "$REPO_DIR"

echo "--- 3. Setting up Virtual Env ---"
if [ ! -d ".venv" ]; then
    uv venv
fi
source .venv/bin/activate

echo "--- 4. Installing Dependencies ---"
uv sync --all-extras

echo "--- 5. Starting Environment Server ---"
# Use tmux to keep the server running in the background
if command -v tmux >/dev/null; then
    tmux new -s env_server -d "source .venv/bin/activate && python -m commitguard_env.server"
else
    python -m commitguard_env.server &
    SERVER_PID=$!
fi

echo "Waiting for server to be healthy..."
max_retries=30
count=0
until $(curl --output /dev/null --silent --head --fail http://localhost:8000/health); do
    printf '.'
    sleep 2
    count=$((count+1))
    if [ $count -eq $max_retries ]; then
      echo "Server failed to start."
      exit 1
    fi
done
echo "Server is healthy!"

echo "--- 5. Starting GRPO Training ---"
# Defaults: 200 samples, 300 steps. 
# Increase samples for better stability, decrease for faster iteration.
python scripts/train_grpo.py --samples 200 --max-steps 300

echo "Training session finished."
