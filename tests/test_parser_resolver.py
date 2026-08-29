from __future__ import annotations

import json
from pathlib import Path

import pytest

from kaapi.analyze import analyze
from kaapi.model import ConfigError
from kaapi.parser import merge_layers, parse_settings
from kaapi.resolver import resolve


def write_settings(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "payload",
    [
        b"[]",
        b'{"permissions": 1}',
        b'{"permissions": {"allow": "Bash"}}',
        b'{"sandbox": {"enabled": "yes"}}',
        b'{"hooks": {"PostToolUse": {}}}',
        b'{"mcpServers": []}',
        b'{"permissions": {}, "permissions": {}}',
        b'{"permissions": {"deny": ["Bash(unclosed"]}}',
        b"\xff",
    ],
)
def test_strict_parsing(tmp_path, payload):
    path = tmp_path / "settings.json"
    path.write_bytes(payload)
    with pytest.raises(ConfigError):
        parse_settings(path)


def test_source_lines_are_jsonpath_specific(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{\n  "permissions": {\n    "allow": [\n      "Bash"\n    ]\n  }\n}\n', encoding="utf-8")
    layer = parse_settings(path)
    assert layer.lines["$.permissions"] == 2
    assert layer.lines["$.permissions.allow"] == 3
    assert layer.lines["$.permissions.allow[0]"] == 4


def test_precedence_arrays_and_lower_deny(tmp_path):
    user = parse_settings(write_settings(tmp_path / "user.json", {"permissions": {"defaultMode": "default", "deny": ["Bash"]}, "sandbox": {"enabled": False}}), "user")
    local = parse_settings(write_settings(tmp_path / "local.json", {"permissions": {"defaultMode": "acceptEdits", "allow": ["Bash"]}}), "local")
    managed = parse_settings(write_settings(tmp_path / "managed.json", {"permissions": {"defaultMode": "dontAsk"}, "sandbox": {"enabled": True}}), "managed")
    merged = merge_layers([managed, user, local])
    resolution = resolve(merged)
    assert merged.data["permissions"]["defaultMode"] == "dontAsk"
    assert merged.data["sandbox"]["enabled"] is True
    assert merged.data["permissions"]["allow"] == ["Bash"]
    assert merged.data["permissions"]["deny"] == ["Bash"]
    assert resolution.facts["tool_states"]["Bash"] == "denied"


def test_supplied_layer_position(tmp_path):
    layers = [
        parse_settings(write_settings(tmp_path / f"{kind}.json", {"sandbox": {"enabled": value}}), kind)
        for kind, value in (("user", False), ("shared", False), ("local", False), ("supplied", True), ("managed", False))
    ]
    assert merge_layers(layers).data["sandbox"]["enabled"] is False
    assert merge_layers(layers[:-1]).data["sandbox"]["enabled"] is True


def test_managed_only_rules_hooks_and_mcp(tmp_path):
    user = parse_settings(write_settings(tmp_path / "u.json", {
        "permissions": {"allow": ["Bash"]},
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "secret"}]}]},
        "mcpServers": {"user-server": {"command": "secret"}},
    }), "user")
    managed = parse_settings(write_settings(tmp_path / "m.json", {
        "allowManagedPermissionRulesOnly": True,
        "allowManagedHooksOnly": True,
        "allowManagedMcpServersOnly": True,
        "permissions": {"deny": ["Bash"]},
        "hooks": {},
        "mcpServers": {},
    }), "managed")
    resolution = resolve(merge_layers([user, managed]))
    assert resolution.permission_counts == {"allow": 0, "ask": 0, "deny": 1}
    assert resolution.hooks == []
    assert resolution.mcp["configured_server_count"] == 0


def test_managed_read_paths_only_filters_allows_but_keeps_denies(tmp_path):
    user = parse_settings(write_settings(tmp_path / "u.json", {"sandbox": {"filesystem": {"allowRead": ["user-allow"], "denyRead": ["user-deny"]}}}), "user")
    managed = parse_settings(write_settings(tmp_path / "m.json", {"sandbox": {"filesystem": {"allowManagedReadPathsOnly": True, "allowRead": ["managed-allow"], "denyRead": ["managed-deny"]}}}), "managed")
    merged = merge_layers([user, managed])
    filesystem = merged.data["sandbox"]["filesystem"]
    assert filesystem["allowRead"] == ["managed-allow"]
    assert filesystem["denyRead"] == ["user-deny", "managed-deny"]


def test_shared_tool_families_and_monitor(tmp_path):
    settings = write_settings(tmp_path / "settings.json", {"permissions": {"defaultMode": "default", "deny": ["Read(secret/**)", "Edit(src/**)", "Bash(rm *)"]}, "sandbox": {"enabled": True, "allowUnsandboxedCommands": False}})
    resolution = resolve(merge_layers([parse_settings(settings)]))
    scoped = resolution.facts["scoped_rule_counts"]
    assert scoped["Read"]["deny"] == scoped["Grep"]["deny"] == scoped["Glob"]["deny"] == scoped["LSP"]["deny"] == 1
    assert scoped["Write"]["deny"] == 2  # Read deny plus Edit-family deny.
    assert scoped["NotebookEdit"]["deny"] == 1
    assert scoped["Monitor"]["deny"] == 1


def test_dontask_ask_is_denied(tmp_path):
    path = write_settings(tmp_path / "settings.json", {"permissions": {"defaultMode": "dontAsk", "ask": ["Bash"]}})
    resolution = resolve(merge_layers([parse_settings(path)]))
    assert resolution.facts["tool_states"]["Bash"] == "denied"


@pytest.mark.parametrize("mode", ["default", "manual", "acceptEdits", "plan", "auto", "dontAsk", "bypassPermissions"])
def test_all_supported_modes(tmp_path, mode):
    path = write_settings(tmp_path / f"{mode}.json", {"permissions": {"defaultMode": mode}})
    resolution = resolve(merge_layers([parse_settings(path)]))
    assert resolution.configured_mode == ("default" if mode == "manual" else mode)


def test_mode_subsets_and_additional_directories(tmp_path):
    path = write_settings(tmp_path / "settings.json", {"permissions": {"defaultMode": "acceptEdits", "additionalDirectories": ["../safe"]}})
    resolution = resolve(merge_layers([parse_settings(path)]))
    assert "shell.in-scope-filesystem-subset:unprompted" in resolution.capabilities
    assert resolution.facts["additional_directory_count"] == 1
    assert resolution.additional_directory_count == 1
    assert resolution.as_dict()["additional_directory_count"] == 1
    assert "../safe" not in json.dumps(resolution.as_dict())


def test_absent_mode_is_uncertain(tmp_path):
    path = write_settings(tmp_path / "settings.json", {"permissions": {"deny": ["Bash"]}})
    resolution = resolve(merge_layers([parse_settings(path)]))
    assert resolution.configured_mode is None
    assert resolution.mode_uncertain is True
    assert resolution.facts["workspace_trust_observed"] is False


def test_lockouts_prevent_active_modes(tmp_path):
    path = write_settings(tmp_path / "settings.json", {"permissions": {"defaultMode": "bypassPermissions", "disableBypassPermissionsMode": "disable"}})
    resolution = resolve(merge_layers([parse_settings(path)]), "claude --dangerously-skip-permissions")
    assert resolution.bypasses == []
    assert resolution.bypass_locked is True
    assert resolution.facts["invocation_bypass_locked"] is True


def test_invocation_is_only_bypass_source(tmp_path):
    path = write_settings(tmp_path / "settings.json", {
        "permissions": {"defaultMode": "default"},
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "--dangerously-skip-permissions"}]}]},
    })
    merged = merge_layers([parse_settings(path)])
    assert resolve(merged).bypasses == []
    assert resolve(merged, "claude --dangerously-skip-permissions").bypasses[0]["source_kind"] == "invocation"


def test_supported_boundary_fields_are_resolved(tmp_path):
    path = write_settings(tmp_path / "settings.json", {"sandbox": {
        "enabled": True,
        "allowUnsandboxedCommands": False,
        "filesystem": {"allowWrite": ["tmp"], "denyWrite": ["etc"], "denyRead": ["secret"], "allowRead": ["src"], "allowManagedReadPathsOnly": True},
        "network": {"allowedDomains": [], "deniedDomains": ["*"], "allowUnixSockets": ["x"], "allowAllUnixSockets": False, "allowLocalBinding": True, "allowMachLookup": True, "httpProxyPort": 8080, "socksProxyPort": 1080},
    }})
    resolution = resolve(merge_layers([parse_settings(path)]))
    assert resolution.sandbox["filesystem"] == {"allow_write_count": 1, "deny_write_count": 1, "deny_read_count": 1, "allow_read_count": 0, "managed_read_paths_only": True}
    exceptions = resolution.network["exceptions"]
    assert exceptions["unix_socket_count"] == 1
    assert exceptions["local_binding"] and exceptions["mach_lookup"]
    assert exceptions["http_proxy_configured"] and exceptions["socks_proxy_configured"]


def test_sandboxed_bash_auto_allow_default_false_and_deny(tmp_path):
    default_path = write_settings(tmp_path / "default.json", {"permissions": {"defaultMode": "default"}, "sandbox": {"enabled": True, "allowUnsandboxedCommands": False}})
    false_path = write_settings(tmp_path / "false.json", {"permissions": {"defaultMode": "default"}, "sandbox": {"enabled": True, "autoAllowBashIfSandboxed": False, "allowUnsandboxedCommands": False}})
    deny_path = write_settings(tmp_path / "deny.json", {"permissions": {"defaultMode": "default", "deny": ["Bash"]}, "sandbox": {"enabled": True, "allowUnsandboxedCommands": False}})
    default_resolution = resolve(merge_layers([parse_settings(default_path)]))
    false_resolution = resolve(merge_layers([parse_settings(false_path)]))
    deny_resolution = resolve(merge_layers([parse_settings(deny_path)]))
    assert default_resolution.facts["sandboxed_bash_unprompted"] is True
    assert "shell.sandboxed-subset:unprompted" in default_resolution.capabilities
    assert false_resolution.facts["sandboxed_bash_unprompted"] is False
    assert deny_resolution.facts["sandboxed_bash_unprompted"] is False


def test_known_non_security_field_does_not_warn(tmp_path):
    path = write_settings(tmp_path / "settings.json", {"model": "some-model", "permissions": {"defaultMode": "dontAsk", "deny": ["Bash", "Edit", "WebFetch", "WebSearch"]}, "sandbox": {"enabled": True, "allowUnsandboxedCommands": False, "network": {"deniedDomains": ["*"], "allowedDomains": []}}})
    document, _, _ = analyze(path)
    assert document["unknown_fields"] == []


@pytest.mark.parametrize(
    "value,expected_layer",
    [
        ({"sandbox": {"failIfUnavailable": True}}, "sandbox"),
        ({"sandbox": {"network": {"allowManagedDomainsOnly": True}}}, "network"),
    ],
)
def test_newer_unmodelled_security_fields_warn(tmp_path, value, expected_layer):
    path = write_settings(tmp_path / "settings.json", value)
    document, _, _ = analyze(path)
    assert document["posture"] in {"WARN", "FAIL"}
    assert any(item["layer"] == expected_layer for item in document["unknown_fields"])
