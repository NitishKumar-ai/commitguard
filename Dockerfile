# Use a robust PyTorch + CUDA base image
FROM pytorch/pytorch:2.4.0-cuda12.1-cudnn9-devel

# Avoid prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install git for Unsloth and HF push
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip
RUN pip install --no-cache-dir -U pip setuptools wheel

# Install Unsloth and training dependencies
# Using the recommended installation for standard environments
RUN pip install --no-cache-dir \
    "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git" \
    trl \
    peft \
    accelerate \
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

# Install the local package
RUN pip install -e .

# Set environment variables
ENV MODEL_NAME="meta-llama/Llama-3.2-3B-Instruct"
ENV OUTPUT_DIR="outputs/commitguard-llama-3b-grpo"
ENV WANDB_PROJECT="commitguard"

# Start training
CMD ["python", "scripts/train_grpo.py", "--samples", "200", "--max-steps", "300", "--push-to-hub"]
