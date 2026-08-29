# Kaapi — Build Specification v1.3

**Status:** Final normative specification for Kaapi P0.

This document is the complete technical source of truth for implementing and
accepting Kaapi P0. A developer must not need
[`SPEC_DEVIATIONS.md`](SPEC_DEVIATIONS.md) to discover required P0 behaviour.
That file is a historical and audit record explaining why this specification
differs from the frozen
[`KAAPI_BUILD_SPEC_v1.2.md`](KAAPI_BUILD_SPEC_v1.2.md).

v1.3 finalises the P0 implementation contract. It does not promote P1 or P2,
redesign the architecture, or make future interfaces or delivery dates
binding. Where this document describes a current implementation mismatch, the
normative vendor-aligned requirement remains authoritative; the bug is not the
desired behaviour.

The terms **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are normative only
when they describe P0. Text explicitly labelled roadmap, planned, historical,
or current implementation limitation is non-normative implementation context.

## 0. v1.3 consolidation record

v1.3 incorporates the accepted P0 decisions established during implementation:

- Claude Code is the only P0 analysis runtime;
- current Claude Code settings precedence, list merging, permission-rule
  ordering, mode names, and hook/bypass constraints are the semantic target;
- strict parsing, unknown-field handling, source locations, structured
  evidence, severity rationale, provenance, and redaction are specified;
- deterministic pretty output has a fixed section order, wrapping width,
  separators, capability summary, evidence presentation, resources, colour,
  and terminal-link contract;
- deterministic versioned JSON and secret-safe snapshots remain separate from
  pretty presentation;
- Python 3.11+, a standard-library CLI, zero runtime dependencies, development
  dependencies, and `uv.lock` define packaging and reproduction;
- the shipped baseline has 17 controls and the P0 fixture set is fixed below;
- understood but unresolved vendor-semantic mismatches are isolated under
  [Known P0 Correctness Limitations](#14-known-p0-correctness-limitations).

Authoritative Claude Code semantics were reverified on **2026-08-26** against
the sources in §16.

---

## 1. Product definition and boundary

Kaapi is a deterministic, local-first security posture and capability analyser
for observed AI coding-agent configuration. P0 analyses Claude Code
configuration before execution and answers:

> What does the observed configuration permit, and what observed source can
> override those controls?

Kaapi computes static **resolved/configured capability**. It does not claim to
observe actual runtime agent behaviour, prove that a capability was exercised,
or know unobserved OS permissions, credentials, containers, session state, or
future command-line arguments.

The capability model is:

```text
DECLARED CONFIGURATION
        ↓
RESOLVED AGENT POLICY
        ↓
OBSERVED LOCAL SOURCES
        ↓
INFERRED CONFIGURED CAPABILITY, WITH CONFIDENCE
```

Every finding MUST separate a directly observed fact from Kaapi's inference.
Severity and confidence are independent. The P0 core MUST be deterministic,
offline, model-free, API-free, local, read-only with respect to inspected
configuration, and secret-safe.

One `Kaapi ☕` header mark is permitted in human output. Findings and machine
output MUST NOT contain coffee jokes or decorative emoji.

### 1.1 P0 scope

P0 MUST provide:

- Claude Code `settings.json` parsing and supported local-source detection;
- resolved permission and configured-capability analysis;
- observed-source bypass detection;
- sandbox, network, hook, and MCP configuration analysis;
- versioned baseline evaluation and rule provenance;
- `check`, `doctor`, `baseline`, `verify`, `rules`, and `version`;
- deterministic pretty and JSON output;
- deterministic fixtures, known-answer tests, and stable exit codes.

### 1.2 Explicit P0 exclusions

P0 MUST NOT implement or describe as available:

- Codex, Cursor, Gemini, or GitHub Copilot configuration analysis;
- blast-radius analysis or Arcanum mapping;
- OWASP mappings;
- SARIF;
- custom organisational policy evaluation;
- `explain` or any model narration;
- runtime monitoring, agent execution, hook execution, MCP connection, DLP,
  prompt-injection execution, or runtime evidence collection;
- auto-remediation or configuration rewriting;
- a web service, hosted backend, account, telemetry, or phone-home behaviour;
- user-defined executable rules or arbitrary natural-language policy
  interpretation;
- a composite numeric security score.

P0 is a CLI and does not depend on a hosted service or another product.

---

## 2. Language, package, and reproducibility

- Python: 3.11 or later.
- Package and console command: `kaapi`.
- Build backend: Hatchling, as declared by `pyproject.toml`.
- CLI framework: standard-library `argparse`.
- Runtime dependencies: none outside the Python standard library.
- Development dependencies: `pytest` and `jsonschema` in the `dev` group.
- Reproducibility mechanism: committed `uv.lock`.
- Reproducible setup: `uv sync --frozen --group dev`.
- Execution in the managed environment: `uv run ...`; manual environment
  activation is not required.
- Package metadata license: Apache-2.0.

This repository does not establish a public Git remote or a published PyPI
release. P0 documentation MUST NOT claim a verified public clone URL or
published `pip`, `pipx`, or `uvx` installation path without separate evidence.

---

## 3. Inputs, discovery, parsing, and precedence

### 3.1 Supported inputs

`check` and `baseline` MUST accept an explicit Claude Code settings path. An
explicit path is one observed document and is the most reproducible input.

`check claude`, `check claude-code`, and `doctor` MAY detect local sources. The
P0 file detector supports, from lower to higher precedence:

1. user settings: `~/.claude/settings.json`;
2. shared-project settings: `.claude/settings.json`;
3. project-local settings: `.claude/settings.local.json`;
4. managed file settings: the platform's `managed-settings.json` path.

`--env-root DIR` MUST remap those locations to a staged directory for
deterministic testing. `--verbose` MUST show inspected paths. Detection MUST
not modify any inspected source.

Claude Code's vendor precedence also places an explicitly supplied
`--settings` session layer above local/project/user files and below managed
settings. Kaapi MUST apply that position whenever the contents of such a layer
are actually supplied through a supported observed input. Kaapi MUST NOT infer
the contents of a `--settings` value or any other unobserved source.

`--invocation STRING` is a separate observed source used only for supported
invocation-level bypass flags. It is not proof that a command ran and is not a
general parser for future Claude settings.

P0 `doctor` may count observed project `.mcp.json` server definitions for
triage. That count does not by itself add those servers to a `check` result
unless their configuration is part of the resolved observed input.

### 3.2 Strict parsing

Settings files MUST be read as UTF-8 strict JSON. The top level MUST be an
object. JSON comments, trailing commas, invalid UTF-8, invalid JSON, and invalid
shapes for supported objects/lists MUST produce a configuration parse error and
exit 3. A parse error MUST identify the source and, when available, line and
column.

The parser MUST preserve deterministic JSONPath-to-source-line locations for
evidence. When a location cannot exist, its line is `null` rather than
fabricated.

### 3.3 Supported P0 settings surfaces

The P0 parser recognises these top-level security surfaces:

```text
$schema
permissions
sandbox
hooks
mcpServers
enableAllProjectMcpServers
enabledMcpjsonServers
disabledMcpjsonServers
allowManagedMcpServersOnly
allowedMcpServers
deniedMcpServers
allowManagedPermissionRulesOnly
allowManagedHooksOnly
```

The implemented nested surface includes:

- `permissions`: `allow`, `ask`, `deny`, `defaultMode`,
  `disableBypassPermissionsMode`, `disableAutoMode`, and
  `additionalDirectories`;
- `sandbox`: `enabled`, `autoAllowBashIfSandboxed`, `excludedCommands`,
  `allowUnsandboxedCommands`, `enableWeakerNestedSandbox`, `filesystem`, and
  `network`;
- `sandbox.filesystem`: `allowWrite`, `denyWrite`, `denyRead`, `allowRead`, and
  `allowManagedReadPathsOnly`;
- `sandbox.network`: `allowedDomains`, `deniedDomains`, `allowUnixSockets`,
  `allowAllUnixSockets`, `allowLocalBinding`, `allowMachLookup`,
  `httpProxyPort`, and `socksProxyPort`;
- documented lifecycle keys inside `hooks` that the parser explicitly knows.

Recognition is not permission to overclaim complete vendor coverage. Newer or
unmodelled security fields follow §3.5.

### 3.4 Merge and precedence

For multiple observed layers, scalar and object values MUST resolve with this
vendor order, highest first:

```text
managed > supplied CLI settings > project local > shared project > user
```

Array-valued settings, including `permissions.allow`, `permissions.ask`, and
`permissions.deny`, combine across scopes rather than allowing a higher scope
to erase lower entries. Resolution MUST be deterministic and duplicates MAY be
removed without changing meaning.

Managed-only switches MUST be honoured when observed:

- `allowManagedPermissionRulesOnly` excludes non-managed permission rules;
- `allowManagedHooksOnly` excludes non-managed hooks;
- `allowManagedMcpServersOnly` constrains MCP server policy to managed data.

Permission rules from all applicable scopes are evaluated together using the
ordering in §4.1. A lower-scope deny therefore still blocks a higher-scope
allow, and the reverse is also true.

### 3.5 Field classification and unknown fields

Each parsed field MUST be classified deterministically as:

- `SUPPORTED`: evaluated by P0;
- `UNKNOWN`: security-relevant shape or field not recognised by the parser;
- `UNSUPPORTED`: known field intentionally outside P0;
- `MALFORMED`: invalid input, which exits 3.

An unknown security-relevant field MUST NOT silently pass. It produces the
layer's `AGENT-*-099` medium finding, appears in the ordered `unknown_fields`
JSON array, increments `Not evaluated`, and prevents a clean PASS. At the
default high gate this WARN result exits 0; a gate that includes medium exits
1. Known non-security fields outside P0 do not independently prevent PASS.

---

## 4. Normative Claude Code permission semantics

This section states the desired P0 semantics even where §14 records a current
implementation mismatch.

### 4.1 Rules and ordering

Permission arrays contain rules in `Tool` or `Tool(specifier)` form:

- an allow match permits the action without manual approval;
- an ask match requires confirmation;
- a deny match prevents the action;
- rule classes are evaluated `deny`, then `ask`, then `allow`; the first
  matching class determines the outcome and specificity does not reverse that
  order;
- a bare rule applies to the whole tool; a scoped rule applies only to matching
  inputs and leaves the remaining tool capability available;
- `*` deny/ask rules match all tool names;
- MCP rules use canonical `mcp__<server>__<tool>` names. A bare broad MCP allow
  glob such as `mcp__*` is not equivalent to an accepted server-specific allow.

Shared rule families MUST follow current Claude tool semantics:

- `Read(path)` applies to `Read`, `Grep`, `Glob`, and `LSP` file access;
- `Edit(path)` applies to `Edit`, `Write`, and `NotebookEdit`;
- `Bash(command)` also governs the related `Monitor` command surface;
- `WebFetch(domain:...)` is domain-scoped;
- `WebSearch` is a whole-tool rule.

Read deny rules also protect matching paths from Edit and Write under the
vendor behaviour. Rule evaluation is configuration semantics, not evidence
that a tool was called.

### 4.2 Permission modes

P0 MUST recognise `default`, `manual`, `acceptEdits`, `plan`, `auto`,
`dontAsk`, and `bypassPermissions`. `manual` is an alias for config value
`default` and MUST normalise to `default`.

An absent `permissions.defaultMode` is not universally proof of Manual mode.
Claude Code's built-in starting mode can depend on plan, account, client, and
feature availability. If Kaapi has not observed the effective session mode, it
MUST distinguish an absent configured value from an observed `default` value
and MUST NOT present the account-dependent starting mode as proven.

| Mode | Required static interpretation |
|---|---|
| `default` | Reads run without prompting; file writes, general shell, network, and other sensitive actions prompt unless a rule changes the result. The documented built-in read-only Bash subset is unprompted. |
| `acceptEdits` | Reads and in-scope file edits are unprompted. The documented common filesystem Bash subset is also unprompted only for the working directory or `additionalDirectories`; protected/out-of-scope paths and other Bash commands still prompt. |
| `plan` | Reads are available and edits remain blocked until the plan is approved. Exploratory commands may still enter the normal permission flow or an available classifier; P0 MUST NOT model plan as proof that all shell execution is impossible. |
| `auto` | Actions are reviewed by Claude Code's background classifier rather than per-action human approval. Kaapi may report broad unattended configured capability, but MUST NOT say every action is unconditionally approved or executed. |
| `dontAsk` | Any action that would require a prompt is denied. Explicit ask rules deny rather than prompt. Only pre-approved actions, the documented read-only Bash subset, and qualifying hook-approved calls can proceed. |
| `bypassPermissions` | Permission prompts and most safety checks are skipped, but current vendor deny rules remain effective and allow rules have no effect. Vendor-defined actions that no mode auto-approves remain exceptions. |

`disableBypassPermissionsMode: "disable"` and `disableAutoMode: "disable"`
MUST prevent their respective modes when the setting is observed and
applicable. A lockout state may be reported only when proved from observed
configuration.

### 4.3 Workspace trust and directories

When the trust state is observed, Kaapi MUST account for it. Project allow
rules may wait for workspace trust, while deny and ask rules apply immediately;
an untracked personal local-settings allow is treated differently by Claude
Code. When trust is not observed, Kaapi MUST state uncertainty rather than
claim that a trust-dependent allow definitely applies.

`permissions.additionalDirectories` expands the working-directory scope for
the vendor behaviours that reference it. P0 MUST include an observed value in
path-scope reasoning without exposing the raw path when doing so would reveal
sensitive configuration.

---

## 5. Resolved capability layers

The resolver MUST emit a normalized, sorted, duplicate-free representation of
configured capability. It MUST preserve the distinction between permitted and
unprompted actions and between tool permission and OS-enforced sandbox scope.

The human capability summary MUST cover, when provable:

- permission mode and allow/ask/deny counts;
- observed permission bypasses and configured lockout;
- shell commands;
- file reads and file writes;
- WebFetch and WebSearch;
- shell/network scope;
- MCP server count and MCP tool approval behaviour;
- sandbox state and escape hatches;
- configured hook event, matcher, and command count.

Risky statements use `[!]`. Secure statements remain explicit without relying
on colour. Every statement MUST be supported by parsed evidence; omission is
preferred to an unprovable claim.

### 5.1 Bypass detection

P0 recognises bypass only from an observed configuration mode or an explicitly
supplied invocation containing a supported bypass flag. Each bypass record MUST
identify mechanism, source kind, source, JSON/invocation path, and line when
available.

Kaapi MUST NOT infer future invocation flags, infer bypass from hook command
text, claim that a prompt appeared, or state that a hook activated bypass.
Current Claude hooks can request `bypassPermissions` only when the session was
already launched with bypass available and the mode is not disabled; otherwise
that update is a no-op. An observed bypass remains a critical posture fact, but
the resolved permission result MUST still preserve vendor-enforced deny rules.

### 5.2 Sandbox and filesystem

The sandbox is an OS-enforced boundary for Bash subprocesses, distinct from
permission approval. Absence of `sandbox.enabled: true` means the Claude Code
sandbox is not enabled. P0 MUST report:

- disabled sandbox;
- `allowUnsandboxedCommands` escape-hatch state, treating an absent value
  according to the vendor default;
- `excludedCommands` presence without exposing its values;
- weaker nested isolation;
- supported filesystem expansions/restrictions and socket/local-binding
  exceptions.

`allowUnsandboxedCommands: false` prevents the
`dangerouslyDisableSandbox` retry. Configured exclusions still execute outside
the sandbox. Kaapi does not test whether the host can initialise the sandbox
and MUST NOT claim runtime enforcement from configuration alone.

### 5.3 Network

Network posture MUST distinguish:

1. WebFetch/WebSearch permission rules for in-process tools;
2. the sandbox proxy boundary for Bash subprocesses;
3. configured domain, Unix-socket, and local-binding exceptions.

With sandboxing disabled, no Claude sandbox destination boundary exists. With
sandboxing enabled but no strict allowlist, no domains are pre-approved, yet a
new destination may enter the permission/classifier flow; this is not proof of
a fixed deny boundary. `allowedDomains`, `deniedDomains`, and compatible
`WebFetch(domain:...)` rules contribute to the configured sandbox boundary.
Kaapi MUST describe configured potential, not claim that a connection occurred.

### 5.4 Hooks

P0 statically identifies configured lifecycle hooks. Command hooks are a risk
surface because vendor documentation says they execute with the user's OS
permissions. P0 MUST retain only safe metadata: event, printable/truncated
matcher, and command count. It MUST render command values as `<present>` and
MUST NOT execute, echo, reconstruct, or reason from raw command text.

A configured hook does not prove that it ran. Kaapi MUST NOT say that hooks ran
or did not run. Dynamic hook output, permission updates, and runtime decisions
are not observed by a settings-only scan. Deny and ask rules remain effective
against hook allow decisions under current vendor semantics.

### 5.5 MCP

P0 reports configured MCP server definitions and supported enabled/disabled or
managed server controls without connecting to a server. Server names MAY be
used as identifiers; MCP command, argument, token, and environment values MUST
be redacted as `<present>` or omitted.

A configured server does not prove that it connected, that a tool was exposed,
or that a tool ran. MCP server configuration does not itself auto-approve MCP
tools. Approval behaviour derives from permission rules and mode, with
interactive-required MCP metadata treated conservatively when observed.

---

## 6. Baseline and posture evaluation

The AI Security Lab Coding-Agent Security Baseline is a versioned,
evidence-backed control set, not a standard. Controls MUST remain declarative,
load through the baseline module, carry stable IDs, and be versioned
independently from Kaapi. `kaapi version` and `check` MUST derive the actual
loaded count rather than hard-code it.

The shipped P0 baseline is `asl-coding-agent-baseline 0.3.1` with 17 controls:

| ID | Default severity | Trigger or purpose |
|---|---|---|
| `AGENT-APRV-001` | critical | observed permission bypass |
| `AGENT-APRV-002` | high | automatic permission mode |
| `AGENT-PERM-001` | high | unprompted shell execution |
| `AGENT-PERM-002` | high | unprompted file mutation |
| `AGENT-SBOX-001` | high | sandbox absent or disabled |
| `AGENT-SBOX-002` | high | unsandboxed retry permitted |
| `AGENT-SBOX-003` | high | weaker nested isolation |
| `AGENT-SBOX-004` | medium | excluded sandbox commands |
| `AGENT-NET-001` | high | outbound capability lacks a configured destination boundary |
| `AGENT-HOOK-001` | medium | executable hook surface configured |
| `AGENT-MCP-001` | medium | MCP capability configured |
| `AGENT-APRV-099` | medium | unknown approval field |
| `AGENT-PERM-099` | medium | unknown permission field |
| `AGENT-SBOX-099` | medium | unknown sandbox field |
| `AGENT-NET-099` | medium | unknown network field |
| `AGENT-HOOK-099` | medium | unknown hook field |
| `AGENT-MCP-099` | medium | unknown MCP field |

Every control MUST have `id`, `title`, `layer`, `rationale`, default severity,
platform applicability, tested versions/sources, `last_verified`, support
confidence, at least one structured provenance source, and remediation.
Framework `references` are empty in P0; OWASP/Arcanum mapping is unavailable.

The posture algorithm is:

- FAIL when one or more evaluated findings are critical or high;
- WARN when findings exist but none is critical/high;
- PASS only when no finding exists and no unknown security field prevents it.

Severity filtering changes displayed findings, not full posture counts.
`--only` and `--ignore` change the evaluated control set and therefore the
derived totals. Passed controls equal evaluated controls minus distinct failed
control IDs.

---

## 7. Finding, evidence, provenance, and redaction model

Every P0 finding has exactly these fields:

```text
id
source_type
title
layer
observed
inference
severity
confidence
sources
references
remediation
evidence
why_severity
```

`source_type` is `baseline` in P0. `layer` is one of `approvals`,
`permissions`, `sandbox`, `network`, `hooks`, or `mcp`. `observed` contains
direct evidence; `inference` contains Kaapi's interpretation;
`why_severity` explains the assigned severity; and `confidence` describes the
finding inference rather than rule support confidence.

`evidence` is a deterministic ordered array:

```json
{
  "source": "path or observed source",
  "line": 14,
  "path": "$.hooks.PostToolUse",
  "detail": "redacted human-readable evidence"
}
```

`line` is an integer or `null`. Multiple observed layers may produce multiple
records; source and array order MUST be stable. Evidence numbering is a pretty
projection only and MUST NOT alter the JSON array.

`sources` stores complete structured control provenance, including canonical
URLs and access dates. `references` is reserved structured mapping data and is
empty for shipped P0 controls. Pretty `Resource` labels are projections of
`sources`; they do not replace them.

The following MUST never appear in pretty output, JSON, snapshots, errors, or
documentation examples: secret values, tokens, environment values, raw hook
commands, MCP command values, or MCP arguments. Presence is represented as
`<present>`. Redaction MUST occur before rendering or snapshot serialization.

---

## 8. CLI contract

The P0 surface is:

```text
kaapi doctor
kaapi check [subject]
kaapi baseline <settings-path>
kaapi verify <settings-path> --baseline <snapshot>
kaapi rules [rule-id]
kaapi version
```

Bare `kaapi`, `kaapi --help`, and `-h` print help and exit 0. Every subcommand
MUST provide `--help` and `-h`, non-empty option documentation, and at least one
example.

### 8.1 Common options

- `--runtime {claude-code,codex,auto}`: `auto` or `claude-code` selects the P0
  Claude parser; `codex` is reserved and MUST return usage error 2.
- `--format {pretty,json}`: P0 output formats; SARIF is not accepted.
- `--output FILE` / `-o FILE`: write requested output and emit no stdout.
- `--quiet` / `-q`: concise human result, without pretty sections or escapes.
- `--verbose` / `-v`: diagnostics including inspected paths.
- `--no-color`: disable ANSI; the presence of `NO_COLOR` does the same.
- `--path FILE`: explicit settings path alternative to positional path.
- `--env-root DIR`: staged local source root.
- `--invocation STRING`: explicit bypass-observation source.

`--quiet` and `--verbose` are mutually exclusive. P1/P2 commands and options
MUST return usage error 2 in P0.

A command MUST reject simultaneous positional and `--path` settings inputs as
a usage error rather than guessing which source wins.

### 8.2 `check`

The subject is `claude`, `claude-code`, or a settings path.

- `--severity {info,low,medium,high,critical}` sets the minimum displayed
  severity; default `info`.
- `--fail-on {none,info,low,medium,high,critical}` sets the exit-1 threshold;
  default `high`.
- repeatable `--only IDS` and `--ignore IDS` accept comma-separated known
  control IDs; unknown IDs are usage errors.

`--fail-on` affects process gating only. It MUST NOT change posture, counts, or
findings. `--fail-on none` returns 0 for findings while still reporting the
true PASS/WARN/FAIL posture and showing process exit code 0.

### 8.3 Exit codes

| Code | Meaning |
|---:|---|
| 0 | Command succeeded and the configured gate passed. |
| 1 | Analysis succeeded and found a result at or above the gate, or asserted verification failed. |
| 2 | Usage, unsupported-surface, or snapshot-contract error. |
| 3 | Configuration parse error. |
| 4 | Internal error or interruption. |

Exit 1 MUST never represent a tool crash.

### 8.4 Version and rules

`version` and `--version` MUST report Kaapi version, baseline name/version,
actual loaded control count, and Python version. `rules` lists deterministic
IDs/titles/severities; `rules ID` shows rationale, support confidence,
verification date, full provenance, and remediation.

---

## 9. Pretty-output contract

`check` pretty output begins with exactly one `Kaapi ☕` mark, `check`, subject,
runtime, baseline name/version, and actual loaded rule count. The runtime and
baseline metadata lines use normal terminal colour for readability.

The major sections appear exactly in this order:

1. `INSPECTION`
2. `POSTURE`
3. `RESOLVED AGENT CAPABILITY`
4. `FINDINGS`
5. `RESULT`

The deterministic inspection trace is:

```text
→ Configuration loaded
→ Permissions resolved
→ Sandbox checked
→ Hooks checked
→ MCP checked
→ Network checked
→ Baseline evaluated
```

These arrows report completed inspections. There are no delays, spinners,
timestamps, animations, terminal-width measurements, or simulated progress.

Major sections and individual findings use this fixed 72-character separator:

```text
────────────────────────────────────────────────────────────────────────
```

Wrapping is deterministic at approximately 72 columns. `POSTURE` includes
verdict; critical/high/medium/low/info counts; fields not evaluated; controls
evaluated; and passed controls.

Findings are grouped in triage order: approvals, permissions, sandbox,
network, hooks, MCP. Within a group, stable ID and evidence ordering applies.
Every finding renders severity, ID, title, evidence, Observed, Inference, Why
severity, Confidence, Remediation, and exactly one Resource line.

Exactly one evidence record renders as `Evidence:`. Multiple records render as
`Evidence 1:`, `Evidence 2:`, and so on, separated readably.

Resources use short labels such as `Claude Code - permissions`. Multiple labels
use ` · ` on one Resource line. Full URLs do not replace labels in plain pretty
output.

`RESULT` contains posture, complete severity summary, a short posture-appropriate
next action, and the actual process exit code after `--fail-on` is applied.

### 9.1 Colour and OSC 8

Colour is supplementary and only enabled on interactive stdout:

- cyan section headings;
- dim grey separators and secondary metadata such as the process-exit line;
- red FAIL, critical, high, and risky capability states;
- yellow WARN and medium;
- blue low;
- green PASS and secure capability states;
- normal terminal colour for explanatory and header metadata text.

`--no-color`, `NO_COLOR`, non-TTY stdout, JSON, quiet output, and output files
MUST contain no ANSI colour codes. `[!]` and textual labels carry the same
meaning without colour.

OSC 8 links are optional decoration only when supported by an interactive
terminal. The visible short label is always present. Unsupported terminals
degrade to plain labels. Captured, redirected, JSON, quiet, no-colour, and file
output MUST contain no OSC 8 sequence. Copy/paste remains readable.

---

## 10. JSON contract

`check --format json` MUST conform to
[`kaapi/schemas/check-v1.schema.json`](../kaapi/schemas/check-v1.schema.json).
The document contains:

- schema and Kaapi versions;
- baseline name/version;
- runtime and subject;
- posture and all severity counts;
- passed controls;
- sorted normalized resolved capability;
- ordered unknown security fields;
- ordered findings selected by `--severity`, each with its complete P0 fields.

Posture, counts, and passed controls are derived from the full evaluated result
even when `--severity` filters the findings array rendered to the user.

JSON has no ANSI, OSC 8, emoji, pretty labels, or presentation numbering.
Canonical provenance URLs remain in `sources`; evidence remains an ordered
array; redaction remains `<present>`. Identical scans MUST produce
byte-identical UTF-8 JSON, including a final newline. Pretty-output changes
MUST NOT silently change the versioned JSON contract.

---

## 11. Snapshot and verification contract

`baseline` emits snapshot JSON to stdout by default or deliberately writes it
when `--output`/`-o` is requested. It MUST NOT modify the inspected settings.
A snapshot contains only:

```json
{
  "schema_version": "1",
  "kaapi_version": "1.0.0",
  "baseline_version": "0.3.1",
  "runtime": "claude-code",
  "capabilities": [],
  "config_fingerprint": "sha256:...",
  "findings": []
}
```

Capabilities and findings are normalized, ordered, and secret-safe. Snapshots
MUST NOT store raw configuration, raw evidence locations, hook commands, MCP
commands/arguments/environment, tokens, or secrets.

`verify` loads a compatible snapshot, rescans the current settings, and
deterministically reports removed and added capabilities. Without
`--expect-reduction`, it reports the delta and exits 0. With the flag, PASS
requires the current capability set to be a strict subset of the snapshot;
otherwise exit 1. Output says `resolved/configured capability reduced`, never
that runtime agent behaviour was reduced.

An unsupported snapshot `schema_version`, unsupported runtime, malformed
snapshot, or unreadable snapshot MUST be refused clearly as exit 2. A newer
implementation reading an older snapshot either compares it correctly or
refuses; it never silently miscompares.

---

## 12. Doctor contract

`doctor` is read-only local environment triage and never gates CI. It exits 0
after a successful report even if its posture summary is FAIL. Human output
reports detected Claude Code, detected Codex presence, observed MCP server
count, posture, critical/high/medium counts, and passed controls. Codex
detection is presence-only; P0 does not parse Codex configuration.

`doctor --env-root fixtures/env` is the deterministic workshop form. JSON
doctor output is deterministic and decoration-free. Verbose mode lists paths.

---

## 13. Fixtures, tests, and P0 completion gate

### 13.1 Required fixtures

Every P0 fixture MUST include an `EXPECTED.md`:

| Fixture | Required result |
|---|---|
| `fixtures/loose/settings.json` | FAIL, exit 1; broad permissions, disabled sandbox, network, hook, MCP findings |
| `fixtures/hardened/settings.json` | PASS, exit 0; strict configured reduction |
| `fixtures/bypass/settings.json` | FAIL, exit 1; observed bypass headlined |
| `fixtures/malformed/settings.json` | parse error, exit 3 |
| `fixtures/unknown-field/settings.json` | WARN, default exit 0; unknown field is not evaluated |
| `fixtures/env` | deterministic staged `doctor`, report-only exit 0 |

Codex, policy, blast-radius, SARIF, and future-runtime fixtures are not P0.

### 13.2 Acceptance tests

`uv run pytest` is the acceptance command. P0 tests MUST cover:

- strict parsing, source lines, precedence, rule ordering, supported modes,
  and the correctness limitations once fixed;
- all 17 controls with known-answer cases;
- fixture verdicts and exit codes;
- repeated byte-identical pretty and JSON output;
- JSON Schema validation;
- offline core with blocked sockets;
- checksummed read-only detection and scanning;
- secret, raw-command, MCP, argument, token, and environment redaction;
- observed-only bypass sourcing and no bypass inference;
- unknown-field WARN behaviour;
- help/version/rules and `--severity`, `--fail-on`, `--only`, `--ignore`,
  `--quiet`, `--verbose`, `--format`, `--output`, and no-colour contracts;
- pretty section order, fixed separators/wrapping, posture counts, capability
  statements, finding group order, evidence numbering, resource labels,
  optional OSC 8, restrained colour, and actual RESULT exit code;
- absence of ANSI/OSC 8 in captured, redirected, JSON, quiet, `--no-color`,
  `NO_COLOR`, and file output;
- snapshot secrecy, schema refusal, observational verify, and strict reduction;
- P1/P2 surfaces returning usage error 2.

Known-answer correctness is the quality bar; no coverage percentage is
required unless separately enforced by the repository.

### 13.3 Completion gate

The workshop P0 gate requires all fixtures, commands, deterministic/offline/
read-only/security tests, pretty/JSON contracts, and baseline-to-verify flow to
pass without a model, API key, or network connection.

Kaapi MUST NOT claim complete current Claude Code semantic parity while any
item in §14 remains unresolved. Passing the existing workshop suite and
achieving complete current-vendor-semantic conformance are distinct claims.

---

## 14. Known P0 Correctness Limitations

This section records understood mismatches between the normative requirements
above and the current implementation. These are not desired behaviour and MUST
be corrected and tested before claiming complete current-semantics parity.

### 14.1 Shared tool-rule families

**Vendor requirement:** `Read(...)` applies to Read, Grep, Glob, and LSP;
`Edit(...)` applies to Edit, Write, and NotebookEdit; Bash rules also cover the
Monitor surface.

**Current implementation:** the resolver defines the read family as Read,
Glob, Grep, LS, and NotebookRead, omits LSP, and resolves those names
independently. It does not model Monitor as part of Bash.

**Correction required:** implement and test the vendor rule-family expansion,
including scoped rules, without treating LS or NotebookRead as undocumented
Read-family substitutes.

### 14.2 `dontAsk` ask rules

**Vendor requirement:** an explicit ask match is denied in `dontAsk`; no prompt
is collected.

**Current implementation:** a matching ask rule can be represented as
permitted but approval-required.

**Correction required:** deny explicit ask matches in this mode and add
positive/negative known-answer cases.

### 14.3 Command-specific mode semantics

**Vendor requirement:** default/manual and `dontAsk` include a documented
read-only Bash subset; `acceptEdits` additionally auto-approves documented
filesystem commands only within working/additional directories; plan mode can
send exploratory commands through the normal permission/classifier flow.

**Current implementation:** Bash is resolved at whole-tool granularity. The
mode-specific command subsets and plan-mode exploratory command path are not
modelled unless an explicit Bash rule changes the whole tool state.

**Correction required:** add command-scoped normalized capability or an
equivalent conservative representation and test path scope and protected-path
exceptions.

### 14.4 Bypass and deny interaction

**Vendor requirement:** current Claude documentation states that deny rules
remain effective in `bypassPermissions`; allow rules have no effect.

**Current implementation:** an observed bypass re-adds every considered tool
to permitted and unprompted sets after deny evaluation, making declared denies
appear ineffective.

**Correction required:** keep the critical observed-bypass finding while
preserving applicable deny results in resolved capability. This is a current
vendor-semantics correction to the older v1.2 assumption, not an architecture
change.

### 14.5 Trust, additional directories, and source coverage

**Vendor requirement:** project allow rules can depend on workspace trust;
deny/ask rules apply before trust; `additionalDirectories` changes path scope;
an observed CLI `--settings` layer sits below managed and above local settings.

**Current implementation:** it merges detected file rules without an observed
workspace-trust state, parses but does not apply `additionalDirectories` to
path capability, and has no general input for resolving arbitrary inline/file
Claude `--settings` content as a distinct layer.

**Correction required:** model only observed trust and source data, carry
uncertainty otherwise, and add staged known-answer fixtures for each layer.

### 14.6 Network boundary simplification

**Vendor requirement:** in-process WebFetch/WebSearch permissions and the Bash
sandbox proxy are distinct. An enabled sandbox without pre-approved domains
prompts/classifies new destinations unless a strict boundary denies them.

**Current implementation:** network capability is collapsed to
`unrestricted`, `restricted`, or `denied`; a wildcard sandbox deny can remove
the in-process web tools from resolved capability. This can conflate sandbox
subprocess reachability with tool permission.

**Correction required:** represent tool permission and sandbox destination
scope separately and add tests for no allowlist, strict denial, and WebFetch
permission combinations.

### 14.7 Absent permission mode

**Vendor requirement:** an omitted `permissions.defaultMode` does not prove
that every Claude client/account starts in Manual mode; the built-in starting
mode can depend on account, plan, feature availability, and client.

**Current implementation:** an absent value normalises unconditionally to
`default` and is rendered as the permission mode.

**Correction required:** represent configured mode separately from an
unobserved effective session default, and add tests that prevent a definitive
mode claim when the setting is absent.

### 14.8 Supported-labelled fields not fully resolved

**Vendor requirement:** a field labelled `SUPPORTED` contributes to the
relevant resolved capability or is explicitly reported as not evaluated.
Managed MCP allow/deny controls, supported sandbox filesystem restrictions,
and supported network exceptions affect their respective layers.

**Current implementation:** several parser-recognised fields are not fully
consumed by capability resolution. Examples include managed MCP allow/deny
policy, filesystem `denyRead`/`denyWrite`/`allowRead`, `allowMachLookup`, proxy
ports, and parts of enabled/disabled MCP selection. They can therefore be
classified as supported without a corresponding capability effect.

**Correction required:** either implement deterministic semantics and
known-answer tests for each field or classify it as unsupported/unknown so
Kaapi cannot report it as evaluated.

Dynamic hook output, actual MCP connection/tool metadata, OS sandbox
availability, and actual tool execution are intentionally unobserved P0
boundaries, not bugs, provided Kaapi makes no claim about them.

---

## 15. P0 boundary and non-binding roadmap

All roadmap items are planned and unavailable in P0. Future interfaces and
delivery dates are not committed. No future runtime is added to current P0 CLI
analysis choices by this document. Support requires authoritative vendor-
semantics verification, provenance-backed controls, deterministic fixtures,
and known-answer tests.

### P1

- Codex configuration support.
- Custom organisational security policies evaluated alongside the built-in
  baseline. A policy may tighten or parameterise supported requirements but
  cannot suppress, downgrade, replace, or weaken a baseline finding.

### P2

- Cursor configuration support.
- Gemini configuration support.
- GitHub Copilot configuration support.
- `explain` remains a separate non-blocking candidate unless explicitly
  removed by a later specification.

The frozen v1.2 document also contains blast radius, Arcanum/OWASP mappings,
and SARIF as design candidates. They are unavailable in P0 and are not delivery
commitments in this roadmap.

Kaapi's roadmap ends at P2. There is no P3 roadmap. Cloud-provider
integrations, hosted agent services, and runtime monitoring are outside the
roadmap.

---

## 16. Authoritative Claude Code references

Reverified **2026-08-26**:

- [Claude Code settings](https://code.claude.com/docs/en/settings)
- [Claude Code permissions](https://code.claude.com/docs/en/permissions)
- [Claude Code permission modes](https://code.claude.com/docs/en/permission-modes)
- [Claude Code sandboxing](https://code.claude.com/docs/en/sandboxing)
- [Claude Code tools reference](https://code.claude.com/docs/en/tools-reference)
- [Claude Code hooks reference](https://code.claude.com/docs/en/hooks)

Baseline provenance MUST retain source-specific access dates in the control
data. This section records the specification-level semantic verification date;
it does not silently rewrite shipped control metadata.

---

## 17. Final reviewer checklist

- [ ] A developer can implement all P0 behaviour from this document alone.
- [ ] No normative P0 requirement exists only in `SPEC_DEVIATIONS.md`.
- [ ] Current implementation bugs appear only as limitations, not desired
      semantics.
- [ ] Claude Code is the only analysed runtime.
- [ ] Observed fact, inference, severity, confidence, and provenance remain
      distinct.
- [ ] Bypass is observed-only and deny-aware.
- [ ] Unknown security fields prevent PASS.
- [ ] Pretty, JSON, snapshot, exit, redaction, and deterministic contracts are
      implemented and tested.
- [ ] The core is offline, local, read-only, model-free, and secret-safe.
- [ ] The 17-control baseline and P0 fixtures pass known-answer tests.
- [ ] P1/P2 surfaces remain unavailable and there is no P3 roadmap.
