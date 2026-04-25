<!--
If an agent is tempted to build something not in the current scope, append it here instead and continue with the locked task.

Source: ../prd.md §14 (Future Work). Do not execute these during the hackathon build unless explicitly re-scoped by the whole team (and documented).
-->

## Future Work (post-hackathon)

- **Sandboxed exploit execution** — replace pattern-match reward with actual exploit runs against compiled code in a Docker sandbox
- **Multi-file commit reasoning** — extend the env to support diffs spanning multiple files, with a context budget
- **Self-play loop** — pair CommitGuard with a code-generation agent; defender and attacker train against each other (the AlphaGo pattern for security)
- **Agentic harness integration** — wire into real CI pipelines via the OpenEnv MCP layer, enabling commit-time security review at PR open
- **Real CVE corpus** — extend beyond Devign to recent CVE-tagged commits from major open-source repos
- **Multi-language support** — current env is C-focused via Devign; extend to Python, JavaScript, Go
- **Reward shape ablations** — formal study of how reward composition affects which vulnerability types the model learns fastest

