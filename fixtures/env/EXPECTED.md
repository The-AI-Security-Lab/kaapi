# Expected: staged environment

- `kaapi doctor --env-root fixtures/env` is deterministic, read-only, and exits
  0 regardless of the report posture.
- Claude Code and Codex presence are detected; Codex is not parsed.
- Two project `.mcp.json` definitions are counted for triage only and are not
  added to the resolved settings analysis.
- Verbose output lists observed paths in stable order.
