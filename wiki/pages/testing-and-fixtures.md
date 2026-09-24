# Testing and fixtures

The P0+P1 acceptance suite is under `tests/` and covers parser and resolver
behavior, controls, fixtures, CLI contracts, determinism, offline operation,
read-only inspection, schema validation, baselines, policy, and verification.

The canonical demonstration fixtures are:

- `fixtures/loose/settings.json` — intentionally fails the default gate.
- `fixtures/hardened/settings.json` — expected hardened posture.
- `fixtures/bypass/settings.json` — observed-source bypass case.
- `fixtures/unknown-field/settings.json` — unknown-field handling.
- `fixtures/env/` — staged discovery and doctor input.
- `fixtures/codex-hardened/config.toml` — restrictive Codex known answer.
- `fixtures/codex-auto/config.toml` — workspace-write/on-request known answer.
- `fixtures/codex-danger/config.toml` — no-sandbox/no-approval secret-safety case.
- `fixtures/codex-env/` — system/user precedence and unobserved project trust.
- `examples/policies/` — templates, domain references, and policy bundles.

Run the full suite from the repository root:

```console
uv run pytest
```

The current P1 release-candidate gate is `133 passed`. Policy tests cover
independent validation, malformed and unknown input, unsupported parameters,
executable shape rejection, baseline non-suppression, separate verdicts,
`PERMITTED_RISK`, deterministic output, no network/model calls, read-only
inputs, secret-safe errors, cross-runtime named MCP allowlists, exact Claude
Bash-rule comparisons, runtime mismatch, repeated policies, and directory
bundles.

The additional Python API tests cover Claude JSON and Codex TOML known
answers, CLI/output parity apart from source identity, source locations,
malformed input, unknown security fields, determinism, secret redaction, and
the no-temporary-file contract.

Release validation builds both the source distribution and wheel offline,
installs the wheel into an isolated environment, and exercises the installed
Claude CLI, Codex CLI, package data, and Python facade. P1 release artifacts
use package version `1.1.0`; baseline versions remain independent.

The external, non-vendored Claude Settings Test Suite is a separate adversarial
benchmark. It is not collected by pytest and must not be treated as evidence
that Kaapi implements its broader reviewer finding taxonomy.

## Validation principles

- Repeat outputs to check deterministic ordering and snapshots.
- Run offline; no model, API, or network is required.
- Confirm inspected settings remain unchanged.
- Confirm secret-like values never appear in terminal output or JSON snapshots.
- Treat hooks and scripts in fixtures as inert text; never execute them.
