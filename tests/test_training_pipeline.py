"""Tests for commitguard_env.training_pipeline — L3 auto-doc."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from commitguard_env.models import Finding, VerifiedFinding
from commitguard_env.training_pipeline import TrainingDataPipeline


@pytest.fixture
def sample_verified() -> VerifiedFinding:
    finding = Finding(
        file="vuln.py", line_start=10, line_end=15,
        cwe_id="CWE-78", cwe_name="OS Command Injection",
        severity="CRITICAL", confidence=0.9,
        exploit_sketch="Trigger via shell=True",
        suggested_fix="Use list notation for args",
        code_snippet="subprocess.call(user_input, shell=True)",
    )
    return VerifiedFinding(
        finding=finding,
        verdict="CONFIRMED",
        exploit_code="print('EXPLOIT_CONFIRMED')",
        exploit_output="EXPLOIT_CONFIRMED",
        execution_time_ms=100,
        sandbox_exit_code=0,
        verified_at="2026-05-30T10:00:00Z"
    )


def test_document_appends_to_buffer(tmp_path: Path, sample_verified: VerifiedFinding) -> None:
    pipeline = TrainingDataPipeline(local_buffer_dir=tmp_path)
    
    pair = pipeline.document(sample_verified, "https://github.com/foo/bar", "abc1234")
    
    assert pair.verdict == "CONFIRMED"
    assert pair.repo_url == "https://github.com/foo/bar"
    assert pipeline.get_new_examples_count() == 1
    
    assert pipeline.buffer_file.exists()
    
    with open(pipeline.buffer_file, "r") as f:
        data = json.loads(f.readline())
        assert data["cwe_id"] == "CWE-78"
        assert data["verdict"] == "CONFIRMED"


def test_flush_resets_buffer(tmp_path: Path, sample_verified: VerifiedFinding) -> None:
    pipeline = TrainingDataPipeline(local_buffer_dir=tmp_path)
    
    # Mock upload to avoid GCS dependency in test
    pipeline._upload_jsonl = lambda local_path, gcs_path: None
    
    pipeline.document(sample_verified, "url", "sha")
    pipeline.document(sample_verified, "url", "sha")
    
    assert pipeline.buffer_file.exists()
    
    count = pipeline.flush_to_gcs()
    
    assert count == 2
    assert not pipeline.buffer_file.exists()
    
    # Counter does not reset on flush, only when L4 triggers retrain
    assert pipeline.get_new_examples_count() == 2
