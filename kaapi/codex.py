"""Thin, deterministic Codex config.toml adapter for Kaapi P1."""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path
from typing import Any

from .model import ConfigError, Evidence, Resolution, SourceLayer, UnknownField
from .parser import MergedSettings, PRECEDENCE


APPROVAL_VALUES = {"untrusted", "on-request", "never"}
SANDBOX_VALUES = {"read-only", "workspace-write", "danger-full-access"}
WEB_SEARCH_VALUES = {"cached", "indexed", "live", "disabled"}
GRANULAR_KEYS = {
    "sandbox_approval", "rules", "mcp_elicitations",
    "request_permissions", "skill_approval",
}
WORKSPACE_KEYS = {
    "network_access", "writable_roots",
    "exclude_slash_tmp", "exclude_tmpdir_env_var",
}
NETWORK_PROXY_KEYS = {
    "enabled", "domains", "unix_sockets", "allow_local_binding",
    "dangerously_allow_non_loopback_proxy",
    "dangerously_allow_all_unix_sockets",
}
MCP_KEYS = {
    "bearer_token_env_var", "command", "cwd", "default_tools_approval_mode",
    "disabled_tools", "enabled", "enabled_tools", "env", "env_http_headers",
    "env_vars", "experimental_environment", "http_headers", "oauth",
    "oauth_resource", "required", "scopes", "startup_timeout_ms",
    "startup_timeout_sec", "tool_timeout_sec", "tools", "url",
}
NON_SECURITY_KEYS = {
    "$schema", "agents", "analytics", "apps_mcp_product_sku",
    "chatgpt_base_url", "compact_prompt", "developer_instructions", "desktop",
    "disable_paste_burst", "experimental_realtime_ws_base_url", "feedback",
    "file_opener", "forced_chatgpt_workspace_id", "history", "instructions",
    "model", "model_auto_compact_token_limit", "model_catalog_json",
    "model_context_window", "model_instructions_file", "model_provider",
    "model_providers", "model_reasoning_effort", "model_reasoning_summary",
    "model_supports_reasoning_summaries", "model_verbosity", "notify",
    "openai_base_url", "otel", "personality", "profile", "profiles",
    "project_doc_fallback_filenames", "project_doc_max_bytes",
    "project_root_markers", "review_model", "service_tier",
    "show_raw_agent_reasoning", "suppress_unstable_features_warning",
    "tool_output_token_limit", "tui",
}


def _child(parent: str, key: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
        return f"{parent}.{key}"
    escaped = key.replace("\\", "\\\\").replace('"', '\\"')
    return f'{parent}["{escaped}"]'


def _line_map(text: str) -> dict[str, int]:
    """Collect conservative TOML key locations without retaining values."""
    result = {"$": 1}
    table: list[str] = []
    for number, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        header = re.match(r"^\[([^\[\]]+)\]\s*(?:#.*)?$", stripped)
        if header:
            table = [part.strip().strip('"').strip("'") for part in header.group(1).split(".")]
            current = "$"
            for part in table:
                current = _child(current, part)
                result.setdefault(current, number)
            continue
        assignment = re.match(
            r"^([A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z_][A-Za-z0-9_-]*)*)\s*=",
            stripped,
        )
        if assignment:
            current = "$"
            for part in [*table, *assignment.group(1).split(".")]:
                current = _child(current, part)
                result.setdefault(current, number)
    return result


def _unknown(
    layer: str, path: str, source: str, lines: dict[str, int]
) -> UnknownField:
    return UnknownField(layer, path, source, lines.get(path))


def _require(
    value: Any,
    expected: type,
    source: str,
    path: str,
    lines: dict[str, int],
    label: str,
) -> None:
    if not isinstance(value, expected):
        raise ConfigError(source, f"{path} must be {label}", lines.get(path))


def _classify(
    data: dict[str, Any], source: str, lines: dict[str, int]
) -> list[UnknownField]:
    unknown: list[UnknownField] = []
    for key, value in data.items():
        path = _child("$", key)
        if key == "approval_policy":
            if isinstance(value, str):
                if value not in APPROVAL_VALUES:
                    raise ConfigError(
                        source, f"{path} has an unsupported value", lines.get(path)
                    )
            elif (
                isinstance(value, dict)
                and set(value) == {"granular"}
                and isinstance(value["granular"], dict)
            ):
                granular_path = _child(path, "granular")
                for nested, nested_value in value["granular"].items():
                    nested_path = _child(granular_path, nested)
                    if nested not in GRANULAR_KEYS:
                        unknown.append(
                            _unknown("approvals", nested_path, source, lines)
                        )
                    elif not isinstance(nested_value, bool):
                        raise ConfigError(
                            source,
                            f"{nested_path} must be a boolean",
                            lines.get(nested_path),
                        )
            else:
                raise ConfigError(
                    source,
                    f"{path} must be a supported string or granular table",
                    lines.get(path),
                )
        elif key == "approvals_reviewer":
            if value not in {"user", "auto_review"}:
                raise ConfigError(
                    source, f"{path} has an unsupported value", lines.get(path)
                )
        elif key == "sandbox_mode":
            if value not in SANDBOX_VALUES:
                raise ConfigError(
                    source, f"{path} has an unsupported value", lines.get(path)
                )
        elif key == "sandbox_workspace_write":
            _require(value, dict, source, path, lines, "a table")
            for nested, nested_value in value.items():
                nested_path = _child(path, nested)
                if nested not in WORKSPACE_KEYS:
                    unknown.append(_unknown("sandbox", nested_path, source, lines))
                elif nested == "writable_roots":
                    if not isinstance(nested_value, list) or any(
                        not isinstance(item, str) for item in nested_value
                    ):
                        raise ConfigError(
                            source,
                            f"{nested_path} must be an array of strings",
                            lines.get(nested_path),
                        )
                elif not isinstance(nested_value, bool):
                    raise ConfigError(
                        source,
                        f"{nested_path} must be a boolean",
                        lines.get(nested_path),
                    )
        elif key == "web_search":
            if value not in WEB_SEARCH_VALUES:
                raise ConfigError(
                    source, f"{path} has an unsupported value", lines.get(path)
                )
        elif key == "allow_login_shell":
            _require(value, bool, source, path, lines, "a boolean")
        elif key == "mcp_servers":
            _require(value, dict, source, path, lines, "a table")
            for server, config in value.items():
                server_path = _child(path, str(server))
                _require(config, dict, source, server_path, lines, "a table")
                for nested in config:
                    if nested not in MCP_KEYS:
                        unknown.append(
                            _unknown("mcp", _child(server_path, nested), source, lines)
                        )
        elif key == "features":
            _require(value, dict, source, path, lines, "a table")
            for feature, feature_value in value.items():
                feature_path = _child(path, feature)
                if feature == "network_proxy":
                    if isinstance(feature_value, bool):
                        continue
                    _require(
                        feature_value,
                        dict,
                        source,
                        feature_path,
                        lines,
                        "a boolean or table",
                    )
                    for nested in feature_value:
                        if nested not in NETWORK_PROXY_KEYS:
                            unknown.append(
                                _unknown(
                                    "network",
                                    _child(feature_path, nested),
                                    source,
                                    lines,
                                )
                            )
                elif feature.startswith("web_search"):
                    unknown.append(_unknown("network", feature_path, source, lines))
                else:
                    unknown.append(
                        _unknown("permissions", feature_path, source, lines)
                    )
        elif key in {"default_permissions", "permissions", "windows"}:
            unknown.append(_unknown("sandbox", path, source, lines))
        elif key == "hooks":
            unknown.append(_unknown("hooks", path, source, lines))
        elif key in {"apps", "plugins", "skills"}:
            unknown.append(_unknown("mcp", path, source, lines))
        elif key == "projects":
            _require(value, dict, source, path, lines, "a table")
        elif key not in NON_SECURITY_KEYS:
            unknown.append(_unknown("permissions", path, source, lines))
    return sorted(unknown, key=lambda item: (item.line or 0, item.path))


def _parse_codex_content(
    content: str | bytes, source: str, kind: str
) -> SourceLayer:
    if not isinstance(content, (str, bytes)):
        raise TypeError("content must be str or bytes")
    if not isinstance(source, str) or not source:
        raise ValueError("source must be a non-empty string")
    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ConfigError(
                source, "invalid UTF-8", content[: exc.start].count(b"\n") + 1
            ) from None
    else:
        text = content
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        raise ConfigError(source, "invalid TOML") from None
    lines = _line_map(text)
    return SourceLayer(
        kind,
        Path(source),
        data,
        lines,
        _classify(data, source, lines),
    )


def parse_codex_config(
    path: str | Path, kind: str = "explicit"
) -> SourceLayer:
    source_path = Path(path)
    try:
        raw = source_path.read_bytes()
    except OSError as exc:
        raise ConfigError(
            str(source_path),
            f"cannot read config file ({exc.strerror or 'I/O error'})",
        ) from None
    return _parse_codex_content(raw, str(source_path), kind)


def parse_codex_config_text(
    content: str | bytes,
    source: str = "<memory:codex>",
    kind: str = "explicit",
) -> SourceLayer:
    """Parse Codex TOML supplied directly in memory."""
    return _parse_codex_content(content, source, kind)


def discovery_paths(
    env_root: str | Path | None = None,
) -> tuple[list[tuple[str, Path]], list[Path]]:
    if env_root is not None:
        root = Path(env_root)
        candidates = [
            ("system", root / "system/etc/codex/config.toml"),
            ("user", root / "home/.codex/config.toml"),
            ("project", root / "project/.codex/config.toml"),
        ]
    else:
        codex_home = Path(
            os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
        )
        system = (
            Path("C:/ProgramData/OpenAI/Codex/config.toml")
            if os.name == "nt"
            else Path("/etc/codex/config.toml")
        )
        candidates = [
            ("system", system),
            ("user", codex_home / "config.toml"),
            ("project", Path.cwd() / ".codex/config.toml"),
        ]
    applicable = [
        (kind, path)
        for kind, path in candidates
        if kind != "project" and path.is_file()
    ]
    untrusted_project = [
        path for kind, path in candidates if kind == "project" and path.is_file()
    ]
    return applicable, untrusted_project


def _merge(low: Any, high: Any) -> Any:
    if isinstance(low, dict) and isinstance(high, dict):
        result = dict(low)
        for key, value in high.items():
            result[key] = _merge(result[key], value) if key in result else value
        return result
    return high


def merge_layers(layers: list[SourceLayer]) -> MergedSettings:
    ordered = sorted(layers, key=lambda layer: PRECEDENCE[layer.kind])
    data: dict[str, Any] = {}
    for layer in ordered:
        data = _merge(data, layer.data)
    unknown = [item for layer in ordered for item in layer.unknown_fields]
    unknown.sort(
        key=lambda item: (
            PRECEDENCE[
                next(
                    layer.kind for layer in ordered if layer.source == item.source
                )
            ],
            item.line or 0,
            item.path,
        )
    )
    return MergedSettings(data, ordered, unknown)


def load_observed(
    subject: str | Path | None, env_root: str | Path | None = None
) -> tuple[MergedSettings, str, list[str], list[str]]:
    if subject is not None and str(subject) != "codex":
        layer = parse_codex_config(subject)
        return merge_layers([layer]), str(subject), [layer.source], []
    paths, skipped_project = discovery_paths(env_root)
    layers = [parse_codex_config(path, kind) for kind, path in paths]
    return (
        merge_layers(layers),
        str(subject or "codex"),
        [layer.source for layer in layers],
        [str(path) for path in skipped_project],
    )


def _evidence(
    merged: MergedSettings, path: str, detail: str
) -> Evidence | None:
    points = merged.evidence_points(path)
    if not points:
        return None
    layer, line = points[-1]
    return Evidence(layer.source, line, path, detail)


def resolve(
    merged: MergedSettings, skipped_project: list[str] | None = None
) -> Resolution:
    data = merged.data
    approval = data.get("approval_policy")
    approval_label = "granular" if isinstance(approval, dict) else approval
    sandbox_mode = data.get("sandbox_mode")
    reviewer = data.get("approvals_reviewer", "user")
    workspace = (
        data.get("sandbox_workspace_write", {})
        if isinstance(data.get("sandbox_workspace_write"), dict)
        else {}
    )
    prompts_allowed = approval in {"on-request", "untrusted"}
    sandbox_prompt_allowed = prompts_allowed
    if isinstance(approval, dict):
        granular = approval.get("granular", {})
        prompts_allowed = any(granular.values())
        sandbox_prompt_allowed = granular.get("sandbox_approval") is True

    if sandbox_mode == "read-only":
        shell_state = write_state = (
            "approval-required" if prompts_allowed else "denied"
        )
    elif sandbox_mode == "workspace-write":
        shell_state = (
            "approval-required" if approval == "untrusted" else "unprompted"
        )
        write_state = "unprompted"
    elif sandbox_mode == "danger-full-access":
        shell_state = write_state = "unprompted"
    else:
        shell_state = write_state = "unknown"

    observed_web_search = data.get("web_search")
    web_search = (
        observed_web_search
        if observed_web_search is not None
        else (
            "live"
            if sandbox_mode == "danger-full-access"
            else "cached"
        )
    )
    search_state = "denied" if web_search == "disabled" else "unprompted"
    states = {
        "Bash": shell_state,
        "Monitor": shell_state,
        "Read": "unprompted",
        "Grep": "unprompted",
        "Glob": "unprompted",
        "LSP": "unprompted",
        "Edit": write_state,
        "Write": write_state,
        "NotebookEdit": write_state,
        "WebFetch": "denied",
        "WebSearch": search_state,
    }

    sandbox_observed = sandbox_mode in SANDBOX_VALUES
    sandbox_enabled = sandbox_mode in {"read-only", "workspace-write"}
    writable_roots = workspace.get("writable_roots", [])
    escalation_available = bool(
        sandbox_enabled and sandbox_prompt_allowed
    )
    sandbox = {
        "enabled": sandbox_enabled,
        "configured_only": sandbox_enabled,
        "mode": sandbox_mode,
        "unsandboxed_retry_allowed": escalation_available,
        "excluded_command_count": 0,
        "weaker_nested_isolation": False,
        "auto_allow_bash_if_sandboxed": sandbox_mode == "workspace-write",
        "filesystem": {
            "allow_write_count": len(writable_roots),
            "deny_write_count": 0,
            "deny_read_count": 0,
            "allow_read_count": 0,
            "managed_read_paths_only": False,
        },
    }

    features = data.get("features", {})
    network_proxy = (
        features.get("network_proxy", False)
        if isinstance(features, dict)
        else False
    )
    proxy_enabled = network_proxy is True or (
        isinstance(network_proxy, dict)
        and network_proxy.get("enabled") is True
    )
    domains = (
        network_proxy.get("domains", {})
        if isinstance(network_proxy, dict)
        and isinstance(network_proxy.get("domains"), dict)
        else {}
    )
    command_network = sandbox_mode == "danger-full-access" or (
        sandbox_mode == "workspace-write"
        and workspace.get("network_access") is True
    )
    live_search = web_search == "live"
    outbound = command_network or live_search
    strict_boundary = bool(
        command_network
        and proxy_enabled
        and domains.get("*") != "allow"
        and not live_search
    )
    network = {
        "webfetch_permission": "denied",
        "websearch_permission": search_state,
        "shell_network_permission": (
            "unprompted" if command_network else "denied"
        ),
        "sandbox_proxy_configured": proxy_enabled,
        "strict_destination_boundary": strict_boundary,
        "outbound_configured_potential": outbound,
        "web_search_mode": web_search,
        "exceptions": {
            "allowed_domain_count": sum(
                value == "allow" for value in domains.values()
            ),
            "denied_domain_count": sum(
                value == "deny" for value in domains.values()
            ),
            "unix_socket_count": (
                len(network_proxy.get("unix_sockets", {}))
                if isinstance(network_proxy, dict)
                and isinstance(network_proxy.get("unix_sockets"), dict)
                else 0
            ),
            "all_unix_sockets": bool(
                isinstance(network_proxy, dict)
                and network_proxy.get("dangerously_allow_all_unix_sockets")
                is True
            ),
            "local_binding": bool(
                isinstance(network_proxy, dict)
                and network_proxy.get("allow_local_binding") is True
            ),
            "mach_lookup": False,
            "http_proxy_configured": False,
            "socks_proxy_configured": False,
        },
    }

    servers = (
        data.get("mcp_servers", {})
        if isinstance(data.get("mcp_servers"), dict)
        else {}
    )
    enabled_server_items = [
        (name, config)
        for name, config in servers.items()
        if isinstance(config, dict) and config.get("enabled", True) is not False
    ]
    enabled_servers = [config for _, config in enabled_server_items]
    auto_servers = sum(
        config.get("default_tools_approval_mode") == "auto"
        for config in enabled_servers
    )
    mcp = {
        "configured_server_count": len(enabled_servers),
        "selected_server_names": [],
        "broad_tool_allow": auto_servers > 0,
        "auto_approved_server_count": auto_servers,
    }

    bypasses: list[dict[str, Any]] = []
    if sandbox_mode == "danger-full-access" and approval == "never":
        point = _evidence(
            merged, "$.sandbox_mode", "danger-full-access configured"
        )
        bypasses.append(
            {
                "mechanism": (
                    "danger-full-access with approval prompts disabled"
                ),
                "source_kind": next(
                    (
                        layer.kind
                        for layer in merged.layers
                        if point and layer.source == point.source
                    ),
                    "settings",
                ),
                "source": point.source if point else "<settings>",
                "path": "$.sandbox_mode",
                "line": point.line if point else None,
            }
        )

    capabilities = {"tool.Read:unprompted"}
    if shell_state != "denied":
        capabilities.add(f"tool.Bash:{shell_state}")
    if write_state != "denied":
        capabilities.add(f"tool.Write:{write_state}")
    if search_state != "denied":
        capabilities.add(f"tool.WebSearch:{search_state}")
    if sandbox_mode == "workspace-write":
        capabilities.add("filesystem.workspace-write:configured")
    elif sandbox_mode == "danger-full-access":
        capabilities.update(
            {
                "filesystem.unrestricted-write:configured",
                "shell.subprocess:without-codex-sandbox",
            }
        )
    if command_network:
        capabilities.add("network.command-access:configured")
    if live_search:
        capabilities.add("network.web-search-live:configured")
    if outbound and not strict_boundary:
        capabilities.add(
            "network.destination:unbounded-configured-potential"
        )
    if mcp["configured_server_count"]:
        capabilities.add("mcp.server-surface:configured")
    if bypasses:
        capabilities.add("permissions.bypass:observed")

    not_evaluated = []
    if approval_label is None:
        not_evaluated.append("approval_policy is not observed")
    if not sandbox_observed:
        not_evaluated.append("sandbox_mode is not observed")
    if skipped_project:
        not_evaluated.append(
            "project config is present but project trust is not observed"
        )
    capability_lines = [
        (
            f"Approval policy: {approval_label or 'not observed'}; "
            f"reviewer: {reviewer}"
        ),
        (
            f"Sandbox mode: {sandbox_mode or 'not observed'} "
            "(runtime enforcement not tested)"
        ),
        f"Shell commands: {shell_state}",
        f"File reads: unprompted; file writes: {write_state}",
        (
            "Command network access: "
            f"{'configured' if command_network else 'not configured'}; "
            f"web search: {web_search}"
            + (
                " (documented default)"
                if observed_web_search is None
                else ""
            )
        ),
        (
            f"MCP servers configured: {mcp['configured_server_count']}; "
            "definitions do not prove connection or execution"
        ),
    ]
    if reviewer == "auto_review":
        capability_lines.insert(
            1,
            "[!] Eligible approval requests use automatic model review",
        )
    if bypasses:
        capability_lines.insert(
            1, "[!] No sandbox and no approval prompts are configured"
        )
    if not_evaluated:
        capability_lines.append(
            "Not evaluated: " + "; ".join(not_evaluated)
        )

    facts = {
        "runtime": "codex",
        "tool_states": states,
        "rules": [],
        "scoped_rule_counts": {},
        "sandbox_observed": sandbox_observed,
        "approval_policy": approval_label,
        "approvals_reviewer": reviewer,
        "command_network": command_network,
        "not_evaluated": not_evaluated,
        "sandboxed_bash_unprompted": False,
        "shell_rule_policy_supported": False,
        "bash_allow_rule_patterns": [],
        "bash_broad_allow_count": 0,
        "mcp_server_names": sorted(name for name, _ in enabled_server_items),
        "mcp_managed_only": None,
        "writable_path_patterns": list(writable_roots),
        "denied_read_patterns": None,
        "denied_write_patterns": None,
        "allowed_domains": sorted(
            name for name, decision in domains.items() if decision == "allow"
        ),
        "denied_domains": sorted(
            name for name, decision in domains.items() if decision == "deny"
        ),
        "hook_events": None,
        "sandbox_mode": sandbox_mode,
        "web_search_mode": web_search,
    }
    return Resolution(
        capabilities=sorted(capabilities),
        capability_lines=capability_lines,
        configured_mode=approval_label,
        mode_source=_evidence(
            merged, "$.approval_policy", "configured approval policy"
        ),
        mode_uncertain=approval_label is None or not sandbox_observed,
        permission_counts={"allow": 0, "ask": 0, "deny": 0},
        scoped_rule_counts={},
        additional_directory_count=len(writable_roots),
        bypasses=bypasses,
        bypass_locked=False,
        auto_locked=False,
        sandbox=sandbox,
        network=network,
        hooks=[],
        mcp=mcp,
        unknown_fields=merged.unknown_fields,
        facts=facts,
    )
