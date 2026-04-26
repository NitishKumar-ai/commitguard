# Use a stable CUDA base
FROM nvidia/cuda:12.4.1-devel-ubuntu22.04

# Avoid prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3.11 and essentials
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    python3.11-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set python3.11 as default
RUN ln -s /usr/bin/python3.11 /usr/bin/python

WORKDIR /app

# Upgrade pip
RUN pip install --no-cache-dir -U pip setuptools wheel

# Install specific stable versions to bypass 2026 experimental version conflicts
# Pinning to known-good versions from the 2024-2025 cycle
RUN pip install --no-cache-dir \
    "torch==2.5.1" \
    "transformers==4.48.2" \
    "trl==0.12.1" \
    "peft==0.14.0" \
    "accelerate==1.2.1" \
    "bitsandbytes==0.45.0" \
    "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git" \
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
