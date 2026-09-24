from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from kaapi.analyze import analyze
from kaapi.codex import parse_codex_config
from kaapi.model import ConfigError


def test_codex_hardened_known_answer(run_cli):
    result = run_cli(
        "check",
        "fixtures/codex-hardened/config.toml",
        "--format",
        "json",
    )
    assert result.returncode == 0
    document = json.loads(result.stdout)
    assert document["runtime"] == "codex"
    assert document["baseline"]["version"] == "0.4.0"
    assert document["posture"] == "PASS"
    assert document["findings"] == []


def test_codex_auto_known_answer(run_cli):
    result = run_cli(
        "check", "fixtures/codex-auto/config.toml", "--format", "json"
    )
    assert result.returncode == 1
    document = json.loads(result.stdout)
    assert {
        "AGENT-PERM-001",
        "AGENT-PERM-002",
        "AGENT-SBOX-002",
    }.issubset({item["id"] for item in document["findings"]})


def test_codex_danger_is_critical_and_secret_safe(run_cli):
    result = run_cli(
        "check", "fixtures/codex-danger/config.toml", "--format", "json"
    )
    assert result.returncode == 1
    assert "KAAPI_CODEX_SECRET" not in result.stdout
    document = json.loads(result.stdout)
    ids = {item["id"] for item in document["findings"]}
    assert {
        "AGENT-APRV-001",
        "AGENT-SBOX-001",
        "AGENT-NET-001",
        "AGENT-MCP-001",
    }.issubset(ids)


def test_codex_strict_toml_and_unknown_fields(tmp_path):
    malformed = tmp_path / "bad.toml"
    malformed.write_text(
        'sandbox_mode = "read-only"\n[broken\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        parse_codex_config(malformed)

    unknown = tmp_path / "unknown.toml"
    unknown.write_text(
        'approval_policy = "never"\n'
        'sandbox_mode = "read-only"\n'
        '[features]\nfuture_shell = true\n',
        encoding="utf-8",
    )
    document, _, _ = analyze(unknown)
    assert document["runtime"] == "codex"
    assert document["posture"] == "WARN"
    assert document["unknown_fields"][0]["layer"] == "permissions"


def test_codex_adapter_is_deterministic_offline_and_read_only(
    monkeypatch, run_cli
):
    path = Path("fixtures/codex-auto/config.toml")
    before = path.read_bytes()

    def blocked(*args, **kwargs):
        raise AssertionError("network call attempted")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    document, _, _ = analyze(path)
    assert document["runtime"] == "codex"
    first = run_cli("check", str(path), "--format", "json")
    second = run_cli("check", str(path), "--format", "json")
    assert first.stdout.encode() == second.stdout.encode()
    assert path.read_bytes() == before


def test_codex_discovery_precedence_and_unobserved_project_trust(run_cli):
    result = run_cli(
        "doctor",
        "--runtime",
        "codex",
        "--env-root",
        "fixtures/codex-env",
        "--format",
        "json",
        "--verbose",
    )
    assert result.returncode == 0
    document = json.loads(result.stdout)
    assert document["runtime"] == "codex"
    assert document["codex_detected"] is True
    assert document["posture"] == "WARN"
    assert document["passed_controls"] > 0
