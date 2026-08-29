"""Secret-safe capability snapshots and observational comparison."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import __version__
from .baseline import load_baseline


SNAPSHOT_KEYS = {"schema_version", "kaapi_version", "baseline_version", "runtime", "capabilities", "config_fingerprint", "findings"}


class SnapshotError(Exception):
    pass


def make_snapshot(document: dict[str, Any], merged_data: dict[str, Any]) -> dict[str, Any]:
    canonical = json.dumps(merged_data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {
        "schema_version": "1",
        "kaapi_version": __version__,
        "baseline_version": load_baseline()["version"],
        "runtime": "claude-code",
        "capabilities": list(document["resolved_capability"]["capabilities"]),
        "config_fingerprint": "sha256:" + hashlib.sha256(canonical).hexdigest(),
        "findings": sorted(item["id"] for item in document["findings"]),
    }


def load_snapshot(path: str | Path) -> dict[str, Any]:
    snapshot_path = Path(path)
    try:
        value = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise SnapshotError(f"snapshot contract error: cannot read a valid snapshot from {snapshot_path}") from None
    if not isinstance(value, dict) or set(value) != SNAPSHOT_KEYS:
        raise SnapshotError("snapshot contract error: malformed snapshot object")
    if value.get("schema_version") != "1":
        raise SnapshotError(f"snapshot contract error: unsupported schema_version {value.get('schema_version')!r}")
    if value.get("runtime") != "claude-code":
        raise SnapshotError(f"snapshot contract error: unsupported runtime {value.get('runtime')!r}")
    if value.get("baseline_version") != load_baseline()["version"]:
        raise SnapshotError("snapshot contract error: incompatible baseline version")
    if not isinstance(value.get("capabilities"), list) or any(not isinstance(item, str) for item in value["capabilities"]):
        raise SnapshotError("snapshot contract error: capabilities must be strings")
    if value["capabilities"] != sorted(set(value["capabilities"])):
        raise SnapshotError("snapshot contract error: capabilities must be sorted and unique")
    if not isinstance(value.get("findings"), list) or any(not isinstance(item, str) for item in value["findings"]):
        raise SnapshotError("snapshot contract error: findings must be strings")
    if not isinstance(value.get("config_fingerprint"), str) or not value["config_fingerprint"].startswith("sha256:"):
        raise SnapshotError("snapshot contract error: invalid config_fingerprint")
    return value


def compare(snapshot: dict[str, Any], current_capabilities: list[str]) -> dict[str, Any]:
    before = set(snapshot["capabilities"])
    current = set(current_capabilities)
    return {
        "strict_reduction": current < before,
        "removed_capabilities": sorted(before - current),
        "added_capabilities": sorted(current - before),
        "unchanged_capability_count": len(before & current),
    }
