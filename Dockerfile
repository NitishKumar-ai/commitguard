# Use the official Unsloth image which has the stack pre-configured and tested
FROM unsloth/unsloth:latest

# Avoid prompts
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# The Unsloth image already has torch, transformers, and unsloth installed.
# We just need to install our project-specific dependencies and ensure TRL is at the right version.
RUN pip install --no-cache-dir \
    "trl==0.12.1" \
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

# Set environment variables for real-time logging and configuration
ENV PYTHONUNBUFFERED=1
ENV MODEL_NAME="meta-llama/Llama-3.2-3B-Instruct"
ENV OUTPUT_DIR="outputs/commitguard-llama-3b-grpo"
ENV WANDB_PROJECT="commitguard"

# Start training automatically
CMD ["python", "scripts/train_grpo.py", "--samples", "200", "--max-steps", "300", "--push-to-hub"]
