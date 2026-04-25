from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="Preprocess Devign-derived samples into CommitGuard JSONL.")
    ap.add_argument("--in", dest="inp", type=Path, default=None, help="Optional input JSONL. If omitted, generates a small synthetic dataset.")
    ap.add_argument("--out", dest="out", type=Path, default=Path("data/devign_filtered.jsonl"))
    ap.add_argument("--limit", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rng = random.Random(args.seed)

    if args.inp is None:
        # Fallback generator for hackathon progress when full Devign isn't wired yet.
        # Produces a small, label-bearing dataset (labels are server-only; env never emits them).
        samples: list[dict] = []
        templates = [
            (
                True,
                "CWE-89",
                "--- a/db.py\n+++ b/db.py\n@@\n- q = f\"SELECT * FROM users WHERE id={user_id}\" \n+ q = \"SELECT * FROM users WHERE id=\" + user_id\n",
                "db.py",
            ),
            (
                False,
                None,
                "--- a/math.py\n+++ b/math.py\n@@\n- return a+b\n+ return a + b\n",
                "math.py",
            ),
        ]
        for i in range(min(args.limit, 200)):
            is_v, cwe, diff, target = rng.choice(templates)
            samples.append(
                {
                    "sample_id": f"synthetic-{i:05d}",
                    "diff": diff,
                    "available_files": [target],
                    "is_vulnerable": is_v,
                    "cwe": cwe,
                    "target_file": target,
                }
            )
        _write_jsonl(args.out, samples)
        return

    raw_rows = _read_jsonl(args.inp)
    out_rows: list[dict] = []

    for r in raw_rows:
        if len(out_rows) >= args.limit:
            break

        # Best-effort field normalization (task docs vary between cwe/cwe_type, etc.)
        sample_id = str(r.get("sample_id") or r.get("commit_id") or r.get("id") or f"row-{len(out_rows)}")
        diff = r.get("diff")
        if not isinstance(diff, str) or not diff.strip():
            continue

        out_rows.append(
            {
                "sample_id": sample_id,
                "diff": diff,
                "available_files": list(r.get("available_files") or ([] if r.get("target_file") is None else [r.get("target_file")])),
                # Server-only truth (env must not emit these).
                "is_vulnerable": r.get("is_vulnerable"),
                "cwe": r.get("cwe") or r.get("cwe_type"),
                "target_file": r.get("target_file"),
                # Optional: repo file contents for request_context support
                "files": r.get("files"),
            }
        )

    _write_jsonl(args.out, out_rows)


if __name__ == "__main__":
    main()

