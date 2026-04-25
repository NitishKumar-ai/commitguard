## Architecture contract (do not improvise)

This is the technical contract for CommitGuard. If you’re about to invent a new shape, don’t. Either it’s already here, or it belongs in `FUTURE_WORK.md`.

Authoritative source: `../prd.md` (§5–§8).

## Repo layout (locked)

Target layout (names are contracts; adjust only if repo already differs):

- `commitguard_env/`
  - `models.py` — typed dataclasses: `Action`, `Observation`, `EnvState`, `GroundTruth`
  - `parse_action.py` — XML action parser (robust to malformed output)
  - `reward.py` — `compute_reward(...) -> float` (pure function)
  - `environment.py` — `CommitGuardEnvironment` implementing OpenEnv reset/step/state
  - `server.py` — FastAPI app exposing OpenEnv HTTP endpoints
- `data/`
  - `devign_filtered.jsonl` — dataset embedded in Docker image
  - `cwe_keywords.json` — top-10 CWE → keyword map (for exploit sketch bonus)
- `tests/` — blocking tests listed in `test_contracts.md`
- `scripts/` — dataset preprocessing and ops scripts (CLI-first)
- `README.md` — story + links + how to run

If the codebase already has a different structure, keep the same semantics and update this file to match.

## Dataclass schemas (typed; no untyped dicts in public APIs)

All public shapes are typed dataclasses. Internal parsing may use dicts, but boundaries must be dataclasses.

### `Action`

- **Raw input**: `raw_action: str` (the model output)
- **Parsed**:
  - `action_type: Literal["request_context", "analyze", "verdict"]`
  - `fields: ActionFields` (typed union by action_type)

### `Observation` (cheating-prevention critical)

Must include only:
- `episode_id: str`
- `step_idx: int`
- `diff: str` (code_before/code_after diff or unified diff string)
- `repo_files: list[str]` (or `available_files`)
- `context_snippets: list[ContextSnippet]` (only if requested)
- `budget_remaining: int`
- `error: str | None` (for malformed actions, etc.)

Must **never** include:
- `is_vulnerable`, `label`, `ground_truth`, `cwe_type`, `target_file_with_label`
- anything that trivially implies the label (e.g., “this sample is vulnerable”)

### `GroundTruth` (server-only)

Lives only on the server. Never serialized into observations.
- `is_vulnerable: bool`
- `cwe: str | None`
- `target_file: str`
- `exploit_keywords: list[str]` (or derived via CWE map)

## Cheating-prevention rule (non-negotiable)

**Observation must never contain ground truth.** Reward is the only scalar feedback; it must not leak label via strings or metadata.

Enforcement:
- observation schema excludes forbidden fields
- `tests/test_no_leak.py` asserts forbidden keys and suspicious strings never appear
- server returns reward as a float only; never returns label/cwe “for debugging”

## Episode contract

- Max **5 steps** per episode.
- Episode ends when `verdict` is received OR budget hits zero.
- `request_context` consumes budget and has per-step penalty.
- `analyze` is allowed, logged, and should not affect reward directly.

## Reward function (signature + invariants)

Reward is RLVR: computed from ground truth and simple keyword checks, **not** an LLM judge.

Signature:

```python
def compute_reward(
    action: "Action",
    ground_truth: "GroundTruth",
    *,
    cwe_keywords: dict[str, list[str]],
    context_requests: int,
) -> float: ...
```

Reward shape (from PRD):
- correct vulnerable/safe: **+1.0**
- correct CWE (when vulnerable): **+0.5**
- plausible exploit sketch (keyword match): **+0.5**
- false positive: **-1.0**
- false negative: **-0.5**
- per context request: **-0.05**
- malformed action: penalize (recommended **-0.5**) but do not crash

## XML action format (the model output contract)

Model outputs exactly one top-level `<action>` block. Parser must tolerate:
- extra whitespace
- missing fields (treated as malformed)
- wrong casing (normalize)
- stray text before/after tags
- malformed XML (best-effort extraction; never crash)

### Spec

Top-level:
- `<action>`
  - `<action_type>request_context|analyze|verdict</action_type>`
  - `<fields>...</fields>`
- `</action>`

Fields by type:

**request_context**
- `<file_path>path/in/repo.ext</file_path>`
- optional: `<start_line>int</start_line>`, `<end_line>int</end_line>`

**analyze**
- `<reasoning>free text</reasoning>`

**verdict**
- `<is_vulnerable>true|false</is_vulnerable>`
- `<vuln_type>CWE-79|CWE-89|...|NONE</vuln_type>`
- `<exploit_sketch>free text</exploit_sketch>`

Parsing rules:
- if `action_type` missing/invalid → malformed
- booleans accept `true/false/1/0/yes/no` (case-insensitive)
- `vuln_type` normalized; if safe verdict, allow `NONE`
- on malformed: return a safe `Action` with `action_type="analyze"` and `error` set, and apply malformed penalty

## Env server HTTP endpoints (P0)

The env server must expose these endpoints (names from PRD §8.1):

- `GET /health` → 200 OK and simple JSON payload
- `POST /reset` → returns initial `Observation` (+ episode id)
- `POST /step` → accepts raw action string, returns `{observation, reward, done, info}`
- `GET /state` → returns minimal server/env state for debugging (no ground truth)
- `GET /docs` → FastAPI OpenAPI docs (automatic)

Do not add new endpoints after scope freeze unless required for reliability.

