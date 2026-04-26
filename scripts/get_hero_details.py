import json
from pathlib import Path

def get_hero_details(sample_id):
    data_path = Path("data/devign_filtered.jsonl")
    with open(data_path, "r") as f:
        for line in f:
            s = json.loads(line)
            if s["sample_id"] == sample_id:
                print(json.dumps(s, indent=2))
                return

if __name__ == "__main__":
    get_hero_details("d9a3b33d2c9f996537b7f1d0246dee2d0120cefb")
