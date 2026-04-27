import os
from huggingface_hub import HfApi

HF_TOKEN = "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" 

api = HfApi(token=HF_TOKEN)
REPO_ID = "Divyank1607/commitguard-data"

print(f"Starting upload process for {REPO_ID}...")

# 1. Create the repo
try:
    api.create_repo(repo_id=REPO_ID, repo_type="dataset", private=True, exist_ok=True)
    print(f"Verified repository: {REPO_ID}")
except Exception as e:
    print(f"Note on repo: {e}")

# 2. Upload the file
try:
    print("Uploading data/devign_train.jsonl... (this may take a minute)")
    api.upload_file(
        path_or_fileobj="data/devign_train.jsonl",
        path_in_repo="devign_train.jsonl",
        repo_id=REPO_ID,
        repo_type="dataset",
    )
    print("✅ Upload successful!")
except Exception as e:
    print(f"❌ Upload failed: {e}")
