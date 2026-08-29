from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("fixture", "exit_code", "posture"),
    [
        ("loose", 1, "FAIL"),
        ("hardened", 0, "PASS"),
        ("bypass", 1, "FAIL"),
        ("unknown-field", 0, "WARN"),
    ],
)
def test_fixture_results(run_cli, fixture, exit_code, posture):
    result = run_cli("check", f"fixtures/{fixture}/settings.json", "--format", "json")
    assert result.returncode == exit_code
    assert result.stderr == ""
    assert json.loads(result.stdout)["posture"] == posture


def test_bypass_is_headlined_and_deny_aware(run_cli):
    result = run_cli("check", "fixtures/bypass/settings.json", "--format", "json")
    document = json.loads(result.stdout)
    assert document["findings"][0]["id"] == "AGENT-APRV-001"
    assert document["resolved_capability"]["network"]["webfetch_permission"] == "denied"
    assert document["resolved_capability"]["network"]["websearch_permission"] == "denied"
    assert not any(item.startswith("tool.Bash:") for item in document["resolved_capability"]["capabilities"])


def test_unknown_field_warn_and_medium_gate(run_cli):
    default = run_cli("check", "fixtures/unknown-field/settings.json", "--format", "json")
    gated = run_cli("check", "fixtures/unknown-field/settings.json", "--format", "json", "--fail-on", "medium")
    assert default.returncode == 0
    assert gated.returncode == 1
    assert json.loads(default.stdout)["posture"] == json.loads(gated.stdout)["posture"] == "WARN"
    assert json.loads(default.stdout)["counts"] == json.loads(gated.stdout)["counts"]


def test_malformed_exit_3(run_cli):
    result = run_cli("check", "fixtures/malformed/settings.json")
    assert result.returncode == 3
    assert result.stdout == ""
    assert "configuration parse error" in result.stderr
    assert "settings.json:3:22" in result.stderr


def test_doctor_staged_environment_is_report_only(run_cli):
    result = run_cli("doctor", "--env-root", "fixtures/env", "--format", "json", "--verbose")
    assert result.returncode == 0
    document = json.loads(result.stdout)
    assert document["claude_code_detected"] is True
    assert document["codex_detected"] is True
    assert document["observed_project_mcp_server_count"] == 2
    assert document["runtime"] == "claude-code"
    assert all(".mcp.json" not in path or path.endswith(".mcp.json") for path in document["inspected_paths"])


def test_every_required_fixture_has_expected_document():
    for fixture in ("loose", "hardened", "bypass", "malformed", "unknown-field", "env"):
        assert (Path("fixtures") / fixture / "EXPECTED.md").is_file()
