from __future__ import annotations

import json

from fastapi.testclient import TestClient

from commitguard_env.server import app


FORBIDDEN_KEYS = {
    "is_vulnerable",
    "label",
    "ground_truth",
    "cwe_type",
    "cwe",
    "target_file_with_label",
}


def _walk(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield ("key", k)
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)
    elif isinstance(obj, str):
        yield ("str", obj)


def test_reset_and_step_do_not_leak_ground_truth() -> None:
    client = TestClient(app)

    r = client.post("/reset")
    assert r.status_code == 200
    reset_payload = r.json()

    s = client.post("/step", json={"action": "<action><action_type>analyze</action_type></action>"})
    assert s.status_code == 200
    step_payload = s.json()

    for payload in (reset_payload, step_payload):
        flat = list(_walk(payload))
        keys = {v for t, v in flat if t == "key"}
        assert not (keys & FORBIDDEN_KEYS)

        # Also guard against obvious label-bearing strings in any nested content.
        strings = [v.lower() for t, v in flat if t == "str"]
        suspicious = ("this sample is vulnerable", "ground truth", "label:")
        assert not any(any(tok in s for tok in suspicious) for s in strings)

        # Ensure payload is valid JSON-serializable.
        json.dumps(payload)

