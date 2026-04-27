from __future__ import annotations

from commitguard_env.models import CommitGuardAction
from commitguard_env.reward import compute_reward


def test_reward_true_positive_correct_cwe_and_exploit_match() -> None:
    a = CommitGuardAction(
        action_type="verdict",
        is_vulnerable=True,
        vuln_type="CWE-89",
        exploit_sketch="This is classic SQL injection: SELECT ... WHERE ... concat",
    )
    r = compute_reward(
        action=a,
        is_vulnerable=True,
        cwe="CWE-89",
        target_file="db.py",
        cwe_keywords={"CWE-89": ["sql", "select", "where", "concat", "injection"]},
        context_requests=0,
    )
    assert r == 2.0


def test_reward_true_positive_wrong_cwe_same_family() -> None:
    # CWE-79 and CWE-89 are both in the "injection" family -> family bonus = 0.5 * 0.5
    a = CommitGuardAction(action_type="verdict", is_vulnerable=True, vuln_type="CWE-79", exploit_sketch="sql injection")
    r = compute_reward(
        action=a,
        is_vulnerable=True,
        cwe="CWE-89",
        target_file="db.py",
        cwe_keywords={"CWE-89": ["sql"]},
        context_requests=0,
    )
    # 1.0 (TP) + 0.25 (family match: 0.5 * 0.5) + 0.5 (keyword: 1/1) = 1.75
    assert r == 1.75


def test_reward_false_positive() -> None:
    a = CommitGuardAction(action_type="verdict", is_vulnerable=True, vuln_type="CWE-89", exploit_sketch="sql")
    r = compute_reward(
        action=a,
        is_vulnerable=False,
        cwe=None,
        target_file=None,
        cwe_keywords={},
        context_requests=0,
    )
    assert r == -1.0


def test_reward_false_negative() -> None:
    a = CommitGuardAction(action_type="verdict", is_vulnerable=False, vuln_type="NONE", exploit_sketch="")
    r = compute_reward(
        action=a,
        is_vulnerable=True,
        cwe="CWE-89",
        target_file="db.py",
        cwe_keywords={"CWE-89": ["sql"]},
        context_requests=0,
    )
    assert r == -0.5


def test_reward_malformed_action_penalty_no_crash() -> None:
    a = CommitGuardAction(action_type="analyze", raw_action="<<<", parse_error="bad_xml")
    r = compute_reward(
        action=a,
        is_vulnerable=True,
        cwe="CWE-89",
        target_file="db.py",
        cwe_keywords={"CWE-89": ["sql"]},
        context_requests=0,
    )
    assert r == -0.5

