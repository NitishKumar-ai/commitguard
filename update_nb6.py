import json

with open('notebooks/train_commitguard.ipynb', 'r') as f:
    d = json.load(f)

for cell in d['cells']:
    if 'source' in cell:
        for i, line in enumerate(cell['source']):
            if '["<action><action_type>verdict</action_type><is_vulnerable>true</is_vulnerable><vuln_type>CWE-119</vuln_type><exploit_sketch>buffer overflow</exploit_sketch></action>"]' in line:
                cell['source'][i] = line.rstrip() + ',\n'
                if len(cell['source']) > i + 1 and ')' in cell['source'][i+1]:
                    cell['source'].insert(i+1, '    ["test_id"]\n')

with open('notebooks/train_commitguard.ipynb', 'w') as f:
    json.dump(d, f, indent=1)
