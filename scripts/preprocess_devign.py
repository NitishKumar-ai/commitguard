import argparse
import json
import random
from collections import Counter
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


# ---------------------------------------------------------------------------
# Fix 2: CWE classification using vulnerable lines, not the whole function.
# Scored rules — highest-scoring match wins. Falls back to CWE-OTHER.
# ---------------------------------------------------------------------------

_CWE_RULES: list[tuple[str, list[str], int]] = [
    ("CWE-119", ["memcpy", "strcpy", "strcat", "strncpy", "memmove", "sprintf",
                  "gets(", "buffer", "overflow", "oob", "av_malloc", "av_realloc",
                  "realloc", "malloc", "alloc", "g_malloc", "g_realloc",
                  "qemu_malloc", "len ", "length", "copy_from", "copy_to"], 5),
    ("CWE-476", ["null", "nullptr", "!= null", "== null", "if (!",
                  "dereference", "segfault", "!obj", "!ctx", "!s->", "!p"], 5),
    ("CWE-189", ["integer overflow", "signedness", "truncat", "wrap",
                  "size_t", "underflow", "narrowing", "(int)", "(uint",
                  "(unsigned)", ">> ", "<< ", "0xffff", "max_", "min_"], 5),
    ("CWE-78",  ["system(", "popen(", "exec(", "execve", "shell",
                  "command", "subprocess"], 8),
    ("CWE-22",  ["../", "..\\", "traversal", "chroot", "realpath",
                  "canonicalize", "symlink", "path"], 7),
    ("CWE-89",  ["sql", "query", "select ", "insert ", "union ",
                  "prepared", "sqlite", "mysql"], 7),
    ("CWE-79",  ["xss", "innerhtml", "script", "sanitize", "escape",
                  "htmlentit", "content-type"], 6),
    ("CWE-20",  ["valid", "saniti", "untrusted", "input", "bounds",
                  "assert", "range", "check", "error", "return -1",
                  "goto fail", "goto err", "goto out"], 2),
]


def infer_cwe(vul_lines_code: list[str], func: str) -> str:
    vul_text = " ".join(vul_lines_code).lower() if vul_lines_code else ""
    func_text = func.lower()

    best_cwe, best_score = "CWE-OTHER", 0

    for cwe, keywords, weight in _CWE_RULES:
        vul_hits = sum(1 for k in keywords if k in vul_text) if vul_text else 0
        func_hits = sum(1 for k in keywords if k in func_text)
        score = vul_hits * weight + func_hits * (weight // 2)
        if score > best_score:
            best_cwe, best_score = cwe, score

    if best_score < 2:
        return "CWE-OTHER"
    return best_cwe


# ---------------------------------------------------------------------------
# Fix 1: Real unified diffs from per-line vulnerability labels.
# ---------------------------------------------------------------------------

def _build_diff(func: str, label: list[int], rng: random.Random, is_vuln: bool) -> str:
    lines = func.splitlines()

    if is_vuln and label and len(label) == len(lines):
        changed_indices = {i for i, l in enumerate(label) if l == 1}
    elif is_vuln and label and any(l == 1 for l in label):
        changed_indices = {i for i, l in enumerate(label) if l == 1}
    else:
        block_size = max(1, min(5, len(lines) // 4))
        start = rng.randint(0, max(0, len(lines) - block_size))
        changed_indices = set(range(start, min(start + block_size, len(lines))))

    if not changed_indices:
        changed_indices = {0}

    ctx = 3
    visible: set[int] = set()
    for ci in changed_indices:
        for offset in range(-ctx, ctx + 1):
            idx = ci + offset
            if 0 <= idx < len(lines):
                visible.add(idx)

    sorted_visible = sorted(visible)
    hunks: list[list[int]] = []
    current_hunk: list[int] = []
    for idx in sorted_visible:
        if current_hunk and idx > current_hunk[-1] + 1:
            hunks.append(current_hunk)
            current_hunk = [idx]
        else:
            current_hunk.append(idx)
    if current_hunk:
        hunks.append(current_hunk)

    diff_parts = ["--- a/source.c", "+++ b/source.c"]
    for hunk in hunks:
        start_line = hunk[0] + 1
        hunk_size = len(hunk)
        diff_parts.append(f"@@ -{start_line},{hunk_size} +{start_line},{hunk_size} @@")
        for idx in hunk:
            line = lines[idx]
            if idx in changed_indices:
                diff_parts.append(f"+{line}")
            else:
                diff_parts.append(f" {line}")

    return "\n".join(diff_parts)


# ---------------------------------------------------------------------------
# Fix 3: CWE rebalancing — cap dominant CWEs, merge tiny ones.
# ---------------------------------------------------------------------------

_MAX_PER_CWE_FRAC = 0.25
_MIN_CWE_SAMPLES = 20


def _rebalance(samples: list[dict], rng: random.Random, limit: int) -> list[dict]:
    by_cwe: dict[str, list[dict]] = {}
    for s in samples:
        by_cwe.setdefault(s["cwe"] or "CWE-OTHER", []).append(s)

    for cwe, items in list(by_cwe.items()):
        if len(items) < _MIN_CWE_SAMPLES and cwe != "CWE-OTHER":
            by_cwe.setdefault("CWE-OTHER", []).extend(items)
            for item in items:
                item["cwe"] = "CWE-OTHER"
            del by_cwe[cwe]

    cap = int(limit * _MAX_PER_CWE_FRAC)
    kept: list[dict] = []
    for cwe, items in by_cwe.items():
        rng.shuffle(items)
        kept.extend(items[:cap])

    rng.shuffle(kept)
    return kept[:limit]


def main() -> None:
    ap = argparse.ArgumentParser(description="Preprocess Devign-derived samples into CommitGuard JSONL.")
    ap.add_argument("--in", dest="inp", type=Path, default=None, help="Optional input JSONL.")
    ap.add_argument("--out", dest="out", type=Path, default=Path("data/devign_filtered.jsonl"))
    ap.add_argument("--test-out", dest="test_out", type=Path, default=Path("data/devign_test.jsonl"))
    ap.add_argument("--limit", type=int, default=5000)
    ap.add_argument("--test-limit", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)

    if args.inp is None:
        try:
            from datasets import load_dataset
            print("Loading DetectVul/devign from Hugging Face...")
            ds = load_dataset('DetectVul/devign', split='train')
            raw_rows = list(ds)
            print(f"Loaded {len(raw_rows)} rows from HF.")
        except Exception as e:
            print(f"Failed to load from HF: {e}")
            return
    else:
        raw_rows = _read_jsonl(args.inp)

    all_samples: list[dict] = []
    
    # Process all rows first
    seen_ids = set()
    for i, r in enumerate(raw_rows):
        func = r.get("func")
        if not func:
            continue
        if len(func.split("\n")) > 80:
            continue

        target = bool(r.get("target", False))
        label = r.get("label", [])
        vul_lines_code = []
        vl = r.get("vul_lines")
        if vl and isinstance(vl, dict):
            vul_lines_code = vl.get("code", [])

        cwe = infer_cwe(vul_lines_code, func) if target else None
        diff = _build_diff(func, label, rng, target)

        # Ensure unique sample_id
        original_id = str(r.get("commit_id") or r.get("id") or f"row-{i}")
        sample_id = original_id
        suffix = 0
        while sample_id in seen_ids:
            suffix += 1
            sample_id = f"{original_id}_{suffix}"
        seen_ids.add(sample_id)

        target_file = "source.c"

        sample = {
            "sample_id": sample_id,
            "diff": diff,
            "available_files": [target_file],
            "is_vulnerable": target,
            "cwe": cwe,
            "target_file": target_file,
            "files": {target_file: func},
        }
        all_samples.append(sample)

    print(f"Total processed samples: {len(all_samples)}")

    # Shuffle and split to ensure NO overlap
    rng.shuffle(all_samples)
    
    # We want to ensure test set has all CWEs if possible
    # Let's pick test set first by picking a few from each CWE
    test_samples: list[dict] = []
    
    vuln_all = [s for s in all_samples if s["is_vulnerable"]]
    safe_all = [s for s in all_samples if not s["is_vulnerable"]]
    
    by_cwe: dict[str, list[dict]] = {}
    for s in vuln_all:
        by_cwe.setdefault(s["cwe"] or "CWE-OTHER", []).append(s)
    
    # Try to pick 5 from each CWE for test set
    for cwe in by_cwe:
        test_samples.extend(by_cwe[cwe][:5])
        by_cwe[cwe] = by_cwe[cwe][5:]
    
    # Fill the rest of test set with random samples (half vuln, half safe)
    remaining_vuln = [s for items in by_cwe.values() for s in items]
    needed_vuln = (args.test_limit // 2) - sum(1 for s in test_samples if s["is_vulnerable"])
    if needed_vuln > 0:
        test_samples.extend(remaining_vuln[:needed_vuln])
        remaining_vuln = remaining_vuln[needed_vuln:]
    
    needed_safe = args.test_limit - len(test_samples)
    test_samples.extend(safe_all[:needed_safe])
    safe_all = safe_all[needed_safe:]
    
    # Now remaining samples go to train
    train_pool_vuln = remaining_vuln
    train_pool_safe = safe_all
    
    print(f"Test set: {len(test_samples)} samples")
    _write_jsonl(args.test_out, test_samples)

    # Rebalance training set
    target_each = args.limit // 2
    vuln_keep = _rebalance(train_pool_vuln, rng, target_each)
    safe_keep = rng.sample(train_pool_safe, min(target_each, len(train_pool_safe)))

    train_rows = vuln_keep + safe_keep
    rng.shuffle(train_rows)

    _write_jsonl(args.out, train_rows)

    print(f"Wrote {len(train_rows)} training samples to {args.out}")
    print(f"Wrote {len(test_samples)} test samples to {args.test_out}")

if __name__ == "__main__":
    main()
