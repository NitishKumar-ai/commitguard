from __future__ import annotations

import sys
from typing import Any

from .agent_prompt import SYSTEM_PROMPT


def format_prompt(diff: str, available_files: list[str] = None) -> str:
    """Format the diff into the expected model prompt."""
    files_str = ", ".join(available_files) if available_files else "None"

    user_prompt = f"""### Input Diff
{diff}

### Environment Info
- Available Files: {files_str}
- Current Step: 0/5

Please provide your next action in XML format:"""

    return (
        f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
        f"{SYSTEM_PROMPT}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
        f"{user_prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
    )

def load_model(model_path: str, is_lora: bool = False, base_model: str = None) -> tuple[Any, Any]:
    """
    Load the LLM and tokenizer for inference.
    """
    try:
        import torch
    except ImportError:
        print("Error: PyTorch is not installed. Please install inference dependencies using: pip install '.[scan]'")
        sys.exit(1)

    if is_lora:
        if not base_model:
            raise ValueError("base_model is required if is_lora=True")
        try:
            from unsloth import FastLanguageModel
            from peft import PeftModel
        except ImportError:
            print("Error: Unsloth/PEFT not installed. Required for LoRA models.")
            sys.exit(1)

        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=base_model,
            max_seq_length=2048,
            load_in_4bit=True,
        )
        model = PeftModel.from_pretrained(model, model_path)
        FastLanguageModel.for_inference(model)
    else:
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError:
            print("Error: Transformers is not installed. Please install inference dependencies using: pip install '.[scan]'")
            sys.exit(1)

        device_map = "auto" if torch.cuda.is_available() else None
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map=device_map
        )
        tokenizer = AutoTokenizer.from_pretrained(model_path)

    return model, tokenizer

def generate(model: Any, tokenizer: Any, prompt: str, max_new_tokens: int = 256) -> str:
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"

    inputs = tokenizer(prompt, return_tensors="pt").to(device)

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
        )

    response = tokenizer.decode(output[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
    return response
