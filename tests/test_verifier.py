"""Tests for commitguard_env.verifier — L2 Exploit Sandbox."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from commitguard_env.models import Finding
from commitguard_env.verifier import ExploitVerifier


@pytest.fixture
def sample_finding() -> Finding:
    return Finding(
        file="vuln.py",
        line_start=10,
        line_end=15,
        cwe_id="CWE-78",
        cwe_name="OS Command Injection",
        severity="CRITICAL",
        confidence=0.9,
        exploit_sketch="Trigger via shell=True",
        suggested_fix="Use list notation for args",
        code_snippet="subprocess.call(user_input, shell=True)",
    )


def test_verdict_logic_confirmed() -> None:
    verifier = ExploitVerifier()
    # Exit 0 + EXPLOIT_CONFIRMED -> CONFIRMED
    verdict = verifier._determine_verdict(0, "some output\nEXPLOIT_CONFIRMED\nmore output")
    assert verdict == "CONFIRMED"


def test_verdict_logic_false_positive() -> None:
    verifier = ExploitVerifier()
    # Exit 0 + NO string -> FALSE_POSITIVE
    verdict = verifier._determine_verdict(0, "some output\nall good")
    assert verdict == "FALSE_POSITIVE"


def test_verdict_logic_unverifiable() -> None:
    verifier = ExploitVerifier()
    # Exit non-0 -> UNVERIFIABLE
    verdict = verifier._determine_verdict(1, "crash")
    assert verdict == "UNVERIFIABLE"
    
    verdict = verifier._determine_verdict(124, "timeout")
    assert verdict == "UNVERIFIABLE"


@patch("commitguard_env.verifier.subprocess.run")
@patch("commitguard_env.verifier._load_gemma_model")
@patch("commitguard_env.verifier._generate_json")
def test_verify_end_to_end(mock_gen_json, mock_load_model, mock_subproc_run, sample_finding) -> None:
    # Setup mocks
    mock_load_model.return_value = (MagicMock(), MagicMock())
    mock_gen_json.return_value = {"exploit_code": "print('EXPLOIT_CONFIRMED')"}
    
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "EXPLOIT_CONFIRMED\n"
    mock_result.stderr = ""
    mock_subproc_run.return_value = mock_result
    
    verifier = ExploitVerifier()
    
    verified = verifier.verify(sample_finding, Path("/tmp/repo"), "latest")
    
    assert verified.verdict == "CONFIRMED"
    assert verified.exploit_code == "print('EXPLOIT_CONFIRMED')"
    assert "EXPLOIT_CONFIRMED" in verified.exploit_output
