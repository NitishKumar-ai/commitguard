import os
from huggingface_hub import HfApi

api = HfApi(token="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")

# Create a job with a more complete image
job = api.run_job(
    image="huggingface/transformers-pytorch-gpu:latest",
    command="bash -c 'pip install unsloth trl datasets && python scripts/grpo_portable.py'",
    flavor="a10g-large",
    env={
        "HF_TOKEN": "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",
    }
)

print(f"Job started: {job.id}")
