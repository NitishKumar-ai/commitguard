## CommitGuard agent entrypoint (read this first)

If you are a coding agent (Claude Code / Cursor agent), this file is your **session bootstrap**.

### Load order (mandatory)

1. Read `.agent/project_context.md`
2. Read `.agent/architecture.md`
3. Read `.agent/coding_conventions.md`
4. Read `.agent/agent_instructions.md` and follow it verbatim
5. Read your task file (create if missing):
   - `tasks_niti.md` or `tasks_deepak.md` or `tasks_divyank.md`

### Scope freeze (non-negotiable)

**Scope freezes at midnight Saturday (00:00 IST).** After that, refuse new features. If asked to expand scope, append to `.agent/FUTURE_WORK.md` and continue the locked task.

### Where the rules live

- Agent system prompt: `.agent/agent_instructions.md`
- Technical contract: `.agent/architecture.md`
- Locked decisions + fallbacks: `.agent/decision_log.md` and `.agent/project_context.md`
- Merge blockers: `.agent/test_contracts.md`
- Git rules: `.agent/git_workflow.md`

