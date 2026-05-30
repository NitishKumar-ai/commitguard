"""CommitGuard v2 — Gemma 4 E4B LoRA fine-tuning script.

Supervised fine-tuning with PEFT LoRA on instruction-tuning pairs
produced by data_prep.py.

Usage:
    python scripts/train_gemma.py --samples 200 --max-steps 500
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main() -> None:
    ap = argparse.ArgumentParser(description="Fine-tune Gemma 4 E4B with LoRA on CommitGuard data.")
    ap.add_argument("--base-model", type=str, default="google/gemma-4-4b-it")
    ap.add_argument("--data-dir", type=Path, default=REPO_ROOT / "data")
    ap.add_argument("--output-dir", type=str, default="outputs/commitguard-gemma-4b")
    ap.add_argument("--samples", type=int, default=5000, help="Max training samples to use.")
    ap.add_argument("--max-steps", type=int, default=500)
    ap.add_argument("--save-steps", type=int, default=100)
    ap.add_argument("--eval-steps", type=int, default=500)
    ap.add_argument("--batch-size", type=int, default=2)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--max-seq-length", type=int, default=4096)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--lora-alpha", type=int, default=32)
    ap.add_argument("--lora-dropout", type=float, default=0.05)
    ap.add_argument("--no-wandb", action="store_true")
    ap.add_argument("--push-to-hub", action="store_true")
    ap.add_argument("--hub-model-id", type=str, default="inmodel-labs/commitguard-gemma-4b")
    args = ap.parse_args()

    # -- Imports (heavy, so deferred) --
    import torch
    from datasets import Dataset, load_dataset
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        TrainingArguments,
        Trainer,
        DataCollatorForSeq2Seq,
    )
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

    if not args.no_wandb:
        try:
            import wandb
            if not os.getenv("WANDB_API_KEY"):
                print("WANDB_API_KEY not set — disabling wandb")
                args.no_wandb = True
            else:
                wandb.init(project="commitguard-v2", name=f"gemma-4b-lora-r{args.lora_r}")
        except ImportError:
            args.no_wandb = True

    # -- 1. Load data --
    train_path = args.data_dir / "gemma_train.jsonl"
    val_path = args.data_dir / "gemma_val.jsonl"

    if not train_path.exists():
        print(f"Training data not found at {train_path}")
        print("Run `python scripts/data_prep.py` first.")
        sys.exit(1)

    print(f"Loading training data from {train_path}...")
    train_ds = load_dataset("json", data_files=str(train_path), split="train")
    train_ds = train_ds.select(range(min(args.samples, len(train_ds))))

    val_ds = None
    if val_path.exists():
        val_ds = load_dataset("json", data_files=str(val_path), split="train")
        print(f"Loaded {len(train_ds)} train, {len(val_ds)} val samples.")
    else:
        print(f"Loaded {len(train_ds)} train samples (no val set).")

    # -- 2. Load tokenizer --
    hf_token = os.getenv("HF_TOKEN")
    print(f"Loading tokenizer: {args.base_model}")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, token=hf_token)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # -- 3. Tokenize --
    def tokenize_fn(example: dict) -> dict:
        """Format as chat-style instruction-response and tokenize."""
        text = (
            f"<start_of_turn>user\n{example['instruction']}<end_of_turn>\n"
            f"<start_of_turn>model\n{example['response']}<end_of_turn>"
        )
        tokenized = tokenizer(
            text,
            truncation=True,
            max_length=args.max_seq_length,
            padding=False,
        )
        tokenized["labels"] = tokenized["input_ids"].copy()
        return tokenized

    print("Tokenizing datasets...")
    train_ds = train_ds.map(tokenize_fn, remove_columns=train_ds.column_names)
    if val_ds is not None:
        val_ds = val_ds.map(tokenize_fn, remove_columns=val_ds.column_names)

    # -- 4. Load model with 4-bit quantization --
    print(f"Loading {args.base_model} with 4-bit quantization...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        quantization_config=bnb_config,
        device_map="auto",
        torch_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        token=hf_token,
    )

    model = prepare_model_for_kbit_training(model)

    # -- 5. Apply LoRA --
    print(f"Applying LoRA (r={args.lora_r}, alpha={args.lora_alpha}, dropout={args.lora_dropout})")
    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # -- 6. Training config --
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        max_steps=args.max_steps,
        logging_steps=10,
        save_steps=args.save_steps,
        eval_strategy="steps" if val_ds is not None else "no",
        eval_steps=args.eval_steps if val_ds is not None else None,
        save_total_limit=3,
        load_best_model_at_end=val_ds is not None,
        metric_for_best_model="eval_loss" if val_ds is not None else None,
        greater_is_better=False,
        bf16=torch.cuda.is_bf16_supported(),
        fp16=not torch.cuda.is_bf16_supported(),
        gradient_checkpointing=True,
        report_to="none" if args.no_wandb else "wandb",
        remove_unused_columns=False,
        optim="adamw_torch",
    )

    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        padding=True,
        return_tensors="pt",
    )

    # -- 7. Train --
    print("Starting training...")
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=data_collator,
    )

    trainer.train()

    # -- 8. Save --
    final_dir = f"{args.output_dir}/final"
    print(f"Saving LoRA adapter to {final_dir}...")
    model.save_pretrained(final_dir)
    tokenizer.save_pretrained(final_dir)
    print("Training complete.")

    # -- 9. Push to Hub --
    if args.push_to_hub:
        print(f"Pushing to HuggingFace Hub: {args.hub_model_id}")
        model.push_to_hub(args.hub_model_id, token=True)
        tokenizer.push_to_hub(args.hub_model_id, token=True)
        print("Pushed successfully.")


if __name__ == "__main__":
    main()
