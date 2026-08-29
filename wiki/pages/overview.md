# Kaapi overview

## Purpose

Kaapi is a deterministic, local-first analyzer of configured security posture
for observed Claude Code settings. It reports configuration potential, not
runtime behavior.

## P0 guarantees

- Claude Code is the only supported runtime in P0.
- Analysis is offline, model-free, API-free, and read-only for inspected files.
- Sensitive hook and MCP values are redacted from output and snapshots.
- Findings, baseline snapshots, and CLI output are deterministic.
- Baseline and rule provenance identify which versioned controls were applied.

## Current boundary

Codex, organisational policy overlays, Cursor, Gemini, GitHub Copilot, blast
radius, OWASP mappings, SARIF, and `explain` are outside P0. The additional
Claude Settings Test Suite is a separate, non-gating adversarial benchmark.

## Sources

- [Build specification v1.3](../../docs/KAAPI_BUILD_SPEC_v1.3.md)
- [Decision log](../../Decisions.MD)
