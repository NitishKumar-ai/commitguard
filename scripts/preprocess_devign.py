import argparse
import json
import random
from pathlib import Path

def _read_jsonl(path: Path) -> list[dict]:
    rows = []
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

def infer_cwe(code: str) -> str:
    code_lower = code.lower()
    if any(x in code_lower for x in ["sql", "select", "where", "query"]):
        return "CWE-89"
    elif any(x in code_lower for x in ["alloc", "free", "memcpy", "strcpy", "buffer"]):
        return "CWE-119"
    elif any(x in code_lower for x in ["null", "pointer", "deref"]):
        return "CWE-476"
    elif any(x in code_lower for x in ["script", "xss", "html", "document."]):
        return "CWE-79"
    elif any(x in code_lower for x in ["system(", "exec", "popen", "shell"]):
        return "CWE-78"
    elif any(x in code_lower for x in ["file", "open(", "read(", "path"]):
        return "CWE-22"
    elif any(x in code_lower for x in ["int", "long", "short", "unsigned", "size", "length"]):
        return "CWE-189"
    else:
        return "CWE-20"

def main() -> None:
    ap = argparse.ArgumentParser(description="Preprocess Devign-derived samples into CommitGuard JSONL.")
    ap.add_argument("--in", dest="inp", type=Path, default=None, help="Optional input JSONL.")
    ap.add_argument("--out", dest="out", type=Path, default=Path("data/devign_filtered.jsonl"))
    ap.add_argument("--limit", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)

    if args.inp is None:
        try:
            from datasets import load_dataset
            print("Loading DetectVul/devign from Hugging Face...")
            ds = load_dataset('DetectVul/devign', split='train')
            raw_rows = []
            for item in ds:
                raw_rows.append(item)
            print(f"Loaded {len(raw_rows)} rows from HF.")
        except Exception as e:
            print(f"Failed to load from HF: {e}")
            return
    else:
        raw_rows = _read_jsonl(args.inp)

    vuln_samples = []
    safe_samples = []

    for r in raw_rows:
        # Check if we have func and target
        func = r.get("func")
        if not func:
            continue
            
        # Filter: drop samples where len(code.split('\n')) > 80
        if len(func.split('\n')) > 80:
            continue
            
        target = r.get("target", False)
        
        # We need a CWE. 
        cwe = infer_cwe(func)
        if not cwe:
            continue

        sample_id = str(r.get("commit_id") or r.get("id") or f"row-{len(vuln_samples) + len(safe_samples)}")
        target_file = "source.c" # default since devign does not provide file path
        
        diff = f"--- a/code_before\n+++ b/code_after\n@@ -1 +1 @@\n+// Synthesized diff\n{func}"

        sample = {
            "sample_id": sample_id,
            "diff": diff,
            "available_files": [target_file],
            "is_vulnerable": bool(target),
            "cwe": cwe if target else None,  # only vulnerable needs CWE
            "target_file": target_file,
            "files": {target_file: func},
        }

        if target:
            vuln_samples.append(sample)
        else:
            safe_samples.append(sample)

    print(f"Filtered down to {len(vuln_samples)} vulnerable and {len(safe_samples)} safe samples.")

    # Balance 50/50
    target_each = args.limit // 2
    vuln_keep = rng.sample(vuln_samples, min(target_each, len(vuln_samples)))
    safe_keep = rng.sample(safe_samples, min(target_each, len(safe_samples)))
    
    out_rows = vuln_keep + safe_keep
    rng.shuffle(out_rows)

    _write_jsonl(args.out, out_rows)
    print(f"Wrote {len(out_rows)} samples to {args.out}")

if __name__ == "__main__":
    main()
