from __future__ import annotations

from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dataclasses import asdict
from pydantic import BaseModel

from .environment import CommitGuardEnvironment
from .parse_action import action_from_json, parse_action


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "devign_filtered.jsonl"

app = FastAPI(title="CommitGuard Env Server", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

env = CommitGuardEnvironment(data_path=DATA_PATH)


class StepRequest(BaseModel):
    # Either send `action` as raw XML text, or send structured fields (curl-friendly).
    action: str | None = None
    action_type: str | None = None
    file_path: str | None = None
    reasoning: str | None = None
    is_vulnerable: bool | None = None
    vuln_type: str | None = None
    exploit_sketch: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/reset")
def reset() -> dict[str, Any]:
    obs = env.reset()
    return {
        "observation": asdict(obs),
        "done": False,
        "reward": 0.0,
    }


@app.post("/step")
def step(req: StepRequest) -> dict[str, Any]:
    if req.action is not None:
        action = parse_action(req.action)
    else:
        action = action_from_json(req.model_dump(exclude_none=True))
    obs, reward, done = env.step(action)
    return {
        "observation": asdict(obs),
        "done": done,
        "reward": reward,
        "info": {"parse_error": action.parse_error},
    }


@app.get("/state")
def state() -> dict[str, Any]:
    st = env.state()
    return {"state": asdict(st)}


def main() -> None:
    uvicorn.run("commitguard_env.server:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()

