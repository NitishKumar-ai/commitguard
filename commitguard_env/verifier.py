"""CommitGuard v3 L2 Verifier — Sandbox exploit generation and execution.

This module is responsible for verifying raw vulnerability findings by generating
and executing proof-of-concept exploits in an isolated Docker sandbox.
"""

from __future__ import annotations

import logging
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import Finding, SandboxConfig, VerificationVerdict, VerifiedFinding
from .scanner_v2 import _generate_json, _load_gemma_model

logger = logging.getLogger(__name__)

_VERIFIER_SYSTEM_PROMPT = """\
You are CommitGuard Verifier, an expert security researcher.
Your task is to write a self-contained Python script to verify if a reported vulnerability is exploitable.
The script will be executed in an isolated Docker container with the repository mounted.

You MUST respond ONLY with a JSON object containing the exploit script. No markdown fences outside the JSON.

{{
  "exploit_code": "# Python code goes here"
}}

Requirements for the exploit script:
1. It MUST import the vulnerable module from the repository and call the vulnerable function/class.
2. It MUST provide input that triggers the vulnerability.
3. If the exploit is successful, the script MUST print exactly "EXPLOIT_CONFIRMED" to stdout.
4. If the exploit fails or the code is safe, the script MUST exit normally (code 0) without printing the confirmation string.
5. If the script crashes, it means the exploit failed or was invalid.

Vulnerability to verify:
CWE: {cwe_id} ({cwe_name})
File: {file_path}
Lines: {line_start}-{line_end}
Suggested sketch: {exploit_sketch}
"""


class ExploitVerifier:
    """Verifies findings by generating and running exploits in a sandbox."""

    def __init__(
        self,
        sandbox_config: SandboxConfig | None = None,
        model_path: str = "",
        base_model: str = "google/gemma-4-4b-it",
    ) -> None:
        self.config = sandbox_config or SandboxConfig()
        self._model_path = model_path
        self._base_model = base_model
        self._model: Any = None
        self._tokenizer: Any = None

    def _ensure_model(self) -> None:
        if self._model is None:
            self._model, self._tokenizer = _load_gemma_model(
                self._model_path, self._base_model
            )

    def _generate_exploit_code(self, finding: Finding, code_context: str) -> str:
        self._ensure_model()

        system_prompt = _VERIFIER_SYSTEM_PROMPT.format(
            cwe_id=finding.cwe_id,
            cwe_name=finding.cwe_name,
            file_path=finding.file,
            line_start=finding.line_start,
            line_end=finding.line_end,
            exploit_sketch=finding.exploit_sketch,
        )

        user_prompt = f"### Vulnerable Code Context\n```\n{code_context}\n```\n\nGenerate the exploit script JSON."

        result = _generate_json(
            self._model, self._tokenizer,
            system_prompt, user_prompt,
            max_new_tokens=1024
        )

        return result.get("exploit_code", "")

    def _run_in_sandbox(self, exploit_code: str, repo_path: Path) -> tuple[int, str, int]:
        """Execute the exploit in a Docker sandbox and return (exit_code, output, duration_ms)."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            exploit_path = tmp_path / "exploit.py"
            exploit_path.write_text(exploit_code, encoding="utf-8")

            # Build docker run command
            cmd = [
                "docker", "run", "--rm",
                f"--cpus={self.config.cpu_limit}",
                f"--memory={self.config.memory_limit}",
                "-v", f"{tmp_path}:/workspace:ro",
                "-v", f"{repo_path.absolute()}:/repo:ro",
                "-e", "PYTHONPATH=/repo",
            ]

            if self.config.network_disabled:
                cmd.extend(["--network", "none"])
            if self.config.read_only_rootfs:
                cmd.append("--read-only")

            cmd.append(self.config.image)

            start_time = time.time()
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.config.timeout_seconds,
                )
                exit_code = result.returncode
                output = result.stdout + "\n" + result.stderr
            except subprocess.TimeoutExpired as exc:
                exit_code = 124  # Standard timeout exit code
                output = f"Execution timed out after {self.config.timeout_seconds}s\n"
                if exc.stdout:
                    output += exc.stdout.decode("utf-8", "replace") + "\n"
                if exc.stderr:
                    output += exc.stderr.decode("utf-8", "replace")
            except Exception as exc:
                exit_code = 1
                output = f"Sandbox execution error: {exc}"

            duration_ms = int((time.time() - start_time) * 1000)
            return exit_code, output, duration_ms

    def _determine_verdict(self, exit_code: int, output: str) -> VerificationVerdict:
        if exit_code == 0:
            if "EXPLOIT_CONFIRMED" in output:
                return "CONFIRMED"
            return "FALSE_POSITIVE"
        return "UNVERIFIABLE"

    def verify(self, finding: Finding, repo_path: Path, commit_sha: str) -> VerifiedFinding:
        """Attempt to verify a finding."""
        logger.info("Verifying %s in %s", finding.cwe_id, finding.file)

        # Get broader context for the exploit generator
        full_path = repo_path / finding.file
        code_context = finding.code_snippet
        if full_path.is_file():
            try:
                lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines()
                ctx_start = max(0, finding.line_start - 50)
                ctx_end = min(len(lines), finding.line_end + 50)
                code_context = "\n".join(lines[ctx_start:ctx_end])
            except Exception:
                pass

        exploit_code = self._generate_exploit_code(finding, code_context)
        
        if not exploit_code:
            logger.warning("Failed to generate exploit code for %s", finding.cwe_id)
            return VerifiedFinding(
                finding=finding,
                verdict="UNVERIFIABLE",
                exploit_code="",
                exploit_output="Failed to generate exploit",
                execution_time_ms=0,
                sandbox_exit_code=1,
                verified_at=datetime.now(timezone.utc).isoformat()
            )

        exit_code, output, duration_ms = self._run_in_sandbox(exploit_code, repo_path)
        verdict = self._determine_verdict(exit_code, output)

        logger.info("Verification result: %s (exit_code=%d, duration=%dms)", verdict, exit_code, duration_ms)

        return VerifiedFinding(
            finding=finding,
            verdict=verdict,
            exploit_code=exploit_code,
            exploit_output=output.strip(),
            execution_time_ms=duration_ms,
            sandbox_exit_code=exit_code,
            verified_at=datetime.now(timezone.utc).isoformat()
        )

    def verify_batch(self, findings: list[Finding], repo_path: Path, commit_sha: str) -> list[VerifiedFinding]:
        """Verify a batch of findings."""
        verified_findings = []
        for finding in findings:
            verified = self.verify(finding, repo_path, commit_sha)
            verified_findings.append(verified)
        return verified_findings
