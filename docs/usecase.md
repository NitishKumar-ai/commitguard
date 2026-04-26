# CommitGuard — Use Cases & Test Scenarios

This document outlines the primary use cases and associated test scenarios for running CommitGuard as a standalone Command Line Interface (CLI) tool and as an integrated Plugin (e.g., CI/CD Pipeline or IDE Extension).

## 1. CommitGuard as a CLI (Standalone Workflow)
This use case is for security researchers, data scientists, and ML engineers training or evaluating the model locally or on a dedicated VM.

### 1.1 Data Preprocessing
- **Scenario:** Convert raw Devign JSON into a filtered, balanced, 5000-sample JSONL file.
- **Action:** Run `python scripts/preprocess_devign.py --limit 5000`
- **Expected Result:** `data/devign_filtered.jsonl` is created with clean, XML-ready code diffs and valid `cwe` labels.

### 1.2 Environment Server (OpenEnv)
- **Scenario:** Start the RLVR training environment.
- **Action:** Run `python -m commitguard_env.server`
- **Expected Result:** Server starts on port 8000. `curl http://localhost:8000/health` returns `{"status": "healthy"}`. `tests/test_no_leak.py` confirms no label leakage in `/reset` or `/state`.

### 1.3 Model Training (GRPO)
- **Scenario:** Train the Llama-3.2-3B model using the live RLVR environment.
- **Action:** Run `python scripts/train_grpo.py --live --steps 500`
- **Expected Result:** Model trains using 4-bit quantization and LoRA. Training curve uploads to WandB. Checkpoints save every 50 steps.

### 1.4 Agentic Evaluation
- **Scenario:** Evaluate the trained LoRA adapter on 100 held-out test samples.
- **Action:** Run `python scripts/evaluate.py --adapter_path ./outputs/commitguard-final`
- **Expected Result:** The agent executes a 5-step loop (request_context -> analyze -> verdict). A detailed `eval_results.json` report is generated showing accuracy per CWE.

### 1.5 Visualization
- **Scenario:** Generate performance plots for reporting.
- **Action:** Run `python plots/plot_baseline_vs_trained.py`
- **Expected Result:** A PNG bar chart is saved showing the clear accuracy delta between baseline and trained model.

---

## 2. CommitGuard as a Plugin (Developer Workflow)
This use case is for software engineers interacting with the trained model during their daily development cycle to prevent vulnerabilities from reaching production.

### 2.1 Git Pre-Commit Hook (Local Plugin)
- **Scenario:** A developer attempts to commit code containing an SQL injection (e.g., `CWE-89`).
- **Action:** Developer runs `git commit -m "Update user query"`. The hook captures the local diff and invokes the CommitGuard agent API.
- **Expected Result:**
  - The agent detects the vulnerability before the commit executes.
  - The commit is **blocked** (exit code 1).
  - The terminal outputs the agent's XML `exploit_sketch`: `"SQL injection in user_id via f-string construction."`

### 2.2 CI/CD Pull Request Reviewer (GitHub Action)
- **Scenario:** A developer opens a Pull Request with a new feature.
- **Action:** GitHub Actions triggers a CommitGuard workflow container. The agent runs a full evaluation loop over the PR's diff patch.
- **Expected Result:**
  - The agent posts an automated review comment directly on the PR.
  - If vulnerable, it flags the specific line and provides a remediation suggestion.
  - The PR status check turns **Red (Failed)** if a severe vulnerability is detected, preventing a merge to the main branch.

### 2.3 IDE Extension (VS Code / Cursor Integration)
- **Scenario:** Real-time vulnerability detection while typing.
- **Action:** Developer saves a file (`Ctrl+S`). The IDE plugin sends the local file diff to a hosted CommitGuard backend.
- **Expected Result:**
  - The agent identifies an issue using its `analyze` action step.
  - A diagnostic warning (red squiggly line) appears under the vulnerable code snippet in the editor.
  - Hovering shows the agent's `<reasoning>` and suggested safe implementation.
