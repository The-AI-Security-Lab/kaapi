# Expected: hardened

- `kaapi check fixtures/hardened/settings.json` reports `PASS` and exits 0.
- General shell, mutation, WebFetch, WebSearch, and broad MCP tool capability
  resolve denied.
- The sandbox is configured, unsandboxed retry is disabled, and the configured
  subprocess destination policy is a strict wildcard deny.
- This fixture's positive configured-capability set is a strict subset of the
  loose fixture snapshot.
