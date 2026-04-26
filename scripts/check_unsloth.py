import torch
from unsloth import FastLanguageModel

try:
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/Llama-3.2-1B-Instruct-bnb-4bit",
        max_seq_length=1024,
        load_in_4bit=True,
    )
    print("Successfully loaded model in 4-bit on this GPU.")
    print(f"Memory allocated: {torch.cuda.memory_allocated() / 1024**2:.1f} MB")
except Exception as e:
    print(f"Failed to load model: {e}")
