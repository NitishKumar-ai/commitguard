## Git workflow (parallel, safe, deadline-optimized)

This repo will have three engineers working in parallel with agents. The workflow exists to prevent integration chaos.

## Branch naming (required)

Format: `<name>/<short-scope>`

Examples:
- `niti/env-scaffolding`
- `deepak/data-pipeline`
- `divyank/training-grpo`

Rules:
- One scope per branch.
- If a branch grows beyond 2–3 related commits, cut scope or split.

## Commit message convention (required)

Use **Conventional Commits**:

- `feat(env): add OpenEnv reset/step`
- `fix(parser): handle malformed xml without crash`
- `test(reward): add 5 handcrafted cases`
- `docs(readme): add demo + wandb links`

Rules:
- Short subject, present tense.
- Prefer “why” over “what” in body.

## Merge policy (hard rules)

- Merge to `main` **only after** the relevant tests pass locally:
  - Env changes: `test_no_leak.py`, `test_env_smoke.py`, `test_action_parser.py`
  - Reward changes: `test_reward.py` + `test_no_leak.py`
  - Parser changes: `test_action_parser.py` + `test_env_smoke.py`
- No “merge now, fix later”. Under deadline, broken `main` is a team-wide blocker.

## Force-push rules

- Before midnight Saturday: allowed on your feature branches if necessary.
- **After midnight Saturday: no force-push to `main` (ever).**
- Prefer no force-push at all; use revert commits if needed.

## PR expectations (fast reviews)

Each PR must include:
- 1–3 sentence summary
- test plan (what you ran)
- risk note (what could break)

If it’s large, it’s wrong: split it.

## Pre-submission checklist (Sunday)

By 3 PM:
- [ ] HF Space live; `/health` 200; `/docs` loads
- [ ] Blocking tests pass (`.agent/test_contracts.md`)
- [ ] Training artifact exists (plots + wandb link)
- [ ] Demo artifact exists (video URL or text trace fallback)
- [ ] README links all resolve (Space, notebook, video, wandb, repo)

By 4:30 PM:
- [ ] Fresh clone + run instructions work
- [ ] Final smoke test: 100 episodes don’t crash
- [ ] Submission package is complete

## CLI-first ops (HF + GCP)

Keep ops repeatable. Prefer CLI over UI clicks.

Hugging Face:
- `huggingface-cli login`
- `huggingface-cli whoami`
- Use git-based Space workflow (clone, commit, push) for deploys.

GCP:
- `gcloud auth login`
- `gcloud config set project <PROJECT_ID>`
- Use `gcloud compute ssh` + `gcloud compute instances list` for VM workflow.

Cross-reference:
- Merge gates: `test_contracts.md`
- Scope freeze + fallbacks: `project_context.md`

