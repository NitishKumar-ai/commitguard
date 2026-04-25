from __future__ import annotations

from commitguard_env.parse_action import parse_action


def test_parse_action_request_context() -> None:
    raw = """
    <action>
      <action_type>request_context</action_type>
      <file_path>auth.c</file_path>
    </action>
    """
    a = parse_action(raw)
    assert a.action_type == "request_context"
    assert a.file_path == "auth.c"
    assert a.parse_error is None


def test_parse_action_analyze() -> None:
    raw = """
    <action>
      <action_type>analyze</action_type>
      <reasoning>hello</reasoning>
    </action>
    """
    a = parse_action(raw)
    assert a.action_type == "analyze"
    assert a.reasoning == "hello"
    assert a.parse_error is None


def test_parse_action_verdict() -> None:
    raw = """
    <action>
      <action_type>verdict</action_type>
      <is_vulnerable>true</is_vulnerable>
      <vuln_type>CWE-89</vuln_type>
      <exploit_sketch>sql injection</exploit_sketch>
    </action>
    """
    a = parse_action(raw)
    assert a.action_type == "verdict"
    assert a.is_vulnerable is True
    assert a.vuln_type == "CWE-89"
    assert a.exploit_sketch == "sql injection"
    assert a.parse_error is None


def test_parse_action_malformed_never_throws_and_sets_error() -> None:
    raw = "<action><action_type>???</action_type><fields>"
    a = parse_action(raw)
    assert a.action_type == "analyze"
    assert a.parse_error is not None

