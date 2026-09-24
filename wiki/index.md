# Kaapi wiki index

This is the content-oriented catalog for the Kaapi documentation layer.
Start with the overview, then follow the architecture and testing pages.

## Core pages

| Page | Summary |
| --- | --- |
| [Overview](pages/overview.md) | Product purpose, guarantees, and current P1 scope. |
| [Architecture](pages/architecture.md) | Deterministic analysis pipeline and module responsibilities. |
| [P0 controls](pages/p0-controls.md) | Baseline controls, severity, provenance, and evaluation boundaries. |
| [P1 Codex adapter](pages/p1-codex.md) | Supported Codex TOML surfaces, precedence, and conservative boundaries. |
| [Organisational policies](pages/organisational-policies.md) | Closed policy schema, independent verdicts, and PERMITTED_RISK. |
| [Testing and fixtures](pages/testing-and-fixtures.md) | Acceptance tests, fixtures, and validation commands. |
| [Roadmap](pages/roadmap.md) | Completed P0/P1 releases and planned P2/P3 boundaries. |
| [LLM wiki pattern](pages/llm-wiki-pattern.md) | Project-specific application of the persistent wiki workflow. |

## Authority and source register

- [Build specification v1.3](../docs/KAAPI_BUILD_SPEC_v1.3.md) — normative
  implementation contract.
- [Decision log](../Decisions.MD) — append-only implementation decisions and
  deviations.
- [Raw-source register](raw/README.md) — immutable-source handling and current
  source locations.
- [Maintenance schema](SCHEMA.md) — wiki workflow and safety rules.

## Maintenance entrypoints

- [Maintenance log](log.md) — chronological ingest and update history.
- Claude Settings Test Suite — external, non-vendored, non-gating adversarial
  benchmark recorded in the source register.
