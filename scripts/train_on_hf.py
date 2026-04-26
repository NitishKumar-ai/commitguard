import argparse
import os
import sys
import requests
from pathlib import Path
from datasets import Dataset
from trl import GRPOConfig, GRPOTrainer
from unsloth import FastLanguageModel, PatchFastRL
from huggingface_hub import login

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from commitguard_env.grpo_prompt import SYSTEM_PROMPT, get_agent_prompt

# Patch TRL for Unsloth speedups
PatchFastRL("GRPO", FastLanguageModel)

def get_reward_from_env_base(env_url):
    def reward_fn(prompts, completions, **kwargs) -> list[float]:
        rewards = []
        for completion in completions:
            try:
                payload = {"action": completion}
                r = requests.post(f"{env_url}/step", json=payload, timeout=15)
                if r.status_code == 200:
                    rewards.append(float(r.json().get("reward", 0.0)))
                else:
                    rewards.append(-0.5)
            except Exception:
                rewards.append(-1.0)
        return rewards
    return reward_fn

def main():
    parser = argparse.ArgumentParser(description="CommitGuard GRPO Trainer for Hugging Face Hub Jobs")
    parser.add_argument("--model_name", type=str, default=os.getenv("MODEL_NAME", "meta-llama/Llama-3.2-3B-Instruct"))
    parser.add_argument("--output_dir", type=str, default="outputs/commitguard-hf")
    parser.add_argument("--steps", type=int, default=int(os.getenv("STEPS", "500")))
    parser.add_argument("--env_url", type=str, default=os.getenv("ENV_URL", "http://localhost:8000"))
    parser.add_argument("--hf_repo", type=str, default=os.getenv("HF_REPO"))
    parser.add_argument("--wandb", type=str, default=os.getenv("WANDB_PROJECT", "commitguard-rlvr"))
    parser.add_argument("--num_generations", type=int, default=int(os.getenv("NUM_GENERATIONS", "4")))
    args = parser.parse_args()

    # 0. Auth
    hf_token = os.getenv("HF_TOKEN")
    if hf_token:
        login(token=hf_token)
    
    if args.wandb:
        os.environ["WANDB_PROJECT"] = args.wandb
        if os.getenv("WANDB_API_KEY"):
            import wandb
            wandb.login(key=os.getenv("WANDB_API_KEY"))

    print(f"--- Training Config ---")
    print(f"Model: {args.model_name}")
    print(f"Steps: {args.steps}")
    print(f"Env URL: {args.env_url}")
    print(f"HF Repo: {args.hf_repo}")
    print(f"-----------------------")

    # 1. Load Model and Tokenizer with Unsloth
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model_name,
        max_seq_length=2048,
        load_in_4bit=True,
        fast_inference=False,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=8,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )
    
    if not hasattr(model, "warnings_issued"):
        model.warnings_issued = {}

    # 2. Prepare Dataset from Environment
    print(f"Fetching {args.steps} samples from environment...")
    train_samples = []
    # Fetching in bulk might be faster, but let's stick to the current logic for compatibility
    for _ in range(min(args.steps, 1000)): 
        try:
            r = requests.post(f"{args.env_url}/reset", timeout=10)
            if r.status_code == 200:
                obs = r.json()["observation"]
                prompt = get_agent_prompt(obs["diff"], obs["available_files"], obs["step_idx"])
                train_samples.append({"prompt": prompt, "system": SYSTEM_PROMPT})
        except Exception as e:
            print(f"Warning: Failed to fetch sample: {e}")
            break
    
    if not train_samples:
        print("Error: No training samples fetched. Check ENV_URL.")
        sys.exit(1)

    dataset = Dataset.from_list(train_samples)

    # 3. Configure GRPO
    training_args = GRPOConfig(
        output_dir=args.output_dir,
        num_generations=args.num_generations,
        max_completion_length=512,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        learning_rate=5e-6,
        logging_steps=1,
        save_steps=100,
        max_steps=args.steps,
        report_to="wandb" if os.getenv("WANDB_API_KEY") else "none",
        bf16=True,
        push_to_hub=True if args.hf_repo else False,
        hub_model_id=args.hf_repo,
        hub_strategy="end",
    )

    # 4. Initialize Trainer
    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        reward_funcs=[get_reward_from_env_base(args.env_url)],
        args=training_args,
        train_dataset=dataset,
    )

    # 5. Launch Training
    print("Starting GRPO Training...")
    trainer.train()

    # 6. Final Push
    if args.hf_repo:
        print(f"Pushing final adapter to {args.hf_repo}...")
        model.push_to_hub(args.hf_repo, token=hf_token)
        tokenizer.push_to_hub(args.hf_repo, token=hf_token)
    else:
        final_path = os.path.join(args.output_dir, "final")
        model.save_pretrained_merged(final_path, tokenizer, save_method="lora")
        print(f"Saved locally to {final_path}")

if __name__ == "__main__":
    main()
