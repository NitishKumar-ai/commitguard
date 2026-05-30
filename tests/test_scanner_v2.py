"""Tests for commitguard_env.scanner_v2 — 3-pass scan loop."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from commitguard_env.scanner_v2 import RepoScanner, _CWE_SEVERITY, _CWE_NAMES
from commitguard_env.models import Finding


# ---------------------------------------------------------------------------
# Deduplication tests
# ---------------------------------------------------------------------------


class TestDeduplication:
    """Test finding deduplication logic."""

    def test_exact_duplicate_kept_once(self) -> None:
        f1 = Finding(
            file="main.c", line_start=10, line_end=20,
            cwe_id="CWE-119", cwe_name="Buffer Overflow",
            severity="HIGH", confidence=0.9,
            exploit_sketch="overflow", suggested_fix="fix",
            code_snippet="code",
        )
        f2 = Finding(
            file="main.c", line_start=10, line_end=20,
            cwe_id="CWE-119", cwe_name="Buffer Overflow",
            severity="HIGH", confidence=0.7,
            exploit_sketch="overflow 2", suggested_fix="fix 2",
            code_snippet="code",
        )
        result = RepoScanner._deduplicate([f1, f2])
        assert len(result) == 1
        assert result[0].confidence == 0.9  # Higher confidence kept

    def test_overlapping_lines_same_cwe_deduped(self) -> None:
        f1 = Finding(
            file="main.c", line_start=10, line_end=25,
            cwe_id="CWE-476", cwe_name="NULL Pointer Dereference",
            severity="MEDIUM", confidence=0.8,
            exploit_sketch="null deref", suggested_fix="check null",
            code_snippet="code",
        )
        f2 = Finding(
            file="main.c", line_start=20, line_end=30,
            cwe_id="CWE-476", cwe_name="NULL Pointer Dereference",
            severity="MEDIUM", confidence=0.6,
            exploit_sketch="null deref 2", suggested_fix="check null 2",
            code_snippet="code",
        )
        result = RepoScanner._deduplicate([f1, f2])
        assert len(result) == 1

    def test_different_files_not_deduped(self) -> None:
        f1 = Finding(
            file="main.c", line_start=10, line_end=20,
            cwe_id="CWE-119", cwe_name="Buffer Overflow",
            severity="HIGH", confidence=0.9,
            exploit_sketch="overflow", suggested_fix="fix",
            code_snippet="code",
        )
        f2 = Finding(
            file="utils.c", line_start=10, line_end=20,
            cwe_id="CWE-119", cwe_name="Buffer Overflow",
            severity="HIGH", confidence=0.8,
            exploit_sketch="overflow", suggested_fix="fix",
            code_snippet="code",
        )
        result = RepoScanner._deduplicate([f1, f2])
        assert len(result) == 2

    def test_different_cwe_same_lines_not_deduped(self) -> None:
        f1 = Finding(
            file="main.c", line_start=10, line_end=20,
            cwe_id="CWE-119", cwe_name="Buffer Overflow",
            severity="HIGH", confidence=0.9,
            exploit_sketch="overflow", suggested_fix="fix",
            code_snippet="code",
        )
        f2 = Finding(
            file="main.c", line_start=10, line_end=20,
            cwe_id="CWE-476", cwe_name="NULL Pointer Dereference",
            severity="MEDIUM", confidence=0.8,
            exploit_sketch="null deref", suggested_fix="check null",
            code_snippet="code",
        )
        result = RepoScanner._deduplicate([f1, f2])
        assert len(result) == 2

    def test_empty_list(self) -> None:
        assert RepoScanner._deduplicate([]) == []


# ---------------------------------------------------------------------------
# Plan phase tests
# ---------------------------------------------------------------------------


class TestPlanPhase:
    """Test file prioritization in the Plan pass."""

    def test_prioritizes_entry_points(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "main.py").write_text("print('entry')\n", encoding="utf-8")
            (tmp_path / "utils.py").write_text("def helper(): pass\n", encoding="utf-8")
            (tmp_path / "app.py").write_text("from flask import Flask\n", encoding="utf-8")

            scanner = RepoScanner()
            plan = scanner._plan(tmp_path)

            # main.py and app.py should appear before utils.py
            main_idx = plan.index("main.py")
            app_idx = plan.index("app.py")
            utils_idx = plan.index("utils.py")
            assert main_idx < utils_idx
            assert app_idx < utils_idx

    def test_skips_hidden_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
            git_dir = tmp_path / ".git"
            git_dir.mkdir()
            (git_dir / "config.py").write_text("y = 2\n", encoding="utf-8")

            scanner = RepoScanner()
            plan = scanner._plan(tmp_path)

            assert "main.py" in plan
            assert ".git/config.py" not in plan

    def test_filters_by_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "code.py").write_text("x = 1\n", encoding="utf-8")
            (tmp_path / "readme.md").write_text("# Readme\n", encoding="utf-8")
            (tmp_path / "data.json").write_text("{}\n", encoding="utf-8")

            scanner = RepoScanner()
            plan = scanner._plan(tmp_path)

            assert "code.py" in plan
            assert "readme.md" not in plan
            assert "data.json" not in plan


# ---------------------------------------------------------------------------
# CWE metadata tests
# ---------------------------------------------------------------------------


class TestCweMetadata:
    """Test CWE severity and name lookups."""

    def test_known_cwe_has_severity(self) -> None:
        assert _CWE_SEVERITY["CWE-89"] == "CRITICAL"
        assert _CWE_SEVERITY["CWE-119"] == "HIGH"
        assert _CWE_SEVERITY["CWE-476"] == "MEDIUM"

    def test_known_cwe_has_name(self) -> None:
        assert "SQL Injection" in _CWE_NAMES["CWE-89"]
        assert "Buffer" in _CWE_NAMES["CWE-119"]
        assert "NULL" in _CWE_NAMES["CWE-476"]
