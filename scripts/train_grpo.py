import os
import sys
import json
import argparse
from pathlib import Path

import torch
import wandb
from datasets import Dataset, load_dataset
from trl import GRPOConfig, GRPOTrainer
from unsloth import FastLanguageModel, PatchFastRL

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent_prompt import SYSTEM_PROMPT
from commitguard_env.parse_action import parse_action
from commitguard_env.reward import compute_reward

PatchFastRL("GRPO", FastLanguageModel)

# --- Configuration ---
MODEL_NAME = os.getenv("MODEL_NAME", "meta-llama/Llama-3.2-3B-Instruct")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs/commitguard-llama-3b-grpo")
WANDB_PROJECT = os.getenv("WANDB_PROJECT", "commitguard")

CWE_KEYWORDS_PATH = REPO_ROOT / "data" / "cwe_keywords.json"
CWE_KEYWORDS: dict[str, list[str]] = {}
if CWE_KEYWORDS_PATH.exists():
    CWE_KEYWORDS = json.loads(CWE_KEYWORDS_PATH.read_text(encoding="utf-8"))

# Pre-built lookup: sample_id -> ground truth fields (loaded in build_dataset)
SAMPLE_LABELS: dict[str, dict] = {}


# --- Local reward: no HTTP, no latency ---
def get_reward_local(prompts, completions, sample_id, **kwargs) -> list[float]:
    rewards = []
    for p_id, completion in zip(sample_id, completions):
        text = completion[-1]["content"] if isinstance(completion, list) else str(completion)
        action = parse_action(text)
        labels = SAMPLE_LABELS.get(p_id, {})
        reward = compute_reward(
            action=action,
            is_vulnerable=labels.get("is_vulnerable"),
            cwe=labels.get("cwe"),
            target_file=labels.get("target_file"),
            cwe_keywords=CWE_KEYWORDS,
            context_requests=0,
        )
        rewards.append(reward)
    return rewards


def format_prompt(sample):
    # Using the Llama-3.2 prompt template from the plan
    return {
        "prompt": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze this commit and submit your verdict.\n\nCode diff:\n```diff\n{sample['diff']}\n```"},
        ],
        "sample_id": sample["sample_id"],
    }


def build_dataset(n_samples: int) -> Dataset:
    data_path = REPO_ROOT / "data" / "devign_filtered.jsonl"
    if not data_path.exists():
        print(f"Dataset file {data_path} not found.")
        return Dataset.from_list([])

    print(f"Loading training samples from {data_path}...")
    raw_dataset = load_dataset("json", data_files=str(data_path), split="train")
    raw_dataset = raw_dataset.select(range(min(n_samples, len(raw_dataset))))

    for row in raw_dataset:
        sid = row["sample_id"]
        SAMPLE_LABELS[sid] = {
            "is_vulnerable": row.get("is_vulnerable"),
            "cwe": row.get("cwe"),
            "target_file": row.get("target_file"),
        }

    dataset = raw_dataset.map(format_prompt)
    print(f"Loaded {len(dataset)} samples ({len(SAMPLE_LABELS)} labels cached in-process).")
    return dataset


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=200)
    ap.add_argument("--max-steps", type=int, default=300)
    ap.add_argument("--save-steps", type=int, default=50)
    ap.add_argument("--num-generations", type=int, default=8)
    ap.add_argument("--batch-size", type=int, default=1)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--lr", type=float, default=5e-6)
    ap.add_argument("--no-wandb", action="store_true")
    ap.add_argument("--push-to-hub", action="store_true")
    ap.add_argument("--hub-model-id", type=str, default="inmodel-labs/commitguard-llama-3b")
    args = ap.parse_args()

    if args.num_generations < 2:
        raise ValueError("--num-generations must be at least 2 for GRPO")
    effective_batch = args.batch_size * args.grad_accum
    if effective_batch % args.num_generations != 0:
        raise ValueError(
            "For single-process GRPO training, --batch-size * --grad-accum "
            f"must be divisible by --num-generations; got {args.batch_size} * "
            f"{args.grad_accum} = {effective_batch}, num_generations={args.num_generations}."
        )

    if not args.no_wandb and not os.getenv("WANDB_API_KEY"):
        print("WANDB_API_KEY not set — disabling wandb logging")
        args.no_wandb = True

    if not args.no_wandb:
        wandb.init(project=WANDB_PROJECT, name=f"grpo-{MODEL_NAME.split('/')[-1]}-run1")

    # 1. Load Model
    hf_token = os.getenv("HF_TOKEN")
    print(f"Loading {MODEL_NAME} with Unsloth 4-bit...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=2048,
        load_in_4bit=True,
        fast_inference=True,
        max_lora_rank=16,
        token=hf_token,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=8,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    # 2. Build dataset
    dataset = build_dataset(args.samples)

    # 3. GRPO config
    training_args = GRPOConfig(
        output_dir=OUTPUT_DIR,
        num_generations=args.num_generations,
        max_completion_length=256,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        logging_steps=1,
        save_steps=args.save_steps,
        max_steps=args.max_steps,
        report_to="none" if args.no_wandb else "wandb",
        bf16=torch.cuda.is_bf16_supported(),
        fp16=not torch.cuda.is_bf16_supported(),
    )

    # 4. Train
    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        reward_funcs=[get_reward_local],
        args=training_args,
        train_dataset=dataset,
    )

    print("Starting GRPO training...")
    trainer.train()

    # 5. Save
    final_dir = f"{OUTPUT_DIR}/final"
    model.save_pretrained_merged(final_dir, tokenizer, save_method="lora")
    print(f"Training complete. LoRA adapter saved to {final_dir}")

    if args.push_to_hub:
        print(f"Pushing to HF Hub: {args.hub_model_id}")
        model.push_to_hub(args.hub_model_id, token=True)
        tokenizer.push_to_hub(args.hub_model_id, token=True)


if __name__ == "__main__":
    main()
