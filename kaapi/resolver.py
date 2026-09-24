"""Resolve observed Claude Code settings into safe configured capabilities."""

from __future__ import annotations

import re
import shlex
from typing import Any

from .model import Evidence, PermissionRule, Resolution
from .parser import MergedSettings


RULE_RE = re.compile(r"^([A-Za-z0-9_*.-]+)(?:\((.*)\))?$")
READ_FAMILY = {"Read", "Grep", "Glob", "LSP"}
EDIT_FAMILY = {"Edit", "Write", "NotebookEdit"}


def _evidence(merged: MergedSettings, path: str, detail: str, all_layers: bool = False) -> list[Evidence]:
    return [Evidence(layer.source, line, path, detail) for layer, line in merged.evidence_points(path, all_layers)]


def _last_evidence(merged: MergedSettings, path: str, detail: str) -> Evidence | None:
    records = _evidence(merged, path, detail)
    return records[0] if records else None


def _permission_rules(merged: MergedSettings) -> list[PermissionRule]:
    managed_only = bool(merged.data.get("allowManagedPermissionRulesOnly"))
    rules: list[PermissionRule] = []
    seen: set[tuple[str, str]] = set()
    for layer in merged.layers:
        if managed_only and not layer.managed:
            continue
        permissions = layer.data.get("permissions")
        if not isinstance(permissions, dict):
            continue
        for rule_class in ("deny", "ask", "allow"):
            values = permissions.get(rule_class, [])
            if not isinstance(values, list):
                continue
            for index, raw in enumerate(values):
                marker = (rule_class, raw)
                if marker in seen:
                    continue
                seen.add(marker)
                match = RULE_RE.fullmatch(raw)
                if match is None:
                    # Vendor accepts evolving rule syntax. A syntactically opaque
                    # string stays represented but cannot produce a broad grant.
                    tool, specifier = raw, None
                else:
                    tool, specifier = match.group(1), match.group(2)
                path = f"$.permissions.{rule_class}[{index}]"
                rules.append(PermissionRule(rule_class, raw, tool, specifier, layer.source, path, layer.lines.get(path), layer.kind))
    return rules


def _rule_targets(rule: PermissionRule, target: str) -> bool:
    if rule.tool == "*":
        return rule.rule_class in {"deny", "ask"}
    if target in READ_FAMILY and rule.tool == "Read":
        return True
    if target in EDIT_FAMILY and rule.tool == "Edit":
        return True
    if target in {"Edit", "Write"} and rule.rule_class == "deny" and rule.tool == "Read":
        return True
    if target in {"Bash", "Monitor"} and rule.tool == "Bash":
        return True
    return rule.tool == target


def _is_broad(rule: PermissionRule) -> bool:
    return rule.specifier is None or rule.specifier == "*"


def _base_state(tool: str, mode: str | None) -> str:
    if tool in READ_FAMILY:
        return "unprompted"
    if mode == "acceptEdits" and tool in EDIT_FAMILY:
        return "unprompted"
    if mode == "plan" and tool in EDIT_FAMILY:
        return "denied"
    if mode == "auto":
        return "classifier-reviewed"
    if mode == "dontAsk":
        return "denied"
    if mode == "bypassPermissions":
        return "unprompted"
    return "approval-required"


def _tool_state(tool: str, mode: str | None, rules: list[PermissionRule]) -> tuple[str, dict[str, int]]:
    matching = [rule for rule in rules if _rule_targets(rule, tool)]
    scoped = {name: sum(1 for rule in matching if rule.rule_class == name and not _is_broad(rule)) for name in ("deny", "ask", "allow")}
    broad = {name: any(rule.rule_class == name and _is_broad(rule) for rule in matching) for name in ("deny", "ask", "allow")}
    if broad["deny"]:
        return "denied", scoped
    if mode == "bypassPermissions":
        # Current vendor behavior: allow has no effect; deny remains effective.
        return _base_state(tool, mode), scoped
    if broad["ask"]:
        return ("denied" if mode == "dontAsk" else "approval-required"), scoped
    if broad["allow"]:
        return "unprompted", scoped
    return _base_state(tool, mode), scoped


def _safe_matcher(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return "<any>"
    printable = "".join(char if char.isprintable() else "?" for char in value)
    return printable[:48] + ("…" if len(printable) > 48 else "")


def _resolve_hooks(merged: MergedSettings) -> list[dict[str, Any]]:
    hooks = merged.data.get("hooks", {})
    result: list[dict[str, Any]] = []
    if not isinstance(hooks, dict):
        return result
    for event in sorted(hooks):
        entries = hooks[event]
        if not isinstance(entries, list):
            continue
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            handlers = entry.get("hooks", [])
            command_count = 0
            if isinstance(handlers, list):
                command_count = sum(
                    1 for handler in handlers
                    if isinstance(handler, dict) and handler.get("type", "command") == "command" and "command" in handler
                )
            if command_count:
                path = f"$.hooks.{event}[{index}]"
                point = merged.evidence_points(path)
                source = point[0][0].source if point else "<merged settings>"
                line = point[0][1] if point else None
                result.append({
                    "event": event,
                    "matcher": _safe_matcher(entry.get("matcher")),
                    "command_count": command_count,
                    "command": "<present>",
                    "source": source,
                    "line": line,
                    "path": path,
                })
    return result


def _resolve_mcp(merged: MergedSettings, rules: list[PermissionRule]) -> dict[str, Any]:
    definitions = merged.data.get("mcpServers", {})
    names = sorted(definitions) if isinstance(definitions, dict) else []
    disabled = set(merged.data.get("disabledMcpjsonServers", [])) | set(merged.data.get("deniedMcpServers", []))
    enabled = set(merged.data.get("enabledMcpjsonServers", []))
    allowed = set(merged.data.get("allowedMcpServers", []))
    enable_all = bool(merged.data.get("enableAllProjectMcpServers"))
    selected: list[str] = []
    for name in names:
        if name in disabled:
            continue
        if allowed and name not in allowed:
            continue
        # In-document definitions are observed configured servers. Project-MCP
        # toggles refine selection when present but never imply a connection.
        if enabled and not enable_all and name not in enabled:
            continue
        selected.append(name)
    server_metadata = []
    for name in selected:
        config = definitions[name]
        server_metadata.append({
            "name": name,
            "command": "<present>" if "command" in config else None,
            "arguments": "<present>" if "args" in config else None,
            "environment": "<present>" if "env" in config else None,
            "url": "<present>" if "url" in config else None,
        })
    mcp_allow_rules = sum(
        1 for rule in rules
        if rule.rule_class == "allow" and rule.tool.startswith("mcp__") and rule.tool != "mcp__*"
    )
    mcp_ask_rules = sum(1 for rule in rules if rule.rule_class == "ask" and rule.tool.startswith("mcp__"))
    mcp_deny_rules = sum(1 for rule in rules if rule.rule_class == "deny" and rule.tool.startswith("mcp__"))
    return {
        "configured_server_count": len(selected),
        "server_names": selected,
        "servers": server_metadata,
        "tool_approval": {
            "server_specific_allow_rules": mcp_allow_rules,
            "ask_rules": mcp_ask_rules,
            "deny_rules": mcp_deny_rules,
            "configured_servers_do_not_imply_approval": True,
        },
        "managed_only": bool(merged.data.get("allowManagedMcpServersOnly")),
    }


def _invocation_bypass(invocation: str | None) -> str | None:
    if not invocation:
        return None
    try:
        tokens = shlex.split(invocation, posix=True)
    except ValueError:
        # It is an observed string but not a safely parseable supported flag source.
        return None
    for index, token in enumerate(tokens):
        if token == "--dangerously-skip-permissions":
            return "--dangerously-skip-permissions"
        if token == "--permission-mode=bypassPermissions":
            return "--permission-mode=bypassPermissions"
        if token == "--permission-mode" and index + 1 < len(tokens) and tokens[index + 1] == "bypassPermissions":
            return "--permission-mode bypassPermissions"
    return None


def resolve(merged: MergedSettings, invocation: str | None = None) -> Resolution:
    data = merged.data
    permissions = data.get("permissions", {}) if isinstance(data.get("permissions", {}), dict) else {}
    raw_mode = permissions.get("defaultMode")
    configured_mode = "default" if raw_mode == "manual" else raw_mode
    bypass_locked = permissions.get("disableBypassPermissionsMode") == "disable"
    auto_locked = permissions.get("disableAutoMode") == "disable"
    if configured_mode == "bypassPermissions" and bypass_locked:
        active_mode = None
    elif configured_mode == "auto" and auto_locked:
        active_mode = None
    else:
        active_mode = configured_mode
    mode_uncertain = configured_mode is None or active_mode is None
    mode_source = _last_evidence(merged, "$.permissions.defaultMode", "configured permission mode")

    rules = _permission_rules(merged)
    counts = {name: sum(rule.rule_class == name for rule in rules) for name in ("allow", "ask", "deny")}
    states: dict[str, str] = {}
    scoped: dict[str, dict[str, int]] = {}
    for tool in ("Bash", "Monitor", "Read", "Grep", "Glob", "LSP", "Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch"):
        states[tool], scoped[tool] = _tool_state(tool, active_mode, rules)

    bypasses: list[dict[str, Any]] = []
    if active_mode == "bypassPermissions":
        evidence = mode_source
        bypasses.append({
            "mechanism": "configured permission mode",
            "source_kind": next((layer.kind for layer in merged.layers if evidence and layer.source == evidence.source), "settings"),
            "source": evidence.source if evidence else "<settings>",
            "path": "$.permissions.defaultMode",
            "line": evidence.line if evidence else None,
        })
    invocation_mechanism = _invocation_bypass(invocation)
    if invocation_mechanism is not None and not bypass_locked:
        bypasses.append({
            "mechanism": invocation_mechanism,
            "source_kind": "invocation",
            "source": "<observed invocation>",
            "path": "$.invocation.permission_bypass",
            "line": None,
        })
        # Invocation bypass changes mode semantics but still preserves denies.
        for tool in states:
            states[tool], scoped[tool] = _tool_state(tool, "bypassPermissions", rules)

    sandbox_data = data.get("sandbox", {}) if isinstance(data.get("sandbox", {}), dict) else {}
    sandbox_enabled = sandbox_data.get("enabled") is True
    auto_allow_sandboxed_bash = sandbox_data.get("autoAllowBashIfSandboxed", True) is not False
    escape_allowed = sandbox_data.get("allowUnsandboxedCommands", True) is not False
    exclusions = sandbox_data.get("excludedCommands", [])
    filesystem = sandbox_data.get("filesystem", {}) if isinstance(sandbox_data.get("filesystem", {}), dict) else {}
    network_data = sandbox_data.get("network", {}) if isinstance(sandbox_data.get("network", {}), dict) else {}
    sandbox = {
        "enabled": sandbox_enabled,
        "configured_only": sandbox_enabled,
        "unsandboxed_retry_allowed": escape_allowed,
        "excluded_command_count": len(exclusions) if isinstance(exclusions, list) else 0,
        "weaker_nested_isolation": sandbox_data.get("enableWeakerNestedSandbox") is True,
        "auto_allow_bash_if_sandboxed": auto_allow_sandboxed_bash,
        "filesystem": {
            "allow_write_count": len(filesystem.get("allowWrite", [])),
            "deny_write_count": len(filesystem.get("denyWrite", [])),
            "deny_read_count": len(filesystem.get("denyRead", [])),
            "allow_read_count": len(filesystem.get("allowRead", [])),
            "managed_read_paths_only": filesystem.get("allowManagedReadPathsOnly") is True,
        },
    }

    allowed_domains = network_data.get("allowedDomains", [])
    denied_domains = network_data.get("deniedDomains", [])
    strict_domain_boundary = bool(sandbox_enabled and "*" in denied_domains)
    webfetch_available = states["WebFetch"] != "denied"
    websearch_available = states["WebSearch"] != "denied"
    shell_available = states["Bash"] != "denied"
    exceptions = {
        "allowed_domain_count": len(allowed_domains),
        "denied_domain_count": len(denied_domains),
        "unix_socket_count": len(network_data.get("allowUnixSockets", [])),
        "all_unix_sockets": network_data.get("allowAllUnixSockets") is True,
        "local_binding": network_data.get("allowLocalBinding") is True,
        "mach_lookup": network_data.get("allowMachLookup") is True,
        "http_proxy_configured": "httpProxyPort" in network_data,
        "socks_proxy_configured": "socksProxyPort" in network_data,
    }
    outbound_possible = webfetch_available or websearch_available or shell_available
    network = {
        "webfetch_permission": states["WebFetch"],
        "websearch_permission": states["WebSearch"],
        "shell_network_permission": states["Bash"],
        "sandbox_proxy_configured": sandbox_enabled,
        "strict_destination_boundary": strict_domain_boundary,
        "outbound_configured_potential": outbound_possible,
        "exceptions": exceptions,
    }

    hooks = _resolve_hooks(merged)
    mcp = _resolve_mcp(merged, rules)

    sandboxed_bash_unprompted = sandbox_enabled and auto_allow_sandboxed_bash and states["Bash"] != "denied"

    capabilities: set[str] = set()
    for tool, state in states.items():
        if state != "denied":
            state_label = f"residual-{state}" if scoped[tool]["deny"] or scoped[tool]["ask"] else state
            capabilities.add(f"tool.{tool}:{state_label}")
        if scoped[tool]["allow"] and active_mode != "bypassPermissions":
            capabilities.add(f"tool.{tool}:scoped-unprompted")
        if scoped[tool]["ask"] and active_mode not in {"dontAsk", "bypassPermissions"} and state != "denied":
            capabilities.add(f"tool.{tool}:scoped-approval")
    if active_mode in {"default", "dontAsk", "acceptEdits"} or active_mode is None:
        capabilities.add("shell.read-only-subset:unprompted")
    if sandboxed_bash_unprompted:
        capabilities.add("shell.sandboxed-subset:unprompted")
    if active_mode == "acceptEdits":
        capabilities.add("shell.in-scope-filesystem-subset:unprompted")
    if active_mode == "plan":
        capabilities.add("shell.exploratory:permission-or-classifier-flow")
    if sandbox_enabled:
        if escape_allowed:
            capabilities.add("sandbox.unsandboxed-retry:available")
        if sandbox["excluded_command_count"]:
            capabilities.add("sandbox.excluded-commands:outside-boundary")
    else:
        capabilities.add("shell.subprocess:without-claude-sandbox")
    if not strict_domain_boundary and outbound_possible:
        capabilities.add("network.destination:unbounded-configured-potential")
    if exceptions["all_unix_sockets"] or exceptions["unix_socket_count"]:
        capabilities.add("network.unix-socket-exception:configured")
    if exceptions["local_binding"]:
        capabilities.add("network.local-binding:configured")
    if exceptions["mach_lookup"]:
        capabilities.add("network.mach-lookup:configured")
    if hooks:
        capabilities.add("hooks.command-surface:configured")
    if mcp["configured_server_count"]:
        capabilities.add("mcp.server-surface:configured")
    if bypasses:
        capabilities.add("permissions.bypass:observed")

    capability_lines = []
    mode_label = configured_mode if configured_mode is not None else "not observed"
    capability_lines.append(f"Permission mode: {mode_label}; allow/ask/deny rules: {counts['allow']}/{counts['ask']}/{counts['deny']}")
    additional_directory_count = len(permissions.get("additionalDirectories", []))
    if additional_directory_count:
        capability_lines.append(f"Configured path scope includes {additional_directory_count} additional director{'y' if additional_directory_count == 1 else 'ies'} (values redacted)")
    if any(sum(values.values()) for values in scoped.values()):
        capability_lines.append("Scoped permission rules preserve residual tool capability outside matching inputs")
    if mode_uncertain:
        capability_lines.append("Permission mode effectiveness is uncertain because the session mode is not observed or is locked out")
    if bypasses:
        capability_lines.append("[!] Permission bypass is observed; applicable deny rules remain effective")
    elif bypass_locked:
        capability_lines.append("Permission bypass mode is configured as disabled")
    capability_lines.extend([
        f"[!] General shell commands: {states['Bash']}" if states["Bash"] != "denied" else "General shell commands: denied",
        f"File reads: {states['Read']}",
        f"[!] File writes: {states['Write']}" if states["Write"] in {"unprompted", "classifier-reviewed"} else f"File writes: {states['Write']}",
        f"WebFetch: {states['WebFetch']}; WebSearch: {states['WebSearch']}",
        ("Shell subprocess sandbox: configured (runtime availability not tested)" if sandbox_enabled else "[!] Shell subprocess sandbox: disabled"),
        ("Sandbox network destination boundary: strict configured deny" if strict_domain_boundary else "[!] Sandbox network destination boundary: not strict"),
        f"MCP servers configured: {mcp['configured_server_count']}; definitions do not imply tool approval",
        f"Command hooks configured: {sum(item['command_count'] for item in hooks)} across {len(hooks)} matcher entries",
    ])
    if sandboxed_bash_unprompted:
        capability_lines.insert(4, "[!] Sandboxed shell commands: unprompted; commands that cannot be sandboxed use the regular permission flow")

    facts = {
        "runtime": "claude-code",
        "tool_states": states,
        "scoped_rule_counts": scoped,
        "rules": rules,
        "additional_directory_count": additional_directory_count,
        "workspace_trust_observed": False,
        "invocation_bypass_locked": invocation_mechanism is not None and bypass_locked,
        "sandboxed_bash_unprompted": sandboxed_bash_unprompted,
        "shell_rule_policy_supported": True,
        "bash_allow_rule_patterns": sorted(
            rule.specifier
            for rule in rules
            if rule.rule_class == "allow"
            and rule.tool == "Bash"
            and rule.specifier not in {None, "*"}
        ),
        "bash_broad_allow_count": sum(
            rule.rule_class == "allow"
            and rule.tool in {"Bash", "*"}
            and rule.specifier in {None, "*"}
            for rule in rules
        ),
        "mcp_server_names": list(mcp["server_names"]),
        "mcp_managed_only": mcp["managed_only"],
        "writable_path_patterns": list(filesystem.get("allowWrite", [])),
        "denied_read_patterns": list(filesystem.get("denyRead", [])),
        "denied_write_patterns": list(filesystem.get("denyWrite", [])),
        "allowed_domains": list(allowed_domains),
        "denied_domains": list(denied_domains),
        "hook_events": sorted({item["event"] for item in hooks}),
        "sandbox_mode": "enabled" if sandbox_enabled else "disabled",
    }
    return Resolution(
        capabilities=sorted(capabilities),
        capability_lines=capability_lines,
        configured_mode=configured_mode,
        mode_source=mode_source,
        mode_uncertain=mode_uncertain,
        permission_counts=counts,
        scoped_rule_counts=scoped,
        additional_directory_count=additional_directory_count,
        bypasses=bypasses,
        bypass_locked=bypass_locked,
        auto_locked=auto_locked,
        sandbox=sandbox,
        network=network,
        hooks=hooks,
        mcp=mcp,
        unknown_fields=merged.unknown_fields,
        facts=facts,
    )
