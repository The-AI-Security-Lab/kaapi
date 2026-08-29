# Testing and fixtures

The P0 acceptance suite is under `tests/` and covers parser and resolver
behavior, controls, fixtures, CLI contracts, determinism, offline operation,
read-only inspection, schema validation, baseline, and verification.

The canonical demonstration fixtures are:

- `fixtures/loose/settings.json` — intentionally fails the default gate.
- `fixtures/hardened/settings.json` — expected hardened posture.
- `fixtures/bypass/settings.json` — observed-source bypass case.
- `fixtures/unknown-field/settings.json` — unknown-field handling.
- `fixtures/env/` — staged discovery and doctor input.

Run the full suite from the repository root:

```console
uv run pytest
```

The external [Claude Settings Test Suite](../../Claude%20Settings%20Test%20Suite/README.md)
is a separate adversarial benchmark. It is not collected by pytest and must
not be treated as evidence that Kaapi P0 implements its broader reviewer
finding taxonomy.

## Validation principles

- Repeat outputs to check deterministic ordering and snapshots.
- Run offline; no model, API, or network is required.
- Confirm inspected settings remain unchanged.
- Confirm secret-like values never appear in terminal output or JSON snapshots.
- Treat hooks and scripts in fixtures as inert text; never execute them.
