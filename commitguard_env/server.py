from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

# Immediate flush logging for HF diagnosis
def print_now(msg: str):
    sys.stdout.write(f"DEBUG: {msg}\n")
    sys.stdout.flush()

print_now("Server process started, beginning imports...")

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dataclasses import asdict
from pydantic import BaseModel

print_now("FastAPI imported.")

from .environment import CommitGuardEnvironment
from .parse_action import action_from_json, parse_action

print_now("Local modules imported.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurable data path with fallback
DATA_PATH_STR = os.environ.get("COMMITGUARD_DATA_PATH", "")
if DATA_PATH_STR:
    DATA_PATH = Path(DATA_PATH_STR)
else:
    # Match Docker path: /app/data/...
    DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "devign_filtered.jsonl"

print_now(f"DATA_PATH resolved to: {DATA_PATH}")

app = FastAPI(title="CommitGuard Env Server", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

env = CommitGuardEnvironment(data_path=DATA_PATH)

@app.on_event("startup")
def startup_event():
    print_now("FastAPI startup event triggered.")
    logger.info(f"Loading data from {DATA_PATH}...")
    try:
        if not DATA_PATH.exists():
            print_now(f"CRITICAL: Data path {DATA_PATH} DOES NOT EXIST")
        env.load()
        logger.info(f"Successfully loaded {len(env._samples)} samples.")
        print_now(f"Loaded {len(env._samples)} samples.")
    except Exception as e:
        logger.error(f"FAILED to load data: {e}")
        print_now(f"ERROR during load: {e}")

class StepRequest(BaseModel):
    action: str | None = None
    action_type: str | None = None
    file_path: str | None = None
    reasoning: str | None = None
    is_vulnerable: bool | None = None
    vuln_type: str | None = None
    exploit_sketch: str | None = None
    episode_id: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


class ResetRequest(BaseModel):
    sample_id: str | None = None

@app.post("/reset")
def reset(req: ResetRequest = ResetRequest()) -> dict[str, Any]:
    try:
        obs = env.reset(sample_id=req.sample_id)
        return {
            "observation": asdict(obs),
            "done": False,
            "reward": 0.0,
        }
    except ValueError as e:
        return {"error": str(e)}


@app.post("/step")
def step(req: StepRequest) -> dict[str, Any]:
    if req.action is not None:
        action = parse_action(req.action)
    else:
        action = action_from_json(req.model_dump(exclude_none=True))
    obs, reward, done = env.step(action, episode_id=req.episode_id)
    return {
        "observation": asdict(obs),
        "done": done,
        "reward": reward,
        "info": {"parse_error": action.parse_error},
    }


@app.get("/state")
def state(episode_id: str | None = None) -> dict[str, Any]:
    st = env.state(episode_id=episode_id)
    return {"state": asdict(st)}


def main() -> None:
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("commitguard_env.server:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
