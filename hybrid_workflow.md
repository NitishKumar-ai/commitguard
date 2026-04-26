# 🔗 CommitGuard — Server-to-Plugin Hybrid Workflow

This document details the end-to-end integration of the **CommitGuard Gymnasium** (hosted on Hugging Face) with the **Developer Plugin** (running locally). This setup realizes the project's core vision: **Commit-Time Security at AI Speed.**

---

## 🏗 Stage 1: Deploying the Gymnasium (The Server)
The "Gymnasium" is the Meta OpenEnv server. It hosts the code diffs, tracks the multi-step agent state, and calculates the RLVR rewards.

### 1.1 Local Preparation
Ensure your `openenv.yaml` is configured with the correct name and metadata.
```yaml
# openenv.yaml
name: commitguard
version: 0.1.0
entrypoint: server
```

### 1.2 Push to Hugging Face Spaces
Use the `openenv` CLI to bundle the project into a Docker container and upload it to a Space.
```bash
# Login to Hugging Face
huggingface-cli login

# Push the environment
# Replace [USER] with your HF username
openenv push --space [USER]/commitguard-gym
```

### 1.3 Verification
Once the Space build is complete:
1.  Open the Space in your browser. You should see the **OpenEnv Gymnasium UI**.
2.  Test the `/health` endpoint:
    `curl https://[USER]-commitguard-gym.hf.space/health`
    *Expected:* `{"status": "healthy"}`

---

## 🧠 Stage 2: Connecting the Trained Model
Your trained Llama-3.2-3B model (or its LoRA adapter) needs to know where to "play."

### 2.1 Configuration
Update your local environment or training script to point to the live HF Space instead of `localhost`.
```bash
export COMMITGUARD_ENV_URL="https://[USER]-commitguard-gym.hf.space"
```

### 2.2 Model Inference Hook
The model takes the local code diff as input and emits an XML action.
- **CLI Mode:** `python scripts/evaluate.py --env_url $COMMITGUARD_ENV_URL`
- **Plugin Mode:** The plugin script captures the diff and calls the model.

---

## 🛠 Stage 3: Setting up the Developer Plugin (Git Hook)
We will implement a local Git `pre-commit` hook that invokes the model and consults the HF Gymnasium for a verdict.

### 3.1 Create the Hook Script
Save this as `.git/hooks/pre-commit` and make it executable (`chmod +x`).

```bash
#!/bin/bash

# 1. Capture the staged diff
DIFF=$(git diff --cached)

# 2. Invoke the CommitGuard Agent
# This script sends the diff to your model (running locally or via API)
# which then interacts with the HF Gymnasium Space.
VERDICT_JSON=$(python scripts/evaluate_single_diff.py --diff "$DIFF")

# 3. Parse the Verdict
IS_VULNERABLE=$(echo $VERDICT_JSON | jq -r '.is_vulnerable')
REASONING=$(echo $VERDICT_JSON | jq -r '.reasoning')

# 4. Block or Allow
if [ "$IS_VULNERABLE" == "true" ]; then
    echo "❌ [CommitGuard] VULNERABILITY DETECTED"
    echo "Reasoning: $REASONING"
    echo "Commit blocked. Please fix the security issue and try again."
    exit 1
else
    echo "✅ [CommitGuard] No vulnerabilities detected. Proceeding..."
    exit 0
fi
```

---

## 🔄 Stage 4: The End-to-End Execution Cycle

1.  **Developer writes code:** E.g., adding an unsanitized SQL query to `db.py`.
2.  **Developer runs `git commit`:** The pre-commit hook triggers.
3.  **The Plugin acts:** 
    - It sends the diff to the **Hugging Face Gymnasium**.
    - The Gymnasium generates an **Observation** (diff + available files).
    - The **Trained Model** processes the observation and generates a **Verdict** action.
    - The Gymnasium calculates the **Reward/Verdict** based on ground truth.
4.  **The Verdict returns:** The hook receives `is_vulnerable: true`.
5.  **The Commit is blocked:** The developer sees the exploit sketch in their terminal and the code never hits the repo.

---

## 🎥 Demonstration Tips for Judges
For the demo video, use a **split-screen** view:
- **Left Side:** The Hugging Face Space UI showing the "Gymnasium" state updating.
- **Right Side:** Your local Terminal showing the `git commit` being blocked by the plugin.
- **Outcome:** This proves that your RL agent has learned to use the Gymnasium's verifiable rewards to protect a real developer workflow.
