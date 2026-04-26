import json

with open('notebooks/train_commitguard.ipynb', 'r') as f:
    d = json.load(f)

# Hardcode the HF token and Wandb setting
# Cell 4:
for i, cell in enumerate(d['cells']):
    if "HF_TOKEN = os.getenv" in "".join(cell.get("source", [])):
        d['cells'][i]['source'] = [
            "from huggingface_hub import login\n",
            "\n",
            "HF_TOKEN = \"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\"\n",
            "if HF_TOKEN:\n",
            "    login(token=HF_TOKEN)\n",
            "    print(\"Logged in via token.\")\n",
            "else:\n",
            "    login()\n"
        ]
    if "USE_WANDB = True" in "".join(cell.get("source", [])):
        d['cells'][i]['source'] = [
            "import wandb\n",
            "\n",
            "USE_WANDB = False\n",
            "os.environ[\"WANDB_DISABLED\"] = \"true\"\n",
            "print(\"Wandb disabled.\")\n"
        ]

# Cell 8 (now with localtunnel wget instead of git clone):
for i, cell in enumerate(d['cells']):
    if "google.colab" in "".join(cell.get("source", [])):
        d['cells'][i]['source'] = [
            "import os, subprocess, time, requests, sys\n",
            "\n",
            "# Check if running in Google Colab\n",
            "if \"google.colab\" in sys.modules:\n",
            "    print(\"Running in Google Colab. Downloading local repository...\")\n",
            "    if not os.path.exists(\"commitguard\"):\n",
            "        os.makedirs(\"commitguard\", exist_ok=True)\n",
            "        !wget -q --header=\"Bypass-Tunnel-Reminder: true\" -O project.zip https://ready-pens-call.loca.lt/project.zip\n",
            "        !unzip -q project.zip -d commitguard\n",
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
