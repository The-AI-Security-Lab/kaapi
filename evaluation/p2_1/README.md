# Kaapi P2.1 workshop evaluation

This is a deliberately small external-style harness. Each case contains an
agent configuration and an `evaluation.json` manifest with:

- one explicit security requirement expressed using an existing Kaapi policy;
- expected posture, policy facts, and harness grade;
- required evidence names.

Run one case from the repository root:

```console
uv run python -m evaluation.p2_1.harness evaluation/p2_1/golden/claude-insecure
```

The harness calls `kaapi.analyze_text(...)`, preserves the matching policy
requirement and finding evidence, and assigns `PASS`, `FAIL`, `INCONCLUSIVE`,
or `NOT_TESTED`. It does not execute the agent, hooks, MCP servers, or any
runtime action. Kaapi's `security_posture` and organisation-policy verdict
remain separate from the harness grade.
