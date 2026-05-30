"""Tests for commitguard_env.github_client — issue formatting and helpers."""

from __future__ import annotations

from commitguard_env.github_client import (
    format_issue_body,
    format_issue_title,
    _parse_owner_repo,
    _cwe_number,
)
from commitguard_env.models import Finding


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

_SAMPLE_FINDING = Finding(
    file="src/auth/login.py",
    line_start=42,
    line_end=58,
    cwe_id="CWE-89",
    cwe_name="SQL Injection",
    severity="HIGH",
    confidence=0.91,
    exploit_sketch="Unsanitized user input passed directly to cursor.execute(). Attacker can inject arbitrary SQL.",
    suggested_fix='Use parameterized queries: cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))',
    code_snippet='query = "SELECT * FROM users WHERE id = " + user_id\ncursor.execute(query)',
)


# ---------------------------------------------------------------------------
# Issue formatting tests
# ---------------------------------------------------------------------------


class TestIssueFormatting:
    """Test that issue templates match the PRD §9 specification."""

    def test_title_includes_severity_badge(self) -> None:
        title = format_issue_title(_SAMPLE_FINDING)
        assert "[HIGH]" in title
        assert "🔴" in title

    def test_title_includes_cwe_and_file(self) -> None:
        title = format_issue_title(_SAMPLE_FINDING)
        assert "CWE-89" in title
        assert "SQL Injection" in title
        assert "src/auth/login.py" in title

    def test_body_has_all_sections(self) -> None:
        body = format_issue_body(_SAMPLE_FINDING)
        # PRD-required sections
        assert "## " in body  # Header
        assert "**File:**" in body
        assert "**Confidence:**" in body
        assert "### Exploit Sketch" in body
        assert "### Vulnerable Code" in body
        assert "### Suggested Fix" in body
        assert "### References" in body
        assert "Filed by CommitGuard v2" in body

    def test_body_includes_cwe_link(self) -> None:
        body = format_issue_body(_SAMPLE_FINDING)
        assert "cwe.mitre.org/data/definitions/89.html" in body

    def test_body_includes_line_numbers(self) -> None:
        body = format_issue_body(_SAMPLE_FINDING)
        assert "42" in body
        assert "58" in body

    def test_body_includes_confidence_percentage(self) -> None:
        body = format_issue_body(_SAMPLE_FINDING)
        assert "91%" in body

    def test_body_includes_code_snippet(self) -> None:
        body = format_issue_body(_SAMPLE_FINDING)
        assert "cursor.execute" in body

    def test_different_severities(self) -> None:
        for severity, emoji in [("CRITICAL", "🟣"), ("HIGH", "🔴"), ("MEDIUM", "🟠"), ("LOW", "🟡"), ("INFO", "🔵")]:
            from dataclasses import replace
            f = replace(_SAMPLE_FINDING, severity=severity)
            title = format_issue_title(f)
            assert emoji in title
            assert f"[{severity}]" in title


# ---------------------------------------------------------------------------
# URL parsing tests
# ---------------------------------------------------------------------------


class TestParseOwnerRepo:
    """Test URL parsing for GitHub owner/repo extraction."""

    def test_standard_url(self) -> None:
        owner, repo = _parse_owner_repo("https://github.com/octocat/Hello-World")
        assert owner == "octocat"
        assert repo == "Hello-World"

    def test_url_with_git_suffix(self) -> None:
        owner, repo = _parse_owner_repo("https://github.com/octocat/Hello-World.git")
        assert owner == "octocat"
        assert repo == "Hello-World"

    def test_url_with_trailing_slash(self) -> None:
        owner, repo = _parse_owner_repo("https://github.com/octocat/Hello-World/")
        assert owner == "octocat"
        assert repo == "Hello-World"


# ---------------------------------------------------------------------------
# Utility tests
# ---------------------------------------------------------------------------


class TestCweNumber:
    """Test CWE number extraction."""

    def test_standard_format(self) -> None:
        assert _cwe_number("CWE-89") == "89"
        assert _cwe_number("CWE-119") == "119"

    def test_no_number(self) -> None:
        # "UNKNOWN" has no digits, so _cwe_number returns the input unchanged
        result = _cwe_number("UNKNOWN")
        assert result == "UNKNOWN"
