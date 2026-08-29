from __future__ import annotations

import json
from pathlib import Path

import pytest

from kaapi.analyze import analyze
from kaapi.baseline import load_baseline


def scan(tmp_path: Path, value: dict) -> set[str]:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    document, _, _ = analyze(path)
    return {finding["id"] for finding in document["findings"]}


def hardened() -> dict:
    return {
        "permissions": {"defaultMode": "dontAsk", "deny": ["Bash", "Edit", "WebFetch", "WebSearch", "mcp__*"]},
        "sandbox": {"enabled": True, "allowUnsandboxedCommands": False, "network": {"allowedDomains": [], "deniedDomains": ["*"]}},
        "hooks": {}, "mcpServers": {},
    }


def test_baseline_has_exact_complete_17_controls():
    baseline = load_baseline()
    assert baseline["name"] == "asl-coding-agent-baseline"
    assert baseline["version"] == "0.3.1"
    assert len(baseline["controls"]) == 17
    assert len({item["id"] for item in baseline["controls"]}) == 17
    for control in baseline["controls"]:
        assert control["sources"]
        assert all(source["url"].startswith("https://code.claude.com/docs/") and source["accessed"] for source in control["sources"])
        assert control["references"] == []


@pytest.mark.parametrize(
    ("control_id", "mutate"),
    [
        ("AGENT-APRV-001", lambda c: c["permissions"].update(defaultMode="bypassPermissions")),
        ("AGENT-APRV-002", lambda c: c["permissions"].update(defaultMode="auto")),
        ("AGENT-PERM-001", lambda c: c["permissions"].update(defaultMode="default", deny=["Edit", "WebFetch", "WebSearch"], allow=["Bash"])),
        ("AGENT-PERM-002", lambda c: c["permissions"].update(defaultMode="acceptEdits", deny=["Bash", "WebFetch", "WebSearch"])),
        ("AGENT-SBOX-001", lambda c: c["sandbox"].update(enabled=False)),
        ("AGENT-SBOX-002", lambda c: c["sandbox"].pop("allowUnsandboxedCommands")),
        ("AGENT-SBOX-003", lambda c: c["sandbox"].update(enableWeakerNestedSandbox=True)),
        ("AGENT-SBOX-004", lambda c: c["sandbox"].update(excludedCommands=["secret"])),
        ("AGENT-NET-001", lambda c: (c["sandbox"]["network"].update(deniedDomains=[]), c["permissions"].update(deny=["Bash", "Edit", "WebSearch"], allow=["WebFetch"]))),
        ("AGENT-HOOK-001", lambda c: c.update(hooks={"Stop": [{"hooks": [{"type": "command", "command": "secret"}]}]})),
        ("AGENT-MCP-001", lambda c: c.update(mcpServers={"demo": {"command": "secret"}})),
    ],
)
def test_primary_control_known_answers(tmp_path, control_id, mutate):
    config = hardened()
    mutate(config)
    assert control_id in scan(tmp_path, config)


@pytest.mark.parametrize(
    ("control_id", "mutation"),
    [
        ("AGENT-APRV-099", lambda c: c.update(futureSecuritySwitch=True)),
        ("AGENT-PERM-099", lambda c: c["permissions"].update(future=True)),
        ("AGENT-SBOX-099", lambda c: c["sandbox"].update(future=True)),
        ("AGENT-NET-099", lambda c: c["sandbox"]["network"].update(future=True)),
        ("AGENT-HOOK-099", lambda c: c.update(hooks={"FutureEvent": []})),
        ("AGENT-MCP-099", lambda c: c.update(mcpServers={"demo": {"futureTransport": True}})),
    ],
)
def test_unknown_control_known_answers(tmp_path, control_id, mutation):
    config = hardened()
    mutation(config)
    assert control_id in scan(tmp_path, config)
