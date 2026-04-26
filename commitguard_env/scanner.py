from __future__ import annotations

from typing import Any

from .inference import format_prompt, generate, load_model
from .models import ScanResult
from .parse_action import parse_action


class CommitGuardScanner:
    """
    Scanner for CommitGuard vulnerabilities.
    Keeps the model in memory to allow fast scanning of multiple diffs.
    """

    def __init__(self, model_path: str = "inmodel-labs/commitguard-llama-3b", is_lora: bool = False, base_model: str = None) -> None:
        self.model_path = model_path
        self.is_lora = is_lora
        self.base_model = base_model
        self.model: Any = None
        self.tokenizer: Any = None

    def load(self) -> None:
        """Load the model and tokenizer into memory."""
        if self.model is None or self.tokenizer is None:
            self.model, self.tokenizer = load_model(self.model_path, self.is_lora, self.base_model)

    def scan(self, diff: str, available_files: list[str] = None) -> ScanResult:
        """
        Scan a given diff for vulnerabilities.
        """
        self.load()

        prompt = format_prompt(diff, available_files)
        response = generate(self.model, self.tokenizer, prompt)
        action = parse_action(response)

        # Map to ScanResult
        return ScanResult(
            is_vulnerable=action.is_vulnerable if action.is_vulnerable is not None else False,
            cwe=action.vuln_type,
            exploit_sketch=action.exploit_sketch,
            raw_response=response,
            parse_error=action.parse_error
        )


def scan(diff: str, model_path: str = "inmodel-labs/commitguard-llama-3b", is_lora: bool = False, base_model: str = None) -> ScanResult:
    """
    Convenience method to scan a single diff. Loads the model, scans, and returns the result.
    If scanning multiple diffs, prefer instantiating CommitGuardScanner directly to avoid reloading the model.
    """
    scanner = CommitGuardScanner(model_path=model_path, is_lora=is_lora, base_model=base_model)
    return scanner.scan(diff)
