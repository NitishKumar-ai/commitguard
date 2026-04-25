## Decision log (locked + fallbacks)

This file is a **contract**. It mirrors `../prd.md` §7.1 and §7.2.

If you want to change a decision: you don’t. If you must due to a trigger, use the fallback and log it.

## Locked technical decisions (PRD §7.1)

| Decision | Choice | Rationale |
|---|---|---|
| Env framework | Meta OpenEnv 0.2.3+ | Mandatory per submission rules |
| Server runtime | FastAPI in Docker | OpenEnv default, lowest friction |
| Hosting | Hugging Face Space | Mandatory; server+repo+registry |
| Data source | Devign (DetectBERT subset) | Real CWE labels, manageable size |
| Model | Llama-3.2-3B-Instruct | Meta-branded; fits A10G with GRPO |
| Training framework | TRL with GRPO | Native OpenEnv integration via reward funcs |
| Training optimization | Unsloth 4-bit + LoRA r=8 | Big memory reduction + speed |
| Training infra | HF Jobs A10G | Unattended, HF-native |
| Dev infra | GCP VM with T4 | Stable, no Colab disconnects |
| Action serialization | XML-tag free-text | Robust to small-model variance |
| Logging | Weights & Biases | TRL native; shareable runs |

## Pre-approved fallback rules (PRD §7.2)

| If this fails | Fall back to | Trigger condition |
|---|---|---|
| Llama-3.2-3B OOM on A10G | Qwen2.5-1.5B-Instruct | First test step crashes |
| HF Jobs queue full | GCP A10G on-demand | Job queues for >30 min |
| 3-action env doesn’t ship by midnight | 2-action env (analyze + verdict) | Midnight checkpoint is red |
| Tiered reward buggy | Binary correct/incorrect reward | Reward checkpoint is red |
| Training curve flat | Qualitative comparison only | Still flat at 10 AM Sunday |
| Demo video hard to record | Side-by-side text trace in README | Recording fails twice |

## New decisions made during the build

Rule: any new decision must be logged here with timestamp + author and must not violate the locked PRD unless it’s a PRD-defined fallback.

Template:
- **[YYYY-MM-DD HH:MM IST] (author)**: decision → rationale → impact → rollback plan

