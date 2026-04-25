## Test contracts (merge blockers)

These tests are **merge gates**. If any fails, do not merge to `main`. See `git_workflow.md`.

Owners are initial; if you touch the area, you own the test too.

### `tests/test_no_leak.py`

- **Asserts**:
  - `Observation` serialization never includes ground-truth fields (e.g., `is_vulnerable`, `ground_truth`, `label`, `cwe_type`).
  - Response payloads from `/reset` and `/step` do not contain forbidden keys or suspicious strings that imply labels.
- **Owner**: Niti (env integrity)
- **Blocking condition**: Any leakage is a submission-killer. Must be fixed immediately.

### `tests/test_reward.py`

- **Asserts**: `compute_reward(...)` returns expected values for **5 handcrafted cases**:
  1. True positive + correct CWE + exploit match
  2. True positive + wrong CWE
  3. False positive
  4. False negative
  5. Malformed action penalty (and no crash)
- **Owner**: Deepak (reward design)
- **Blocking condition**: If tiered reward is flaky, trigger fallback to binary reward (log in `decision_log.md`).

### `tests/test_action_parser.py`

- **Asserts**:
  - XML action parsing works for all 3 action types.
  - Parser is robust to malformed inputs (missing tags, invalid XML, extra text).
  - Parser never throws; returns a safe Action + error info.
- **Owner**: Divyank (agent I/O contract)
- **Blocking condition**: Any parser crash blocks training and demo; fix before anything else.

### `tests/test_env_smoke.py`

- **Asserts**:
  - 100 random episodes do not crash.
  - `reset`/`step` latency stays reasonable and budget cap terminates episodes.
  - Malformed actions do not crash and return done when appropriate.
- **Owner**: Niti (env reliability)
- **Blocking condition**: If smoke test fails, training is not allowed to run.

## Required behavior under failure

- If a test reveals a scope-level failure, use a PRD-approved fallback (see `project_context.md`) rather than inventing new features.
- If a failure requires a new decision, log it in `decision_log.md` with timestamp + author.

