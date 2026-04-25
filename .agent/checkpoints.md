## Checkpoints (sync-or-die contract)

Goal: keep three engineers aligned and prevent “cool demo” scope creep from killing the submission. Source: `../prd.md` §12.

### Checkpoint 1 — Midnight (00:00 IST) — scope freeze + Phase 1 gate

**Everyone must demonstrate (live, locally or on Space):**
- **Env server runs** and responds to `GET /health`
- **OpenEnv loop works**: `reset` → `step` → done, without crashing
- **Action parser is robust**: malformed XML doesn’t crash; returns safe error
- **No-leak invariant**: observation contains no ground truth fields

**Role deliverables:**
- **Env/Server owner**: endpoints exist (`/health`, `/reset`, `/step`, `/state`, `/docs`)
- **Reward owner**: reward function wired and deterministic on handcrafted cases
- **Training owner**: mock training loop can call env repeatedly (even if reward is dummy)

**If any of these are red, trigger a scope cut immediately:**
- 3-action env incomplete → cut to 2-action env (analyze + verdict)
- Tiered reward unstable → cut to binary reward only

**After this checkpoint:**
- **Scope freeze is active.** New features go to `.agent/FUTURE_WORK.md` only.

### Checkpoint 2 — 9:00 AM Sunday — training evidence gate

**Everyone must demonstrate:**
- Training run launched (HF Jobs A10G preferred) or fallback running
- Wandb logging works (reward curve visible)
- Evaluation script/notebook can run 100 held-out samples

**Scope-cut triggers:**
- Training blocked by infra >30 min → move to GCP A10G fallback
- Training curve still flat by 10:00 AM → commit to qualitative narrative (no more training tweaks)

**What gets cut first (in order):**
1. P2 items (web UI polish, blog post)
2. Per-CWE breakdown (keep overall accuracy)
3. Exploit sketch bonus (keep binary + CWE if stable)
4. CWE classification bonus (keep binary only)

### Checkpoint 3 — 3:00 PM Sunday — feature freeze gate

**Everyone must demonstrate:**
- HF Space is live and stable; `/health` 200; `/docs` loads
- `tests/` pass (see `.agent/test_contracts.md`)
- Demo artifact path is locked (video or text-trace fallback)
- README has all submission links (Space, notebook, video, wandb, repo)

**Hard rule:**
- **No changes after 3:00 PM** except emergency fixes that prevent submission failure.

**Final scope cuts (if needed to protect submission):**
1. Video → text trace in README
2. Training curve → single plot + narrative
3. Held-out eval → small N sanity check

