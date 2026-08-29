# Expected: unknown field

- The default check reports `WARN`, includes `AGENT-PERM-099`, marks one field
  not evaluated, and exits 0 at the default high gate.
- `--fail-on medium` exits 1 without changing posture or full counts.
