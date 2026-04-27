import json
import torch
import sys
from transformers import AutoModelForCausalLM, AutoTokenizer
from pathlib import Path

# Add project root for imports
sys.path.append(str(Path(__file__).resolve().parent.parent))
from agent_prompt import SYSTEM_PROMPT

def test_model():
    model_id = "Divyank1607/commitguard-llama-3b-lora"
    print(f"Testing model: {model_id} on CPU")
    
    try:
        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        print("Tokenizer loaded.")
        
        # Load 1 sample from test data
        test_file = "data/devign_test.jsonl"
        with open(test_file, "r", encoding="utf-8") as f:
            sample = json.loads(f.readline())
        print(f"Loaded sample {sample['sample_id']}")
        
        prompt = (
            f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
            f"{SYSTEM_PROMPT}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
            f"Analyze this commit and submit your verdict.\n\n"
            f"Code diff:\n```diff\n{sample['diff']}\n```<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        )
        
        print("Attempting to load model on CPU (this will be slow and use RAM)...")
        # Use low_cpu_mem_usage=True to avoid doubling RAM during load
        model = AutoModelForCausalLM.from_pretrained(
            model_id, 
            device_map="cpu",
            low_cpu_mem_usage=True
        )
        print("Model loaded.")
        
        inputs = tokenizer(prompt, return_tensors="pt").to("cpu")
        print("Generating response (this will take several minutes on CPU)...")
        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=128,
                temperature=0.1,
                do_sample=False,
            )
        
        response = tokenizer.decode(output[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        print("\nModel Response:")
        print("-" * 40)
        print(response)
        print("-" * 40)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_model()
