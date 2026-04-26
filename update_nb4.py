import json

with open('notebooks/train_commitguard.ipynb', 'r') as f:
    d = json.load(f)

for i, cell in enumerate(d['cells']):
    if "google.colab" in "".join(cell.get("source", [])):
        d['cells'][i]['source'] = [
            "import os, subprocess, time, requests, sys\n",
            "\n",
            "# Check if running in Google Colab\n",
            "if \"google.colab\" in sys.modules:\n",
            "    print(\"Running in Google Colab.\")\n",
            "    # Reset to base directory in case cell is run multiple times\n",
            "    os.chdir(\"/content\")\n",
            "    \n",
            "    if not os.path.exists(\"/content/project.zip\"):\n",
            "        from google.colab import files\n",
            "        print(\"\\n--- WE NEED YOUR PROJECT.ZIP ---\")\n",
            "        print(\"Please click 'Choose Files' below and select project.zip from your computer:\\n\")\n",
            "        uploaded = files.upload()\n",
            "    \n",
            "    if os.path.exists(\"/content/project.zip\"):\n",
            "        print(\"Extracting project.zip...\")\n",
            "        !unzip -q -o /content/project.zip -d /content/commitguard\n",
            "    else:\n",
            "        print(\"\\n*** ERROR: project.zip still not found! ***\\n\")\n",
            "        sys.exit(1)\n",
            "        \n",
            "    os.chdir(\"/content/commitguard\")\n",
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
