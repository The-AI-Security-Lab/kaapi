"""Kaapi P0 command-line interface."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

from . import __version__
from .analyze import analyze, load_observed
from .baseline import SEVERITY_ORDER, control_map, load_baseline
from .model import ConfigError
from .render import colorize_pretty, json_text, pretty_check, quiet_check
from .snapshot import SnapshotError, compare, load_snapshot, make_snapshot


class KaapiArgumentParser(argparse.ArgumentParser):
    pass


def _version_text() -> str:
    baseline = load_baseline()
    return (
        f"kaapi {__version__}\n"
        f"baseline {baseline['name']} {baseline['version']} ({len(baseline['controls'])} controls)\n"
        f"python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}\n"
    )


def _parser() -> KaapiArgumentParser:
    parser = KaapiArgumentParser(
        prog="kaapi",
        description="Deterministic local-first Claude Code security posture analysis (P0).",
        epilog="Example: kaapi check fixtures/loose/settings.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=_version_text().rstrip(), help="show Kaapi, baseline, and Python versions")
    sub = parser.add_subparsers(dest="command", title="commands")

    doctor = sub.add_parser("doctor", help="triage observed local configuration", description="Read-only local environment triage.", epilog="Example: kaapi doctor --env-root fixtures/env")
    _runtime(doctor)
    _format(doctor)
    _output(doctor)
    _verbosity(doctor)
    doctor.add_argument("--no-color", action="store_true", help="disable terminal colour")
    doctor.add_argument("--env-root", metavar="DIR", help="remap discovery to a staged environment root")
    doctor.add_argument("--invocation", metavar="STRING", help="observe supported invocation-level bypass flags")

    check = sub.add_parser("check", help="analyse Claude Code settings", description="Analyse observed Claude Code configuration.", epilog="Example: kaapi check fixtures/hardened/settings.json --format json")
    check.add_argument("subject", nargs="?", help="claude, claude-code, or a settings JSON path")
    check.add_argument("--path", metavar="FILE", help="explicit settings path instead of the positional subject")
    _runtime(check)
    _format(check)
    _output(check)
    _verbosity(check)
    check.add_argument("--no-color", action="store_true", help="disable terminal colour")
    check.add_argument("--env-root", metavar="DIR", help="remap discovered local settings paths")
    check.add_argument("--invocation", metavar="STRING", help="observe supported invocation-level bypass flags")
    check.add_argument("--severity", choices=list(SEVERITY_ORDER), default="info", help="minimum finding severity to display")
    check.add_argument("--fail-on", choices=["none", *SEVERITY_ORDER], default="high", help="minimum severity that exits 1")
    check.add_argument("--only", action="append", metavar="IDS", help="evaluate comma-separated control IDs; repeatable")
    check.add_argument("--ignore", action="append", metavar="IDS", help="ignore comma-separated control IDs; repeatable")

    baseline = sub.add_parser("baseline", help="write a secret-safe capability snapshot", description="Create a versioned, secret-safe configured-capability snapshot.", epilog="Example: kaapi baseline settings.json -o before.json")
    baseline.add_argument("settings_path", nargs="?", help="Claude Code settings JSON path")
    baseline.add_argument("--path", metavar="FILE", help="explicit settings path alternative")
    _runtime(baseline)
    baseline.add_argument("--format", choices=["json"], default="json", help="snapshot output format (JSON)")
    _output(baseline)
    _verbosity(baseline)
    baseline.add_argument("--no-color", action="store_true", help="disable terminal colour (snapshots are always plain)")

    verify = sub.add_parser("verify", help="compare settings with a snapshot", description="Compare resolved/configured capability with a compatible snapshot.", epilog="Example: kaapi verify settings.json --baseline before.json --expect-reduction")
    verify.add_argument("settings_path", nargs="?", help="current Claude Code settings JSON path")
    verify.add_argument("--path", metavar="FILE", help="explicit settings path alternative")
    verify.add_argument("--baseline", required=True, metavar="SNAPSHOT", help="baseline snapshot JSON path")
    verify.add_argument("--expect-reduction", action="store_true", help="exit 1 unless current capability is a strict subset")
    _runtime(verify)
    _format(verify)
    _output(verify)
    _verbosity(verify)
    verify.add_argument("--no-color", action="store_true", help="disable terminal colour")

    rules = sub.add_parser("rules", help="list or inspect shipped controls", description="Show declarative P0 baseline controls and provenance.", epilog="Example: kaapi rules AGENT-APRV-001")
    rules.add_argument("rule_id", nargs="?", help="specific control ID")
    _format(rules)
    _output(rules)
    rules.add_argument("--no-color", action="store_true", help="disable terminal colour")

    version = sub.add_parser("version", help="show version and baseline metadata", description="Show Kaapi, loaded baseline, and Python versions.", epilog="Example: kaapi version")
    _format(version)
    _output(version)
    version.add_argument("--no-color", action="store_true", help="disable terminal colour")
    return parser


def _runtime(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--runtime", choices=["claude-code", "codex", "auto"], default="auto", help="analysis runtime; codex is reserved in P0")


def _format(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=["pretty", "json"], default="pretty", help="output format")


def _output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", "-o", metavar="FILE", help="write output to a file and emit no stdout")


def _verbosity(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--quiet", "-q", action="store_true", help="emit one concise undecorated result line")
    group.add_argument("--verbose", "-v", action="store_true", help="include inspected paths and diagnostics")


def _csv_ids(values: list[str] | None) -> set[str]:
    result: set[str] = set()
    for value in values or []:
        for item in value.split(","):
            item = item.strip()
            if item:
                result.add(item)
    return result


def _validate_runtime(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if getattr(args, "runtime", "auto") == "codex":
        parser.error("runtime 'codex' is reserved and unavailable in P0")


def _settings_arg(args: argparse.Namespace, positional_name: str, parser: argparse.ArgumentParser, required: bool = False) -> str | None:
    positional = getattr(args, positional_name, None)
    option = getattr(args, "path", None)
    if positional and option:
        parser.error("positional settings input and --path cannot be used together")
    value = option or positional
    if value in {"codex", "cursor", "gemini", "github-copilot"}:
        parser.error(f"analysis subject '{value}' is unavailable in P0")
    if required and not value:
        parser.error("a settings path is required")
    return value


def _gate_from_counts(counts: dict[str, int], fail_on: str) -> int:
    if fail_on == "none":
        return 0
    threshold = SEVERITY_ORDER[fail_on]
    return 1 if any(count and SEVERITY_ORDER[level] >= threshold for level, count in counts.items()) else 0


def _atomic_write(path: str, value: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False) as handle:
            handle.write(value)
            temporary = handle.name
        os.replace(temporary, target)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def _refuse_output_collision(output: str | None, inputs: list[str | None], parser: argparse.ArgumentParser) -> None:
    if not output:
        return
    target = Path(output).resolve(strict=False)
    for item in inputs:
        if item is not None and target == Path(item).resolve(strict=False):
            parser.error("--output must not overwrite an inspected input")


def _emit(value: str, output: str | None) -> None:
    if output:
        _atomic_write(output, value)
    else:
        sys.stdout.write(value)


def _use_color(args: argparse.Namespace) -> bool:
    return bool(
        not getattr(args, "no_color", False)
        and "NO_COLOR" not in os.environ
        and not getattr(args, "output", None)
        and getattr(args, "format", "pretty") == "pretty"
        and not getattr(args, "quiet", False)
        and sys.stdout.isatty()
    )


def _run_check(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    _validate_runtime(args, parser)
    subject = _settings_arg(args, "subject", parser) or "claude-code"
    known = set(control_map())
    only, ignore = _csv_ids(args.only), _csv_ids(args.ignore)
    unknown_ids = (only | ignore) - known
    if unknown_ids:
        parser.error("unknown control ID(s): " + ", ".join(sorted(unknown_ids)))
    document, resolution, inspected = analyze(
        subject,
        env_root=args.env_root,
        invocation=args.invocation,
        only=only or None,
        ignore=ignore,
        severity=args.severity,
    )
    _refuse_output_collision(args.output, inspected, parser)
    exit_code = _gate_from_counts(document["counts"], args.fail_on)
    if args.format == "json":
        value = json_text(document)
    elif args.quiet:
        value = quiet_check(document, exit_code)
    else:
        value = pretty_check(document, resolution, inspected, exit_code, args.verbose)
        if _use_color(args):
            value = colorize_pretty(value)
    _emit(value, args.output)
    return exit_code


def _run_baseline(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    _validate_runtime(args, parser)
    settings = _settings_arg(args, "settings_path", parser, required=True)
    _refuse_output_collision(args.output, [settings], parser)
    document, _, _ = analyze(settings)
    merged, _, _ = load_observed(settings)
    value = json_text(make_snapshot(document, merged.data))
    _emit(value, args.output)
    return 0


def _verify_pretty(delta: dict[str, Any], exit_code: int) -> str:
    verdict = "PASS" if (exit_code == 0) else "FAIL"
    statement = "resolved/configured capability reduced" if delta["strict_reduction"] else "resolved/configured capability was not strictly reduced"
    lines = [
        "Kaapi verify",
        f"{verdict}: {statement}",
        f"Removed capabilities: {len(delta['removed_capabilities'])}",
        f"Added capabilities: {len(delta['added_capabilities'])}",
    ]
    lines.extend(f"- removed: {item}" for item in delta["removed_capabilities"])
    lines.extend(f"- added: {item}" for item in delta["added_capabilities"])
    lines.append(f"Process exit code: {exit_code}")
    return "\n".join(lines) + "\n"


def _run_verify(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    _validate_runtime(args, parser)
    settings = _settings_arg(args, "settings_path", parser, required=True)
    snapshot = load_snapshot(args.baseline)
    document, _, inspected = analyze(settings)
    _refuse_output_collision(args.output, [*inspected, args.baseline], parser)
    delta = compare(snapshot, document["resolved_capability"]["capabilities"])
    exit_code = 1 if args.expect_reduction and not delta["strict_reduction"] else 0
    report = {
        "schema_version": "1",
        "runtime": "claude-code",
        "subject": settings,
        "strict_reduction": delta["strict_reduction"],
        "removed_capabilities": delta["removed_capabilities"],
        "added_capabilities": delta["added_capabilities"],
        "unchanged_capability_count": delta["unchanged_capability_count"],
        "assertion": "expect-reduction" if args.expect_reduction else "report-only",
        "process_exit_code": exit_code,
    }
    if args.format == "json":
        value = json_text(report)
    elif args.quiet:
        value = f"{'PASS' if exit_code == 0 else 'FAIL'} strict_reduction={str(delta['strict_reduction']).lower()} exit={exit_code}\n"
    else:
        value = _verify_pretty(delta, exit_code)
        if args.verbose:
            value += "".join(f"Inspected: {path}\n" for path in inspected)
        if _use_color(args):
            value = colorize_pretty(value)
    _emit(value, args.output)
    return exit_code


def _doctor_mcp_count(env_root: str | None) -> tuple[int, str | None]:
    path = (Path(env_root) / "project/.mcp.json") if env_root else (Path.cwd() / ".mcp.json")
    if not path.is_file():
        return 0, None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return 0, str(path)
    if not isinstance(value, dict):
        return 0, str(path)
    servers = value.get("mcpServers", value)
    return (len(servers) if isinstance(servers, dict) else 0), str(path)


def _run_doctor(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    _validate_runtime(args, parser)
    document, _, inspected = analyze("claude-code", env_root=args.env_root, invocation=args.invocation)
    root = Path(args.env_root) if args.env_root else None
    codex_path = (root / "home/.codex/config.toml") if root else (Path.home() / ".codex/config.toml")
    mcp_count, mcp_path = _doctor_mcp_count(args.env_root)
    _refuse_output_collision(args.output, [*inspected, mcp_path, str(codex_path)], parser)
    report = {
        "schema_version": "1",
        "runtime": "claude-code",
        "claude_code_detected": bool(inspected),
        "codex_detected": codex_path.is_file(),
        "observed_project_mcp_server_count": mcp_count,
        "posture": document["posture"],
        "counts": {key: document["counts"][key] for key in ("critical", "high", "medium")},
        "passed_controls": len(document["passed_controls"]),
        "inspected_paths": sorted(inspected + ([mcp_path] if mcp_path else [])) if args.verbose else [],
    }
    if args.format == "json":
        value = json_text(report)
    elif args.quiet:
        value = f"{report['posture']} claude={str(report['claude_code_detected']).lower()} codex={str(report['codex_detected']).lower()} mcp={mcp_count} exit=0\n"
    else:
        lines = [
            "Kaapi doctor",
            f"Claude Code detected: {'yes' if report['claude_code_detected'] else 'no'}",
            f"Codex detected: {'yes' if report['codex_detected'] else 'no'} (presence only; not analysed)",
            f"Observed project MCP servers: {mcp_count}",
            f"Posture: {report['posture']}",
            f"Critical: {report['counts']['critical']}",
            f"High: {report['counts']['high']}",
            f"Medium: {report['counts']['medium']}",
            f"Passed controls: {report['passed_controls']}",
        ]
        if args.verbose:
            lines.extend(f"Inspected: {path}" for path in report["inspected_paths"])
        lines.append("Process exit code: 0 (report only)")
        value = "\n".join(lines) + "\n"
        if _use_color(args):
            value = colorize_pretty(value)
    _emit(value, args.output)
    return 0


def _run_rules(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    baseline = load_baseline()
    controls = baseline["controls"]
    if args.rule_id:
        matches = [control for control in controls if control["id"] == args.rule_id]
        if not matches:
            parser.error(f"unknown control ID: {args.rule_id}")
        selected: Any = matches[0]
    else:
        selected = [{"id": item["id"], "title": item["title"], "severity": item["severity"]} for item in controls]
    if args.format == "json":
        value = json_text(selected)
    elif isinstance(selected, list):
        value = "\n".join(f"{item['id']}  {item['severity']}  {item['title']}" for item in selected) + "\n"
    else:
        lines = [
            f"{selected['id']} — {selected['title']}",
            f"Severity: {selected['severity']}",
            f"Layer: {selected['layer']}",
            f"Rationale: {selected['rationale']}",
            f"Support confidence: {selected['support_confidence']}",
            f"Last verified: {selected['last_verified']}",
            f"Remediation: {selected['remediation']}",
            "Provenance:",
        ]
        lines.extend(f"- {source['label']}: {source['url']} (accessed {source['accessed']})" for source in selected["sources"])
        value = "\n".join(lines) + "\n"
    _emit(value, args.output)
    return 0


def _run_version(args: argparse.Namespace) -> int:
    if args.format == "json":
        baseline = load_baseline()
        value = json_text({
            "kaapi_version": __version__,
            "baseline_name": baseline["name"],
            "baseline_version": baseline["version"],
            "control_count": len(baseline["controls"]),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        })
    else:
        value = _version_text()
    _emit(value, args.output)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args_list = list(argv) if argv is not None else None
    if args_list == [] or (args_list is None and len(sys.argv) == 1):
        parser.print_help()
        return 0
    try:
        args = parser.parse_args(args_list)
        if args.command is None:
            parser.print_help()
            return 0
        if args.command == "check":
            return _run_check(args, parser)
        if args.command == "baseline":
            return _run_baseline(args, parser)
        if args.command == "verify":
            return _run_verify(args, parser)
        if args.command == "doctor":
            return _run_doctor(args, parser)
        if args.command == "rules":
            return _run_rules(args, parser)
        if args.command == "version":
            return _run_version(args)
        parser.error("unsupported command")
    except ConfigError as exc:
        print(exc.safe_message(), file=sys.stderr)
        return 3
    except SnapshotError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("kaapi interrupted", file=sys.stderr)
        return 4
    except SystemExit:
        raise
    except Exception as exc:
        print(f"kaapi internal error: {type(exc).__name__}", file=sys.stderr)
        return 4
    return 4
