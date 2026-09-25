# Kaapi overview

## Purpose

Kaapi is a deterministic, local-first analyzer of configured security posture
for observed Claude Code and Codex settings. It reports configuration
potential, not runtime behavior.

Kaapi remains an independent reusable project. Charlie is a potential consumer
of Kaapi's configured-authority analysis, not a rename or replacement for
Kaapi. The current primitive is deterministic static analysis producing
normalized capabilities, baseline findings, and source evidence/provenance.

For Charlie, keep these concepts distinct:

- `CONFIGURED`: authority inferred from configuration;
- `EXPECTED`: authority intended or permitted by policy;
- `OBSERVED`: runtime behavior actually seen.

Kaapi currently supports CONFIGURED strongly and provides foundations for
EXPECTED through organisational policies. Its `observed` wording refers to
observed configuration sources, not runtime agent actions. Runtime telemetry is
not currently implemented.

## Current guarantees

- Claude Code retains its frozen P0 behavior and baseline 0.3.1.
- P1 adds a thin Codex TOML adapter with a runtime-specific baseline 0.4.0.
- Organisational policies are closed data evaluated independently of baseline
  posture.
- P2.1 adds in-memory policy input to the Python API and a four-case workshop
  evaluation harness; P2.2A adds the optional local FastAPI transport.
- Analysis is offline, model-free, does not call hosted APIs, and is read-only
  for inspected files.
- `kaapi.analyze_text(...)` provides an in-process Python API, and P2.2A adds a
  versioned local HTTP endpoint; Kaapi does not provide a hosted endpoint.
- Sensitive hook and MCP values are redacted from output and snapshots.
- Findings, baseline snapshots, and CLI output are deterministic.
- Baseline and rule provenance identify which versioned controls were applied.

## Current release and development boundary

Cursor, Gemini, GitHub Copilot, blast radius, Arcanum/OWASP mappings, SARIF,
and `explain` remain unavailable in `v1.1.0`. P2.1 and P2.2A are implemented
on the development branch; portable packaging, hosted integration, and the
expanded dataset remain planned P2 work. The earlier feature backlog has moved
to P3. The additional Claude Settings Test Suite is a separate, non-gating
adversarial benchmark.

The Codex adapter intentionally does not infer project trust, CLI overrides,
managed requirements, permission profiles, hooks, apps, plugins, skills, or
runtime behavior. Unsupported security-relevant surfaces prevent a clean PASS.
`allow_login_shell` is parsed and validated but does not currently materially
affect resolution or findings. Codex coverage is tested but less extensively
than Claude coverage.

## Sources

- [Build specification v1.3](../../docs/KAAPI_BUILD_SPEC_v1.3.md)
- [Decision log](../../Decisions.MD)
