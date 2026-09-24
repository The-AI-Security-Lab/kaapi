from __future__ import annotations

import json
from pathlib import Path

import pytest

from kaapi import analyze_text
from kaapi.model import ConfigError


def _without_memory_source(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: "<source>"
            if key in {"source", "subject"}
            else _without_memory_source(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_without_memory_source(item) for item in value]
    return value


@pytest.mark.parametrize(
    ("fixture", "runtime", "posture"),
    [
        ("fixtures/hardened/settings.json", "claude-code", "PASS"),
        ("fixtures/loose/settings.json", "claude-code", "FAIL"),
        ("fixtures/codex-hardened/config.toml", "codex", "PASS"),
        ("fixtures/codex-danger/config.toml", "codex", "FAIL"),
    ],
)
def test_analyze_text_known_answers(fixture, runtime, posture):
    content = Path(fixture).read_bytes()
    document = analyze_text(content, runtime=runtime)
    assert document["runtime"] == runtime
    assert document["posture"] == posture


@pytest.mark.parametrize(
    ("fixture", "runtime"),
    [
        ("fixtures/hardened/settings.json", "claude-code"),
        ("fixtures/loose/settings.json", "claude-code"),
        ("fixtures/codex-hardened/config.toml", "codex"),
        ("fixtures/codex-danger/config.toml", "codex"),
    ],
)
def test_analyze_text_matches_cli_analysis_except_source_identity(
    fixture, runtime, run_cli
):
    cli_document = json.loads(
        run_cli("check", fixture, "--runtime", runtime, "--format", "json").stdout
    )
    memory_document = analyze_text(
        Path(fixture).read_bytes(), runtime=runtime
    )
    assert _without_memory_source(memory_document) == _without_memory_source(
        cli_document
    )


def test_analyze_text_reuses_source_locations_and_never_persists(tmp_path):
    content = '{\n  "permissions": {\n    "futureSecuritySwitch": true\n  }\n}\n'
    document = analyze_text(content, runtime="claude-code")
    assert document["subject"] == "<memory:claude-code>"
    assert document["unknown_fields"][0]["source"] == "<memory:claude-code>"
    assert document["unknown_fields"][0]["line"] == 3
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("content", "runtime", "message"),
    [
        ('{"permissions": [}', "claude-code", "invalid JSON"),
        ('sandbox_mode = "read-only"\n[broken', "codex", "invalid TOML"),
    ],
)
def test_analyze_text_reuses_programmatic_parse_errors(content, runtime, message):
    with pytest.raises(ConfigError, match=message):
        analyze_text(content, runtime=runtime)


@pytest.mark.parametrize(
    ("content", "runtime", "layer"),
    [
        (
            '{"futureSecuritySwitch": true, "permissions": {"defaultMode": "dontAsk", "deny": ["Bash", "Edit", "WebFetch", "WebSearch", "mcp__*"]}, "sandbox": {"enabled": true, "allowUnsandboxedCommands": false, "network": {"deniedDomains": ["*"]}}, "hooks": {}, "mcpServers": {}}',
            "claude-code",
            "approvals",
        ),
        ('approval_policy = "never"\n[features]\nfuture_shell = true\n', "codex", "permissions"),
    ],
)
def test_analyze_text_preserves_unknown_security_field_handling(
    content, runtime, layer
):
    document = analyze_text(content, runtime=runtime)
    assert document["posture"] == "WARN"
    assert document["unknown_fields"][0]["layer"] == layer


@pytest.mark.parametrize(
    ("fixture", "runtime", "secret"),
    [
        (
            "fixtures/loose/settings.json",
            "claude-code",
            "KAAPI_SECRET_MCP_COMMAND",
        ),
        (
            "fixtures/codex-danger/config.toml",
            "codex",
            "KAAPI_CODEX_SECRET_COMMAND",
        ),
    ],
)
def test_analyze_text_is_deterministic_and_secret_safe(fixture, runtime, secret):
    content = Path(fixture).read_bytes()
    first = analyze_text(content, runtime=runtime)
    second = analyze_text(content, runtime=runtime)
    assert first == second
    assert secret not in json.dumps(first, sort_keys=True)
