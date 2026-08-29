"""Declarative baseline loading and deterministic control evaluation."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from .model import Evidence, Resolution
from .parser import MergedSettings


BASELINE_RESOURCE = "baseline-0.3.1.json"
LAYER_ORDER = {"approvals": 0, "permissions": 1, "sandbox": 2, "network": 3, "hooks": 4, "mcp": 5}
SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
UNKNOWN_IDS = {
    "approvals": "AGENT-APRV-099",
    "permissions": "AGENT-PERM-099",
    "sandbox": "AGENT-SBOX-099",
    "network": "AGENT-NET-099",
    "hooks": "AGENT-HOOK-099",
    "mcp": "AGENT-MCP-099",
}


def load_baseline() -> dict[str, Any]:
    resource = files("kaapi").joinpath("data", BASELINE_RESOURCE)
    baseline = json.loads(resource.read_text(encoding="utf-8"))
    required = {
        "id", "title", "layer", "rationale", "severity", "platform_applicability",
        "tested_versions", "last_verified", "support_confidence", "sources",
        "references", "remediation",
    }
    controls = baseline.get("controls")
    if not isinstance(controls, list) or not controls:
        raise RuntimeError("invalid shipped baseline: controls missing")
    ids: set[str] = set()
    for control in controls:
        if not isinstance(control, dict) or not required.issubset(control):
            raise RuntimeError("invalid shipped baseline: incomplete control")
        if control["id"] in ids:
            raise RuntimeError("invalid shipped baseline: duplicate control ID")
        ids.add(control["id"])
        if not control["sources"] or control["references"] != []:
            raise RuntimeError("invalid shipped baseline: provenance contract")
    return baseline


def control_map(baseline: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    baseline = baseline or load_baseline()
    return {control["id"]: control for control in baseline["controls"]}


def _points(merged: MergedSettings, path: str, detail: str, all_layers: bool = False) -> list[Evidence]:
    points = merged.evidence_points(path, all_layers)
    return [Evidence(layer.source, line, path, detail) for layer, line in points]


def _fallback_evidence(merged: MergedSettings, path: str, detail: str) -> list[Evidence]:
    evidence = _points(merged, path, detail)
    if evidence:
        return evidence
    if merged.layers:
        return [Evidence(merged.layers[-1].source, merged.layers[-1].lines.get("$"), path, detail)]
    return [Evidence("<no observed settings>", None, path, detail)]


def _finding(control: dict[str, Any], observed: str, inference: str, why: str, confidence: str, evidence: list[Evidence]) -> dict[str, Any]:
    return {
        "id": control["id"],
        "source_type": "baseline",
        "title": control["title"],
        "layer": control["layer"],
        "observed": observed,
        "inference": inference,
        "severity": control["severity"],
        "confidence": confidence,
        "sources": control["sources"],
        "references": control["references"],
        "remediation": control["remediation"],
        "evidence": [item.as_dict() for item in evidence],
        "why_severity": why,
    }


def evaluate(merged: MergedSettings, resolution: Resolution, selected_ids: set[str] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    baseline = load_baseline()
    controls = control_map(baseline)
    selected = selected_ids if selected_ids is not None else set(controls)
    findings: list[dict[str, Any]] = []

    def add(control_id: str, observed: str, inference: str, why: str, confidence: str, evidence: list[Evidence]) -> None:
        if control_id in selected:
            findings.append(_finding(controls[control_id], observed, inference, why, confidence, evidence))

    if resolution.bypasses:
        evidence = [Evidence(item["source"], item["line"], item["path"], f"observed bypass mechanism: {item['mechanism']}") for item in resolution.bypasses]
        add(
            "AGENT-APRV-001",
            "A supported permission-bypass mechanism is present in an observed source.",
            "The resolved configuration permits bypass behavior, while applicable deny rules remain effective.",
            "Critical because most permission prompts and safety checks can be skipped.",
            "high",
            evidence,
        )
    if resolution.configured_mode == "auto" and not resolution.auto_locked:
        add(
            "AGENT-APRV-002",
            "The configured permission mode is auto.",
            "Actions can be reviewed by the background classifier without per-action human approval.",
            "High because the observed mode permits broad unattended configured capability.",
            "high",
            _fallback_evidence(merged, "$.permissions.defaultMode", "automatic mode configured"),
        )

    shell_state = resolution.facts["tool_states"]["Bash"]
    if shell_state == "unprompted" or resolution.facts["sandboxed_bash_unprompted"]:
        evidence = _points(merged, "$.permissions.defaultMode", "mode permits unprompted shell capability")
        for rule in resolution.facts["rules"]:
            if rule.rule_class == "allow" and rule.tool in {"Bash", "*"} and rule.specifier in {None, "*"}:
                evidence.append(Evidence(rule.source, rule.line, rule.path, "broad Bash allow rule is present"))
        if resolution.facts["sandboxed_bash_unprompted"]:
            evidence.extend(_points(merged, "$.sandbox.autoAllowBashIfSandboxed", "sandboxed Bash auto-approval is enabled"))
            if not _points(merged, "$.sandbox.autoAllowBashIfSandboxed", ""):
                evidence.extend(_fallback_evidence(merged, "$.sandbox.enabled", "sandboxed Bash auto-approval uses the vendor default true"))
        add(
            "AGENT-PERM-001",
            "General or sandboxable Bash capability resolves as unprompted.",
            "Configured shell commands within the resolved category can proceed without a per-action human prompt, subject to applicable denies, fallback flow, and OS boundaries.",
            "High because general shell access reaches broad ambient host capability.",
            "high",
            evidence or _fallback_evidence(merged, "$.permissions", "unprompted shell capability resolved"),
        )
    write_state = resolution.facts["tool_states"]["Write"]
    if write_state == "unprompted":
        evidence = _points(merged, "$.permissions.defaultMode", "mode permits unprompted file mutation")
        for rule in resolution.facts["rules"]:
            if rule.rule_class == "allow" and rule.tool in {"Edit", "Write"} and rule.specifier in {None, "*"}:
                evidence.append(Evidence(rule.source, rule.line, rule.path, "broad Edit-family allow rule is present"))
        add(
            "AGENT-PERM-002",
            "File mutation capability resolves as unprompted.",
            "Configured file writes can proceed without a per-action human prompt within applicable scope.",
            "High because unprompted mutation can alter source or configuration.",
            "high",
            evidence or _fallback_evidence(merged, "$.permissions", "unprompted file mutation resolved"),
        )

    if not resolution.sandbox["enabled"]:
        add(
            "AGENT-SBOX-001",
            "sandbox.enabled is not observed as true.",
            "The Claude Code OS-enforced boundary is not configured for Bash subprocesses.",
            "High because subprocesses lack this additional configured containment boundary.",
            "high",
            _fallback_evidence(merged, "$.sandbox.enabled", "sandbox is absent or disabled"),
        )
    if resolution.sandbox["enabled"] and resolution.sandbox["unsandboxed_retry_allowed"]:
        add(
            "AGENT-SBOX-002",
            "The sandbox is configured and unsandboxed retry is not disabled.",
            "The dangerouslyDisableSandbox retry escape hatch remains configured as available.",
            "High because a command can be retried outside the configured sandbox boundary.",
            "high",
            _fallback_evidence(merged, "$.sandbox.allowUnsandboxedCommands", "unsandboxed retry is allowed by value or vendor default"),
        )
    if resolution.sandbox["weaker_nested_isolation"]:
        add(
            "AGENT-SBOX-003",
            "enableWeakerNestedSandbox is true.",
            "Nested sandbox isolation is configured in its weaker form.",
            "High because the configured OS isolation boundary is weakened.",
            "high",
            _fallback_evidence(merged, "$.sandbox.enableWeakerNestedSandbox", "weaker nested isolation enabled"),
        )
    if resolution.sandbox["excluded_command_count"]:
        add(
            "AGENT-SBOX-004",
            "One or more excluded sandbox commands are present; values are redacted.",
            "Those configured commands can execute outside the sandbox when invoked.",
            "Medium because this is a scoped escape surface rather than proof of execution.",
            "high",
            _fallback_evidence(merged, "$.sandbox.excludedCommands", "excluded command values: <present>"),
        )

    if resolution.network["outbound_configured_potential"] and not resolution.network["strict_destination_boundary"]:
        evidence = _points(merged, "$.sandbox.network", "no strict sandbox destination boundary is configured")
        if not evidence:
            evidence = _fallback_evidence(merged, "$.sandbox.enabled", "outbound-capable tools or shell lack a strict configured destination boundary")
        add(
            "AGENT-NET-001",
            "Outbound-capable tool or shell permission is available without a strict configured destination boundary.",
            "The configuration can enter an approval or classifier flow for destinations beyond a fixed allow boundary; no connection is claimed.",
            "High because unbounded configured destinations increase data-exposure potential.",
            "medium",
            evidence,
        )

    if resolution.hooks:
        evidence = [Evidence(item["source"], item["line"], item["path"], f"{item['event']} matcher {item['matcher']}: {item['command_count']} command value(s) <present>") for item in resolution.hooks]
        add(
            "AGENT-HOOK-001",
            "Executable command hook configuration is present; command values are redacted.",
            "A lifecycle event could execute configured commands with user OS permissions; execution is not observed.",
            "Medium because this is an executable static surface without evidence it ran.",
            "high",
            evidence,
        )
    if resolution.mcp["configured_server_count"]:
        add(
            "AGENT-MCP-001",
            f"{resolution.mcp['configured_server_count']} MCP server definition(s) are selected by observed configuration.",
            "The servers could add tool surfaces if they later connect; connection, exposure, approval, and execution are not observed.",
            "Medium because server configuration expands potential integration surface but does not auto-approve tools.",
            "high",
            _fallback_evidence(merged, "$.mcpServers", "MCP server definitions present; command, arguments, environment, and URL values are redacted"),
        )

    for layer, control_id in UNKNOWN_IDS.items():
        items = [item for item in resolution.unknown_fields if item.layer == layer]
        if items:
            add(
                control_id,
                f"{len(items)} unknown {layer} security field(s) are present.",
                "Kaapi cannot evaluate their effect, so the configuration cannot receive a clean PASS.",
                "Medium because the effect is unknown rather than proven critical or high capability.",
                "high",
                [Evidence(item.source, item.line, item.path, "unknown security field is not evaluated") for item in items],
            )

    findings.sort(key=lambda finding: (LAYER_ORDER[finding["layer"]], finding["id"], [(e["source"], e["line"] or 0, e["path"]) for e in finding["evidence"]]))
    failed = {finding["id"] for finding in findings}
    passed = sorted(selected - failed)
    return findings, passed
