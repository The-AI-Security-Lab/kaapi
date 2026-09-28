# Kaapi — Security Analysis for AI Coding Agents

Kaapi is an open-source [AI Security Lab](https://www.aisecuritylab.com/)
project that helps security and engineering teams understand what AI coding
agents are configured and permitted to do. It deterministically analyses
supported agent configurations, identifies security-relevant weaknesses, and
evaluates resolved capabilities against organisational security requirements.

**Current release: `v1.1.0` (P1)**

Supports Claude Code and Codex. Local, offline after installation, model-free,
deterministic, and read-only with respect to the configuration being
inspected.

## Why Kaapi

AI coding agents can be given significant authority through configuration:
filesystem access, command execution, sandbox and approval settings, external
integrations such as MCP servers, and configuration governing access to
developer environments. These settings are spread across runtime-specific
formats and can be difficult to review consistently.

Kaapi helps teams answer practical questions:

- What is this coding agent configured to do?
- Which capabilities are permitted by its resolved configuration?
- Which security-relevant configuration weaknesses are present?
- Does the configuration satisfy an organisation's security policy?
- Did a configuration change improve or weaken the assessed posture?

Kaapi answers these questions through static configuration evidence. It does
not execute the agent or claim that configured controls were enforced at
runtime.

## Current capabilities

Released `v1.1.0` includes:

| Capability | Current support |
| --- | --- |
| Claude Code | Strict JSON parsing, staged configuration discovery, capability resolution, security findings, snapshots, and verification |
| Codex | Conservative TOML parsing and resolution for supported approval, sandbox, network, filesystem, web-search, and MCP settings |
| Security posture | Versioned runtime baselines with deterministic findings, severity, evidence, remediation, and provenance |
| Organisational policy-as-code | Closed JSON policies, composition from files or directories, and independent `PASS`, `FAIL`, or `PERMITTED_RISK` verdicts |
| Change assessment | Secret-safe snapshots and deterministic comparison of assessed configuration changes |
| Interfaces | CLI workflows and the public in-process `kaapi.analyze_text(...)` Python API |
| Operating model | Local, offline after installation, model-free, deterministic, and read-only for inspected configuration |

The built-in baseline and organisational policy remain independent: accepting
a capability in organisational policy never removes or downgrades a security
finding. Claude uses baseline `0.3.1`; Codex uses baseline `0.4.0`; these
baseline versions are independent of the Kaapi package version.

## Evidence boundary

Kaapi primarily establishes evidence about:

1. **Configured authority** — security-relevant settings observed in supported
   configuration sources.
2. **Resolved permitted capabilities** — what those settings permit after
   applying Kaapi's documented precedence and resolution rules.

Configuration analysis alone does **not** establish:

3. **Observed runtime behaviour** — what the agent actually attempted or did.
4. **Independently verified security outcomes** — whether runtime controls were
   enforced or a vulnerability was remediated in practice.

> Kaapi evaluates whether coding-agent configuration and resolved capabilities
> satisfy the supplied organisational policy.

A Kaapi `PASS` is evidence about the supported configuration surfaces that
were assessed. It is not proof that an agent will obey policy at runtime.
Likewise, snapshot reduction shows an improvement between assessed
configurations; it does not by itself prove runtime remediation.

## Contents

- [Why Kaapi](#why-kaapi)
- [Current capabilities](#current-capabilities)
- [Evidence boundary](#evidence-boundary)
- [Quick start](#quick-start)
- [Results and exit codes](#results-and-exit-codes)
- [Test the released P1 milestone](#test-the-released-p1-milestone)
- [Snapshot and CI workflows](#snapshot-and-ci-workflows)
- [Organisational policy guide](#organisational-policy-guide)
- [Roadmap](#roadmap)
- [AI Security Lab](#ai-security-lab)
- [CLI reference](#cli-reference)
- [Staged discovery](#staged-discovery)
- [License](#license)

## Quick start

Run all commands from the repository root.

### 1. Install

Use Python 3.11 or later and `uv`:

```console
cd /path/to/kaapi
uv sync --frozen --group dev
uv run kaapi --version
```

The version command reports `kaapi 1.1.0`. The initial dependency installation
may require package-registry access, but Kaapi does not use a model, API key,
or network connection while analysing configuration.

### 2. Analyse Claude Code or Codex

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

### 3. Validate and apply an organisational policy

```console
uv run kaapi policy validate examples/policies/template.json
uv run kaapi check ~/.claude/settings.json --runtime claude-code --policy examples/policies/template.json
uv run kaapi check ~/.codex/config.toml --runtime codex --policy examples/policies/template.json
```

The template uses controls shared by both runtimes. Build a team-specific
policy with the [organisational policy guide](#organisational-policy-guide).

### 4. Use the Python API

The public in-process API accepts configuration content directly and returns
the same versioned structured analysis document as `kaapi check`:

```python
from pathlib import Path

from kaapi import analyze_text

claude_result = analyze_text(
    Path("settings.json").read_text(encoding="utf-8"),
    runtime="claude-code",
    source="settings.json",
)

codex_result = analyze_text(
    Path("config.toml").read_text(encoding="utf-8"),
    runtime="codex",
    source="config.toml",
)
```

Content may be a UTF-8 `str` or `bytes`. Without `source`, Kaapi uses a
deterministic synthetic evidence identifier such as `<memory:claude-code>` and
does not create a temporary file. Parsing and validation errors raise
`ConfigError`.

The released `analyze_text(...)` API does **not** accept organisational-policy
inputs. Use the CLI policy workflow for policy evaluation. Kaapi `v1.1.0` also
does not include FastAPI, an HTTP endpoint, authentication, a hosted service,
or a browser upload flow; these must not be inferred from the in-process API.

## Results and exit codes

Kaapi reports security posture and organisational-policy compliance
independently:

| Result | Question answered |
| --- | --- |
| `posture` / `security_posture` | Does the built-in runtime baseline find configured risk? |
| `organisation_policy.verdict` | Does the configuration and resolved capability set satisfy the supplied policy? |

Policy `PERMITTED_RISK` never removes or downgrades a baseline finding.

| Exit code | Meaning |
| --- | --- |
| 0 | Analysis completed and all active gates passed |
| 1 | Analysis completed but the security or policy gate failed |
| 2 | Invalid CLI usage |
| 3 | Configuration or policy parsing failed safely |

## Test the released P1 milestone

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

### P0 — Foundation · Complete

Claude Code configuration analysis, capability resolution, security posture
checks, snapshots and verification, and local CLI workflows (`v1.0.0`).

### P1 — Multi-runtime & Policy · Released (`v1.1.0`)

Codex support, organisational policy-as-code, independent security and policy
verdicts, and the public in-process Python API.

### P2 — Evaluation & API · In development

Evaluation integration, deterministic HTTP/API access, portable service
packaging, expanded security evaluations and evidence, and
distribution/deployment readiness. **P2 functionality is unreleased and is
not available in `v1.1.0`.**

### P3 — Broader Analysis & Reporting · Planned

Broader coding-agent coverage, security mappings, capability and blast-radius
analysis, machine-readable reporting, and usability improvements.

P2 will reuse the deterministic Kaapi engine; an LLM or runtime execution will
not become a dependency of local analysis. P3 is a backlog rather than a
commitment to implement every listed feature. See the
[authoritative roadmap](wiki/pages/roadmap.md) and
[decision log](Decisions.MD) for the detailed boundaries.

## AI Security Lab

Kaapi is an open-source project from
[AI Security Lab](https://www.aisecuritylab.com/). The broader Lab work covers
AI security research, practical methodology, education, and related open
projects. Kaapi focuses specifically on deterministic configuration and
configured-capability evidence for supported AI coding agents.

Project details are maintained in the
[build specification](docs/KAAPI_BUILD_SPEC_v1.3.md),
[decision log](Decisions.MD), and [project wiki](wiki/index.md).

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

## License

Kaapi is available under the [Apache License 2.0](LICENSE).
