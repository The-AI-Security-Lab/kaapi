# Organisational policies

## Contract

An organisation policy is strict JSON matching
[`policy.schema.json`](../../kaapi/schemas/policy.schema.json). It contains an
identifier and a non-empty list of known baseline controls. Each requirement
uses:

- `pass`: the selected requirement must pass;
- `allow`: an existing baseline risk is explicitly accepted and reported as
  `PERMITTED_RISK`.

Optional `domain` and `runtimes` metadata make reference policies
self-describing and fail closed when applied to the wrong runtime.

Closed parameters cover:

- approvals and human-prompt-capable allowed modes;
- MCP counts, named allow/require lists, auto approval, and managed-only state;
- Claude configured Bash allow-rule patterns and default-deny mode;
- writable paths and required filesystem deny patterns;
- sandbox state, modes, and excluded-command counts;
- outbound potential, domains, local binding, and Unix sockets;
- Claude hook counts and allowed events.

Policy requirement results expose comparison counts instead of unexpected Bash
patterns, paths, or domains. The surrounding runtime report keeps its existing
contract: Claude's resolved MCP metadata may list selected server names, while
secret-bearing MCP configuration remains redacted. Unknown keys, controls,
parameters, duplicate keys/controls, and every expression, script, template,
or executable shape are rejected.

## Composition

`--policy FILE` is repeatable. `--policy-dir DIR` loads every direct `.json`
file in sorted filename order. Policy IDs must be unique.

```console
uv run kaapi check fixtures/codex-hardened/config.toml \
  --policy examples/policies/reference/common/approvals-human.json \
  --policy examples/policies/reference/common/mcp-github-only.json
uv run kaapi check fixtures/codex-hardened/config.toml \
  --policy-dir examples/policies/bundles/strict-common
```

The aggregate verdict is `FAIL` if any policy fails, otherwise
`PERMITTED_RISK` if any policy permits baseline risk, otherwise `PASS`.

## Verdict separation

`kaapi check ... --policy FILE` preserves baseline posture, counts, findings,
severities, evidence, and passed controls. It adds:

- `security_posture`, identical to the baseline `posture`;
- `organisation_policy.verdict`, one of `PASS`, `FAIL`, or
  `PERMITTED_RISK`;
- one deterministic result per selected requirement.

Policy `FAIL` exits 1 independently of the security `--fail-on` threshold.
`PERMITTED_RISK` never changes a risky baseline finding to green.

## Commands and examples

```console
uv run kaapi policy validate examples/policies/strict.json
uv run kaapi check fixtures/codex-auto/config.toml --policy examples/policies/development.json
uv run kaapi policy validate --policy-dir examples/policies/bundles/strict-common
```

Validation needs no installed agent, model, API, or network. Policy values are
never executed. Named MCP allowlists work for Claude and Codex. Exact configured
Claude Bash patterns are supported, but Codex Starlark `.rules` files are not a
P1 input and runtime execution is never claimed. See the
[decision log](../../Decisions.MD) for the format and verdict decisions.
