"""Deterministic human and machine rendering."""

from __future__ import annotations

import json
import textwrap
from typing import Any


SEPARATOR = "─" * 72
WIDTH = 72


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def colorize_pretty(value: str) -> str:
    """Apply restrained colour only after deterministic plain rendering."""
    cyan, red, yellow, green, blue, dim, reset = (
        "\x1b[36m", "\x1b[31m", "\x1b[33m", "\x1b[32m", "\x1b[34m", "\x1b[2m", "\x1b[0m"
    )
    result: list[str] = []
    headings = {"INSPECTION", "POSTURE", "RESOLVED AGENT CAPABILITY", "FINDINGS", "RESULT"}
    for line in value.splitlines():
        if line in headings:
            line = f"{cyan}{line}{reset}"
        elif line == SEPARATOR:
            line = f"{dim}{line}{reset}"
        elif line.startswith(("Verdict: FAIL", "Posture: FAIL", "CRITICAL ", "HIGH ")):
            line = f"{red}{line}{reset}"
        elif line.startswith(("Verdict: WARN", "Posture: WARN", "MEDIUM ")):
            line = f"{yellow}{line}{reset}"
        elif line.startswith(("Verdict: PASS", "Posture: PASS")):
            line = f"{green}{line}{reset}"
        elif line.startswith("LOW "):
            line = f"{blue}{line}{reset}"
        elif line.startswith("Process exit code:"):
            line = f"{dim}{line}{reset}"
        result.append(line)
    return "\n".join(result) + "\n"


def _wrapped(label: str, value: str, subsequent: str = "  ") -> list[str]:
    prefix = f"{label}: "
    return textwrap.wrap(
        value,
        width=WIDTH,
        initial_indent=prefix,
        subsequent_indent=" " * len(prefix) if subsequent == "  " else subsequent,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [prefix.rstrip()]


def quiet_check(document: dict[str, Any], exit_code: int) -> str:
    counts = document["counts"]
    return (
        f"{document['posture']} critical={counts['critical']} high={counts['high']} "
        f"medium={counts['medium']} low={counts['low']} info={counts['info']} exit={exit_code}\n"
    )


def pretty_check(document: dict[str, Any], resolution: Any, inspected: list[str], exit_code: int, verbose: bool = False) -> str:
    baseline = document["baseline"]
    lines = [
        "Kaapi ☕",
        "check",
        f"Subject: {document['subject']}",
        f"Runtime: {document['runtime']}",
        f"Baseline: {baseline['name']} {baseline['version']} ({baseline['control_count']} rules)",
        "",
        SEPARATOR,
        "INSPECTION",
        SEPARATOR,
        "→ Configuration loaded",
        "→ Permissions resolved",
        "→ Sandbox checked",
        "→ Hooks checked",
        "→ MCP checked",
        "→ Network checked",
        "→ Baseline evaluated",
    ]
    if verbose:
        if inspected:
            lines.extend(f"Inspected: {path}" for path in inspected)
        else:
            lines.append("Inspected: no settings files detected")
    counts = document["counts"]
    lines.extend([
        "",
        SEPARATOR,
        "POSTURE",
        SEPARATOR,
        f"Verdict: {document['posture']}",
        f"Critical: {counts['critical']}",
        f"High: {counts['high']}",
        f"Medium: {counts['medium']}",
        f"Low: {counts['low']}",
        f"Info: {counts['info']}",
        f"Not evaluated: {document['fields_not_evaluated']}",
        f"Controls evaluated: {document['controls_evaluated']}",
        f"Passed controls: {len(document['passed_controls'])}",
        "",
        SEPARATOR,
        "RESOLVED AGENT CAPABILITY",
        SEPARATOR,
    ])
    for statement in resolution.capability_lines:
        lines.extend(textwrap.wrap(statement, WIDTH, subsequent_indent="  ", break_long_words=False, break_on_hyphens=False) or [""])
    lines.extend(["", SEPARATOR, "FINDINGS", SEPARATOR])
    if not document["findings"]:
        lines.append("No findings at the selected display severity.")
    for finding in document["findings"]:
        lines.extend(["", SEPARATOR, f"{finding['severity'].upper()}  {finding['id']}  {finding['title']}"])
        evidence = finding["evidence"]
        for index, item in enumerate(evidence, 1):
            label = "Evidence" if len(evidence) == 1 else f"Evidence {index}"
            location = item["source"] + (f":{item['line']}" if item["line"] is not None else "")
            lines.extend(_wrapped(label, f"{location} {item['path']} — {item['detail']}"))
        lines.extend(_wrapped("Observed", finding["observed"]))
        lines.extend(_wrapped("Inference", finding["inference"]))
        lines.extend(_wrapped("Why severity", finding["why_severity"]))
        lines.extend(_wrapped("Confidence", finding["confidence"]))
        lines.extend(_wrapped("Remediation", finding["remediation"]))
        labels = " · ".join(source["label"] for source in finding["sources"])
        lines.extend(_wrapped("Resource", labels))
    next_action = {
        "PASS": "Keep the configuration under version control and re-check changes.",
        "WARN": "Review fields or surfaces that Kaapi could not fully evaluate.",
        "FAIL": "Address critical and high findings before unattended use.",
    }[document["posture"]]
    lines.extend([
        "",
        SEPARATOR,
        "RESULT",
        SEPARATOR,
        f"Posture: {document['posture']}",
        f"Severity summary: critical={counts['critical']} high={counts['high']} medium={counts['medium']} low={counts['low']} info={counts['info']}",
        f"Next action: {next_action}",
        f"Process exit code: {exit_code}",
    ])
    return "\n".join(lines) + "\n"
