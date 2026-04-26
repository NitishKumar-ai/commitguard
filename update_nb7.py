import json

with open('notebooks/train_commitguard.ipynb', 'r') as f:
    d = json.load(f)

for cell in d['cells']:
    if 'source' in cell:
        source_code = "".join(cell['source'])
        if 'samples.append({' in source_code and 'SYSTEM_PROMPT' in source_code:
            # We found Cell 7
            new_source = []
            for line in cell['source']:
                if 'user_msg = get_agent_prompt' in line:
                    new_source.append('    state_r = requests.get(f"{ENV_URL}/state").json()\n')
                    new_source.append('    current_sample_id = state_r.get("state", {}).get("current_sample_id", "unknown")\n')
                    new_source.append(line)
                elif '        ],\\n' in line or '        ],\n' in line:
                    new_source.append(line)
                    new_source.append('        "sample_id": current_sample_id,\n')
                else:
                    new_source.append(line)
            cell['source'] = new_source

with open('notebooks/train_commitguard.ipynb', 'w') as f:
    json.dump(d, f, indent=1)
