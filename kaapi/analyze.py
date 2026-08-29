"""Top-level scan orchestration and stable analysis document creation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import __version__
from .baseline import SEVERITY_ORDER, evaluate, load_baseline
from .parser import MergedSettings, discover_settings, merge_layers, parse_settings
from .resolver import resolve


def select_controls(only: set[str] | None = None, ignore: set[str] | None = None) -> set[str]:
    baseline = load_baseline()
    known = {control["id"] for control in baseline["controls"]}
    selected = set(known if not only else only)
    selected -= ignore or set()
    return selected


def load_observed(subject: str | Path | None, env_root: str | Path | None = None) -> tuple[MergedSettings, str, list[str]]:
    if subject is not None and str(subject) not in {"claude", "claude-code"}:
        layer = parse_settings(subject, "explicit")
        return merge_layers([layer]), str(subject), [layer.source]
    layers = discover_settings(env_root)
    if not layers:
        # Absence is a valid observed posture, represented by no documents.
        return merge_layers([]), str(subject or "claude-code"), []
    return merge_layers(layers), str(subject or "claude-code"), [layer.source for layer in layers]


def analyze(
    subject: str | Path | None,
    *,
    env_root: str | Path | None = None,
    invocation: str | None = None,
    only: set[str] | None = None,
    ignore: set[str] | None = None,
    severity: str = "info",
) -> tuple[dict[str, Any], Any, list[str]]:
    merged, subject_label, inspected = load_observed(subject, env_root)
    resolution = resolve(merged, invocation)
    selected = select_controls(only, ignore)
    findings, passed = evaluate(merged, resolution, selected)
    counts = {name: sum(item["severity"] == name for item in findings) for name in ("critical", "high", "medium", "low", "info")}
    if counts["critical"] or counts["high"]:
        posture = "FAIL"
    elif findings or resolution.unknown_fields:
        posture = "WARN"
    else:
        posture = "PASS"
    displayed = [item for item in findings if SEVERITY_ORDER[item["severity"]] >= SEVERITY_ORDER[severity]]
    baseline = load_baseline()
    document = {
        "schema_version": "1",
        "kaapi_version": __version__,
        "baseline": {
            "name": baseline["name"],
            "version": baseline["version"],
            "control_count": len(baseline["controls"]),
        },
        "runtime": "claude-code",
        "subject": subject_label,
        "posture": posture,
        "counts": counts,
        "fields_not_evaluated": len(resolution.unknown_fields),
        "controls_evaluated": len(selected),
        "passed_controls": passed,
        "resolved_capability": resolution.as_dict(),
        "unknown_fields": [item.as_dict() for item in resolution.unknown_fields],
        "findings": displayed,
    }
    return document, resolution, inspected


def gate_exit(findings: list[dict[str, Any]], fail_on: str) -> int:
    if fail_on == "none":
        return 0
    threshold = SEVERITY_ORDER[fail_on]
    return 1 if any(SEVERITY_ORDER[item["severity"]] >= threshold for item in findings) else 0
