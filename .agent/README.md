## What this folder is

`.agent/` is the **operating system for AI agents** on this repo. It locks the architecture decisions from `../prd.md`, prevents scope creep under deadline pressure, and makes sure three engineers can use Cursor / Claude Code in parallel without drifting.

If you're an agent: **load `project_context.md` first**. If you're a human: treat this folder like the team's constitution.

## Nonnegotiable rule (scope freeze)

**Scope freeze is midnight Saturday (00:00 IST).** After that time:
- Do not add features, endpoints, model changes, UI, or nice to haves.
- Only do bug fixes, tests, wiring, docs, and reliability work that protects the locked deliverables.
- If youre tempted to add something: append it to `FUTURE_WORK.md` and continue the locked task.

## Files and what each enforces

- `project_context.md`: **Single source of truth**. The compressed PRD: what were building, why, who for, locked stack, 30sec pitch, nongoals.
- `architecture.md`: **Technical contract**. File layout, dataclass schemas, XML action format, reward signature, observation schema, cheating prevention, required HTTP endpoints.
- `coding_conventions.md`: **How we write code**. Typed dataclasses, import order, errors, forbidden patterns, repo hygiene.
- `decision_log.md`: **Locked decisions + fallbacks**. PRD 7.1 in table form, PRD 7.2 fallback triggers. New decisions go here with timestamp+author.
- `agent_instructions.md`: **System prompt** for any coding agent. Read order, refusal rules, time pressure behavior, fallback triggers.
- `checkpoints.md`: **Team sync contract** at midnight / 9 AM / 3 PM. What must be demoable; what triggers scope cuts; what gets cut first.
- `test_contracts.md`: **Blocking tests** required before merge: no-leak, reward cases, XML parser robustness, env smoke.
- `git_workflow.md`: **Parallel work rules**. Branch naming, commit conventions, merge gates, no-force-push rules, pre-submission checklist.
- `FUTURE_WORK.md`: **Parking lot** for anything not in current scope (pre-populated from PRD 14).

## Where the real spec lives

The authoritative PRD is `../prd.md`. If any `.agent/` file disagrees with the PRD, **the PRD wins** and you must update the `.agent/` file immediately.

## Task files (per person)

This repo expects per-person task lists:
- `../tasks_niti.md`
- `../tasks_deepak.md`
- `../tasks_divyank.md`

If they dont exist yet, create them now with 1020 bullet tasks each and keep them updated. Agents should read the relevant one **after** `project_context.md` and `architecture.md`.

