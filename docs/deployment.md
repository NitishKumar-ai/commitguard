# 🚀 CommitGuard — Comprehensive GCP Deployment & Training Guide (A10G)

This document is a deep-dive, step-by-step manual for deploying the CommitGuard environment and training pipeline to a Google Cloud Platform (GCP) instance. We are targeting an **NVIDIA A10G GPU** to execute **GRPO (Group Relative Policy Optimization)** on the Llama-3.2-3B model.

---

## 📋 1. Prerequisites: Setting Up Your Toolbox
Before you touch the cloud, you must ensure your local environment and external accounts are configured. These are the building blocks of the entire run.

### A. GCP Account & Project Setup
*   **Active Project:** You must have a GCP project created. Note your `PROJECT_ID`.
*   **GPU Quota:** By default, GCP projects have 0 quota for GPUs. You must navigate to `IAM & Admin > Quotas` and request a limit increase for `NVIDIA_A10G_GPUS` in your desired region (e.g., `us-central1`). **Do this 24 hours in advance.**

### B. Weights & Biases (WandB) for Visualization
*   **Why?** RL training can be unstable. WandB allows you to monitor the "Reward" and "KL Divergence" curves in real-time from your browser.
*   **Action:** Create a free account at [wandb.ai](https://wandb.ai), navigate to your settings, and copy your **API Key**.

### C. Hugging Face Account & Llama Access
*   **Model Gating:** Llama-3.2-3B is a gated model. You must visit the [model page](https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct) and apply for access. Approval usually takes 30-60 minutes.
*   **Access Token:** Generate a "Write" token in your Hugging Face settings to allow the VM to download the model and upload your finished adapters.

### D. Local gcloud CLI Initialization
*   **Installation:** Install the Google Cloud SDK on your laptop.
*   **Authentication:** Run `gcloud auth login` and `gcloud config set project [YOUR_PROJECT_ID]`. This allows your local terminal to "talk" to GCP.

---

## 🛠 Step 1: Provisioning the High-Performance VM
We are using the **G2 Standard 4** machine. It is specifically designed for AI workloads.

### Detailed Breakdown of the Creation Command
*   **`--machine-type g2-standard-4`:** Provides 4 vCPUs and 16GB of system RAM, ensuring the CPU doesn't bottleneck the GPU.
*   **`--accelerator type=nvidia-a10g,count=1`:** Attaches the A10G GPU. Its 24GB of VRAM is the "Goldilocks" zone for 3B parameter models—enough to handle the model plus the multiple "generations" required by the GRPO algorithm.
*   **`--image-family common-cu121`:** Uses a specialized Google image that comes with **CUDA 12.1 and NVIDIA drivers pre-installed**. This saves you 30 minutes of manual driver installation.
*   **`--provisioning-model=SPOT`:** **CRITICAL FOR BUDGET.** Spot instances use excess capacity and are ~70% cheaper than standard instances. If the instance is reclaimed by Google, your 50-step checkpoints ensure you don't lose much progress.

```bash
gcloud compute instances create commitguard-trainer \
    --project=[PROJECT_ID] \
    --zone=us-central1-a \
    --machine-type=g2-standard-4 \
    --accelerator=count=1,type=nvidia-a10g \
    --image-project=ml-images \
    --image-family=common-cu121 \
    --boot-disk-size=100GB \
    --boot-disk-type=pd-balanced \
    --maintenance-policy=TERMINATE \
    --provisioning-model=SPOT
```

---

## 🏗 Step 2: Environment Preparation
Once the VM is "Running," we need to turn it into a specialized CommitGuard lab.

### A. Secure Connection (SSH)
Connect to the machine's terminal:
```bash
gcloud compute ssh commitguard-trainer --zone=us-central1-a
```

### B. Repository & Virtual Environment
We isolate our dependencies to prevent conflicts with system-level Python packages.
```bash
# Clone the project
git clone https://github.com/[YOUR_USER]/commitguard.git
cd commitguard

# Create a 'venv' (Virtual Environment)
python3 -m venv .venv
source .venv/bin/activate

# Authenticate with Hugging Face (Required for gated Llama models)
huggingface-cli login
```

### C. Installing the "Train" Stack
The `-e ".[train]"` command installs the `commitguard` package in "editable" mode along with all optional training libraries like `torch`, `peft`, and `trl`.
```bash
pip install -U pip
pip install -e ".[train]"

# Flash Attention 2: This is a specialized kernel that makes Llama training 
# significantly faster and more memory-efficient on A10G hardware.
pip install flash-attn --no-build-isolation
```

---

## 📡 Step 3: Launching the Verifiable Reward Server
CommitGuard uses **RLVR**. In this setup, the model doesn't just "guess" if it's right; it submits an action to a server that calculates a reward based on hard evidence.

### Running in the Background
Since training takes hours, we run the server in the background using the `&` symbol.
```bash
# Start the server
python -m commitguard_env.server &

# Verify Health: This ensures the database and API are ready.
# If this fails, the trainer will hang indefinitely.
curl http://localhost:8000/health
# You should see: {"status":"healthy"}
```

---

## 🧠 Step 4: Executing the GRPO Training Run
GRPO is a "reinforcement learning" algorithm. It asks the model to generate 4 different answers for the same code diff, compares them to each other, and rewards the ones that follow the XML format and correctly identify the vulnerability.

### Hyperparameter Explanation
*   **`--steps 500`:** The model will see roughly 2,000 examples (4 generations x 500 steps).
*   **`4-bit Quantization`:** Automatically handled by the script. It "compresses" the model weights so they fit into the GPU's memory without losing accuracy.
*   **`LoRA r=8`:** "Low-Rank Adaptation." Instead of training 3 billion parameters, we only train about 5 million. This makes training stable and fast.
*   **`--live`:** Tells the script to fetch rewards from the server we started in Step 3.

```bash
# Login to WandB so your graphs show up online
export WANDB_API_KEY=[YOUR_WANDB_KEY]

python scripts/train_grpo.py \
    --model_name "meta-llama/Llama-3.2-3B-Instruct" \
    --output_dir "./outputs/commitguard-final" \
    --steps 500 \
    --live \
    --wandb "commitguard-rlvr"
```

---

## 💾 Step 5: Post-Run Weight Management & Cleanup
Once the 500 steps are complete, the "brain" of your agent exists as a LoRA adapter in the `./outputs` folder.

### A. Permanent Storage (Hugging Face)
The VM's disk is temporary. Move your weights to Hugging Face immediately.
```bash
huggingface-cli login --token [YOUR_HF_TOKEN]
huggingface-cli upload [HF_USERNAME]/commitguard-llama3b-adapter ./outputs/commitguard-final
```

### B. Cost Control: Deleting the VM
**DO NOT FORGET THIS STEP.** An idle A10G instance costs money every hour.
```bash
# Exit the VM
exit

# Delete from your local terminal
gcloud compute instances delete commitguard-trainer --zone=us-central1-a
```

---

## 🆘 Critical Troubleshooting

### "CUDA Out of Memory"
*   **Symptom:** Training crashes with a long error ending in `OutOfMemoryError`.
*   **Fix:** The "Group" in GRPO is currently set to 4 generations. Open `scripts/train_grpo.py` and change `num_generations=4` to `num_generations=2`. This cuts memory usage in half.

### "Connection Refused"
*   **Symptom:** Reward function returns -1.0 for everything or throws errors.
*   **Fix:** Your environment server crashed or wasn't started. Run `ps aux | grep server` to check if it is still running.

### The "Midnight Fallback"
If the 3B model is too slow for the submission deadline:
*   Switch to the **1.5B Qwen** model. It uses the same XML format but is 2x faster.
*   Command: `python scripts/train_grpo.py --model_name "Qwen/Qwen2.5-1.5B-Instruct" ...`

---

## ✅ Final Success Checklist
1. [ ] **Health Check:** `curl` returns healthy.
2. [ ] **WandB Tracking:** You can see the `reward` curve moving on the website.
3. [ ] **Checkpoints:** You see folders like `checkpoint-50`, `checkpoint-100` in the output directory.
4. [ ] **Clean Exit:** The VM is deleted after the adapter is uploaded to Hugging Face.
