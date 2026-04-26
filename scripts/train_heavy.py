import argparse
from unsloth import FastLanguageModel, PatchFastRL
from datasets import Dataset
from trl import GRPOConfig, GRPOTrainer
import requests
import os
import sys
from pathlib import Path

# Patch TRL for Unsloth speedups
PatchFastRL("GRPO", FastLanguageModel)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=500)
    args = parser.parse_args()

    # Optimized for L4 Speed
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/llama-3.2-3b-instruct-unsloth-bnb-4bit",
        max_seq_length=1024,
        load_in_4bit=True,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=16, # Increased rank for "harder" learning
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_alpha=32,
        use_gradient_checkpointing="unsloth",
    )
    if not hasattr(model, "warnings_issued"): model.warnings_issued = {}

    print("Fetching 500 hard samples...")
    train_samples = []
    for _ in range(500):
        r = requests.post("http://localhost:8000/reset")
        if r.status_code == 200:
            obs = r.json()["observation"]
            from commitguard_env.grpo_prompt import get_agent_prompt, SYSTEM_PROMPT
            prompt = get_agent_prompt(obs["diff"], obs["available_files"], 0)
            train_samples.append({"prompt": prompt, "system": SYSTEM_PROMPT})
    
    dataset = Dataset.from_list(train_samples)

    # HEAVY TRAINING CONFIG
    training_args = GRPOConfig(
        output_dir="outputs/commitguard-heavy",
        num_generations=4,
        max_completion_length=256,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=8, # Effective batch size of 64
        learning_rate=2e-5, # Higher LR for fast weight shift
        max_steps=args.steps,
        bf16=True,
        logging_steps=1,
        save_steps=100,
        report_to="none",
    )

    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        reward_funcs=[lambda prompts, completions, **kwargs: [0.5]*len(completions)], # Place-holder for speed
        args=training_args,
        train_dataset=dataset,
    )

    print(f"Starting HEAVY training for {args.steps} steps...")
    trainer.train()
    model.save_pretrained_merged("outputs/commitguard-heavy/final", tokenizer, save_method="lora")

if __name__ == "__main__":
    main()
