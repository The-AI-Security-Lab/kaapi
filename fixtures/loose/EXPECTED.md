# Expected: loose

- `kaapi check fixtures/loose/settings.json` reports `FAIL` and exits 1.
- Findings include broad unprompted shell and file mutation, disabled sandbox,
  weaker/excluded sandbox surfaces, unbounded configured network potential,
  executable hooks, and configured MCP capability.
- Hook commands and MCP command, arguments, and environment values never appear;
  their presence is rendered as `<present>`.
