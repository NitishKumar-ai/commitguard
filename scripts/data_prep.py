"""CommitGuard v2 — Data preparation for Gemma 4 E4B LoRA fine-tuning.

Downloads Devign dataset, applies synthetic augmentation, and formats
into instruction-tuning pairs with structured JSON output.

Outputs: data/gemma_train.jsonl, data/gemma_val.jsonl, data/gemma_test.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

# Reuse existing CWE inference logic
import sys
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.preprocess_devign import infer_cwe, _build_diff, _read_jsonl, _write_jsonl


# ---------------------------------------------------------------------------
# CWE metadata
# ---------------------------------------------------------------------------

_CWE_NAMES: dict[str, str] = {
    "CWE-78": "OS Command Injection",
    "CWE-89": "SQL Injection",
    "CWE-79": "Cross-site Scripting",
    "CWE-119": "Buffer Overflow",
    "CWE-120": "Buffer Copy without Checking Size of Input",
    "CWE-125": "Out-of-bounds Read",
    "CWE-787": "Out-of-bounds Write",
    "CWE-476": "NULL Pointer Dereference",
    "CWE-22": "Path Traversal",
    "CWE-20": "Improper Input Validation",
    "CWE-189": "Numeric Errors",
    "CWE-190": "Integer Overflow or Wraparound",
    "CWE-OTHER": "Other Vulnerability",
}

_CWE_SEVERITY: dict[str, str] = {
    "CWE-78": "CRITICAL",
    "CWE-89": "CRITICAL",
    "CWE-119": "HIGH",
    "CWE-120": "HIGH",
    "CWE-787": "HIGH",
    "CWE-125": "HIGH",
    "CWE-476": "MEDIUM",
    "CWE-22": "MEDIUM",
    "CWE-79": "MEDIUM",
    "CWE-20": "MEDIUM",
    "CWE-189": "MEDIUM",
    "CWE-190": "MEDIUM",
    "CWE-OTHER": "LOW",
}


# ---------------------------------------------------------------------------
# Synthetic augmentation
# ---------------------------------------------------------------------------

# C/C++ identifier pattern
_IDENT_RE = re.compile(r"\b([a-z_][a-z0-9_]{2,})\b", re.IGNORECASE)

# Common variable names to avoid renaming (keywords, types, etc.)
_SKIP_IDENTS: set[str] = {
    "int", "char", "void", "long", "short", "float", "double", "unsigned",
    "signed", "const", "static", "extern", "return", "sizeof", "struct",
    "enum", "union", "typedef", "include", "define", "ifdef", "ifndef",
    "endif", "elif", "else", "for", "while", "break", "continue", "switch",
    "case", "default", "goto", "NULL", "null", "true", "false", "bool",
    "size_t", "uint8_t", "uint16_t", "uint32_t", "uint64_t",
    "int8_t", "int16_t", "int32_t", "int64_t",
    "printf", "scanf", "malloc", "free", "memcpy", "strcpy", "strlen",
    "strcmp", "strncmp", "memset", "assert", "exit",
}


def _augment_rename_vars(code: str, rng: random.Random) -> str:
    """Rename a random subset of local identifiers to make harder negatives."""
    idents = set(_IDENT_RE.findall(code))
    idents -= _SKIP_IDENTS
    if not idents:
        return code

    # Pick 1-3 identifiers to rename
    to_rename = rng.sample(sorted(idents), min(3, len(idents)))
    result = code
    for ident in to_rename:
        suffix = rng.randint(1, 999)
        new_name = f"{ident}_{suffix}"
        result = re.sub(rf"\b{re.escape(ident)}\b", new_name, result)

    return result


def _augment_inject_decoy(code: str, rng: random.Random) -> str:
    """Inject benign code that superficially resembles a vulnerability pattern."""
    decoys = [
        "\n    // bounds check\n    if (len > 0 && len < MAX_SIZE) { /* ok */ }\n",
        "\n    // input validation\n    assert(input != NULL);\n",
        "\n    // safe copy\n    size_t safe_len = strnlen(src, sizeof(buf));\n",
        "\n    // null check\n    if (ptr == NULL) return -1;\n",
    ]
    lines = code.splitlines()
    if len(lines) < 5:
        return code
    insert_at = rng.randint(2, len(lines) - 2)
    decoy = rng.choice(decoys)
    lines.insert(insert_at, decoy)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Instruction formatting
# ---------------------------------------------------------------------------

def _format_instruction_pair(
    code: str,
    is_vulnerable: bool,
    cwe: str | None,
    vul_lines: list[int] | None,
) -> dict[str, str]:
    """Format a single sample as an instruction-tuning pair."""
    instruction = f"Analyze this code for vulnerabilities:\n\n```c\n{code}\n```"

    if is_vulnerable and cwe:
        cwe_name = _CWE_NAMES.get(cwe, "Unknown Vulnerability")
        severity = _CWE_SEVERITY.get(cwe, "MEDIUM")

        # Generate exploit sketch based on CWE
        sketch = _generate_exploit_sketch(cwe, code)
        fix = _generate_fix_suggestion(cwe)

        # Determine line range if we have per-line labels
        line_start = 1
        line_end = len(code.splitlines())
        if vul_lines:
            vul_indices = [i + 1 for i, v in enumerate(vul_lines) if v == 1]
            if vul_indices:
                line_start = min(vul_indices)
                line_end = max(vul_indices)

        response = json.dumps({
            "is_vulnerable": True,
            "cwe_id": cwe,
            "cwe_name": cwe_name,
            "severity": severity,
            "confidence": round(random.uniform(0.80, 0.99), 2),
            "line_start": line_start,
            "line_end": line_end,
            "exploit_sketch": sketch,
            "suggested_fix": fix,
        }, indent=2)
    else:
        response = json.dumps({
            "is_vulnerable": False,
            "confidence": round(random.uniform(0.85, 0.99), 2),
        }, indent=2)

    return {"instruction": instruction, "response": response}


def _generate_exploit_sketch(cwe: str, code: str) -> str:
    """Generate a plausible exploit sketch for training data."""
    sketches: dict[str, str] = {
        "CWE-119": "Buffer overflow due to unchecked copy operation. An attacker can supply oversized input to overflow the buffer and potentially execute arbitrary code.",
        "CWE-120": "Buffer copy without size validation. Attacker-controlled input length can exceed buffer capacity, leading to memory corruption.",
        "CWE-787": "Out-of-bounds write via unvalidated index or size parameter. Can corrupt adjacent memory structures.",
        "CWE-125": "Out-of-bounds read through unchecked array access. Can leak sensitive data from adjacent memory.",
        "CWE-476": "NULL pointer dereference after failed allocation or lookup. Attacker can trigger a denial-of-service crash.",
        "CWE-189": "Integer signedness or truncation issue. Can cause incorrect size calculations leading to buffer overflow.",
        "CWE-190": "Integer overflow in size calculation. Can wrap to small value, causing undersized allocation followed by overflow.",
        "CWE-20": "Missing input validation allows malformed data to reach security-critical operations.",
        "CWE-22": "Path traversal via unsanitized file path. Attacker can read/write arbitrary files using ../ sequences.",
        "CWE-78": "OS command injection via unsanitized input passed to system() or popen(). Attacker can execute arbitrary commands.",
        "CWE-89": "SQL injection through string concatenation in query construction. Attacker can extract or modify database contents.",
        "CWE-79": "Cross-site scripting via unsanitized user input reflected in HTML output.",
    }
    return sketches.get(cwe, "Potential vulnerability detected in the code logic.")


def _generate_fix_suggestion(cwe: str) -> str:
    """Generate a fix suggestion for training data."""
    fixes: dict[str, str] = {
        "CWE-119": "Add bounds checking before memory operations. Use safer alternatives like snprintf() instead of sprintf().",
        "CWE-120": "Validate source size against destination buffer capacity before copying. Use strncpy() with explicit size limit.",
        "CWE-787": "Validate array indices and sizes against buffer boundaries before write operations.",
        "CWE-125": "Add bounds checking before array access. Validate index is within [0, array_size) range.",
        "CWE-476": "Add NULL check after allocation/lookup before dereferencing. Return error on NULL.",
        "CWE-189": "Use consistent signed/unsigned types. Cast explicitly and validate ranges before arithmetic.",
        "CWE-190": "Check for overflow before arithmetic: if (a > SIZE_MAX - b) return error; Use safe integer arithmetic functions.",
        "CWE-20": "Validate all input parameters at function entry. Check lengths, ranges, and formats before use.",
        "CWE-22": "Canonicalize file paths and verify they remain within the expected directory. Reject paths containing '..'.",
        "CWE-78": "Use parameterized execution (execvp) instead of shell interpretation. Sanitize all user input.",
        "CWE-89": "Use parameterized queries or prepared statements. Never concatenate user input into SQL strings.",
        "CWE-79": "HTML-encode all user-supplied output. Use a templating engine with auto-escaping enabled.",
    }
    return fixes.get(cwe, "Review and fix the identified security issue.")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Prepare Devign data for Gemma 4 E4B LoRA fine-tuning.")
    ap.add_argument("--in", dest="inp", type=Path, default=None, help="Optional input JSONL (skips HF download).")
    ap.add_argument("--out-dir", dest="out_dir", type=Path, default=Path("data"), help="Output directory.")
    ap.add_argument("--limit", type=int, default=5000, help="Max training samples.")
    ap.add_argument("--test-limit", type=int, default=100, help="Max test samples.")
    ap.add_argument("--val-limit", type=int, default=100, help="Max validation samples.")
    ap.add_argument("--augment", action="store_true", default=True, help="Apply synthetic augmentation.")
    ap.add_argument("--augment-factor", type=int, default=2, help="Augmentation multiplier for vulnerable samples.")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # --- 1. Load raw data ---
    if args.inp is None:
        try:
            from datasets import load_dataset
            print("Loading DetectVul/devign from Hugging Face...")
            ds = load_dataset("DetectVul/devign", split="train")
            raw_rows = list(ds)
            print(f"Loaded {len(raw_rows)} rows from HF.")
        except Exception as e:
            print(f"Failed to load from HF: {e}")
            return
    else:
        raw_rows = _read_jsonl(args.inp)

    # --- 2. Process and classify ---
    all_samples: list[dict] = []
    seen_ids: set[str] = set()

    for i, r in enumerate(raw_rows):
        func = r.get("func")
        if not func or len(func.split("\n")) > 80:
            continue

        target = bool(r.get("target", False))
        label = r.get("label", [])
        vul_lines_code: list[str] = []
        vl = r.get("vul_lines")
        if vl and isinstance(vl, dict):
            vul_lines_code = vl.get("code", [])

        cwe = infer_cwe(vul_lines_code, func) if target else None
        diff = _build_diff(func, label, rng, target)

        # Unique sample ID
        original_id = str(r.get("commit_id") or r.get("id") or f"row-{i}")
        sample_id = original_id
        suffix = 0
        while sample_id in seen_ids:
            suffix += 1
            sample_id = f"{original_id}_{suffix}"
        seen_ids.add(sample_id)

        # Instruction pair
        pair = _format_instruction_pair(func, target, cwe, label)

        sample = {
            "sample_id": sample_id,
            "instruction": pair["instruction"],
            "response": pair["response"],
            "is_vulnerable": target,
            "cwe": cwe,
            "func": func,
            "label": label,
        }
        all_samples.append(sample)

    print(f"Processed {len(all_samples)} samples.")

    # --- 3. Synthetic augmentation ---
    if args.augment:
        vuln_samples = [s for s in all_samples if s["is_vulnerable"]]
        augmented: list[dict] = []

        for s in vuln_samples:
            for aug_idx in range(args.augment_factor - 1):
                func = s["func"]

                # Apply random augmentation
                aug_type = rng.choice(["rename", "decoy", "both"])
                if aug_type in ("rename", "both"):
                    func = _augment_rename_vars(func, rng)
                if aug_type in ("decoy", "both"):
                    func = _augment_inject_decoy(func, rng)

                pair = _format_instruction_pair(func, True, s["cwe"], s.get("label"))
                aug_id = f"{s['sample_id']}_aug{aug_idx}"
                augmented.append({
                    "sample_id": aug_id,
                    "instruction": pair["instruction"],
                    "response": pair["response"],
                    "is_vulnerable": True,
                    "cwe": s["cwe"],
                    "func": func,
                    "label": s.get("label", []),
                })

        all_samples.extend(augmented)
        print(f"After augmentation: {len(all_samples)} samples (+{len(augmented)} augmented).")

    # --- 4. Split: train / val / test ---
    rng.shuffle(all_samples)

    # Stratified split: ensure each split has balanced vulnerable/safe
    vuln = [s for s in all_samples if s["is_vulnerable"]]
    safe = [s for s in all_samples if not s["is_vulnerable"]]
    rng.shuffle(vuln)
    rng.shuffle(safe)

    test_vuln = vuln[:args.test_limit // 2]
    test_safe = safe[:args.test_limit // 2]
    vuln = vuln[args.test_limit // 2:]
    safe = safe[args.test_limit // 2:]

    val_vuln = vuln[:args.val_limit // 2]
    val_safe = safe[:args.val_limit // 2]
    vuln = vuln[args.val_limit // 2:]
    safe = safe[args.val_limit // 2:]

    train_vuln = vuln[:args.limit // 2]
    train_safe = safe[:args.limit // 2]

    test_set = test_vuln + test_safe
    val_set = val_vuln + val_safe
    train_set = train_vuln + train_safe

    rng.shuffle(test_set)
    rng.shuffle(val_set)
    rng.shuffle(train_set)

    # --- 5. Write output (instruction pairs only) ---
    def _to_output(samples: list[dict]) -> list[dict]:
        return [{"instruction": s["instruction"], "response": s["response"]} for s in samples]

    _write_jsonl(args.out_dir / "gemma_train.jsonl", _to_output(train_set))
    _write_jsonl(args.out_dir / "gemma_val.jsonl", _to_output(val_set))
    _write_jsonl(args.out_dir / "gemma_test.jsonl", _to_output(test_set))

    print(f"\nOutput written to {args.out_dir}/:")
    print(f"  gemma_train.jsonl: {len(train_set)} samples")
    print(f"  gemma_val.jsonl:   {len(val_set)} samples")
    print(f"  gemma_test.jsonl:  {len(test_set)} samples")

    # Stats
    for name, split in [("train", train_set), ("val", val_set), ("test", test_set)]:
        n_vuln = sum(1 for s in split if s["is_vulnerable"])
        n_safe = len(split) - n_vuln
        print(f"  {name}: {n_vuln} vulnerable, {n_safe} safe")


if __name__ == "__main__":
    main()
