"""Strict JSON parsing, field classification, discovery, and layer merging."""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .model import ConfigError, SourceLayer, UnknownField


PRECEDENCE = {"user": 0, "shared": 1, "local": 2, "supplied": 3, "explicit": 3, "managed": 4}

TOP_SUPPORTED = {
    "$schema",
    "permissions",
    "sandbox",
    "hooks",
    "mcpServers",
    "enableAllProjectMcpServers",
    "enabledMcpjsonServers",
    "disabledMcpjsonServers",
    "allowManagedMcpServersOnly",
    "allowedMcpServers",
    "deniedMcpServers",
    "allowManagedPermissionRulesOnly",
    "allowManagedHooksOnly",
}

# Documented settings with no independently evaluated P0 security meaning.
TOP_UNSUPPORTED = {
    "env", "model", "availableModels", "cleanupPeriodDays", "includeCoAuthoredBy",
    "attribution", "statusLine", "fileSuggestion", "outputStyle", "language",
    "apiKeyHelper", "forceLoginMethod", "forceLoginOrgUUID", "plansDirectory",
    "respectGitignore", "spinnerTipsEnabled", "spinnerVerbs", "preferredNotifChannel",
    "autoUpdatesChannel", "autoUpdates", "companyAnnouncements", "enabledPlugins",
    "extraKnownMarketplaces", "strictKnownMarketplaces", "awsAuthRefresh",
    "awsCredentialExport", "otelHeadersHelper", "alwaysThinkingEnabled",
    "fastModePerSessionOptIn", "teammateMode", "agent", "effortLevel",
}

PERMISSION_FIELDS = {
    "allow", "ask", "deny", "defaultMode", "disableBypassPermissionsMode",
    "disableAutoMode", "additionalDirectories",
}
SANDBOX_FIELDS = {
    "enabled", "autoAllowBashIfSandboxed", "excludedCommands",
    "allowUnsandboxedCommands", "enableWeakerNestedSandbox", "filesystem", "network",
}
FILESYSTEM_FIELDS = {"allowWrite", "denyWrite", "denyRead", "allowRead", "allowManagedReadPathsOnly"}
NETWORK_FIELDS = {
    "allowedDomains", "deniedDomains", "allowUnixSockets", "allowAllUnixSockets",
    "allowLocalBinding", "allowMachLookup", "httpProxyPort", "socksProxyPort",
}
HOOK_EVENTS = {
    "PreToolUse", "PermissionRequest", "PostToolUse", "PostToolUseFailure",
    "Notification", "UserPromptSubmit", "SessionStart", "SessionEnd", "Stop",
    "SubagentStart", "SubagentStop", "PreCompact", "Setup", "TeammateIdle",
    "TaskCompleted", "ConfigChange", "WorktreeCreate", "WorktreeRemove",
    "InstructionsLoaded", "Elicitation",
}
HOOK_ENTRY_FIELDS = {"matcher", "hooks"}
HOOK_HANDLER_FIELDS = {"type", "command", "prompt", "timeout", "statusMessage", "async", "once"}
MCP_CONTROL_FIELDS = {
    "mcpServers", "enableAllProjectMcpServers", "enabledMcpjsonServers",
    "disabledMcpjsonServers", "allowManagedMcpServersOnly", "allowedMcpServers",
    "deniedMcpServers",
}
PERMISSION_RULE_RE = re.compile(r"^[A-Za-z0-9_*.-]+(?:\(.*\))?$")


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate object key")
        result[key] = value
    return result


class _LocationWalker:
    """Walk already validated JSON and record value start lines by JSONPath."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.length = len(text)
        self.locations: dict[str, int] = {"$": 1}
        self.decoder = json.JSONDecoder()

    def _line(self, pos: int) -> int:
        return self.text.count("\n", 0, pos) + 1

    def _ws(self, pos: int) -> int:
        while pos < self.length and self.text[pos] in " \t\r\n":
            pos += 1
        return pos

    @staticmethod
    def _child(path: str, key: str) -> str:
        if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$-]*", key):
            return f"{path}.{key}"
        encoded = json.dumps(key, ensure_ascii=False)
        return f"{path}[{encoded}]"

    def walk(self) -> dict[str, int]:
        self._value(self._ws(0), "$")
        return self.locations

    def _value(self, pos: int, path: str) -> int:
        pos = self._ws(pos)
        self.locations[path] = self._line(pos)
        char = self.text[pos]
        if char == "{":
            return self._object(pos, path)
        if char == "[":
            return self._array(pos, path)
        _, end = self.decoder.raw_decode(self.text, pos)
        return end

    def _object(self, pos: int, path: str) -> int:
        pos = self._ws(pos + 1)
        if self.text[pos] == "}":
            return pos + 1
        while True:
            key, end = self.decoder.raw_decode(self.text, pos)
            pos = self._ws(end)
            pos = self._ws(pos + 1)  # colon
            child = self._child(path, key)
            self.locations[child] = self._line(pos)
            pos = self._ws(self._value(pos, child))
            if self.text[pos] == "}":
                return pos + 1
            pos = self._ws(pos + 1)

    def _array(self, pos: int, path: str) -> int:
        pos = self._ws(pos + 1)
        if self.text[pos] == "]":
            return pos + 1
        index = 0
        while True:
            child = f"{path}[{index}]"
            pos = self._ws(self._value(pos, child))
            index += 1
            if self.text[pos] == "]":
                return pos + 1
            pos = self._ws(pos + 1)


def _require_object(value: Any, source: str, path: str, lines: dict[str, int]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(source, f"{path} must be an object", lines.get(path))
    return value


def _require_list(value: Any, source: str, path: str, lines: dict[str, int], item_type: type = str) -> list[Any]:
    if not isinstance(value, list) or any(not isinstance(item, item_type) for item in value):
        raise ConfigError(source, f"{path} must be an array of {item_type.__name__} values", lines.get(path))
    return value


def _require_bool(value: Any, source: str, path: str, lines: dict[str, int]) -> None:
    if not isinstance(value, bool):
        raise ConfigError(source, f"{path} must be a boolean", lines.get(path))


def _unknown(layer: str, path: str, source: str, lines: dict[str, int]) -> UnknownField:
    return UnknownField(layer=layer, path=path, source=source, line=lines.get(path))


def _validate_and_classify(data: dict[str, Any], source: str, lines: dict[str, int]) -> list[UnknownField]:
    unknown: list[UnknownField] = []
    for key, value in data.items():
        path = _LocationWalker._child("$", key)
        if key not in TOP_SUPPORTED:
            if key not in TOP_UNSUPPORTED:
                unknown.append(_unknown("approvals", path, source, lines))
            continue
        if key == "$schema":
            if not isinstance(value, str):
                raise ConfigError(source, "$.\u0024schema must be a string", lines.get(path))
        elif key == "permissions":
            obj = _require_object(value, source, path, lines)
            for child, child_value in obj.items():
                child_path = _LocationWalker._child(path, child)
                if child not in PERMISSION_FIELDS:
                    unknown.append(_unknown("permissions", child_path, source, lines))
                elif child in {"allow", "ask", "deny", "additionalDirectories"}:
                    _require_list(child_value, source, child_path, lines)
                    if child in {"allow", "ask", "deny"}:
                        for index, rule in enumerate(child_value):
                            rule_path = f"{child_path}[{index}]"
                            if PERMISSION_RULE_RE.fullmatch(rule) is None:
                                raise ConfigError(source, f"{rule_path} is not a valid permission rule", lines.get(rule_path))
                elif child == "defaultMode":
                    if not isinstance(child_value, str) or child_value not in {
                        "default", "manual", "acceptEdits", "plan", "auto", "dontAsk", "bypassPermissions"
                    }:
                        raise ConfigError(source, f"{child_path} has an unsupported mode", lines.get(child_path))
                elif child in {"disableBypassPermissionsMode", "disableAutoMode"}:
                    if child_value != "disable":
                        raise ConfigError(source, f"{child_path} must be the string 'disable'", lines.get(child_path))
        elif key == "sandbox":
            obj = _require_object(value, source, path, lines)
            for child, child_value in obj.items():
                child_path = _LocationWalker._child(path, child)
                if child not in SANDBOX_FIELDS:
                    unknown.append(_unknown("sandbox", child_path, source, lines))
                elif child in {"enabled", "autoAllowBashIfSandboxed", "allowUnsandboxedCommands", "enableWeakerNestedSandbox"}:
                    _require_bool(child_value, source, child_path, lines)
                elif child == "excludedCommands":
                    _require_list(child_value, source, child_path, lines)
                elif child == "filesystem":
                    fs = _require_object(child_value, source, child_path, lines)
                    for fs_key, fs_value in fs.items():
                        fs_path = _LocationWalker._child(child_path, fs_key)
                        if fs_key not in FILESYSTEM_FIELDS:
                            unknown.append(_unknown("sandbox", fs_path, source, lines))
                        elif fs_key == "allowManagedReadPathsOnly":
                            _require_bool(fs_value, source, fs_path, lines)
                        else:
                            _require_list(fs_value, source, fs_path, lines)
                elif child == "network":
                    net = _require_object(child_value, source, child_path, lines)
                    for net_key, net_value in net.items():
                        net_path = _LocationWalker._child(child_path, net_key)
                        if net_key not in NETWORK_FIELDS:
                            unknown.append(_unknown("network", net_path, source, lines))
                        elif net_key in {"allowedDomains", "deniedDomains", "allowUnixSockets"}:
                            _require_list(net_value, source, net_path, lines)
                        elif net_key in {"allowAllUnixSockets", "allowLocalBinding", "allowMachLookup"}:
                            _require_bool(net_value, source, net_path, lines)
                        elif not isinstance(net_value, int) or isinstance(net_value, bool) or not (1 <= net_value <= 65535):
                            raise ConfigError(source, f"{net_path} must be a valid port", lines.get(net_path))
        elif key == "hooks":
            hooks = _require_object(value, source, path, lines)
            for event, entries in hooks.items():
                event_path = _LocationWalker._child(path, event)
                if event not in HOOK_EVENTS:
                    unknown.append(_unknown("hooks", event_path, source, lines))
                    continue
                _require_list(entries, source, event_path, lines, dict)
                for i, entry in enumerate(entries):
                    entry_path = f"{event_path}[{i}]"
                    for entry_key, entry_value in entry.items():
                        item_path = _LocationWalker._child(entry_path, entry_key)
                        if entry_key not in HOOK_ENTRY_FIELDS:
                            unknown.append(_unknown("hooks", item_path, source, lines))
                        elif entry_key == "matcher" and not isinstance(entry_value, str):
                            raise ConfigError(source, f"{item_path} must be a string", lines.get(item_path))
                        elif entry_key == "hooks":
                            _require_list(entry_value, source, item_path, lines, dict)
                            for j, handler in enumerate(entry_value):
                                handler_path = f"{item_path}[{j}]"
                                for handler_key in handler:
                                    if handler_key not in HOOK_HANDLER_FIELDS:
                                        unknown.append(_unknown("hooks", _LocationWalker._child(handler_path, handler_key), source, lines))
        elif key == "mcpServers":
            servers = _require_object(value, source, path, lines)
            for server, config in servers.items():
                server_path = _LocationWalker._child(path, server)
                _require_object(config, source, server_path, lines)
                # Server definitions are intentionally safe-projected later. Unknown
                # transport fields are MCP security unknowns, except documented keys.
                for config_key in config:
                    if config_key not in {"type", "command", "args", "env", "url", "headers", "oauth", "disabled", "alwaysAllow"}:
                        unknown.append(_unknown("mcp", _LocationWalker._child(server_path, config_key), source, lines))
        elif key in {"enableAllProjectMcpServers", "allowManagedMcpServersOnly", "allowManagedPermissionRulesOnly", "allowManagedHooksOnly"}:
            _require_bool(value, source, path, lines)
        elif key in {"enabledMcpjsonServers", "disabledMcpjsonServers", "allowedMcpServers", "deniedMcpServers"}:
            _require_list(value, source, path, lines)
    return sorted(unknown, key=lambda item: (PRECEDENCE.get(_source_kind_for_path(item.source), 9), item.source, item.line or 0, item.path))


def _source_kind_for_path(source: str) -> str:
    # Only a stable fallback for sorting standalone unknown records.
    return "explicit"


def parse_settings(path: str | Path, kind: str = "explicit") -> SourceLayer:
    source_path = Path(path)
    try:
        raw = source_path.read_bytes()
    except OSError as exc:
        raise ConfigError(str(source_path), f"cannot read settings file ({exc.strerror or 'I/O error'})") from None
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        line = raw[:exc.start].count(b"\n") + 1
        raise ConfigError(str(source_path), "invalid UTF-8", line) from None
    try:
        data = json.loads(text, object_pairs_hook=_pairs_no_duplicates)
    except json.JSONDecodeError as exc:
        raise ConfigError(str(source_path), "invalid JSON", exc.lineno, exc.colno) from None
    except ValueError:
        raise ConfigError(str(source_path), "duplicate object key") from None
    if not isinstance(data, dict):
        raise ConfigError(str(source_path), "top level must be an object", 1, 1)
    lines = _LocationWalker(text).walk()
    unknown = _validate_and_classify(data, str(source_path), lines)
    return SourceLayer(kind=kind, path=source_path, data=data, lines=lines, unknown_fields=unknown)


def _pick_existing(candidates: Iterable[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def discovery_paths(env_root: str | Path | None = None, project_root: str | Path | None = None) -> list[tuple[str, Path]]:
    if env_root is not None:
        root = Path(env_root)
        candidates = [
            ("user", [root / "home/.claude/settings.json", root / ".claude/settings.json"]),
            ("shared", [root / "project/.claude/settings.json"]),
            ("local", [root / "project/.claude/settings.local.json", root / ".claude/settings.local.json"]),
            ("managed", [root / "managed/managed-settings.json", root / "managed-settings.json"]),
        ]
    else:
        project = Path(project_root) if project_root is not None else Path.cwd()
        if sys.platform == "darwin":
            managed = Path("/Library/Application Support/ClaudeCode/managed-settings.json")
        elif os.name == "nt":
            managed = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "ClaudeCode/managed-settings.json"
        else:
            managed = Path("/etc/claude-code/managed-settings.json")
        candidates = [
            ("user", [Path.home() / ".claude/settings.json"]),
            ("shared", [project / ".claude/settings.json"]),
            ("local", [project / ".claude/settings.local.json"]),
            ("managed", [managed]),
        ]
    found: list[tuple[str, Path]] = []
    for kind, choices in candidates:
        selected = _pick_existing(choices)
        if selected is not None:
            found.append((kind, selected))
    return found


def discover_settings(env_root: str | Path | None = None, project_root: str | Path | None = None) -> list[SourceLayer]:
    return [parse_settings(path, kind) for kind, path in discovery_paths(env_root, project_root)]


def _stable_unique(items: list[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for item in items:
        marker = json.dumps(item, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        if marker not in seen:
            seen.add(marker)
            result.append(item)
    return result


def _merge(low: Any, high: Any) -> Any:
    if isinstance(low, dict) and isinstance(high, dict):
        result = {key: value for key, value in low.items()}
        for key, value in high.items():
            result[key] = _merge(result[key], value) if key in result else value
        return result
    if isinstance(low, list) and isinstance(high, list):
        return _stable_unique(low + high)
    return high


@dataclass
class MergedSettings:
    data: dict[str, Any]
    layers: list[SourceLayer]
    unknown_fields: list[UnknownField]

    def evidence_points(self, path: str, all_layers: bool = False) -> list[tuple[SourceLayer, int | None]]:
        points = [(layer, layer.lines.get(path)) for layer in self.layers if path in layer.lines]
        if all_layers:
            return points
        return points[-1:] if points else []


def merge_layers(layers: list[SourceLayer]) -> MergedSettings:
    ordered = sorted(layers, key=lambda layer: PRECEDENCE[layer.kind])
    merged: dict[str, Any] = {}
    for layer in ordered:
        merged = _merge(merged, layer.data)

    managed_only_rules = bool(merged.get("allowManagedPermissionRulesOnly"))
    managed_only_hooks = bool(merged.get("allowManagedHooksOnly"))
    managed_only_mcp = bool(merged.get("allowManagedMcpServersOnly"))
    if managed_only_rules:
        permission_data: dict[str, Any] = {}
        for layer in ordered:
            if layer.managed and isinstance(layer.data.get("permissions"), dict):
                permission_data = _merge(permission_data, layer.data["permissions"])
        if "permissions" in merged:
            for field in ("allow", "ask", "deny"):
                merged["permissions"].pop(field, None)
            for field in ("allow", "ask", "deny"):
                if field in permission_data:
                    merged["permissions"][field] = permission_data[field]
    if managed_only_hooks:
        managed_hooks: dict[str, Any] = {}
        for layer in ordered:
            if layer.managed and isinstance(layer.data.get("hooks"), dict):
                managed_hooks = _merge(managed_hooks, layer.data["hooks"])
        merged["hooks"] = managed_hooks
    if managed_only_mcp:
        managed_servers: dict[str, Any] = {}
        for layer in ordered:
            if layer.managed and isinstance(layer.data.get("mcpServers"), dict):
                managed_servers = _merge(managed_servers, layer.data["mcpServers"])
        merged["mcpServers"] = managed_servers

    filesystem = merged.get("sandbox", {}).get("filesystem", {}) if isinstance(merged.get("sandbox"), dict) else {}
    if isinstance(filesystem, dict) and filesystem.get("allowManagedReadPathsOnly") is True:
        managed_allow_read: list[Any] = []
        for layer in ordered:
            layer_sandbox = layer.data.get("sandbox", {})
            layer_filesystem = layer_sandbox.get("filesystem", {}) if isinstance(layer_sandbox, dict) else {}
            if layer.managed and isinstance(layer_filesystem, dict):
                managed_allow_read.extend(layer_filesystem.get("allowRead", []))
        filesystem["allowRead"] = _stable_unique(managed_allow_read)

    unknown = [item for layer in ordered for item in layer.unknown_fields]
    unknown.sort(key=lambda item: (PRECEDENCE[next((layer.kind for layer in ordered if layer.source == item.source), "explicit")], item.line or 0, item.path))
    return MergedSettings(data=merged, layers=ordered, unknown_fields=unknown)
