from __future__ import annotations

import hashlib
import json
import socket
from pathlib import Path

from kaapi.analyze import analyze


SECRETS = [
    "KAAPI_SECRET_SENTINEL",
    "KAAPI_SECRET_MCP_COMMAND",
    "KAAPI_SECRET_MCP_ARGUMENT",
    "KAAPI_SECRET_MCP_ENV",
    "secret-excluded-command",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_repeated_pretty_json_doctor_are_byte_identical(run_cli):
    commands = [
        ("check", "fixtures/loose/settings.json", "--no-color"),
        ("check", "fixtures/loose/settings.json", "--format", "json"),
        ("doctor", "--env-root", "fixtures/env", "--format", "json", "--verbose"),
    ]
    for command in commands:
        first, second = run_cli(*command), run_cli(*command)
        assert first.returncode == second.returncode
        assert first.stdout.encode() == second.stdout.encode()
        assert first.stderr.encode() == second.stderr.encode()


def test_inspected_files_are_read_only(run_cli):
    paths = [path for path in Path("fixtures").rglob("*") if path.is_file()]
    before = {str(path): digest(path) for path in paths}
    run_cli("doctor", "--env-root", "fixtures/env")
    run_cli("check", "fixtures/loose/settings.json", "--format", "json")
    after = {str(path): digest(path) for path in paths}
    assert before == after


def test_core_does_not_create_or_connect_sockets(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("network call attempted")
    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    document, _, _ = analyze("fixtures/loose/settings.json")
    assert document["posture"] == "FAIL"


def test_secret_redaction_across_outputs_and_snapshot(run_cli, tmp_path):
    outputs = []
    for args in [
        ("check", "fixtures/loose/settings.json", "--no-color"),
        ("check", "fixtures/loose/settings.json", "--format", "json"),
        ("check", "fixtures/loose/settings.json", "--quiet"),
    ]:
        outputs.append(run_cli(*args).stdout)
    snapshot = tmp_path / "before.json"
    baseline = run_cli("baseline", "fixtures/loose/settings.json", "-o", str(snapshot))
    assert baseline.returncode == 0 and baseline.stdout == ""
    outputs.append(snapshot.read_text())
    combined = "\n".join(outputs)
    assert "<present>" in combined
    for secret in SECRETS:
        assert secret not in combined


def test_snapshot_and_strict_reduction_contract(run_cli, tmp_path):
    snapshot = tmp_path / "before.json"
    assert run_cli("baseline", "fixtures/loose/settings.json", "-o", str(snapshot)).returncode == 0
    value = json.loads(snapshot.read_text())
    assert set(value) == {"schema_version", "kaapi_version", "baseline_version", "runtime", "capabilities", "config_fingerprint", "findings"}
    assert value["capabilities"] == sorted(set(value["capabilities"]))
    assert run_cli("verify", "fixtures/hardened/settings.json", "--baseline", str(snapshot), "--expect-reduction").returncode == 0
    assert run_cli("verify", "fixtures/loose/settings.json", "--baseline", str(snapshot), "--expect-reduction").returncode == 1
    report = run_cli("verify", "fixtures/hardened/settings.json", "--baseline", str(snapshot), "--format", "json")
    assert report.returncode == 0
    assert json.loads(report.stdout)["strict_reduction"] is True


def test_specification_checksum_is_preserved():
    assert digest(Path("docs/KAAPI_BUILD_SPEC_v1.3.md")) == "8a1e41be6381ad1987989396d948433e56f9cd1af22f77ea51583db2e6564b32"


def test_v12_is_not_present_or_synthesized():
    assert not Path("docs/KAAPI_BUILD_SPEC_v1.2.md").exists()
