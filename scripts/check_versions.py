# /// script
# dependencies = [
#   "unsloth",
#   "torch",
#   "trl",
#   "transformers",
#   "setuptools",
# ]
# ///
import unsloth
import torch
import trl
import transformers
print(f"Unsloth imported successfully")
print(f"Torch: {torch.__version__}")
print(f"TRL: {trl.__version__}")
print(f"Transformers: {transformers.__version__}")
