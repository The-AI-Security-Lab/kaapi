from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.p2_1.harness import assess_configuration, evaluate_case
from kaapi import analyze_text
from kaapi.policy import PolicyError


ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "evaluation" / "p2_1" / "golden"


def _policy(manifest: dict) -> dict:
    return manifest["security_requirement"]["policy"]


def _normalise_sources(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: "<source>" if key in {"source", "subject"} else _normalise_sources(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalise_sources(item) for item in value]
    return value


@pytest.mark.parametrize(
    "case_name",
    ["claude-insecure", "claude-hardened", "codex-insecure", "codex-hardened"],
)
def test_p2_1_golden_cases_match_expected(case_name):
    case_dir = GOLDEN / case_name
    manifest = json.loads((case_dir / "evaluation.json").read_text(encoding="utf-8"))
    result = evaluate_case(case_dir)
    expected = manifest["expected"]
    assert result["grade"] == expected["grade"]
    assert result["security_posture"] == expected["security_posture"]
    assert result["policy_verdict"] == expected["policy_verdict"]
    assert result["policy_status"] == expected["policy_status"]
    for key, value in expected["observed"].items():
        assert result["evidence"]["policy_requirement"]["observed"][key] == value


@pytest.mark.parametrize(
    "case_name",
    ["claude-insecure", "claude-hardened", "codex-insecure", "codex-hardened"],
)
def test_p2_1_cli_and_python_assessments_are_equivalent(case_name, run_cli, tmp_path):
    case_dir = GOLDEN / case_name
    manifest = json.loads((case_dir / "evaluation.json").read_text(encoding="utf-8"))
    config_path = case_dir / manifest["config"]
    policy_path = tmp_path / f"{case_name}-policy.json"
    policy_path.write_text(json.dumps(_policy(manifest)), encoding="utf-8")
    cli = run_cli(
        "check",
        str(config_path),
        "--runtime",
        manifest["runtime"],
        "--policy",
        str(policy_path),
        "--format",
        "json",
    )
    assert cli.returncode in {0, 1}
    cli_document = json.loads(cli.stdout)
    api_document = analyze_text(
        config_path.read_bytes(),
        runtime=manifest["runtime"],
        source=str(config_path),
        policy=_policy(manifest),
    )
    assert _normalise_sources(api_document) == _normalise_sources(cli_document)


def test_analyze_text_accepts_policy_text_and_preserves_legacy_callers():
    config = (GOLDEN / "claude-hardened" / "settings.json").read_bytes()
    manifest = json.loads(
        (GOLDEN / "claude-hardened" / "evaluation.json").read_text(encoding="utf-8")
    )
    policy_text = json.dumps(_policy(manifest))
    from_text = analyze_text(config, runtime="claude-code", policy=policy_text)
    from_mapping = analyze_text(config, runtime="claude-code", policy=_policy(manifest))
    without_policy = analyze_text(config, runtime="claude-code")
    assert from_text == from_mapping
    assert "organisation_policy" not in without_policy
    assert from_text["organisation_policy"]["verdict"] == "PASS"


def test_repeated_golden_evaluation_is_byte_deterministic():
    case_dir = GOLDEN / "codex-insecure"
    first = json.dumps(evaluate_case(case_dir), sort_keys=True, separators=(",", ":"))
    second = json.dumps(evaluate_case(case_dir), sort_keys=True, separators=(",", ":"))
    assert first == second


def test_missing_required_evidence_is_inconclusive_not_pass():
    config = (GOLDEN / "claude-hardened" / "settings.json").read_bytes()
    manifest = json.loads(
        (GOLDEN / "claude-hardened" / "evaluation.json").read_text(encoding="utf-8")
    )
    requirement = json.loads(json.dumps(manifest["security_requirement"]))
    requirement["required_evidence"].append("finding")
    result = assess_configuration(
        config,
        runtime="claude-code",
        security_requirement=requirement,
    )
    assert result["grade"] == "INCONCLUSIVE"
    assert "missing: finding" in result["limitations"][1]


def test_empty_requirement_observation_is_inconclusive_not_pass():
    config = (GOLDEN / "claude-hardened" / "settings.json").read_bytes()
    result = assess_configuration(
        config,
        runtime="claude-code",
        security_requirement={
            "control_id": "AGENT-APRV-001",
            "policy": {
                "schema_version": "1",
                "id": "no-bypass",
                "runtimes": ["claude-code"],
                "requirements": [
                    {"control_id": "AGENT-APRV-001", "expectation": "pass"}
                ],
            },
            "required_evidence": [
                "organisation_policy",
                "policy_requirement",
                "requirement_observation",
            ],
        },
    )
    assert result["grade"] == "INCONCLUSIVE"


def test_missing_evidence_declaration_is_not_tested():
    config = (GOLDEN / "claude-hardened" / "settings.json").read_bytes()
    result = assess_configuration(
        config,
        runtime="claude-code",
        security_requirement={
            "control_id": "AGENT-SBOX-001",
            "policy": {
                "schema_version": "1",
                "id": "sandbox",
                "requirements": [
                    {
                        "control_id": "AGENT-SBOX-001",
                        "expectation": "pass",
                        "parameters": {"require_enabled": True},
                    }
                ],
            },
        },
    )
    assert result["grade"] == "NOT_TESTED"


def test_unsupported_requirement_is_not_tested():
    config = (GOLDEN / "claude-hardened" / "settings.json").read_bytes()
    result = assess_configuration(
        config,
        runtime="claude-code",
        security_requirement={
            "control_id": "AGENT-MCP-001",
            "policy": {
                "schema_version": "1",
                "id": "codex-only",
                "runtimes": ["codex"],
                "requirements": [
                    {"control_id": "AGENT-MCP-001", "expectation": "pass"}
                ],
            },
            "required_evidence": [
                "organisation_policy",
                "policy_requirement",
                "requirement_observation",
            ],
        },
    )
    assert result["grade"] == "NOT_TESTED"


def test_malformed_configuration_is_not_tested():
    result = assess_configuration(
        '{"permissions": [}',
        runtime="claude-code",
        security_requirement={
            "control_id": "AGENT-SBOX-001",
            "policy": {
                "schema_version": "1",
                "id": "sandbox",
                "requirements": [
                    {
                        "control_id": "AGENT-SBOX-001",
                        "expectation": "pass",
                        "parameters": {"require_enabled": True},
                    }
                ],
            },
            "required_evidence": [
                "organisation_policy",
                "policy_requirement",
                "requirement_observation",
            ],
        },
    )
    assert result["grade"] == "NOT_TESTED"


def test_missing_configuration_is_not_tested(tmp_path):
    (tmp_path / "evaluation.json").write_text(
        json.dumps(
            {
                "schema_version": "1",
                "case_id": "missing",
                "runtime": "claude-code",
                "config": "missing.json",
                "security_requirement": {
                    "control_id": "AGENT-SBOX-001",
                    "policy": {
                        "schema_version": "1",
                        "id": "sandbox",
                        "requirements": [
                            {
                                "control_id": "AGENT-SBOX-001",
                                "expectation": "pass",
                                "parameters": {"require_enabled": True},
                            }
                        ],
                    },
                    "required_evidence": [
                        "organisation_policy",
                        "policy_requirement",
                        "requirement_observation",
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    result = evaluate_case(tmp_path)
    assert result["grade"] == "NOT_TESTED"
    assert "unavailable" in result["limitations"][0]


def test_malformed_policy_still_raises_from_public_api():
    with pytest.raises(PolicyError, match="invalid JSON"):
        analyze_text(
            (GOLDEN / "claude-hardened" / "settings.json").read_bytes(),
            runtime="claude-code",
            policy="{not-json",
        )
