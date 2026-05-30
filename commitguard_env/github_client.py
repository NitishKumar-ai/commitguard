"""GitHub integration for CommitGuard v2 — clone repos and file structured issues.

Uses PyGithub for API interaction and git for shallow cloning.
Rate limiting is handled with exponential backoff and jitter.
"""

from __future__ import annotations

import logging
import os
import random
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from .models import Finding

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SEVERITY_EMOJI: dict[str, str] = {
    "CRITICAL": "🟣",
    "HIGH": "🔴",
    "MEDIUM": "🟠",
    "LOW": "🟡",
    "INFO": "🔵",
}

_MAX_RETRIES: int = 3
_BASE_BACKOFF_SECONDS: float = 2.0


# ---------------------------------------------------------------------------
# Repo cloning
# ---------------------------------------------------------------------------


def clone_repo(url: str, *, depth: int = 1, target_dir: Optional[Path] = None) -> Path:
    """Shallow-clone a public GitHub repo and return the local path.

    Parameters
    ----------
    url : str
        HTTPS clone URL, e.g. ``https://github.com/owner/repo``.
    depth : int
        Git clone depth (default 1 for speed).
    target_dir : Path | None
        Where to clone. If *None*, creates a temp directory.

    Returns
    -------
    Path
        Absolute path to the cloned repo root.
    """
    if target_dir is None:
        target_dir = Path(tempfile.mkdtemp(prefix="commitguard_"))
    else:
        target_dir.mkdir(parents=True, exist_ok=True)

    # Normalise URL — strip trailing slashes, ensure .git suffix is optional
    url = url.rstrip("/")
    if not url.endswith(".git"):
        url = url + ".git"

    logger.info("Cloning %s (depth=%d) → %s", url, depth, target_dir)
    try:
        subprocess.run(
            ["git", "clone", "--depth", str(depth), "--single-branch", url, str(target_dir)],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.CalledProcessError as exc:
        logger.error("git clone failed: %s", exc.stderr)
        raise RuntimeError(f"Failed to clone {url}: {exc.stderr}") from exc

    logger.info("Cloned successfully: %s", target_dir)
    return target_dir


def cleanup_clone(repo_path: Path) -> None:
    """Remove a cloned repo directory."""
    if repo_path.exists():
        shutil.rmtree(repo_path, ignore_errors=True)
        logger.info("Cleaned up clone: %s", repo_path)


# ---------------------------------------------------------------------------
# Issue formatting
# ---------------------------------------------------------------------------

_CWE_LINK_TEMPLATE = "https://cwe.mitre.org/data/definitions/{num}.html"


def _cwe_number(cwe_id: str) -> str:
    """Extract the numeric portion from 'CWE-89' → '89'."""
    m = re.search(r"\d+", cwe_id)
    return m.group() if m else cwe_id


def format_issue_title(finding: Finding) -> str:
    """Generate the GitHub Issue title for a finding."""
    emoji = _SEVERITY_EMOJI.get(finding.severity, "⚪")
    return f"{emoji} [{finding.severity}] {finding.cwe_name} — {finding.cwe_id} in `{finding.file}`"


def format_issue_body(finding: Finding) -> str:
    """Render a finding into the CommitGuard v2 GitHub Issue markdown template.

    Follows the template defined in PRD §9.
    """
    emoji = _SEVERITY_EMOJI.get(finding.severity, "⚪")
    cwe_num = _cwe_number(finding.cwe_id)
    cwe_link = _CWE_LINK_TEMPLATE.format(num=cwe_num)

    body = f"""## {emoji} [{finding.severity}] {finding.cwe_name} — {finding.cwe_id}

**File:** `{finding.file}` · **Lines:** {finding.line_start}–{finding.line_end}
**Confidence:** {int(finding.confidence * 100)}%

### Exploit Sketch
{finding.exploit_sketch}

### Vulnerable Code
```
{finding.code_snippet}
```

### Suggested Fix
{finding.suggested_fix}

### References
- [{finding.cwe_id}: {finding.cwe_name}]({cwe_link})
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)

---
*Filed by CommitGuard v2 · Inmodel Labs*
"""
    return body


# ---------------------------------------------------------------------------
# GitHub API interaction (PyGithub)
# ---------------------------------------------------------------------------


def _get_github_instance():  # type: ignore[return]
    """Create an authenticated PyGithub ``Github`` instance."""
    try:
        from github import Github
    except ImportError as exc:
        raise ImportError(
            "PyGithub is required for GitHub integration. "
            "Install with: pip install 'commitguard[v2]'"
        ) from exc

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise EnvironmentError(
            "GITHUB_TOKEN environment variable is required for filing issues. "
            "Create a PAT with repo + issues:write scope."
        )
    return Github(token)


def _parse_owner_repo(repo_url: str) -> tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL.

    Handles: https://github.com/owner/repo[.git]
    """
    url = repo_url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    parts = url.split("/")
    if len(parts) < 2:
        raise ValueError(f"Cannot parse owner/repo from URL: {repo_url}")
    return parts[-2], parts[-1]


def _backoff_retry(func, *, max_retries: int = _MAX_RETRIES):  # type: ignore[return]
    """Execute *func* with exponential backoff on rate-limit errors."""
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as exc:
            exc_str = str(exc).lower()
            is_rate_limit = "rate limit" in exc_str or "403" in exc_str or "429" in exc_str
            if is_rate_limit and attempt < max_retries:
                wait = _BASE_BACKOFF_SECONDS * (2 ** attempt) + random.uniform(0, 1)
                logger.warning("Rate limited (attempt %d/%d), waiting %.1fs", attempt + 1, max_retries, wait)
                time.sleep(wait)
            else:
                raise


def check_duplicate_issue(repo_url: str, finding: Finding) -> bool:
    """Check if an issue with the same title already exists.

    Returns True if a duplicate is found.
    """
    gh = _get_github_instance()
    owner, repo_name = _parse_owner_repo(repo_url)
    repo = gh.get_repo(f"{owner}/{repo_name}")

    title_prefix = f"[{finding.severity}] {finding.cwe_name} — {finding.cwe_id} in `{finding.file}`"
    existing = repo.get_issues(state="all")

    # Only check first 100 issues to avoid excessive API calls
    for i, issue in enumerate(existing):
        if i >= 100:
            break
        if title_prefix in issue.title:
            logger.info("Duplicate issue found: #%d — %s", issue.number, issue.title)
            return True

    return False


def file_issue(repo_url: str, finding: Finding, *, skip_dedup: bool = False) -> str:
    """Create a GitHub Issue for a finding.

    Parameters
    ----------
    repo_url : str
        Full GitHub repo URL.
    finding : Finding
        The vulnerability finding to file.
    skip_dedup : bool
        If True, skip duplicate checking.

    Returns
    -------
    str
        URL of the created issue.
    """
    if not skip_dedup:
        if check_duplicate_issue(repo_url, finding):
            logger.info("Skipping duplicate issue for %s in %s", finding.cwe_id, finding.file)
            return ""

    gh = _get_github_instance()
    owner, repo_name = _parse_owner_repo(repo_url)
    repo = gh.get_repo(f"{owner}/{repo_name}")

    title = format_issue_title(finding)
    body = format_issue_body(finding)

    labels: list[str] = ["security", "commitguard"]
    # Add severity label if it exists in the repo
    try:
        repo_labels = [lb.name for lb in repo.get_labels()]
        labels = [lb for lb in labels if lb in repo_labels]
    except Exception:
        labels = []  # Don't fail if labels don't exist

    def _create() -> str:
        issue = repo.create_issue(title=title, body=body, labels=labels)
        logger.info("Filed issue #%d: %s", issue.number, issue.html_url)
        return str(issue.html_url)

    return _backoff_retry(_create)


def file_all_issues(repo_url: str, findings: list[Finding]) -> list[str]:
    """File GitHub Issues for all findings, with dedup and rate limit handling.

    Returns a list of issue URLs (empty strings for skipped duplicates).
    """
    urls: list[str] = []
    for finding in findings:
        try:
            url = file_issue(repo_url, finding)
            urls.append(url)
        except Exception as exc:
            logger.error("Failed to file issue for %s in %s: %s", finding.cwe_id, finding.file, exc)
            urls.append("")
    return urls
