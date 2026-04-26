import torch
print(f"Torch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
try:
    from unsloth import FastLanguageModel
    print("Unsloth imported successfully")
except Exception as e:
    print(f"Error importing Unsloth: {e}")
    import traceback
    traceback.print_exc()
