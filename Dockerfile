# Use a pre-configured PyTorch + CUDA base to save build time and avoid 'int1' issues
FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-devel

# Avoid prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies needed for bitsandbytes and Unsloth
RUN apt-get update && apt-get install -y \
    git \
    libaio-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip
RUN pip install --no-cache-dir -U pip setuptools wheel

# 1. Install Unsloth first (it's the most sensitive to environment)
RUN pip install --no-cache-dir "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"

# 2. Install specifically pinned versions of the RL stack
# We use 0.12.1 for TRL and 4.48.2 for transformers - these are stable with Torch 2.5.1
RUN pip install --no-cache-dir \
    "transformers==4.48.2" \
    "trl==0.12.1" \
    "peft==0.14.0" \
    "accelerate==1.2.1" \
    "bitsandbytes==0.45.0"

# 3. Install remaining data and server dependencies
RUN pip install --no-cache-dir \
    datasets \
    wandb \
    matplotlib \
    fastapi \
    uvicorn \
    pydantic \
    openenv

# Copy the project files
COPY . .

# Install the local package in editable mode
RUN pip install -e .

# Set environment variables
ENV MODEL_NAME="meta-llama/Llama-3.2-3B-Instruct"
ENV OUTPUT_DIR="outputs/commitguard-llama-3b-grpo"
ENV WANDB_PROJECT="commitguard"

# Start training automatically
CMD ["python", "scripts/train_grpo.py", "--samples", "200", "--max-steps", "300", "--push-to-hub"]
