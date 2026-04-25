## Coding conventions (enforced under deadline pressure)

This repo is optimized for: **correctness, reproducibility, and not leaking labels**. Read `architecture.md` first.

## Python style (hard rules)

- **Typed dataclasses everywhere** for public API shapes (actions/observations/state).
  - Use `@dataclass(frozen=True, slots=True)` by default.
  - Public functions must be type-annotated end-to-end.
- **No untyped dicts in public APIs.** Dicts are allowed only internally (e.g., during XML parse), and must be converted to dataclasses at the boundary.
- Keep functions small. Prefer pure functions (`reward.py`) with no hidden state.

## Import ordering

1. stdlib
2. third-party
3. local modules

Within a section: alphabetical. One import per line if it improves diff clarity.

## Docstrings and naming

- Docstrings: short, imperative, include constraints (e.g., “must not leak ground truth”).
- Names: explicit over clever (`compute_reward`, `parse_action_xml`, `EpisodeState`).

## Error handling patterns

- **Never crash on model output.** Malformed actions must be handled gracefully.
- Raise exceptions only for programmer errors; user/model errors return structured error fields.
- Every boundary (HTTP handlers, XML parser) must be defensive:
  - validate inputs
  - clamp budgets
  - return safe defaults

## Forbidden patterns (do not do these)

- **No LLM-as-judge in reward.** Reward must be verifiable (dataset truth + keyword checks). See `architecture.md`.
- **No label leakage**: do not log, return, or print ground truth in observations, HTTP responses, or “debug” endpoints.
- **No hardcoded local paths** (e.g., `C:\\Users\\...`, `/home/...`). Use repo-relative paths + `pathlib`.
- **No committing data files > 5MB** without explicit team sign-off. (If necessary, use HF Datasets or remote storage.)
- **No localStorage in any UI.** If you add UI later (unlikely), store state server-side or in-memory only.
- **No adding endpoints/features after scope freeze** (midnight Saturday).

## Repo hygiene

- Prefer CLI-driven ops so teammates can reproduce quickly:
  - HF: `huggingface-cli`, `hf` (where available), `git lfs` if needed
  - GCP: `gcloud`
- Keep logs minimal. Under hackathon pressure, noisy logs hide real bugs.
- Don’t vendor big artifacts in git. Link them (video, wandb, Space) from README.

## Scope creep rule (non-negotiable)

If you’re tempted to add a feature that isn’t required for the locked deliverables:
- Append one bullet to `FUTURE_WORK.md` (with 1-line rationale).
- Return to your current task.

## Cross-reference

- Architecture contract: `architecture.md`
- Scope and fallbacks: `project_context.md`
- Locked decisions: `decision_log.md`

