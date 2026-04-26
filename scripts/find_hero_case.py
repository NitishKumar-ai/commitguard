import json
from pathlib import Path

def find_hero_case():
    data_path = Path("data/devign_filtered.jsonl")
    if not data_path.exists():
        print("Data not found.")
        return

    with open(data_path, "r") as f:
        samples = [json.loads(line) for line in f]

    # Filter for interesting CWEs (SQLi, Command Injection, etc.)
    hero_candidates = [
        s for s in samples 
        if s["is_vulnerable"] and s["cwe"] in ["CWE-89", "CWE-78", "CWE-22", "CWE-119"]
    ]

    print(f"Found {len(hero_candidates)} hero candidates.")
    
    for s in hero_candidates[:5]:
        print("-" * 40)
        print(f"Sample ID: {s['sample_id']}")
        print(f"CWE: {s['cwe']}")
        print(f"Diff Context:\n{s['diff'][:300]}...")
        print("-" * 40)

if __name__ == "__main__":
    find_hero_case()
