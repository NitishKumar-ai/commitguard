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

# 1. Install Unsloth — it pulls compatible trl, transformers, peft, accelerate
RUN pip install --no-cache-dir "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"

# 2. Install remaining deps (don't re-pin packages Unsloth already resolved)
RUN pip install --no-cache-dir \
    bitsandbytes \
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
ENV PYTHONUNBUFFERED=1
ENV MODEL_NAME="meta-llama/Llama-3.2-3B-Instruct"
ENV OUTPUT_DIR="outputs/commitguard-llama-3b-grpo"
ENV WANDB_PROJECT="commitguard"

# Start training automatically
CMD ["python", "scripts/train_grpo.py", "--samples", "200", "--max-steps", "300", "--push-to-hub"]
