from typing import Any, Dict, List, Optional
import requests
from commitguard_env.models import CommitGuardAction, CommitGuardObservation

class CommitGuardClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def reset(self) -> Dict[str, Any]:
        resp = requests.post(f"{self.base_url}/reset")
        resp.raise_for_status()
        return resp.json()

    def step(self, action: str | Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(action, str):
            payload = {"action": action}
        else:
            payload = action
        resp = requests.post(f"{self.base_url}/step", json=payload)
        resp.raise_for_status()
        return resp.json()

    def health(self) -> Dict[str, str]:
        resp = requests.get(f"{self.base_url}/health")
        resp.raise_for_status()
        return resp.json()
