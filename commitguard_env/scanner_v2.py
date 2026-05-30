"""CommitGuard v2 Scanner — 3-pass Plan→Execute→Review scanning loop.

Orchestrates vulnerability detection over entire repositories using
Gemma 4 E4B (LoRA) with chunked memory and cross-file context.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

from .models import CodeChunk, Finding

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SCANNABLE_EXTENSIONS: set[str] = {
    ".py", ".c", ".cpp", ".h", ".hpp",
    ".js", ".ts", ".jsx", ".tsx",
    ".go", ".java", ".rb", ".rs",
    ".php", ".cs", ".swift",
}

# Severity mapping by CWE family
_CWE_SEVERITY: dict[str, str] = {
    "CWE-78": "CRITICAL",   # Command injection
    "CWE-89": "CRITICAL",   # SQL injection
    "CWE-119": "HIGH",      # Buffer overflow
    "CWE-120": "HIGH",
    "CWE-787": "HIGH",      # Out-of-bounds write
    "CWE-476": "MEDIUM",    # NULL pointer deref
    "CWE-22": "MEDIUM",     # Path traversal
    "CWE-79": "MEDIUM",     # XSS
    "CWE-20": "MEDIUM",     # Input validation
    "CWE-190": "MEDIUM",    # Integer overflow
    "CWE-189": "MEDIUM",    # Integer issues
    "CWE-125": "HIGH",      # Out-of-bounds read
}

_CWE_NAMES: dict[str, str] = {
    "CWE-78": "OS Command Injection",
    "CWE-89": "SQL Injection",
    "CWE-79": "Cross-site Scripting",
    "CWE-119": "Improper Restriction of Operations within the Bounds of a Memory Buffer",
    "CWE-120": "Buffer Copy without Checking Size of Input",
    "CWE-125": "Out-of-bounds Read",
    "CWE-787": "Out-of-bounds Write",
    "CWE-476": "NULL Pointer Dereference",
    "CWE-22": "Improper Limitation of a Pathname to a Restricted Directory",
    "CWE-20": "Improper Input Validation",
    "CWE-190": "Integer Overflow or Wraparound",
    "CWE-189": "Numeric Errors",
}

# System prompt for Gemma 4 E4B vulnerability analysis
_GEMMA_SYSTEM_PROMPT = """\
You are CommitGuard, an expert security auditor. Analyze the given code for exploitable vulnerabilities.

Respond ONLY with a JSON object. Do not include any other text, markdown, or explanation outside the JSON.

If a vulnerability is found:
{
  "is_vulnerable": true,
  "cwe_id": "CWE-XXX",
  "cwe_name": "Name of the vulnerability class",
  "severity": "CRITICAL|HIGH|MEDIUM|LOW",
  "confidence": 0.0 to 1.0,
  "exploit_sketch": "Concrete attack scenario describing the vulnerability",
  "suggested_fix": "Specific code fix recommendation",
  "line_start": <first vulnerable line number>,
  "line_end": <last vulnerable line number>
}

If the code is safe:
{
  "is_vulnerable": false,
  "confidence": 0.0 to 1.0
}

Focus on these vulnerability classes:
- CWE-119/120/787: Buffer overflow, out-of-bounds read/write
- CWE-476: NULL pointer dereference
- CWE-189/190: Integer overflow, signedness issues
- CWE-20: Missing input validation
- CWE-22: Path traversal
- CWE-78: Command injection
- CWE-89: SQL injection
- CWE-79: Cross-site scripting (XSS)
"""

_GEMMA_REVIEW_PROMPT = """\
You are CommitGuard reviewing a previously flagged potential vulnerability.

Re-examine this code in broader context. Confirm or reject the finding.

Previously flagged:
- CWE: {cwe_id}
- File: {file_path}
- Lines: {line_start}-{line_end}
- Original exploit sketch: {exploit_sketch}

Respond with JSON only:
{{
  "confirmed": true or false,
  "confidence": 0.0 to 1.0,
  "reasoning": "Why this is/isn't a real vulnerability in context"
}}
"""


# ---------------------------------------------------------------------------
# Model loader
# ---------------------------------------------------------------------------


def _load_gemma_model(
    model_path: str,
    base_model: str = "google/gemma-4-4b-it",
    max_seq_length: int = 4096,
) -> tuple[Any, Any]:
    """Load Gemma 4 E4B with LoRA adapter for inference.

    Falls back to base model if no adapter path is provided.
    """
    try:
        import torch
    except ImportError:
        print("Error: PyTorch is required. Install with: pip install 'commitguard[scan]'")
        sys.exit(1)

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from peft import PeftModel
    except ImportError:
        print("Error: transformers + peft required. Install with: pip install 'commitguard[scan]'")
        sys.exit(1)

    logger.info("Loading base model: %s", base_model)

    # 4-bit quantization config
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        quantization_config=bnb_config,
        device_map="auto",
        torch_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
    )

    # Load LoRA adapter if provided
    if model_path and model_path != base_model:
        logger.info("Loading LoRA adapter: %s", model_path)
        model = PeftModel.from_pretrained(model, model_path)

    model.eval()
    logger.info("Model loaded successfully.")
    return model, tokenizer


def _generate_json(
    model: Any,
    tokenizer: Any,
    system_prompt: str,
    user_prompt: str,
    max_new_tokens: int = 512,
) -> dict[str, Any]:
    """Generate a JSON response from the model."""
    import torch

    messages = [
        {"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"},
    ]

    # Use chat template if available
    if hasattr(tokenizer, "apply_chat_template"):
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    else:
        prompt = f"{system_prompt}\n\n{user_prompt}"

    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=4096)
    if torch.cuda.is_available():
        inputs = {k: v.cuda() for k, v in inputs.items()}

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=1.0,
        )

    response = tokenizer.decode(output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

    # Parse JSON from response (handle markdown code blocks)
    response = response.strip()
    if response.startswith("```"):
        # Strip markdown fences
        lines = response.split("\n")
        response = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        import re
        json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        logger.warning("Failed to parse JSON from model response: %s", response[:200])
        return {"is_vulnerable": False, "confidence": 0.0, "parse_error": response[:200]}


# ---------------------------------------------------------------------------
# RepoScanner — 3-pass scan loop
# ---------------------------------------------------------------------------


class RepoScanner:
    """Scan an entire repository for vulnerabilities using a 3-pass loop.

    Pass 1 (Plan):   Identify attack surface and prioritize files.
    Pass 2 (Execute): Run model inference on each file chunk.
    Pass 3 (Review):  Cross-validate findings and filter false positives.
    """

    def __init__(
        self,
        model_path: str = "",
        base_model: str = "google/gemma-4-4b-it",
        *,
        confidence_threshold: float = 0.5,
        review_threshold: float = 0.6,
        max_chunks_per_file: int = 20,
    ) -> None:
        self._model_path = model_path
        self._base_model = base_model
        self._confidence_threshold = confidence_threshold
        self._review_threshold = review_threshold
        self._max_chunks_per_file = max_chunks_per_file
        self._model: Any = None
        self._tokenizer: Any = None

    def _ensure_model(self) -> None:
        if self._model is None:
            self._model, self._tokenizer = _load_gemma_model(
                self._model_path, self._base_model
            )

    def reload_adapter(self, new_adapter_path: str) -> None:
        """Hot-swap the PEFT LoRA adapter for the active model."""
        if self._model is None:
            self._model_path = new_adapter_path
            return
            
        try:
            from peft import PeftModel
        except ImportError:
            logger.warning("peft not installed, cannot hot-swap adapter.")
            return

        logger.info("Hot-swapping LoRA adapter to: %s", new_adapter_path)
        
        if isinstance(self._model, PeftModel):
            base_model = self._model.get_base_model()
            self._model = PeftModel.from_pretrained(base_model, new_adapter_path)
        else:
            self._model = PeftModel.from_pretrained(self._model, new_adapter_path)
            
        self._model.eval()
        self._model_path = new_adapter_path
        logger.info("Adapter hot-swap complete.")

    # -- Pass 1: Plan --

    def _plan(self, repo_path: Path) -> list[str]:
        """Identify and prioritize scannable files.

        Prioritizes files likely to contain vulnerabilities:
        - Entry points (main, app, server, handler, route)
        - Data flow files (db, query, sql, auth, login)
        - External interface files (api, endpoint, controller)
        """
        all_files: list[tuple[int, str]] = []

        # Priority keywords (higher = scanned first)
        high_priority = {"main", "app", "server", "handler", "route", "api", "endpoint", "controller"}
        medium_priority = {"db", "database", "query", "sql", "auth", "login", "session", "token", "password"}
        low_priority = {"util", "helper", "config", "test", "spec", "mock"}

        for fp in sorted(repo_path.rglob("*")):
            if not fp.is_file() or fp.suffix not in _SCANNABLE_EXTENSIONS:
                continue
            parts = fp.relative_to(repo_path).parts
            if any(p.startswith(".") or p in {"node_modules", "__pycache__", ".git", "vendor", "venv", ".venv"} for p in parts):
                continue

            rel = str(fp.relative_to(repo_path)).replace("\\", "/")
            name_lower = fp.stem.lower()

            if any(kw in name_lower for kw in high_priority):
                priority = 3
            elif any(kw in name_lower for kw in medium_priority):
                priority = 2
            elif any(kw in name_lower for kw in low_priority):
                priority = 0
            else:
                priority = 1

            all_files.append((priority, rel))

        # Sort by priority descending
        all_files.sort(key=lambda x: x[0], reverse=True)
        file_list = [f for _, f in all_files]

        logger.info("Plan: %d scannable files identified", len(file_list))
        return file_list

    # -- Pass 2: Execute --

    def _execute(
        self,
        repo_path: Path,
        file_list: list[str],
        chunks_by_file: dict[str, list[CodeChunk]],
        context_retriever: Optional[Any] = None,
    ) -> list[Finding]:
        """Run model inference on each file's chunks."""
        self._ensure_model()
        candidates: list[Finding] = []

        for file_path in file_list:
            file_chunks = chunks_by_file.get(file_path, [])
            if not file_chunks:
                # Read the file directly if no chunks
                full_path = repo_path / file_path
                if not full_path.is_file():
                    continue
                try:
                    content = full_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                file_chunks = [CodeChunk(
                    file_path=file_path,
                    start_line=1,
                    end_line=len(content.splitlines()),
                    content=content,
                    token_count=len(content.split()),
                )]

            for chunk in file_chunks[:self._max_chunks_per_file]:
                # Build context prompt
                context_str = ""
                if context_retriever is not None:
                    try:
                        related = context_retriever.retrieve(file_path, chunk.content[:200])
                        if related:
                            context_parts = [f"// Context from {c.file_path}:{c.start_line}-{c.end_line}\n{c.content[:300]}" for c in related[:3]]
                            context_str = "\n\n".join(context_parts)
                    except Exception:
                        pass

                user_prompt = f"File: {file_path} (lines {chunk.start_line}-{chunk.end_line})\n\n"
                if context_str:
                    user_prompt += f"### Related Context\n{context_str}\n\n"
                user_prompt += f"### Code to Analyze\n```\n{chunk.content}\n```"

                result = _generate_json(
                    self._model, self._tokenizer,
                    _GEMMA_SYSTEM_PROMPT, user_prompt
                )

                if result.get("is_vulnerable") and result.get("confidence", 0) >= self._confidence_threshold:
                    cwe_id = result.get("cwe_id", "CWE-OTHER")
                    finding = Finding(
                        file=file_path,
                        line_start=result.get("line_start", chunk.start_line),
                        line_end=result.get("line_end", chunk.end_line),
                        cwe_id=cwe_id,
                        cwe_name=result.get("cwe_name", _CWE_NAMES.get(cwe_id, "Unknown")),
                        severity=result.get("severity", _CWE_SEVERITY.get(cwe_id, "MEDIUM")),
                        confidence=float(result.get("confidence", 0.5)),
                        exploit_sketch=result.get("exploit_sketch", ""),
                        suggested_fix=result.get("suggested_fix", ""),
                        code_snippet=chunk.content[:500],
                    )
                    candidates.append(finding)
                    logger.info("Candidate finding: %s in %s:%d-%d (conf=%.2f)",
                                finding.cwe_id, finding.file, finding.line_start, finding.line_end, finding.confidence)

        logger.info("Execute: %d candidate findings", len(candidates))
        return candidates

    # -- Pass 3: Review --

    def _review(self, repo_path: Path, candidates: list[Finding]) -> list[Finding]:
        """Cross-validate candidates and filter false positives."""
        self._ensure_model()
        confirmed: list[Finding] = []

        for finding in candidates:
            # Read broader context for the file
            full_path = repo_path / finding.file
            broader_context = ""
            if full_path.is_file():
                try:
                    lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines()
                    # Expand context window: ±20 lines around the finding
                    ctx_start = max(0, finding.line_start - 20)
                    ctx_end = min(len(lines), finding.line_end + 20)
                    broader_context = "\n".join(lines[ctx_start:ctx_end])
                except Exception:
                    broader_context = finding.code_snippet

            review_prompt = _GEMMA_REVIEW_PROMPT.format(
                cwe_id=finding.cwe_id,
                file_path=finding.file,
                line_start=finding.line_start,
                line_end=finding.line_end,
                exploit_sketch=finding.exploit_sketch,
            )
            user_prompt = f"### Broader Context\n```\n{broader_context}\n```"

            result = _generate_json(
                self._model, self._tokenizer,
                review_prompt, user_prompt,
            )

            review_confidence = float(result.get("confidence", 0.0))
            is_confirmed = result.get("confirmed", False)

            if is_confirmed and review_confidence >= self._review_threshold:
                # Update confidence to the review confidence if higher
                final_confidence = max(finding.confidence, review_confidence)
                from dataclasses import replace
                updated = replace(finding, confidence=final_confidence)
                confirmed.append(updated)
                logger.info("Confirmed: %s in %s (conf=%.2f → %.2f)",
                            finding.cwe_id, finding.file, finding.confidence, final_confidence)
            else:
                logger.info("Rejected: %s in %s (review_conf=%.2f, confirmed=%s)",
                            finding.cwe_id, finding.file, review_confidence, is_confirmed)

        logger.info("Review: %d/%d findings confirmed", len(confirmed), len(candidates))
        return confirmed

    # -- Public API --

    def scan(self, repo_path: Path) -> list[Finding]:
        """Execute the full 3-pass scan loop on a repository.

        Parameters
        ----------
        repo_path : Path
            Path to the cloned repository root.

        Returns
        -------
        list[Finding]
            Final list of confirmed vulnerability findings.
        """
        logger.info("Starting 3-pass scan on %s", repo_path)

        # Optional: set up memory management
        chunker = None
        store = None
        retriever = None
        chunks_by_file: dict[str, list[CodeChunk]] = {}

        try:
            from .memory import CodeChunker, EmbeddingStore, ImportGraphBuilder, ContextRetriever

            chunker = CodeChunker()
            all_chunks = chunker.chunk_repo(repo_path)

            # Group chunks by file
            for chunk in all_chunks:
                chunks_by_file.setdefault(chunk.file_path, []).append(chunk)

            # Build embedding index and import graph
            try:
                store = EmbeddingStore()
                store.add(all_chunks)

                graph_builder = ImportGraphBuilder()
                import_graph = graph_builder.build(repo_path)

                retriever = ContextRetriever(store, import_graph)
                logger.info("Memory system initialized: %d chunks indexed", len(all_chunks))
            except ImportError:
                logger.warning("sentence-transformers/faiss not available; scanning without cross-file context")
        except ImportError:
            logger.warning("Memory module not available; scanning without chunking")

        # Pass 1: Plan
        file_list = self._plan(repo_path)

        # Pass 2: Execute
        candidates = self._execute(repo_path, file_list, chunks_by_file, retriever)

        if not candidates:
            logger.info("No vulnerabilities detected.")
            return []

        # Pass 3: Review
        findings = self._review(repo_path, candidates)

        # Deduplicate: if same file + overlapping lines + same CWE, keep highest confidence
        findings = self._deduplicate(findings)

        logger.info("Scan complete: %d findings", len(findings))
        return findings

    @staticmethod
    def _deduplicate(findings: list[Finding]) -> list[Finding]:
        """Remove duplicate findings (same file, overlapping lines, same CWE)."""
        if not findings:
            return []

        # Sort by confidence descending
        sorted_findings = sorted(findings, key=lambda f: f.confidence, reverse=True)
        kept: list[Finding] = []

        for finding in sorted_findings:
            is_dup = False
            for existing in kept:
                if (
                    finding.file == existing.file
                    and finding.cwe_id == existing.cwe_id
                    and finding.line_start <= existing.line_end
                    and finding.line_end >= existing.line_start
                ):
                    is_dup = True
                    break
            if not is_dup:
                kept.append(finding)

        return kept
