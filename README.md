# Kaapi P0

Kaapi is a deterministic, local-first security posture and configured-capability
analyser for observed Claude Code settings. It is offline, model-free, API-free,
read-only with respect to inspected configuration, and redacts sensitive hook
and MCP values. It reports static configuration potential, not runtime behavior.

P0 analyses Claude Code only. Codex, Cursor, Gemini, GitHub Copilot,
organisational policy overlays, blast radius, OWASP mappings, SARIF, and
`explain` are not available.

## Project status

P0 is complete against `docs/KAAPI_BUILD_SPEC_v1.3.md`. The P0 test suite
passes with 96 tests. The build specification is the authoritative recreation
contract; implementation decisions are recorded in `Decisions.MD`.

The maintained project wiki starts at [`wiki/index.md`](wiki/index.md). It is
an evolving documentation layer; it does not replace the build specification
or the decision log.

The `Claude Settings Test Suite` is a separate, non-gating adversarial
security-review benchmark and is not part of the P0 acceptance gate.

## Roadmap

- P1: Codex support.
- P1: Custom organisational security-policy overlays.
- P2: Cursor, Gemini, and GitHub Copilot support.

The planned Kaapi roadmap currently ends at P2.

## Requirements and setup

Use Python 3.11 or later and `uv`:

```console
uv sync --frozen --group dev
```

No runtime dependency, model, API key, or network connection is used by Kaapi's
analysis path.

## Workshop commands

Run these commands from the repository root, exactly as shown:

```console
uv run kaapi doctor --env-root fixtures/env
uv run kaapi check fixtures/loose/settings.json
uv run kaapi check fixtures/hardened/settings.json
uv run kaapi check fixtures/bypass/settings.json
uv run kaapi baseline fixtures/loose/settings.json -o before.json
uv run kaapi verify fixtures/hardened/settings.json --baseline before.json --expect-reduction
uv run pytest
```

The loose and bypass checks intentionally exit 1 because their analyses
succeed and meet the default high-severity gate. The hardened check, doctor,
snapshot, strict-reduction verification, and test suite exit 0.

## CLI

```console
uv run kaapi --help
uv run kaapi check --help
uv run kaapi doctor --help
uv run kaapi baseline --help
uv run kaapi verify --help
uv run kaapi rules --help
uv run kaapi version --help
```

Use `--format json` for the versioned check document, `--output FILE` to emit no
stdout, `--severity` to filter displayed findings, and `--fail-on` to select the
independent process gate. `NO_COLOR` and `--no-color` disable terminal colour.

`baseline` writes a secret-safe configured-capability snapshot. `verify`
compares observed settings with that snapshot; `--expect-reduction` requires a
strict subset and does not claim actual runtime behavior changed.

## Staged discovery

For deterministic local discovery, `--env-root DIR` uses:

```text
DIR/home/.claude/settings.json
DIR/project/.claude/settings.json
DIR/project/.claude/settings.local.json
DIR/managed/managed-settings.json
DIR/project/.mcp.json              # doctor triage count only
```

The settings precedence is managed, supplied session layer, project local,
shared project, then user. Arrays combine across applicable scopes; deny,
ask, and allow classes are evaluated in that order.
