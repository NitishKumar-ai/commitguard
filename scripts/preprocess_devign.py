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
        samples: list[dict] = []
        templates = [
            # SQL Injection - Vulnerable (f-string/concat) -> Secure (parameterized)
            {
                "is_vulnerable": True,
                "cwe": "CWE-89",
                "diff": "--- a/db.py\n+++ b/db.py\n@@\n- cursor.execute(\"SELECT * FROM users WHERE id = %s\", (user_id,))\n+ cursor.execute(f\"SELECT * FROM users WHERE id = {user_id}\")\n",
                "target_file": "db.py"
            },
            {
                "is_vulnerable": False,
                "cwe": "CWE-89",
                "diff": "--- a/db.py\n+++ b/db.py\n@@\n- cursor.execute(\"SELECT * FROM users WHERE id = \" + user_id)\n+ cursor.execute(\"SELECT * FROM users WHERE id = %s\", (user_id,))\n",
                "target_file": "db.py"
            },
            # XSS - Vulnerable (innerHTML) -> Secure (textContent)
            {
                "is_vulnerable": True,
                "cwe": "CWE-79",
                "diff": "--- a/app.js\n+++ b/app.js\n@@\n- el.textContent = user_input;\n+ el.innerHTML = user_input;\n",
                "target_file": "app.js"
            },
            {
                "is_vulnerable": False,
                "cwe": "CWE-79",
                "diff": "--- a/app.js\n+++ b/app.js\n@@\n- el.innerHTML = \"Welcome \" + name;\n+ el.textContent = \"Welcome \" + name;\n",
                "target_file": "app.js"
            },
            # Auth Bypass - Vulnerable (weak check) -> Secure (strong check)
            {
                "is_vulnerable": True,
                "cwe": "CWE-287",
                "diff": "--- a/auth.py\n+++ b/auth.py\n@@\n- if user.is_authenticated and user.has_perm('admin'):\n+ if user.username == 'admin':\n",
                "target_file": "auth.py"
            },
            {
                "is_vulnerable": False,
                "cwe": "CWE-287",
                "diff": "--- a/auth.py\n+++ b/auth.py\n@@\n- if request.user:\n+ if request.user and request.user.is_authenticated:\n",
                "target_file": "auth.py"
            },
            # Path Traversal
            {
                "is_vulnerable": True,
                "cwe": "CWE-22",
                "diff": "--- a/files.py\n+++ b/files.py\n@@\n- path = os.path.join(SAFE_DIR, os.path.basename(filename))\n+ path = os.path.join(SAFE_DIR, filename)\n",
                "target_file": "files.py"
            }
        ]
        
        for i in range(args.limit):
            tpl = rng.choice(templates)
            samples.append(
                {
                    "sample_id": f"synthetic-{i:05d}",
                    "diff": tpl["diff"],
                    "available_files": [tpl["target_file"]],
                    "is_vulnerable": tpl["is_vulnerable"],
                    "cwe": tpl["cwe"],
                    "target_file": tpl["target_file"],
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

