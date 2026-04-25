# CommitGuard

CommitGuard is an OpenEnv reinforcement learning environment for commit-time vulnerability detection.

## Features
- 3-action design: `request_context`, `analyze`, `verdict`.
- Tiered rewards for correctness, CWE classification, and exploit sketching.
- Cheating prevention: Ground truth is never leaked to the agent.

## Installation
```bash
pip install .
```

## Running the Server
```bash
python -m commitguard_env.server
```
