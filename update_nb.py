import json
import os

with open('notebooks/train_commitguard.ipynb', 'r') as f:
    d = json.load(f)

# Cell 3 is installing unsloth
d['cells'][3]['source'] = [
    "!pip install -q unsloth\n",
    "!pip uninstall unsloth -y && pip install -q --upgrade --no-cache-dir \"unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git\"\n",
    "!pip install -q trl>=0.12 peft bitsandbytes transformers datasets accelerate wandb fastapi uvicorn[standard] requests matplotlib"
]

# Cell 8 is setting up repo (Wait, let's find the correct cell index)
cell_idx = 0
for i, cell in enumerate(d['cells']):
    if "import os, subprocess, time, requests, sys" in "".join(cell.get("source", [])):
        cell_idx = i
        break

d['cells'][cell_idx]['source'] = [
    "import os, subprocess, time, requests, sys\n",
    "\n",
    "# Check if running in Google Colab\n",
    "if \"google.colab\" in sys.modules:\n",
    "    print(\"Running in Google Colab. Cloning repository...\")\n",
    "    if not os.path.exists(\"commitguard\"):\n",
    "        !git clone -b Divyank1 https://github.com/NitishKumar-ai/commitguard.git\n",
    "    os.chdir(\"commitguard\")\n",
    "    REPO_DIR = os.getcwd()\n",
    "else:\n",
    "    if os.path.basename(os.getcwd()) == \"notebooks\":\n",
    "        REPO_DIR = os.path.abspath(\"..\")\n",
    "    else:\n",
    "        REPO_DIR = os.getcwd()\n",
    "    os.chdir(REPO_DIR)\n",
    "\n",
    "print(f\"Using REPO_DIR: {REPO_DIR}\")\n",
    "\n",
    "# 2. Install current project in editable mode\n",
    "!pip install -e . -q\n",
    "\n",
    "# 3. Start env server in background\n",
    "server_proc = subprocess.Popen(\n",
    "    [sys.executable, \"-m\", \"commitguard_env.server\"],\n",
    "    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True\n",
    ")\n",
    "time.sleep(5)\n",
    "\n",
    "try:\n",
    "    r = requests.get(\"http://localhost:8000/health\")\n",
    "    print(f\"Env server: {r.json()}\")\n",
    "except Exception as e:\n",
    "    print(f\"Server failed to start: {e}\")\n",
    "    stdout, stderr = server_proc.communicate(timeout=1)\n",
    "    print(f\"STDOUT: {stdout}\")\n",
    "    print(f\"STDERR: {stderr}\")\n",
    "\n",
    "# Quick sanity  reset + step\n",
    "r = requests.post(\"http://localhost:8000/reset\", json={})\n",
    "obs = r.json()[\"observation\"]\n",
    "print(f\"Sample diff length: {len(obs['diff'])} chars, files: {obs['available_files']}\")\n"
]

with open('notebooks/train_commitguard.ipynb', 'w') as f:
    json.dump(d, f, indent=1)
