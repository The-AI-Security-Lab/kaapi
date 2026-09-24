from __future__ import annotations

import json
import socket
from pathlib import Path

import jsonschema
import pytest

from kaapi.policy import PolicyError, load_policy


def write_policy(tmp_path: Path, value: object) -> Path:
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_policy_schema_and_examples_validate(run_cli):
    schema = json.loads(
        Path("kaapi/schemas/policy.schema.json").read_text(encoding="utf-8")
    )
    for path in Path("examples/policies").rglob("*.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(value)
        result = run_cli("policy", "validate", str(path), "--format", "json")
        assert result.returncode == 0
        assert json.loads(result.stdout)["valid"] is True


@pytest.mark.parametrize(
    "value",
    [
        [],
        {
            "schema_version": "1",
            "id": "x",
            "requirements": [],
        },
        {
            "schema_version": "1",
            "id": "x",
            "requirements": [
                {
                    "control_id": "UNKNOWN-001",
                    "expectation": "pass",
                }
            ],
        },
        {
            "schema_version": "1",
            "id": "x",
            "future": True,
            "requirements": [
                {
                    "control_id": "AGENT-SBOX-001",
                    "expectation": "pass",
                }
            ],
        },
        {
            "schema_version": "1",
            "id": "x",
            "requirements": [
                {
                    "control_id": "AGENT-SBOX-001",
                    "expectation": "pass",
                    "parameters": {"max_configured_servers": 1},
                }
            ],
        },
        {
            "schema_version": "1",
            "id": "x",
            "requirements": [
                {
                    "control_id": "AGENT-SBOX-001",
                    "expectation": "pass",
                    "script": "do_not_execute()",
                }
            ],
        },
    ],
)
def test_policy_rejects_malformed_unknown_and_executable_shapes(
    run_cli, tmp_path, value
):
    path = write_policy(tmp_path, value)
    result = run_cli("policy", "validate", str(path))
    assert result.returncode == 3
    assert result.stdout == ""
    assert "policy validation error" in result.stderr
    assert "do_not_execute" not in result.stderr


def test_policy_fail_and_permitted_risk_are_separate_from_security(
    run_cli, tmp_path
):
    strict = write_policy(
        tmp_path,
        {
            "schema_version": "1",
            "id": "no-mcp",
            "requirements": [
                {
                    "control_id": "AGENT-MCP-001",
                    "expectation": "pass",
                    "parameters": {"max_configured_servers": 0},
                }
            ],
        },
    )
    failed = run_cli(
        "check",
        "fixtures/codex-danger/config.toml",
        "--policy",
        str(strict),
        "--fail-on",
        "none",
        "--format",
        "json",
    )
    assert failed.returncode == 1
    failed_document = json.loads(failed.stdout)
    assert failed_document["security_posture"] == "FAIL"
    assert failed_document["organisation_policy"]["verdict"] == "FAIL"

    permitted = write_policy(
        tmp_path,
        {
            "schema_version": "1",
            "id": "one-mcp",
            "requirements": [
                {
                    "control_id": "AGENT-MCP-001",
                    "expectation": "pass",
                    "parameters": {"max_configured_servers": 1},
                }
            ],
        },
    )
    permitted_result = run_cli(
        "check",
        "fixtures/codex-danger/config.toml",
        "--policy",
        str(permitted),
        "--fail-on",
        "none",
        "--format",
        "json",
    )
    assert permitted_result.returncode == 0
    permitted_document = json.loads(permitted_result.stdout)
    assert permitted_document["security_posture"] == "FAIL"
    assert (
        permitted_document["organisation_policy"]["verdict"]
        == "PERMITTED_RISK"
    )
    assert (
        permitted_document["organisation_policy"]["requirements"][0]["status"]
        == "PERMITTED_RISK"
    )


def test_policy_never_suppresses_or_downgrades_baseline_findings(
    run_cli, tmp_path
):
    policy_path = write_policy(
        tmp_path,
        {
            "schema_version": "1",
            "id": "explicit-risk",
            "requirements": [
                {
                    "control_id": "AGENT-APRV-001",
                    "expectation": "allow",
                }
            ],
        },
    )
    baseline = json.loads(
        run_cli(
            "check",
            "fixtures/codex-danger/config.toml",
            "--format",
            "json",
        ).stdout
    )
    overlaid = json.loads(
        run_cli(
            "check",
            "fixtures/codex-danger/config.toml",
            "--policy",
            str(policy_path),
            "--format",
            "json",
        ).stdout
    )
    assert overlaid["posture"] == overlaid["security_posture"]
    assert overlaid["posture"] == baseline["posture"]
    assert overlaid["counts"] == baseline["counts"]
    assert overlaid["findings"] == baseline["findings"]
    assert overlaid["organisation_policy"]["verdict"] == "PERMITTED_RISK"


def test_policy_output_is_deterministic_schema_valid_and_secret_safe(
    run_cli, tmp_path
):
    policy_path = write_policy(
        tmp_path,
        {
            "schema_version": "1",
            "id": "safe-policy",
            "requirements": [
                {
                    "control_id": "AGENT-MCP-001",
                    "expectation": "allow",
                }
            ],
        },
    )
    command = (
        "check",
        "fixtures/codex-danger/config.toml",
        "--policy",
        str(policy_path),
        "--format",
        "json",
    )
    first, second = run_cli(*command), run_cli(*command)
    assert first.stdout.encode() == second.stdout.encode()
    assert "KAAPI_CODEX_SECRET" not in first.stdout
    schema = json.loads(
        Path("kaapi/schemas/check-v1.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(schema).validate(
        json.loads(first.stdout)
    )


def test_policy_validation_is_agent_independent_offline_and_read_only(
    monkeypatch, tmp_path
):
    path = write_policy(
        tmp_path,
        {
            "schema_version": "1",
            "id": "offline",
            "requirements": [
                {
                    "control_id": "AGENT-SBOX-001",
                    "expectation": "pass",
                }
            ],
        },
    )
    before = path.read_bytes()

    def blocked(*args, **kwargs):
        raise AssertionError("network call attempted")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    policy = load_policy(path)
    assert policy.policy_id == "offline"
    assert path.read_bytes() == before


def test_policy_errors_do_not_echo_values(run_cli, tmp_path):
    secret = "KAAPI_POLICY_SECRET_SENTINEL"
    path = write_policy(
        tmp_path,
        {
            "schema_version": "1",
            "id": "safe",
            "secret": secret,
            "requirements": [
                {
                    "control_id": "AGENT-SBOX-001",
                    "expectation": "pass",
                }
            ],
        },
    )
    result = run_cli("policy", "validate", str(path))
    assert result.returncode == 3
    assert secret not in result.stderr


def test_policy_output_cannot_overwrite_policy_input(run_cli, tmp_path):
    path = write_policy(
        tmp_path,
        {
            "schema_version": "1",
            "id": "collision",
            "requirements": [
                {
                    "control_id": "AGENT-SBOX-001",
                    "expectation": "pass",
                }
            ],
        },
    )
    before = path.read_bytes()
    result = run_cli(
        "policy", "validate", str(path), "--output", str(path)
    )
    assert result.returncode == 2
    assert path.read_bytes() == before


def test_policy_control_unavailable_for_runtime_does_not_silently_pass(
    run_cli, tmp_path
):
    path = write_policy(
        tmp_path,
        {
            "schema_version": "1",
            "id": "claude-hook-on-codex",
            "requirements": [
                {
                    "control_id": "AGENT-HOOK-001",
                    "expectation": "pass",
                }
            ],
        },
    )
    result = run_cli(
        "check",
        "fixtures/codex-hardened/config.toml",
        "--policy",
        str(path),
        "--format",
        "json",
    )
    assert result.returncode == 1
    policy = json.loads(result.stdout)["organisation_policy"]
    assert policy["verdict"] == "FAIL"
    assert policy["requirements"][0]["observed"] == {
        "control_available": False
    }


def test_named_mcp_allowlist_is_enforced_for_claude_and_codex(
    run_cli, tmp_path
):
    claude = tmp_path / "claude.json"
    claude.write_text(
        json.dumps(
            {
                "permissions": {"defaultMode": "dontAsk"},
                "mcpServers": {"github": {"url": "https://example.invalid"}},
            }
        ),
        encoding="utf-8",
    )
    codex = tmp_path / "codex.toml"
    codex.write_text(
        'approval_policy = "never"\n'
        'sandbox_mode = "read-only"\n'
        'web_search = "disabled"\n'
        '[mcp_servers.github]\n'
        'url = "https://example.invalid"\n',
        encoding="utf-8",
    )
    policy = "examples/policies/reference/common/mcp-github-only.json"
    for path, runtime in ((claude, "claude-code"), (codex, "codex")):
        result = run_cli(
            "check",
            str(path),
            "--runtime",
            runtime,
            "--policy",
            policy,
            "--fail-on",
            "none",
            "--format",
            "json",
        )
        assert result.returncode == 0
        organisation = json.loads(result.stdout)["organisation_policy"]
        assert organisation["verdict"] == "PERMITTED_RISK"
        assert organisation["requirements"][0]["observed"][
            "unexpected_server_count"
        ] == 0

    unapproved = tmp_path / "unapproved.toml"
    secret_name = "KAAPI_UNAPPROVED_MCP_SENTINEL"
    unapproved.write_text(
        'approval_policy = "never"\n'
        'sandbox_mode = "read-only"\n'
        f'[mcp_servers.{secret_name}]\n'
        'url = "https://example.invalid"\n',
        encoding="utf-8",
    )
    failed = run_cli(
        "check",
        str(unapproved),
        "--runtime",
        "codex",
        "--policy",
        policy,
        "--fail-on",
        "none",
        "--format",
        "json",
    )
    assert failed.returncode == 1
    assert secret_name not in failed.stdout
    requirement = json.loads(failed.stdout)["organisation_policy"][
        "requirements"
    ][0]
    assert requirement["status"] == "FAIL"
    assert requirement["observed"]["unexpected_server_count"] == 1
    assert requirement["observed"]["missing_required_server_count"] == 1


def test_claude_bash_rule_policy_is_exact_and_codex_fails_unsupported(
    run_cli, tmp_path
):
    policy = "examples/policies/reference/claude-code/bash-ls-la-only.json"
    allowed = tmp_path / "allowed.json"
    allowed.write_text(
        json.dumps(
            {
                "permissions": {
                    "defaultMode": "dontAsk",
                    "allow": ["Bash(ls -la)"],
                }
            }
        ),
        encoding="utf-8",
    )
    passed = run_cli(
        "check",
        str(allowed),
        "--policy",
        policy,
        "--fail-on",
        "none",
        "--format",
        "json",
    )
    assert passed.returncode == 0
    assert (
        json.loads(passed.stdout)["organisation_policy"]["verdict"] == "PASS"
    )

    disallowed = tmp_path / "disallowed.json"
    secret_rule = "KAAPI_BASH_RULE_SENTINEL"
    disallowed.write_text(
        json.dumps(
            {
                "permissions": {
                    "defaultMode": "dontAsk",
                    "allow": [
                        "Bash(ls -la)",
                        f"Bash({secret_rule})",
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    failed = run_cli(
        "check",
        str(disallowed),
        "--policy",
        policy,
        "--fail-on",
        "none",
        "--format",
        "json",
    )
    assert failed.returncode == 1
    assert secret_rule not in failed.stdout
    observed = json.loads(failed.stdout)["organisation_policy"][
        "requirements"
    ][0]["observed"]
    assert observed["unexpected_bash_rule_count"] == 1

    codex = run_cli(
        "check",
        "fixtures/codex-hardened/config.toml",
        "--policy",
        policy,
        "--format",
        "json",
    )
    assert codex.returncode == 1
    assert json.loads(codex.stdout)["organisation_policy"]["requirements"][0][
        "observed"
    ] == {"policy_runtime_supported": False}


def test_repeatable_and_directory_policies_compose_deterministically(
    run_cli, tmp_path
):
    directory_command = (
        "check",
        "fixtures/codex-hardened/config.toml",
        "--policy-dir",
        "examples/policies/bundles/strict-common",
        "--format",
        "json",
    )
    first = run_cli(*directory_command)
    second = run_cli(*directory_command)
    assert first.returncode == second.returncode == 0
    assert first.stdout.encode() == second.stdout.encode()
    document = json.loads(first.stdout)
    policy = document["organisation_policy"]
    assert policy["policy_id"] == "bundle"
    assert policy["verdict"] == "PASS"
    assert policy["policy_ids"] == [
        "strict.approvals",
        "strict.filesystem",
        "strict.mcp",
        "strict.network",
        "strict.sandbox",
    ]
    assert all("policy_id" in item for item in policy["requirements"])
    schema = json.loads(
        Path("kaapi/schemas/check-v1.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(schema).validate(document)

    repeated = run_cli(
        "check",
        "fixtures/codex-hardened/config.toml",
        "--policy",
        "examples/policies/no-mcp.json",
        "--policy",
        "examples/policies/reference/common/sandbox-required.json",
        "--format",
        "json",
    )
    assert repeated.returncode == 0
    assert json.loads(repeated.stdout)["organisation_policy"][
        "policy_id"
    ] == "bundle"

    no_human_prompt = run_cli(
        "check",
        "fixtures/codex-hardened/config.toml",
        "--policy",
        "examples/policies/reference/common/approvals-human.json",
        "--fail-on",
        "none",
        "--format",
        "json",
    )
    assert no_human_prompt.returncode == 1
    assert json.loads(no_human_prompt.stdout)["organisation_policy"][
        "verdict"
    ] == "FAIL"

    human_prompt = tmp_path / "human-prompt.toml"
    human_prompt.write_text(
        'approval_policy = "on-request"\n'
        'approvals_reviewer = "user"\n'
        'sandbox_mode = "read-only"\n'
        'web_search = "disabled"\n',
        encoding="utf-8",
    )
    human_prompt_result = run_cli(
        "check",
        str(human_prompt),
        "--runtime",
        "codex",
        "--policy",
        "examples/policies/reference/common/approvals-human.json",
        "--fail-on",
        "none",
        "--format",
        "json",
    )
    assert human_prompt_result.returncode == 0
    assert json.loads(human_prompt_result.stdout)["organisation_policy"][
        "verdict"
    ] == "PASS"

    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        Path("examples/policies/no-mcp.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    rejected = run_cli(
        "policy",
        "validate",
        "examples/policies/no-mcp.json",
        str(duplicate),
    )
    assert rejected.returncode == 3
    assert "duplicate policy id" in rejected.stderr


def test_filesystem_network_hook_and_runtime_parameters(run_cli, tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps(
            {
                "permissions": {"defaultMode": "dontAsk"},
                "sandbox": {
                    "enabled": True,
                    "allowUnsandboxedCommands": False,
                    "filesystem": {
                        "allowWrite": [],
                        "denyWrite": [],
                        "denyRead": ["**/.env", "**/.ssh/**"],
                        "allowRead": [],
                        "allowManagedReadPathsOnly": True,
                    },
                    "network": {
                        "allowedDomains": [],
                        "deniedDomains": ["*"],
                    },
                },
                "hooks": {},
            }
        ),
        encoding="utf-8",
    )
    result = run_cli(
        "check",
        str(settings),
        "--policy",
        "examples/policies/reference/claude-code/sensitive-files-denied.json",
        "--policy",
        "examples/policies/reference/claude-code/no-command-hooks.json",
        "--policy",
        "examples/policies/reference/common/network-offline.json",
        "--format",
        "json",
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["organisation_policy"]["verdict"] == "PASS"

    unavailable = run_cli(
        "check",
        "fixtures/codex-hardened/config.toml",
        "--policy",
        "examples/policies/reference/claude-code/sensitive-files-denied.json",
        "--format",
        "json",
    )
    assert unavailable.returncode == 1
    assert json.loads(unavailable.stdout)["organisation_policy"]["verdict"] == (
        "FAIL"
    )
