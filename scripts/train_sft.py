import os
import sys
import json
import argparse
from pathlib import Path

import torch
from datasets import Dataset, load_dataset
from trl import SFTTrainer, SFTConfig
from unsloth import FastLanguageModel

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent_prompt import SYSTEM_PROMPT

# --- Configuration ---
MODEL_NAME = os.getenv("MODEL_NAME", "meta-llama/Llama-3.2-3B-Instruct")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs/commitguard-llama-3b-sft")

def get_formatting_func(tokenizer):
    def formatting_prompts_func(examples):
        instructions = examples["diff"]
        is_vulnerable_list = examples["is_vulnerable"]
        cwe_list = examples["cwe"]
        
        texts = []
        for diff, is_vulnerable, cwe in zip(instructions, is_vulnerable_list, cwe_list):
            vuln_str = "true" if is_vulnerable else "false"
            cwe_str = cwe if cwe and is_vulnerable else "NONE"
            
            if is_vulnerable:
                sketch = f"Attacker targets the vulnerable pattern in the code diff ({cwe_str})."
            else:
                sketch = "No vulnerability identified in the provided code diff."

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Analyze this commit and submit your verdict.\n\nCode diff:\n```diff\n{diff}\n```"},
                {"role": "assistant", "content": f"<action>\n<action_type>verdict</action_type>\n<fields>\n<is_vulnerable>{vuln_str}</is_vulnerable>\n<vuln_type>{cwe_str}</vuln_type>\n<exploit_sketch>{sketch}</exploit_sketch>\n</fields>\n</action>"}
            ]
            
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
            texts.append(text)
        return { "text" : texts }
    return formatting_prompts_func

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=1000)
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--batch-size", type=int, default=2)
    ap.add_argument("--grad-accum", type=int, default=4)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--max-seq-length", type=int, default=2048)
    ap.add_argument("--push-to-hub", action="store_true")
    ap.add_argument("--hub-model-id", type=str, default="inmodel-labs/commitguard-llama-3b-sft")
    args = ap.parse_args()

    # 1. Load Model & Tokenizer
    print(f"Loading {MODEL_NAME} with Unsloth...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=args.max_seq_length,
        load_in_4bit=True,
        token=os.getenv("HF_TOKEN"),
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_alpha=32,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    # 2. Prepare Dataset
    data_path = REPO_ROOT / "data" / "devign_train.jsonl"
    if not data_path.exists():
        print(f"Dataset file {data_path} not found.")
        return

    print(f"Loading SFT samples from {data_path}...")
    dataset = load_dataset("json", data_files=str(data_path), split="train")
    dataset = dataset.select(range(min(args.samples, len(dataset))))
    
    formatting_func = get_formatting_func(tokenizer)
    dataset = dataset.map(formatting_func, batched=True)

    # 3. SFT Config
    training_args = SFTConfig(
        output_dir=OUTPUT_DIR,
        dataset_text_field="text",
        max_seq_length=args.max_seq_length,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        num_train_epochs=args.epochs,
        logging_steps=10,
        save_steps=100,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=3407,
    )

    # 4. Train
    print("Starting Supervised Fine-Tuning...")
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=training_args,
    )
    
    trainer.train()

    # 5. Save
    final_dir = f"{OUTPUT_DIR}/final"
    model.save_pretrained_merged(final_dir, tokenizer, save_method="lora")
    print(f"SFT complete. LoRA adapter saved to {final_dir}")

    if args.push_to_hub:
        print(f"Pushing to HF Hub: {args.hub_model_id}")
        model.push_to_hub(args.hub_model_id, token=True)
        tokenizer.push_to_hub(args.hub_model_id, token=True)

if __name__ == "__main__":
    main()
