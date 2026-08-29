from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
import pytest


ANSI_OSC = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")


@pytest.mark.parametrize("args", [(), ("--help",), ("-h",), ("doctor", "--help"), ("check", "--help"), ("baseline", "--help"), ("verify", "--help"), ("rules", "--help"), ("version", "--help")])
def test_help_every_command(run_cli, args):
    result = run_cli(*args)
    assert result.returncode == 0
    assert "usage:" in result.stdout
    assert "Example:" in result.stdout
    assert result.stderr == ""


def test_version_and_rules(run_cli):
    version = run_cli("version")
    global_version = run_cli("--version")
    rules = run_cli("rules")
    detail = run_cli("rules", "AGENT-APRV-001")
    assert version.returncode == global_version.returncode == rules.returncode == detail.returncode == 0
    assert "kaapi 1.0.0" in version.stdout and "0.3.1 (17 controls)" in version.stdout
    assert len(rules.stdout.strip().splitlines()) == 17
    assert "https://code.claude.com/docs/en/permission-modes" in detail.stdout
    assert "accessed 2026-08-26" in detail.stdout


def test_check_json_schema_and_final_newline(run_cli):
    result = run_cli("check", "fixtures/loose/settings.json", "--format", "json")
    schema = json.loads(Path("kaapi/schemas/check-v1.schema.json").read_text())
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(json.loads(result.stdout))
    assert result.stdout.endswith("\n") and not result.stdout.endswith("\n\n")


def test_severity_filters_display_not_counts_or_posture(run_cli):
    all_result = json.loads(run_cli("check", "fixtures/loose/settings.json", "--format", "json").stdout)
    critical = json.loads(run_cli("check", "fixtures/loose/settings.json", "--format", "json", "--severity", "critical").stdout)
    assert critical["findings"] == []
    assert critical["counts"] == all_result["counts"]
    assert critical["posture"] == "FAIL"


def test_fail_on_none_reports_true_posture_and_actual_exit(run_cli):
    result = run_cli("check", "fixtures/loose/settings.json", "--fail-on", "none", "--no-color")
    assert result.returncode == 0
    assert "Verdict: FAIL" in result.stdout
    assert "Process exit code: 0" in result.stdout


def test_only_ignore_and_unknown_ids(run_cli):
    only = run_cli("check", "fixtures/loose/settings.json", "--only", "AGENT-HOOK-001", "--format", "json")
    ignored = run_cli("check", "fixtures/loose/settings.json", "--ignore", "AGENT-PERM-001,AGENT-PERM-002", "--format", "json")
    unknown = run_cli("check", "fixtures/loose/settings.json", "--only", "NO-SUCH-ID")
    assert json.loads(only.stdout)["controls_evaluated"] == 1
    assert all(item["id"] not in {"AGENT-PERM-001", "AGENT-PERM-002"} for item in json.loads(ignored.stdout)["findings"])
    assert unknown.returncode == 2


def test_quiet_verbose_conflict_and_path_conflict(run_cli):
    quiet = run_cli("check", "fixtures/hardened/settings.json", "--quiet")
    conflict = run_cli("check", "fixtures/hardened/settings.json", "--quiet", "--verbose")
    path_conflict = run_cli("check", "fixtures/hardened/settings.json", "--path", "fixtures/loose/settings.json")
    verbose = run_cli("check", "fixtures/hardened/settings.json", "--verbose", "--no-color")
    assert quiet.stdout == "PASS critical=0 high=0 medium=0 low=0 info=0 exit=0\n"
    assert conflict.returncode == path_conflict.returncode == 2
    assert "Inspected: fixtures/hardened/settings.json" in verbose.stdout


def test_output_file_has_no_stdout_or_decoration(run_cli, tmp_path):
    output = tmp_path / "result.txt"
    result = run_cli("check", "fixtures/loose/settings.json", "--output", str(output))
    assert result.returncode == 1 and result.stdout == ""
    assert "Kaapi ☕" in output.read_text()
    assert ANSI_OSC.search(output.read_text()) is None


def test_output_cannot_overwrite_inspected_inputs(run_cli, tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text('{"permissions": {"deny": ["Bash"]}}\n', encoding="utf-8")
    original = settings.read_bytes()
    check = run_cli("check", str(settings), "--output", str(settings))
    baseline = run_cli("baseline", str(settings), "--output", str(settings))
    assert check.returncode == baseline.returncode == 2
    assert settings.read_bytes() == original


@pytest.mark.parametrize("args", [("check", "fixtures/hardened/settings.json", "--format", "sarif"), ("check", "fixtures/hardened/settings.json", "--runtime", "codex"), ("check", "codex"), ("check", "cursor"), ("explain",), ("policy",), ("check", "fixtures/hardened/settings.json", "--owasp")])
def test_p1_p2_surfaces_are_usage_errors(run_cli, args):
    assert run_cli(*args).returncode == 2


def test_pretty_contract_order_separator_evidence_and_resources(run_cli):
    value = run_cli("check", "fixtures/loose/settings.json", "--no-color").stdout
    assert value.count("Kaapi ☕") == 1
    positions = [value.index(name) for name in ("INSPECTION", "POSTURE", "RESOLVED AGENT CAPABILITY", "FINDINGS", "RESULT")]
    assert positions == sorted(positions)
    assert "─" * 72 in value
    assert "Evidence 1:" in value and "Evidence 2:" in value
    assert "Resource: Claude Code - permissions" in value
    assert "https://code.claude.com" not in value
    assert "Observed:" in value and "Inference:" in value and "Why severity:" in value


@pytest.mark.parametrize("extra,env", [(("--format", "json"), {}), (("--quiet",), {}), (("--no-color",), {}), ((), {"NO_COLOR": "1"})])
def test_machine_and_plain_modes_have_no_ansi_or_osc(run_cli, extra, env):
    result = run_cli("check", "fixtures/hardened/settings.json", *extra, env=env)
    assert ANSI_OSC.search(result.stdout) is None


def test_unknown_options_and_bad_snapshot_are_code_2(run_cli, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema_version":"2"}', encoding="utf-8")
    assert run_cli("check", "fixtures/hardened/settings.json", "--future").returncode == 2
    assert run_cli("verify", "fixtures/hardened/settings.json", "--baseline", str(bad)).returncode == 2
