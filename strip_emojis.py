import os
import re

def strip_emojis(text):
    # This regex is a simple way to catch most common emojis/non-ascii symbols
    return text.encode('ascii', 'ignore').decode('ascii')

files_to_clean = [
    "tasks_deepak.md",
    "tasks_divyank.md",
    "tasks_niti.md",
    "README_SUBMISSION.md",
    "README.md",
    "prd.md",
    "AGENT.md",
    "GEMINI.md"
]

for filename in files_to_clean:
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        clean_content = strip_emojis(content)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(clean_content)
        print(f"Cleaned {filename}")
