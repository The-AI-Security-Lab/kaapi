"""Top-level scan orchestration and stable analysis document creation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import __version__
from .baseline import SEVERITY_ORDER, evaluate, load_baseline
from .codex import load_observed as load_codex_observed
from .codex import merge_layers as merge_codex_layers
from .codex import parse_codex_config_text
from .codex import resolve as resolve_codex
from .parser import (
    MergedSettings,
    discover_settings,
    merge_layers,
    parse_settings,
    parse_settings_text,
)
from .policy import (
    Policy,
    evaluate_policies,
    load_policy_text,
    load_policy_value,
)
from .resolver import resolve


def select_runtime(
    subject: str | Path | None, requested: str = "auto"
) -> str:
    if requested != "auto":
        return requested
    value = str(subject) if subject is not None else "claude-code"
    if value == "codex" or Path(value).suffix.lower() == ".toml":
        return "codex"
    return "claude-code"


def select_controls(
    only: set[str] | None = None,
    ignore: set[str] | None = None,
    runtime: str = "claude-code",
) -> set[str]:
    baseline = load_baseline(runtime)
    known = {control["id"] for control in baseline["controls"]}
    selected = set(known if not only else only)
    selected -= ignore or set()
    return selected


def _load_observed(
    subject: str | Path | None,
    env_root: str | Path | None = None,
    runtime: str = "auto",
) -> tuple[MergedSettings, str, list[str], list[str], str]:
    selected_runtime = select_runtime(subject, runtime)
    if selected_runtime == "codex":
        merged, label, inspected, skipped = load_codex_observed(
            subject, env_root
        )
        return merged, label, inspected, skipped, selected_runtime
    if subject is not None and str(subject) not in {"claude", "claude-code"}:
        layer = parse_settings(subject, "explicit")
        return (
            merge_layers([layer]),
            str(subject),
            [layer.source],
            [],
            selected_runtime,
        )
    layers = discover_settings(env_root)
    if not layers:
        # Absence is a valid observed posture, represented by no documents.
        return (
            merge_layers([]),
            str(subject or "claude-code"),
            [],
            [],
            selected_runtime,
        )
    return (
        merge_layers(layers),
        str(subject or "claude-code"),
        [layer.source for layer in layers],
        [],
        selected_runtime,
    )


def load_observed(
    subject: str | Path | None,
    env_root: str | Path | None = None,
    runtime: str = "auto",
) -> tuple[MergedSettings, str, list[str]]:
    merged, label, inspected, _, _ = _load_observed(
        subject, env_root, runtime
    )
    return merged, label, inspected


def _build_analysis_document(
    merged: MergedSettings,
    subject_label: str,
    skipped: list[str],
    selected_runtime: str,
    *,
    invocation: str | None = None,
    only: set[str] | None = None,
    ignore: set[str] | None = None,
    severity: str = "info",
) -> tuple[dict[str, Any], Any]:
    resolution = (
        resolve_codex(merged, skipped)
        if selected_runtime == "codex"
        else resolve(merged, invocation)
    )
    all_findings, _ = evaluate(merged, resolution, None)
    resolution.facts["baseline_failed_control_ids"] = sorted(
        {item["id"] for item in all_findings}
    )
    resolution.facts["baseline_control_ids"] = sorted(
        control["id"]
        for control in load_baseline(selected_runtime)["controls"]
    )
    selected = select_controls(only, ignore, selected_runtime)
    findings, passed = evaluate(merged, resolution, selected)
    counts = {
        name: sum(item["severity"] == name for item in findings)
        for name in ("critical", "high", "medium", "low", "info")
    }
    not_evaluated = len(resolution.unknown_fields) + len(
        resolution.facts.get("not_evaluated", [])
    )
    has_findings = bool(findings or not_evaluated)
    if counts["critical"] or counts["high"]:
        posture = "FAIL"
    elif has_findings:
        posture = "WARN"
    else:
        posture = "PASS"
    displayed = [
        item
        for item in findings
        if SEVERITY_ORDER[item["severity"]] >= SEVERITY_ORDER[severity]
    ]
    baseline = load_baseline(selected_runtime)
    document = {
        "schema_version": "1",
        "kaapi_version": __version__,
        "baseline": {
            "name": baseline["name"],
            "version": baseline["version"],
            "control_count": len(baseline["controls"]),
        },
        "runtime": selected_runtime,
        "subject": subject_label,
        "posture": posture,
        "counts": counts,
        "fields_not_evaluated": not_evaluated,
        "controls_evaluated": len(selected),
        "passed_controls": passed,
        "resolved_capability": resolution.as_dict(),
        "unknown_fields": [item.as_dict() for item in resolution.unknown_fields],
        "findings": displayed,
    }
    return document, resolution


def apply_policies(
    document: dict[str, Any],
    resolution: Any,
    policies: tuple[Policy, ...],
) -> dict[str, Any]:
    """Add the independent policy assessment to an analysis document."""
    if not policies:
        return document
    document["security_posture"] = document["posture"]
    document["organisation_policy"] = evaluate_policies(
        policies,
        resolution,
        set(resolution.facts["baseline_failed_control_ids"]),
    )
    return document


def _load_policy_inputs(
    policy: str | bytes | Mapping[str, Any] | Sequence[str | bytes | Mapping[str, Any]] | None,
) -> tuple[Policy, ...]:
    if policy is None:
        return ()
    if isinstance(policy, (str, bytes)):
        return (load_policy_text(policy),)
    if isinstance(policy, Mapping):
        return (load_policy_value(dict(policy)),)
    if isinstance(policy, Sequence):
        policies: list[Policy] = []
        for index, item in enumerate(policy):
            source = f"<memory:policy:{index}>"
            if isinstance(item, (str, bytes)):
                policies.append(load_policy_text(item, source))
            elif isinstance(item, Mapping):
                policies.append(load_policy_value(dict(item), source))
            else:
                raise TypeError("each policy must be str, bytes, or a mapping")
        if not policies:
            raise ValueError("policy sequence must not be empty")
        return tuple(policies)
    raise TypeError("policy must be str, bytes, a mapping, or a non-empty sequence")


def analyze(
    subject: str | Path | None,
    *,
    env_root: str | Path | None = None,
    invocation: str | None = None,
    only: set[str] | None = None,
    ignore: set[str] | None = None,
    severity: str = "info",
    runtime: str = "auto",
) -> tuple[dict[str, Any], Any, list[str]]:
    merged, subject_label, inspected, skipped, selected_runtime = (
        _load_observed(subject, env_root, runtime)
    )
    document, resolution = _build_analysis_document(
        merged,
        subject_label,
        skipped,
        selected_runtime,
        invocation=invocation,
        only=only,
        ignore=ignore,
        severity=severity,
    )
    return document, resolution, inspected


def analyze_text(
    content: str | bytes,
    *,
    runtime: str,
    source: str | None = None,
    policy: str | bytes | Mapping[str, Any] | Sequence[str | bytes | Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Analyze configuration text and optionally evaluate closed policies.

    The returned value is the same versioned structured document produced by
    :func:`analyze`; ``source`` is a deterministic display identifier used for
    evidence and defaults to a synthetic in-memory source. ``policy`` accepts
    one policy JSON document or a non-empty sequence of policy JSON documents,
    supplied as text, bytes, or decoded mappings. Policy evaluation is the
    same independent overlay used by the CLI.
    """
    if runtime not in {"claude-code", "codex"}:
        raise ValueError("runtime must be 'claude-code' or 'codex'")
    source_label = source or f"<memory:{runtime}>"
    layer = (
        parse_codex_config_text(content, source_label)
        if runtime == "codex"
        else parse_settings_text(content, source_label)
    )
    merged = (
        merge_codex_layers([layer])
        if runtime == "codex"
        else merge_layers([layer])
    )
    document, resolution = _build_analysis_document(
        merged,
        source_label,
        [],
        runtime,
    )
    return apply_policies(document, resolution, _load_policy_inputs(policy))


def gate_exit(findings: list[dict[str, Any]], fail_on: str) -> int:
    if fail_on == "none":
        return 0
    threshold = SEVERITY_ORDER[fail_on]
    return 1 if any(SEVERITY_ORDER[item["severity"]] >= threshold for item in findings) else 0
