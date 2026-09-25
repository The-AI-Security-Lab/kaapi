# Kaapi P1 — v1.1.0

Kaapi is a deterministic, local-first security posture and
configured-capability analyser for observed Claude Code and Codex settings. It
is offline, model-free, does not call hosted APIs, is read-only with respect to
inspected configuration, and redacts sensitive hook and MCP values. It reports
static configuration potential, not runtime behavior.

Kaapi `1.1.0` adds a thin Codex `config.toml` adapter, closed-data
organisational policy overlays, and a public in-process Python analysis API.
The P2.1 workshop evaluation slice is complete and validated on
`codex/p2.1-workshop-evaluation` at commit
`9a0bc6ba34576782675aded9e16b718c24fea9bd`. The remaining P2 stages are
documented below; they are not part of this release.

## P1 milestone

P1 is cumulative: it preserves the complete P0 Claude Code analyser and adds
Codex configuration analysis, custom organisational policies, and the public
`analyze_text(...)` facade. Codex does not replace or weaken the Claude path.

| Capability | P0 | P1 |
| --- | --- | --- |
| Claude Code settings analysis | Included | Preserved and regression-tested |
| Claude baseline and snapshots | Included | Preserved at baseline 0.3.1 |
| Codex `config.toml` analysis | Not included | Added with baseline 0.4.0 |
| Custom organisational policies | Not included | Added for Claude and Codex |
| In-process Python analysis API | Not included | Added for Claude and Codex |
| Deterministic, offline, read-only analysis | Included | Preserved |

The combined P0+P1 acceptance suite passes with 133 tests. Those tests cover
the original Claude parser, resolution, findings, fixtures, CLI, and snapshot
contracts as well as the Codex, policy, and in-memory Python API paths.

The build specification remains authoritative. Implementation decisions and
scope exclusions are recorded in [`Decisions.MD`](Decisions.MD), and the
maintained wiki starts at [`wiki/index.md`](wiki/index.md).

P1 does not include an HTTP service, hosted deployment, policy inputs through
`analyze_text(...)`, runtime execution, or the planned P2/P3 backlog. See the
[roadmap](wiki/pages/roadmap.md) for the approved phase boundaries.

## Contents

- [Quick start](#quick-start)
- [Understand the result](#understand-the-result)
- [Test the complete P1 milestone](#test-the-complete-p1-milestone)
- [Snapshot and CI workflows](#snapshot-and-ci-workflows)
- [Organisational policy guide](#organisational-policy-guide)
- [Roadmap](#roadmap)
- [CLI reference](#cli-reference)
- [Staged discovery](#staged-discovery)

## Quick start

Run all commands from the repository root.

### 1. Install

Use Python 3.11 or later and `uv`:

```console
cd /path/to/kaapi
uv sync --frozen --group dev
uv run kaapi --version
```

The version command reports `kaapi 1.1.0`. Package releases and security
baseline versions are independent: Claude uses baseline `0.3.1` and Codex uses
baseline `0.4.0`.

The initial dependency installation may require package-registry access. Kaapi
itself does not use a model, API key, or network connection while analysing
configuration.

### 2. Scan Claude or Codex

Kaapi reads the supplied file and does not modify it:

```console
uv run kaapi check ~/.claude/settings.json --runtime claude-code
uv run kaapi check ~/.codex/config.toml --runtime codex
```

Use versioned JSON for review or CI:

```console
uv run kaapi check ~/.claude/settings.json --runtime claude-code --format json --output claude-posture.json
uv run kaapi check ~/.codex/config.toml --runtime codex --format json --output codex-posture.json
```

### 3. Apply an organisational policy

```console
uv run kaapi policy validate examples/policies/template.json
uv run kaapi check ~/.claude/settings.json --runtime claude-code --policy examples/policies/template.json
uv run kaapi check ~/.codex/config.toml --runtime codex --policy examples/policies/template.json
```

The template uses controls shared by both runtimes. Build a team-specific
policy with the [organisational policy guide](#organisational-policy-guide).

### Python library entry point

For in-process callers, Kaapi exposes a small public facade that accepts
configuration content directly and returns the same versioned structured
analysis document as `check`:

```python
from kaapi import analyze_text

document = analyze_text(
    config_content,
    runtime="claude-code",  # or "codex"
    source="settings.json",  # optional display identifier
)
```

`config_content` may be UTF-8 `str` or `bytes`. Without `source`, evidence uses
a deterministic synthetic identifier such as `<memory:claude-code>`; no
temporary configuration file is written. Parsing and validation errors raise
the existing `ConfigError`. Pass one policy JSON document as `policy=` to
evaluate the same closed organisational-policy overlay used by the CLI; policy
content may be UTF-8 text, bytes, or a decoded mapping, and a non-empty
sequence supports a deterministic policy bundle. Invalid policy input raises
`PolicyError`. The facade is a general Kaapi library capability, not a
Charlie-specific API. The existing CLI, snapshots, verification, and policy
verdict semantics remain supported.

For the workshop integration, run a checked-in golden case:

```console
uv run python -m evaluation.p2_1.harness evaluation/p2_1/golden/claude-insecure
```

The external-style harness owns grading and preserves Kaapi's policy result,
findings, evidence, and static-analysis limitations. It reports `PASS`,
`FAIL`, `INCONCLUSIVE`, or `NOT_TESTED`; it does not execute an agent.

The P2.2A local REST service is an optional HTTP extra. It does not add
authentication, persistence, hosted deployment, or a browser upload/paste
flow. A remote or browser consumer still needs its own deployment boundary.

### Local FastAPI API

Install the local HTTP extra and start the versioned service:

```console
uv sync --extra http
uv run uvicorn kaapi.http_api:app --host 127.0.0.1 --port 8000
```

Submit a supported Claude JSON or Codex TOML configuration as text:

```console
curl -X POST http://127.0.0.1:8000/v1/analyze \
  -H 'content-type: application/json' \
  --data '{"runtime":"claude-code","config":"{\"sandbox\":{\"enabled\":true}}"}'
```

The request object accepts `runtime`, `config`, optional `policy`, and optional
`source`. The successful response is the same structured document returned by
`analyze_text(...)`; an adverse `posture` or policy verdict is still an HTTP
200 response. Invalid requests use a stable `{"error":{"code":...,"message":...}}`
envelope and never expose stack traces or filesystem details. Request bodies
are limited to 1 MiB. The service performs static configuration analysis only;
it does not execute agents or verify runtime enforcement.

## Understand the result

Kaapi reports two independent questions:

| Result | Question answered |
| --- | --- |
| `posture` / `security_posture` | Does the built-in runtime baseline find configured risk? |
| `organisation_policy.verdict` | Does the configuration meet the supplied team policy? |

Policy `PERMITTED_RISK` never removes or downgrades a baseline finding.

| Exit code | Meaning |
| --- | --- |
| 0 | Analysis completed and all active gates passed |
| 1 | Analysis completed but the security or policy gate failed |
| 2 | Invalid CLI usage |
| 3 | Configuration or policy parsing failed safely |

## Test the complete P1 milestone

Run all automated P0 and P1 tests first:

```console
uv run pytest
```

Expected result:

```text
133 passed
```

If dependencies are already installed but `uv` cannot access its cache, run
the same suite through the repository environment:

```console
.venv/bin/python -m pytest
```

### Test Claude Code support inherited from P0

```console
uv run kaapi doctor --runtime claude-code --env-root fixtures/env
uv run kaapi check fixtures/hardened/settings.json --runtime claude-code --quiet
uv run kaapi check fixtures/loose/settings.json --runtime claude-code --quiet
uv run kaapi check fixtures/bypass/settings.json --runtime claude-code --quiet
```

Expected known answers:

| Fixture | Expected result |
| --- | --- |
| `hardened` | `PASS`, exit 0 |
| `loose` | `FAIL`, exit 1 |
| `bypass` | `FAIL`, exit 1 |

The two failures are successful analyses that intentionally meet Kaapi's
default high-severity process gate. They are not parser or test failures.

### Test Codex support added in P1

```console
uv run kaapi doctor --runtime codex --env-root fixtures/codex-env --format json --verbose
uv run kaapi check fixtures/codex-hardened/config.toml --runtime codex --quiet
uv run kaapi check fixtures/codex-auto/config.toml --runtime codex --quiet
uv run kaapi check fixtures/codex-danger/config.toml --runtime codex --format json
```

Expected known answers:

| Fixture | Expected result |
| --- | --- |
| `codex-hardened` | `PASS`, exit 0 |
| `codex-auto` | `FAIL` with three high findings, exit 1 |
| `codex-danger` | `FAIL` with critical/high findings, exit 1 |

The dangerous fixture also verifies that secret-like MCP values do not appear
in terminal or JSON output.

### Test custom organisational policies added in P1

```console
uv run kaapi policy validate examples/policies/strict.json
uv run kaapi check fixtures/codex-hardened/config.toml --policy examples/policies/strict.json --quiet
uv run kaapi check fixtures/codex-auto/config.toml --policy examples/policies/development.json --quiet
```

Expected results:

| Command | Expected result |
| --- | --- |
| Validate `strict.json` | `VALID`, exit 0 |
| Strict policy on `codex-hardened` | Security `PASS`, policy `PASS`, exit 0 |
| Development policy on `codex-auto` | Security `FAIL`, policy `PERMITTED_RISK`, exit 1 |

`PERMITTED_RISK` never removes a baseline finding. The final example remains
exit 1 because the independent security posture still fails.

## Snapshot and CI workflows

Claude reduction:

```console
uv run kaapi baseline fixtures/loose/settings.json --runtime claude-code --output /tmp/kaapi-claude-before.json
uv run kaapi verify fixtures/hardened/settings.json --runtime claude-code --baseline /tmp/kaapi-claude-before.json --expect-reduction --quiet
```

Codex reduction:

```console
uv run kaapi baseline fixtures/codex-danger/config.toml --runtime codex --output /tmp/kaapi-codex-before.json
uv run kaapi verify fixtures/codex-hardened/config.toml --runtime codex --baseline /tmp/kaapi-codex-before.json --expect-reduction --quiet
```

Both verify commands should report `PASS strict_reduction=true exit=0`.

For CI, keep the process gate and write the versioned report as an artifact:

```console
uv run kaapi check path/to/settings.json --runtime claude-code --policy my-policy.json --format json --output kaapi-report.json
uv run kaapi check path/to/config.toml --runtime codex --policy my-policy.json --format json --output kaapi-report.json
```

Exit 1 fails the job while preserving the JSON report for review.

## Organisational policy guide

Policies are strict JSON matching
[`policy.schema.json`](kaapi/schemas/policy.schema.json). They select known
controls with a `pass` or explicit `allow` expectation and may use only the
documented closed parameters. They cannot contain expressions, scripts,
custom scanner rules, severity overrides, or executable logic.

### What a P1 policy can express

| Requirement | P1 support |
| --- | --- |
| Require a known baseline control to pass | Yes |
| Explicitly accept a known baseline risk | Yes, reported as `PERMITTED_RISK` |
| Limit the total configured MCP server count | Yes |
| Allow or require MCP server names | Yes, Claude and Codex |
| Limit Claude sandbox exclusions or command hooks | Yes |
| Restrict configured Claude Bash allow-rule patterns | Yes, Claude |
| Restrict configured filesystem paths and network domains | Yes, where observed |
| Restrict Codex command prefix rules from `.rules` files | Not yet |
| Add expressions, scripts, or custom scanner logic | No |

The organisation-policy result reports comparison counts and verdicts instead
of echoing unexpected Bash patterns, paths, or domains. Kaapi's existing
runtime report contract still applies: Claude's resolved MCP metadata may list
selected server names, while MCP commands, arguments, environment values,
URLs, and other secret-bearing configuration remain redacted.

`kaapi check ... --policy FILE` retains the independent security posture and
findings and adds an organisation-policy verdict:

- `PASS`: all selected organisation requirements pass;
- `FAIL`: at least one organisation requirement fails;
- `PERMITTED_RISK`: the organisation accepts or parameterises a capability
  that the built-in baseline still reports as risky.

The example policies are
[`strict.json`](examples/policies/strict.json) and
[`development.json`](examples/policies/development.json). A copy-ready
starting point is [`template.json`](examples/policies/template.json).
Domain references live under
[`examples/policies/reference/`](examples/policies/reference/), and the
cross-runtime strict bundle is
[`examples/policies/bundles/strict-common/`](examples/policies/bundles/strict-common/).

| Policy area | Reference |
| --- | --- |
| Human-prompt-capable approval modes | [`approvals-human.json`](examples/policies/reference/common/approvals-human.json) |
| Sandbox required | [`sandbox-required.json`](examples/policies/reference/common/sandbox-required.json) |
| Network disabled | [`network-offline.json`](examples/policies/reference/common/network-offline.json) |
| GitHub-only MCP | [`mcp-github-only.json`](examples/policies/reference/common/mcp-github-only.json) |
| Claude Bash rules | [`bash-ls-la-only.json`](examples/policies/reference/claude-code/bash-ls-la-only.json) |
| Claude sensitive files | [`sensitive-files-denied.json`](examples/policies/reference/claude-code/sensitive-files-denied.json) |
| Claude command hooks | [`no-command-hooks.json`](examples/policies/reference/claude-code/no-command-hooks.json) |
| Codex shell approvals | [`shell-human-approval.json`](examples/policies/reference/codex/shell-human-approval.json) |
| Codex writable roots | [`filesystem-workspace-only.json`](examples/policies/reference/codex/filesystem-workspace-only.json) |

### Policy authoring workflow

1. Choose the target runtime: `claude-code` or `codex`.
2. List that runtime's available controls with `kaapi rules`.
3. Copy `examples/policies/template.json` and remove requirements your team
   does not need.
4. Add only supported controls and parameters.
5. Validate the policy before applying it.
6. Test it against a known fixture and the team's real configuration.
7. Use JSON output in CI so security posture and policy verdict remain
   separate.

First list the controls available for the runtime you intend to inspect:

```console
uv run kaapi rules --runtime claude-code --format json
uv run kaapi rules --runtime codex --format json
```

Use one policy, repeat `--policy`, or load a whole directory:

```console
uv run kaapi check ~/.codex/config.toml --policy examples/policies/no-mcp.json
uv run kaapi check ~/.codex/config.toml \
  --policy examples/policies/reference/common/approvals-human.json \
  --policy examples/policies/reference/common/mcp-github-only.json
uv run kaapi check ~/.codex/config.toml \
  --policy-dir examples/policies/bundles/strict-common
```

Directory policies are loaded by sorted filename. The aggregate verdict is
`FAIL` if any policy fails, otherwise `PERMITTED_RISK` if any policy permits
baseline risk, otherwise `PASS`. Duplicate policy IDs are rejected.

To create a maintained team bundle, copy only the domains you need, edit their
closed parameters, validate the directory, and then apply it as one unit:

```console
mkdir -p policies/my-team
cp examples/policies/reference/common/approvals-human.json policies/my-team/10-approvals.json
cp examples/policies/reference/common/network-offline.json policies/my-team/20-network.json
cp examples/policies/reference/common/mcp-github-only.json policies/my-team/30-mcp.json
uv run kaapi policy validate --policy-dir policies/my-team
uv run kaapi check ~/.codex/config.toml --runtime codex --policy-dir policies/my-team
```

Each copied file remains independently runnable with `--policy`. Keep every
`id` unique after copying, especially when combining directories.

### Start from the template

Copy `examples/policies/template.json` to a new file, or start with this
secure-by-default policy using controls shared by Claude and Codex:

```json
{
  "schema_version": "1",
  "id": "my-organisation",
  "requirements": [
    {
      "control_id": "AGENT-APRV-001",
      "expectation": "pass"
    },
    {
      "control_id": "AGENT-MCP-001",
      "expectation": "pass",
      "parameters": {
        "max_configured_servers": 0
      }
    },
    {
      "control_id": "AGENT-SBOX-002",
      "expectation": "pass"
    }
  ]
}
```

Policy fields:

- `schema_version` must be `"1"`.
- `id` is a 1–64 character identifier containing letters, numbers, dots,
  underscores, or hyphens.
- `domain` optionally labels one closed area: `approvals`, `shell`,
  `filesystem`, `sandbox`, `network`, `hooks`, or `mcp`.
- `runtimes` optionally limits the policy to `claude-code`, `codex`, or
  both. Applying it to another runtime fails explicitly.
- `control_id` must be reported by `kaapi rules` for the active runtime.
- `expectation: "pass"` requires the control to pass.
- `expectation: "allow"` explicitly accepts the finding but reports
  `PERMITTED_RISK`; it does not alter the baseline.

Closed parameters are grouped by control:

| Area | Examples | Runtime |
| --- | --- | --- |
| Approvals | `allowed_modes` | Claude and Codex |
| MCP | server count, allowed/required names, auto-approval count, managed-only | Varies by parameter |
| Shell | allowed/required Bash rule patterns, maximum rules, default deny | Claude |
| Filesystem | additional directories, writable paths, required deny patterns | Varies by parameter |
| Sandbox | required enabled state, allowed modes, excluded command count | Claude and Codex |
| Network | outbound potential, domain lists, local binding, Unix sockets | Claude and Codex |
| Hooks | command count and allowed events | Claude |

Controls not provided by the active runtime fail explicitly instead of being
silently ignored. Use the runtime-specific `rules` command before sharing a
policy across Claude and Codex.

### Scenario recipes

#### Do not allow any MCP servers

This requirement is fully expressible for Claude and Codex. Use
[`no-mcp.json`](examples/policies/no-mcp.json):

```json
{
  "schema_version": "1",
  "id": "no-mcp",
  "requirements": [
    {
      "control_id": "AGENT-MCP-001",
      "expectation": "pass",
      "parameters": {
        "max_configured_servers": 0
      }
    }
  ]
}
```

A configuration with no MCP servers receives policy `PASS`. Any configured
MCP server receives policy `FAIL`.

```console
uv run kaapi policy validate examples/policies/no-mcp.json
uv run kaapi check ~/.claude/settings.json --runtime claude-code --policy examples/policies/no-mcp.json
uv run kaapi check ~/.codex/config.toml --runtime codex --policy examples/policies/no-mcp.json
```

#### If your goal is “allow only the GitHub MCP server”

Use
[`mcp-github-only.json`](examples/policies/reference/common/mcp-github-only.json).
It requires exactly one enabled server whose configuration key is `github`:

```json
{
  "schema_version": "1",
  "id": "reference.mcp-github-only",
  "domain": "mcp",
  "runtimes": ["claude-code", "codex"],
  "requirements": [
    {
      "control_id": "AGENT-MCP-001",
      "expectation": "pass",
      "parameters": {
        "max_configured_servers": 1,
        "allowed_server_names": ["github"],
        "required_server_names": ["github"]
      }
    }
  ]
}
```

1. Name the approved MCP definition `github` in Claude's `mcpServers` or
   Codex's `mcp_servers` table.
2. Validate the reference policy.
3. Run it against either configuration.
4. Add another domain policy with another `--policy`, or use a bundle.

```console
uv run kaapi policy validate examples/policies/reference/common/mcp-github-only.json
uv run kaapi check ~/.claude/settings.json --runtime claude-code \
  --policy examples/policies/reference/common/mcp-github-only.json
uv run kaapi check ~/.codex/config.toml --runtime codex \
  --policy examples/policies/reference/common/mcp-github-only.json
```

The policy fails for zero servers, a differently named server, or more than one
server. A matching GitHub configuration reports `PERMITTED_RISK` because the
built-in baseline still reports the MCP surface independently. Server names are
matched exactly and case-sensitively. The policy requirement reports counts;
the surrounding runtime report retains its documented redaction contract.

#### If your goal is “allow only `ls -la`”

For Claude, use
[`bash-ls-la-only.json`](examples/policies/reference/claude-code/bash-ls-la-only.json).
It requires `dontAsk`, exactly one configured Bash allow rule, and the exact
rule pattern `ls -la`:

```json
{
  "schema_version": "1",
  "id": "reference.claude-bash-ls-la-only",
  "domain": "shell",
  "runtimes": ["claude-code"],
  "requirements": [
    {
      "control_id": "AGENT-PERM-001",
      "expectation": "pass",
      "parameters": {
        "allowed_bash_rule_patterns": ["ls -la"],
        "required_bash_rule_patterns": ["ls -la"],
        "max_bash_allow_rules": 1,
        "require_default_deny": true
      }
    }
  ]
}
```

The corresponding Claude permission configuration is:

```json
{
  "permissions": {
    "defaultMode": "dontAsk",
    "allow": ["Bash(ls -la)"]
  }
}
```

```console
uv run kaapi policy validate examples/policies/reference/claude-code/bash-ls-la-only.json
uv run kaapi check ~/.claude/settings.json --runtime claude-code \
  --policy examples/policies/reference/claude-code/bash-ls-la-only.json
```

> **Runtime boundary:** this proves the configured Claude allow-rule set, not
> that `ls -la` is literally the only command Claude can execute. Claude Code
> has a vendor-defined built-in read-only command set that runs in every mode.
> Codex command decisions are stored in separate Starlark `.rules` files;
> Kaapi P1 does not ingest those files, so applying this Claude-only policy to
> Codex fails explicitly.

The runtime boundary follows the vendor documentation for
[Claude Code permission rules](https://code.claude.com/docs/en/permissions),
[Claude permission modes](https://code.claude.com/docs/en/permission-modes),
and [Codex rules and managed configuration](https://openai.com/index/running-codex-safely/).

#### Do not allow command hooks

For Claude, [`no-command-hooks.json`](examples/policies/no-command-hooks.json)
enforces a zero count:

```json
{
  "schema_version": "1",
  "id": "no-command-hooks",
  "requirements": [
    {
      "control_id": "AGENT-HOOK-001",
      "expectation": "pass",
      "parameters": {
        "max_command_hooks": 0
      }
    }
  ]
}
```

This control is Claude-only. Applying it to Codex fails explicitly because the
active Codex baseline does not provide that control.

```console
uv run kaapi policy validate examples/policies/no-command-hooks.json
uv run kaapi check ~/.claude/settings.json --runtime claude-code --policy examples/policies/no-command-hooks.json
```

#### Accept a development risk without hiding it

Use [`development.json`](examples/policies/development.json) as the pattern
for an explicit exception. An `allow` expectation produces
`PERMITTED_RISK` when the baseline finds the selected risk. The finding,
severity, and security posture remain unchanged.

Validate before use:

```console
uv run kaapi policy validate my-policy.json
```

Apply the policy to either runtime:

```console
uv run kaapi check ~/.claude/settings.json --runtime claude-code --policy my-policy.json
uv run kaapi check ~/.codex/config.toml --runtime codex --policy my-policy.json
```

Use `--format json` to consume `security_posture` and
`organisation_policy.verdict` independently in CI.

## Roadmap

| Phase | Status | Scope |
| --- | --- | --- |
| P0 (`v1.0.0`) | Complete | Deterministic Claude Code configuration analysis and verification foundation |
| P1 (`v1.1.0`) | Complete | Codex support, organisational policy-as-code, independent verdicts, and the in-process Python API |
| P2.1 | Complete and validated | Public policy evaluation and four-case workshop golden harness |
| P2.2A | Complete and accepted | Local FastAPI REST API with Python/HTTP parity and stable client errors |
| P2.2B–P2.4 | Planned next stages | Portable Docker service, dataset/evidence expansion, and hosting/distribution/release readiness |
| P3 | Planned backlog, not implemented | Deferred adapters, mappings, SARIF, blast-radius modelling, and usability enhancements |

P2 reuses the existing deterministic engine and will not make hosted
deployment, an LLM, or runtime execution a dependency of local Kaapi usage.
P3 is a backlog rather than a commitment to implement every listed feature.
The detailed approved roadmap is maintained in
[`wiki/pages/roadmap.md`](wiki/pages/roadmap.md).

## CLI reference

```console
uv run kaapi --help
uv run kaapi check --help
uv run kaapi doctor --help
uv run kaapi baseline --help
uv run kaapi verify --help
uv run kaapi rules --help
uv run kaapi policy --help
uv run kaapi policy validate --help
uv run kaapi version --help
```

Use `--format json` for the versioned check document, `--output FILE` to emit no
stdout, `--severity` to filter displayed findings, and `--fail-on` to select the
independent process gate. `NO_COLOR` and `--no-color` disable terminal colour.

`baseline` writes a secret-safe configured-capability snapshot. `verify`
compares observed settings with that snapshot; `--expect-reduction` requires a
strict subset and does not claim actual runtime behavior changed.

Use `--runtime codex` or an explicit `.toml` path for Codex. The thin P1
adapter evaluates approval policy/reviewer, classic sandbox mode,
workspace-write network access and writable-root counts, web-search mode,
network-proxy boundaries, and MCP server definitions. It parses and validates
`allow_login_shell`, but that field does not currently materially affect
resolution or findings.
Unsupported permission profiles, hooks, apps/plugins/skills, and other
security-relevant feature flags are reported as not evaluated.

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

Codex staged discovery uses:

```text
DIR/system/etc/codex/config.toml
DIR/home/.codex/config.toml
DIR/project/.codex/config.toml     # detected, not applied without observed trust
```

System values are below user values. Supply a project `config.toml` explicitly
to analyse that document reproducibly; automatic project-layer application
requires a future supported trust observation.
