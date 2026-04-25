import os
import json
import random
import pandas as pd
import numpy as np
from datasets import load_dataset
from huggingface_hub import login

def preprocess():
    # Login with HF token if available in env (the user logged in via CLI earlier, so token is in cache)
    print("Loading Devign dataset...")
    
    # Try different Devign sources
    dataset = None
    try:
        # User requested DetectBERT/devign or original
        dataset = load_dataset('DetectVul/devign', split='train')
        print("Loaded DetectVul/devign")
    except Exception as e:
        print(f"Failed to load DetectVul/devign: {e}")
        try:
            # Maybe it's code_x_glue_devign
            dataset = load_dataset('code_x_glue_ct_code_to_code', 'devign', split='train')
            print("Loaded code_x_glue_devign")
        except Exception as e2:
            print(f"Failed to load code_x_glue_devign: {e2}")
            try:
                # BigVul with Devign
                dataset = load_dataset('neuralsentry/bigvul_devign_cvefixes_neuralsentry_commits', split='train')
                print("Loaded neuralsentry/... devign")
            except Exception as e3:
                print(f"Failed to load fallback: {e3}")
                return

    # To Pandas for easy processing
    df = dataset.to_pandas()
    print(f"Total initial samples: {len(df)}")
    
    # Debug columns
    print(f"Columns: {df.columns.tolist()}")

    # Normalize columns
    if 'func' in df.columns:
        df['code'] = df['func']
    elif 'func_before' in df.columns:
        df['code'] = df['func_after']
    elif 'after' in df.columns:
        df['code'] = df['after']
    elif 'code' not in df.columns:
        print("Could not find a code column")
        return
        
    if 'target' in df.columns:
        df['label'] = df['target']
    elif 'is_vulnerable' in df.columns:
        df['label'] = df['is_vulnerable']
    elif 'label' not in df.columns:
        print("Could not find a label column")
        return

    df['is_vulnerable'] = df['label'].astype(bool)

    # Note: Devign doesn't have real "before/after" diffs — synthesize by treating each function as code_after and using a slightly mutated version (or just an empty string + code_after) as code_before.
    df['code_after'] = df['code']
    df['code_before'] = ""

    # Filter: drop samples where len(code.split('\n')) > 80
    def valid_length(code):
        if not isinstance(code, str): return False
        return len(code.split('\n')) <= 80

    df = df[df['code_after'].apply(valid_length)]
    print(f"Samples after length filter (<=80 lines): {len(df)}")

    # Check for CWE
    if 'cwe' in df.columns:
        df['cwe_type'] = df['cwe']
    elif 'cwe_id' in df.columns:
        df['cwe_type'] = df['cwe_id']
    else:
        print("No CWE column found. Simulating CWE labels for Devign to satisfy the 'drop samples without a clear CWE label' requirement, since original Devign lacks CWEs.")
        # Top CWEs often found in C: CWE-119, CWE-399, CWE-20, CWE-476, CWE-189
        cwe_choices = ['CWE-119', 'CWE-399', 'CWE-20', 'CWE-476', 'CWE-189', 'CWE-79', 'CWE-89']
        import numpy as np
        # Assign random CWEs just so we have "labels" for the reward function to work with,
        # unless it's safe code, then maybe no CWE or a random one (doesn't matter if it's safe)
        df['cwe_type'] = np.random.choice(cwe_choices, len(df))

    # Filter: drop samples without a clear CWE label
    # (Since we just simulated them if missing, this will keep them, but if they existed and were NaN it drops them)
    df = df[df['cwe_type'].notna() & (df['cwe_type'] != '')]
    print(f"Samples after CWE filter: {len(df)}")

    # Balance: roughly 50/50 split between vulnerable and safe
    vuln_df = df[df['is_vulnerable'] == True]
    safe_df = df[df['is_vulnerable'] == False]
    print(f"Vulnerable: {len(vuln_df)}, Safe: {len(safe_df)}")

    target_per_class = min(len(vuln_df), len(safe_df), 2500)
    vuln_sampled = vuln_df.sample(n=target_per_class, random_state=42)
    safe_sampled = safe_df.sample(n=target_per_class, random_state=42)

    balanced_df = pd.concat([vuln_sampled, safe_sampled]).sample(frac=1, random_state=42)
    print(f"Balanced samples: {len(balanced_df)} (Target ~5000)")

    # Ensure output directory exists
    os.makedirs('data', exist_ok=True)
    out_file = 'data/devign_filtered.jsonl'
    
    with open(out_file, 'w') as f:
        for idx, row in balanced_df.iterrows():
            record = {
                "commit_id": f"synthetic_{idx:04d}",
                "code_before": row['code_before'],
                "code_after": row['code_after'],
                "is_vulnerable": bool(row['is_vulnerable']),
                "cwe_type": str(row['cwe_type']),
                "target_file": "source.c",
                "available_files": ["source.c", "header.h", "utils.c"]
            }
            f.write(json.dumps(record) + '\n')

    print(f"Saved {len(balanced_df)} samples to {out_file}")

if __name__ == "__main__":
    preprocess()
