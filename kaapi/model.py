"""Internal immutable data model for observed configuration and results."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Evidence:
    source: str
    line: int | None
    path: str
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "line": self.line,
            "path": self.path,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class UnknownField:
    layer: str
    path: str
    source: str
    line: int | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "layer": self.layer,
            "path": self.path,
            "source": self.source,
            "line": self.line,
        }


@dataclass
class SourceLayer:
    kind: str
    path: Path
    data: dict[str, Any]
    lines: dict[str, int]
    unknown_fields: list[UnknownField] = field(default_factory=list)

    @property
    def source(self) -> str:
        return str(self.path)

    @property
    def managed(self) -> bool:
        return self.kind == "managed"


@dataclass(frozen=True)
class PermissionRule:
    rule_class: str
    raw: str
    tool: str
    specifier: str | None
    source: str
    path: str
    line: int | None
    source_kind: str


@dataclass
class Resolution:
    capabilities: list[str]
    capability_lines: list[str]
    configured_mode: str | None
    mode_source: Evidence | None
    mode_uncertain: bool
    permission_counts: dict[str, int]
    scoped_rule_counts: dict[str, dict[str, int]]
    additional_directory_count: int
    bypasses: list[dict[str, Any]]
    bypass_locked: bool
    auto_locked: bool
    sandbox: dict[str, Any]
    network: dict[str, Any]
    hooks: list[dict[str, Any]]
    mcp: dict[str, Any]
    unknown_fields: list[UnknownField]
    facts: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "capabilities": self.capabilities,
            "configured_mode": self.configured_mode,
            "mode_uncertain": self.mode_uncertain,
            "permission_counts": self.permission_counts,
            "scoped_rule_counts": self.scoped_rule_counts,
            "additional_directory_count": self.additional_directory_count,
            "bypasses": self.bypasses,
            "bypass_locked": self.bypass_locked,
            "auto_locked": self.auto_locked,
            "sandbox": self.sandbox,
            "network": self.network,
            "hooks": self.hooks,
            "mcp": self.mcp,
        }


class ConfigError(Exception):
    """A safe, user-facing configuration parse error."""

    def __init__(
        self,
        source: str,
        reason: str,
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        self.source = source
        self.reason = reason
        self.line = line
        self.column = column
        super().__init__(reason)

    def safe_message(self) -> str:
        location = self.source
        if self.line is not None:
            location += f":{self.line}"
            if self.column is not None:
                location += f":{self.column}"
        return f"configuration parse error: {location}: {self.reason}"
