"""Closed-data organisational policy validation and evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .baseline import load_baseline


TOP_REQUIRED_KEYS = {"schema_version", "id", "requirements"}
TOP_OPTIONAL_KEYS = {"domain", "runtimes"}
REQUIREMENT_KEYS = {"control_id", "expectation", "parameters"}
DOMAINS = {
    "baseline",
    "approvals",
    "shell",
    "filesystem",
    "sandbox",
    "network",
    "hooks",
    "mcp",
}
RUNTIMES = {"claude-code", "codex"}
DOMAIN_CONTROLS = {
    "approvals": {"AGENT-APRV-001", "AGENT-APRV-002"},
    "shell": {"AGENT-PERM-001"},
    "filesystem": {"AGENT-PERM-002"},
    "sandbox": {
        "AGENT-SBOX-001",
        "AGENT-SBOX-002",
        "AGENT-SBOX-003",
        "AGENT-SBOX-004",
    },
    "network": {"AGENT-NET-001"},
    "hooks": {"AGENT-HOOK-001"},
    "mcp": {"AGENT-MCP-001"},
}
PARAMETER_TYPES = {
    "AGENT-APRV-001": {
        "allowed_modes": "strings",
    },
    "AGENT-PERM-001": {
        "allowed_bash_rule_patterns": "strings",
        "required_bash_rule_patterns": "strings",
        "max_bash_allow_rules": "integer",
        "require_default_deny": "boolean",
    },
    "AGENT-PERM-002": {
        "max_additional_directories": "integer",
        "max_writable_paths": "integer",
        "allowed_write_patterns": "strings",
        "required_denied_read_patterns": "strings",
        "required_denied_write_patterns": "strings",
        "require_managed_read_paths_only": "boolean",
    },
    "AGENT-SBOX-001": {
        "require_enabled": "boolean",
        "allowed_sandbox_modes": "strings",
    },
    "AGENT-SBOX-004": {
        "max_excluded_commands": "integer",
    },
    "AGENT-NET-001": {
        "require_strict_destination_boundary": "boolean",
        "allow_outbound_potential": "boolean",
        "allowed_domains": "strings",
        "required_denied_domains": "strings",
        "max_allowed_domains": "integer",
        "allow_local_binding": "boolean",
        "allow_all_unix_sockets": "boolean",
        "max_unix_socket_count": "integer",
    },
    "AGENT-HOOK-001": {
        "max_command_hooks": "integer",
        "allowed_hook_events": "strings",
    },
    "AGENT-MCP-001": {
        "max_configured_servers": "integer",
        "allowed_server_names": "strings",
        "required_server_names": "strings",
        "max_auto_approved_servers": "integer",
        "require_managed_only": "boolean",
    },
}
SUPPORTED_PARAMETERS = {
    control_id: set(parameters)
    for control_id, parameters in PARAMETER_TYPES.items()
}
PARAMETER_ENUMS = {
    "allowed_modes": {
        "default",
        "acceptEdits",
        "plan",
        "auto",
        "dontAsk",
        "bypassPermissions",
        "untrusted",
        "on-request",
        "never",
        "granular",
    },
    "allowed_sandbox_modes": {
        "enabled",
        "disabled",
        "read-only",
        "workspace-write",
        "danger-full-access",
    },
}


class PolicyError(Exception):
    def __init__(self, source: str, reason: str) -> None:
        self.source = source
        self.reason = reason
        super().__init__(reason)

    def safe_message(self) -> str:
        return f"policy validation error: {self.source}: {self.reason}"


@dataclass(frozen=True)
class Policy:
    source: str
    policy_id: str
    domain: str
    runtimes: tuple[str, ...]
    requirements: tuple[dict[str, Any], ...]


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def known_control_ids() -> set[str]:
    return {
        control["id"]
        for runtime in ("claude-code", "codex")
        for control in load_baseline(runtime)["controls"]
    }


def load_policy(path: str | Path) -> Policy:
    source_path = Path(path)
    try:
        raw = source_path.read_bytes()
    except OSError as exc:
        raise PolicyError(
            str(source_path),
            f"cannot read policy file ({exc.strerror or 'I/O error'})",
        ) from None
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise PolicyError(str(source_path), "invalid UTF-8") from None
    try:
        value = json.loads(text, object_pairs_hook=_no_duplicates)
    except (json.JSONDecodeError, ValueError):
        raise PolicyError(str(source_path), "invalid JSON") from None
    if not isinstance(value, dict):
        raise PolicyError(str(source_path), "top level must be an object")
    keys = set(value)
    if not TOP_REQUIRED_KEYS.issubset(keys) or not keys.issubset(
        TOP_REQUIRED_KEYS | TOP_OPTIONAL_KEYS
    ):
        raise PolicyError(
            str(source_path), "top-level keys do not match the policy schema"
        )
    if value.get("schema_version") != "1":
        raise PolicyError(str(source_path), "unsupported schema_version")
    policy_id = value.get("id")
    if (
        not isinstance(policy_id, str)
        or not policy_id
        or len(policy_id) > 64
        or any(
            char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
            for char in policy_id
        )
    ):
        raise PolicyError(str(source_path), "id has an invalid format")
    domain = value.get("domain", "baseline")
    if domain not in DOMAINS:
        raise PolicyError(str(source_path), "domain has an invalid value")
    runtimes = value.get("runtimes", sorted(RUNTIMES))
    if (
        not isinstance(runtimes, list)
        or not runtimes
        or any(item not in RUNTIMES for item in runtimes)
        or len(set(runtimes)) != len(runtimes)
    ):
        raise PolicyError(str(source_path), "runtimes has an invalid value")
    requirements = value.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        raise PolicyError(
            str(source_path), "requirements must be a non-empty array"
        )
    known = known_control_ids()
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, requirement in enumerate(requirements):
        label = f"requirements[{index}]"
        if not isinstance(requirement, dict):
            raise PolicyError(str(source_path), f"{label} must be an object")
        if not {"control_id", "expectation"}.issubset(requirement) or not set(
            requirement
        ).issubset(REQUIREMENT_KEYS):
            raise PolicyError(
                str(source_path),
                f"{label} keys do not match the policy schema",
            )
        control_id = requirement.get("control_id")
        if not isinstance(control_id, str) or control_id not in known:
            raise PolicyError(
                str(source_path), f"{label} contains an unknown control ID"
            )
        if control_id in seen:
            raise PolicyError(
                str(source_path), f"{label} duplicates a control ID"
            )
        seen.add(control_id)
        if (
            domain != "baseline"
            and control_id not in DOMAIN_CONTROLS[domain]
        ):
            raise PolicyError(
                str(source_path),
                f"{label} control does not belong to the policy domain",
            )
        expectation = requirement.get("expectation")
        if expectation not in {"pass", "allow"}:
            raise PolicyError(
                str(source_path), f"{label} has an unsupported expectation"
            )
        parameters = requirement.get("parameters", {})
        if not isinstance(parameters, dict):
            raise PolicyError(
                str(source_path), f"{label}.parameters must be an object"
            )
        supported = SUPPORTED_PARAMETERS.get(control_id, set())
        if not set(parameters).issubset(supported):
            raise PolicyError(
                str(source_path),
                f"{label} contains an unsupported parameter",
            )
        if expectation == "allow" and parameters:
            raise PolicyError(
                str(source_path),
                f"{label} cannot combine allow with parameters",
            )
        for name, parameter in parameters.items():
            parameter_type = PARAMETER_TYPES[control_id][name]
            if parameter_type == "integer" and (
                not isinstance(parameter, int)
                or isinstance(parameter, bool)
                or parameter < 0
            ):
                raise PolicyError(
                    str(source_path),
                    f"{label} parameter must be a non-negative integer",
                )
            if parameter_type == "boolean" and not isinstance(parameter, bool):
                raise PolicyError(
                    str(source_path),
                    f"{label} parameter must be a boolean",
                )
            if parameter_type == "strings" and (
                not isinstance(parameter, list)
                or len(parameter) > 128
                or any(
                    not isinstance(item, str)
                    or not item
                    or len(item) > 512
                    or any(ord(char) < 32 for char in item)
                    for item in parameter
                )
                or len(set(parameter)) != len(parameter)
            ):
                raise PolicyError(
                    str(source_path),
                    f"{label} parameter must be an array of unique strings",
                )
            allowed_values = PARAMETER_ENUMS.get(name)
            if allowed_values is not None and not set(parameter).issubset(
                allowed_values
            ):
                raise PolicyError(
                    str(source_path),
                    f"{label} parameter contains an unsupported value",
                )
        normalized.append(
            {
                "control_id": control_id,
                "expectation": expectation,
                "parameters": dict(sorted(parameters.items())),
            }
        )
    normalized.sort(key=lambda item: item["control_id"])
    return Policy(
        source=str(source_path),
        policy_id=policy_id,
        domain=domain,
        runtimes=tuple(sorted(runtimes)),
        requirements=tuple(normalized),
    )


def validation_result(policy: Policy) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "valid": True,
        "policy_id": policy.policy_id,
        "domain": policy.domain,
        "runtimes": list(policy.runtimes),
        "requirement_count": len(policy.requirements),
    }


def load_policies(
    policy_paths: list[str] | tuple[str, ...] | None = None,
    policy_directories: list[str] | tuple[str, ...] | None = None,
) -> tuple[Policy, ...]:
    files = [Path(path) for path in policy_paths or ()]
    for directory_value in policy_directories or ():
        directory = Path(directory_value)
        if not directory.is_dir():
            raise PolicyError(str(directory), "policy directory is not readable")
        discovered = sorted(directory.glob("*.json"))
        if not discovered:
            raise PolicyError(str(directory), "policy directory contains no JSON files")
        files.extend(discovered)
    unique_files: list[Path] = []
    seen_paths: set[Path] = set()
    for path in files:
        resolved = path.resolve(strict=False)
        if resolved not in seen_paths:
            seen_paths.add(resolved)
            unique_files.append(path)
    policies = [load_policy(path) for path in unique_files]
    seen_ids: set[str] = set()
    for policy in policies:
        if policy.policy_id in seen_ids:
            raise PolicyError(policy.source, "duplicate policy id in bundle")
        seen_ids.add(policy.policy_id)
    return tuple(sorted(policies, key=lambda item: item.policy_id))


def validation_bundle_result(policies: tuple[Policy, ...]) -> dict[str, Any]:
    if len(policies) == 1:
        return validation_result(policies[0])
    return {
        "schema_version": "1",
        "valid": True,
        "policy_ids": [policy.policy_id for policy in policies],
        "policy_count": len(policies),
        "requirement_count": sum(
            len(policy.requirements) for policy in policies
        ),
    }


def _safe_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        name: (
            {"item_count": len(value)}
            if isinstance(value, list)
            else value
        )
        for name, value in sorted(parameters.items())
    }


def _set_check(
    actual: Any,
    expected: list[str],
    *,
    allowed: bool,
) -> tuple[bool, int, int]:
    if actual is None:
        return False, 0, 0
    actual_set = set(actual)
    expected_set = set(expected)
    unexpected = len(actual_set - expected_set) if allowed else 0
    missing = len(expected_set - actual_set) if not allowed else 0
    return (unexpected == 0 if allowed else missing == 0), unexpected, missing


def _evaluate_parameters(
    control_id: str,
    parameters: dict[str, Any],
    resolution: Any,
) -> tuple[bool, dict[str, Any]]:
    facts = resolution.facts
    observed: dict[str, Any] = {}
    checks: list[bool] = []

    def unsupported(name: str) -> None:
        observed[f"{name}_supported"] = False
        checks.append(False)

    for name, expected in sorted(parameters.items()):
        if name == "max_configured_servers":
            actual = int(resolution.mcp["configured_server_count"])
            observed["configured_server_count"] = actual
            checks.append(actual <= expected)
        elif name == "allowed_server_names":
            actual = facts.get("mcp_server_names")
            passed, unexpected, _ = _set_check(
                actual, expected, allowed=True
            )
            observed["configured_server_count"] = len(actual or [])
            observed["unexpected_server_count"] = unexpected
            checks.append(passed)
        elif name == "required_server_names":
            actual = facts.get("mcp_server_names")
            passed, _, missing = _set_check(
                actual, expected, allowed=False
            )
            observed["configured_server_count"] = len(actual or [])
            observed["missing_required_server_count"] = missing
            checks.append(passed)
        elif name == "max_auto_approved_servers":
            actual = resolution.mcp.get("auto_approved_server_count")
            if actual is None:
                unsupported(name)
            else:
                observed["auto_approved_server_count"] = int(actual)
                checks.append(int(actual) <= expected)
        elif name == "require_managed_only":
            actual = facts.get("mcp_managed_only")
            if actual is None:
                unsupported(name)
            else:
                observed["managed_only"] = bool(actual)
                checks.append(bool(actual) is expected)
        elif name in {
            "allowed_bash_rule_patterns",
            "required_bash_rule_patterns",
            "max_bash_allow_rules",
            "require_default_deny",
        }:
            if facts.get("shell_rule_policy_supported") is not True:
                unsupported(name)
                continue
            patterns = facts["bash_allow_rule_patterns"]
            broad_count = int(facts["bash_broad_allow_count"])
            observed["bash_allow_rule_count"] = len(patterns) + broad_count
            observed["broad_bash_allow_rule_count"] = broad_count
            if name == "allowed_bash_rule_patterns":
                passed, unexpected, _ = _set_check(
                    patterns, expected, allowed=True
                )
                observed["unexpected_bash_rule_count"] = (
                    unexpected + broad_count
                )
                checks.append(passed and broad_count == 0)
            elif name == "required_bash_rule_patterns":
                passed, _, missing = _set_check(
                    patterns, expected, allowed=False
                )
                observed["missing_required_bash_rule_count"] = missing
                checks.append(passed)
            elif name == "max_bash_allow_rules":
                checks.append(len(patterns) + broad_count <= expected)
            else:
                default_deny = resolution.configured_mode == "dontAsk"
                observed["default_deny"] = default_deny
                checks.append(default_deny is expected)
        elif name == "max_additional_directories":
            actual = int(resolution.additional_directory_count)
            observed["additional_directory_count"] = actual
            checks.append(actual <= expected)
        elif name == "max_writable_paths":
            actual = facts.get("writable_path_patterns")
            if actual is None:
                unsupported(name)
            else:
                observed["writable_path_count"] = len(actual)
                checks.append(len(actual) <= expected)
        elif name == "allowed_write_patterns":
            actual = facts.get("writable_path_patterns")
            passed, unexpected, _ = _set_check(
                actual, expected, allowed=True
            )
            observed["writable_path_count"] = len(actual or [])
            observed["unexpected_writable_path_count"] = unexpected
            checks.append(passed)
        elif name in {
            "required_denied_read_patterns",
            "required_denied_write_patterns",
        }:
            fact_name = (
                "denied_read_patterns"
                if name == "required_denied_read_patterns"
                else "denied_write_patterns"
            )
            actual = facts.get(fact_name)
            if actual is None:
                unsupported(name)
            else:
                passed, _, missing = _set_check(
                    actual, expected, allowed=False
                )
                observed[f"{fact_name}_count"] = len(actual)
                observed[f"missing_{fact_name}_count"] = missing
                checks.append(passed)
        elif name == "require_managed_read_paths_only":
            filesystem = resolution.sandbox.get("filesystem", {})
            if "managed_read_paths_only" not in filesystem:
                unsupported(name)
            else:
                actual = bool(filesystem["managed_read_paths_only"])
                observed["managed_read_paths_only"] = actual
                checks.append(actual is expected)
        elif name == "require_enabled":
            actual = bool(resolution.sandbox["enabled"])
            observed["sandbox_enabled"] = actual
            checks.append(actual is expected)
        elif name == "allowed_sandbox_modes":
            actual = facts.get("sandbox_mode")
            observed["sandbox_mode"] = actual
            checks.append(actual in expected)
        elif name == "max_excluded_commands":
            actual = int(resolution.sandbox["excluded_command_count"])
            observed["excluded_command_count"] = actual
            checks.append(actual <= expected)
        elif name == "require_strict_destination_boundary":
            actual = bool(resolution.network["strict_destination_boundary"])
            observed["strict_destination_boundary"] = actual
            checks.append(actual is expected)
        elif name == "allow_outbound_potential":
            actual = bool(resolution.network["outbound_configured_potential"])
            observed["outbound_configured_potential"] = actual
            checks.append(bool(expected) or not actual)
        elif name == "allowed_domains":
            actual = facts.get("allowed_domains")
            passed, unexpected, _ = _set_check(
                actual, expected, allowed=True
            )
            observed["allowed_domain_count"] = len(actual or [])
            observed["unexpected_allowed_domain_count"] = unexpected
            checks.append(passed)
        elif name == "required_denied_domains":
            actual = facts.get("denied_domains")
            passed, _, missing = _set_check(
                actual, expected, allowed=False
            )
            observed["denied_domain_count"] = len(actual or [])
            observed["missing_denied_domain_count"] = missing
            checks.append(passed)
        elif name == "max_allowed_domains":
            actual = len(facts.get("allowed_domains") or [])
            observed["allowed_domain_count"] = actual
            checks.append(actual <= expected)
        elif name in {"allow_local_binding", "allow_all_unix_sockets"}:
            key = (
                "local_binding"
                if name == "allow_local_binding"
                else "all_unix_sockets"
            )
            actual = bool(resolution.network["exceptions"][key])
            observed[key] = actual
            checks.append(bool(expected) or not actual)
        elif name == "max_unix_socket_count":
            actual = int(
                resolution.network["exceptions"]["unix_socket_count"]
            )
            observed["unix_socket_count"] = actual
            checks.append(actual <= expected)
        elif name == "max_command_hooks":
            if facts.get("hook_events") is None:
                unsupported(name)
            else:
                actual = sum(
                    int(item["command_count"]) for item in resolution.hooks
                )
                observed["command_hook_count"] = actual
                checks.append(actual <= expected)
        elif name == "allowed_hook_events":
            actual = facts.get("hook_events")
            if actual is None:
                unsupported(name)
            else:
                passed, unexpected, _ = _set_check(
                    actual, expected, allowed=True
                )
                observed["hook_event_count"] = len(actual)
                observed["unexpected_hook_event_count"] = unexpected
                checks.append(passed)
        elif name == "allowed_modes":
            actual = resolution.configured_mode
            observed["configured_mode"] = actual
            checks.append(actual in expected)
        else:
            unsupported(name)
    return all(checks), dict(sorted(observed.items()))


def evaluate_policy(
    policy: Policy,
    resolution: Any,
    baseline_failed_ids: set[str],
) -> dict[str, Any]:
    active_control_ids = set(resolution.facts["baseline_control_ids"])
    results: list[dict[str, Any]] = []
    runtime_supported = resolution.facts["runtime"] in policy.runtimes
    for requirement in policy.requirements:
        control_id = requirement["control_id"]
        baseline_finding = control_id in baseline_failed_ids
        parameters = requirement["parameters"]
        if not runtime_supported:
            result = {
                "control_id": control_id,
                "expectation": requirement["expectation"],
                "status": "FAIL",
                "baseline_finding": baseline_finding,
                "parameters": _safe_parameters(parameters),
                "observed": {"policy_runtime_supported": False},
            }
        elif control_id not in active_control_ids:
            result = {
                "control_id": control_id,
                "expectation": requirement["expectation"],
                "status": "FAIL",
                "baseline_finding": False,
                "parameters": _safe_parameters(parameters),
                "observed": {"control_available": False},
            }
        elif parameters:
            parameters_pass, observed = _evaluate_parameters(
                control_id, parameters, resolution
            )
            status = (
                "FAIL"
                if not parameters_pass
                else ("PERMITTED_RISK" if baseline_finding else "PASS")
            )
            result = {
                "control_id": control_id,
                "expectation": requirement["expectation"],
                "status": status,
                "baseline_finding": baseline_finding,
                "parameters": _safe_parameters(parameters),
                "observed": observed,
            }
        else:
            if requirement["expectation"] == "allow":
                status = "PERMITTED_RISK" if baseline_finding else "PASS"
            else:
                status = "FAIL" if baseline_finding else "PASS"
            result = {
                "control_id": control_id,
                "expectation": requirement["expectation"],
                "status": status,
                "baseline_finding": baseline_finding,
                "parameters": _safe_parameters(parameters),
                "observed": {},
            }
        results.append(result)
    statuses = {item["status"] for item in results}
    verdict = (
        "FAIL"
        if "FAIL" in statuses
        else (
            "PERMITTED_RISK"
            if "PERMITTED_RISK" in statuses
            else "PASS"
        )
    )
    return {
        "schema_version": "1",
        "policy_id": policy.policy_id,
        "verdict": verdict,
        "requirements": results,
    }


def evaluate_policies(
    policies: tuple[Policy, ...],
    resolution: Any,
    baseline_failed_ids: set[str],
) -> dict[str, Any]:
    evaluated = [
        evaluate_policy(policy, resolution, baseline_failed_ids)
        for policy in policies
    ]
    if len(evaluated) == 1:
        return evaluated[0]
    requirements: list[dict[str, Any]] = []
    for policy, result in zip(policies, evaluated):
        for requirement in result["requirements"]:
            requirements.append(
                {
                    "policy_id": policy.policy_id,
                    "domain": policy.domain,
                    **requirement,
                }
            )
    verdicts = {result["verdict"] for result in evaluated}
    verdict = (
        "FAIL"
        if "FAIL" in verdicts
        else (
            "PERMITTED_RISK"
            if "PERMITTED_RISK" in verdicts
            else "PASS"
        )
    )
    return {
        "schema_version": "1",
        "policy_id": "bundle",
        "policy_ids": [policy.policy_id for policy in policies],
        "verdict": verdict,
        "requirements": requirements,
    }
