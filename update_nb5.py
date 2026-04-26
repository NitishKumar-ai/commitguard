import json

with open('notebooks/train_commitguard.ipynb', 'r') as f:
    d = json.load(f)

for cell in d['cells']:
    if 'source' in cell:
        for i, line in enumerate(cell['source']):
            if 'fast_inference=True' in line:
                cell['source'][i] = line.replace('fast_inference=True', 'fast_inference=False')

with open('notebooks/train_commitguard.ipynb', 'w') as f:
    json.dump(d, f, indent=1)
