from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Add project root to path for imports to find agent_prompt if run directly
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    from agent_prompt import SYSTEM_PROMPT
except ImportError:
    # Fallback if not found
    SYSTEM_PROMPT = """You are a senior security researcher and pentester. Your task is to analyze code commits (diffs) to determine if they introduce exploitable vulnerabilities.

You operate in a multi-step environment (up to 5 steps). You can request more context, analyze your thoughts, or issue a final verdict.

### Action Format
You MUST respond with exactly ONE action per turn, wrapped in XML tags:

1. **Request Context:** Use this if you need to see the full content of a file listed in 'available_files'.
<action>
<action_type>request_context</action_type>
<file_path>filename.c</file_path>
</action>

2. **Analyze:** Use this for your internal Chain-of-Thought reasoning. Be detailed.
<action>
<action_type>analyze</action_type>
<reasoning>Your detailed step-by-step security analysis here...</reasoning>
</action>

3. **Verdict:** Use this to terminate the episode with your final judgment.
<action>
<action_type>verdict</action_type>
<is_vulnerable>true/false</is_vulnerable>
<vuln_type>CWE-XX (e.g., CWE-89)</vuln_type>
<exploit_sketch>Brief description of how this could be exploited...</exploit_sketch>
</action>

### Rules & Constraints
- If the code is safe, set is_vulnerable to false and vuln_type to NONE.
- Be specific in exploit_sketch: name the attack vector (e.g., buffer overflow via unchecked memcpy).
- Common CWE types: CWE-89 (SQLi), CWE-79 (XSS), CWE-78 (Command Inj), CWE-22 (Path Traversal), CWE-119 (Buffer Overflow), CWE-476 (Null Dereference), CWE-190 (Integer Overflow).
- You have a maximum of 5 steps per episode.
- Context requests have a small cost; be efficient.
- Verifiable rewards (RLVR) are based on the accuracy of your final verdict and the presence of correct exploit keywords.
"""


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
    import torch
    
    if is_lora:
        if not base_model:
            raise ValueError("base_model is required if is_lora=True")
        from unsloth import FastLanguageModel
        from peft import PeftModel
        
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=base_model,
            max_seq_length=2048,
            load_in_4bit=True,
        )
        model = PeftModel.from_pretrained(model, model_path)
        FastLanguageModel.for_inference(model)
    else:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        
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
            temperature=0.1,
            do_sample=False,
        )
        
    response = tokenizer.decode(output[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
    return response
