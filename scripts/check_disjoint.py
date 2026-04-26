import json
from pathlib import Path

def get_ids(file_path):
    ids = set()
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            obj = json.loads(line)
            ids.add(obj.get('commit_id') or obj.get('sample_id'))
    return ids

train_ids = get_ids('data/devign_train.jsonl')
test_ids = get_ids('data/devign_test.jsonl')

overlap = train_ids.intersection(test_ids)
print(f"Train IDs: {len(train_ids)}")
print(f"Test IDs: {len(test_ids)}")
print(f"Overlap: {len(overlap)}")
if overlap:
    print(f"Overlapping IDs: {list(overlap)[:5]}")
