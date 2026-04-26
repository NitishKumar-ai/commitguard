import json
import os

target_id = "2bf3aa85f08186b8162b76e7e8efe5b5a44306a6"
data_dir = r"c:\Users\DIVYANK BHARDWAJ\Desktop\hackathon project\commitguard\data"
files = ["devign_test.jsonl", "devign_filtered.jsonl"]

found = False
for filename in files:
    path = os.path.join(data_dir, filename)
    if not os.path.exists(path):
        continue
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            if data.get("sample_id") == target_id:
                print(json.dumps(data, indent=2))
                found = True
                break
    if found:
        break

if not found:
    print(f"Sample {target_id} not found in {files}")
