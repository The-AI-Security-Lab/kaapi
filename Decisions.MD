# Kaapi P0 Decision Log

This log is append-only. Superseded decisions remain in place and are replaced
only by a later entry that explicitly names the earlier decision.

## DEC-001 — Clean-room source boundary

- Date: 2026-08-29
- Context: The workspace contains only `docs/KAAPI_BUILD_SPEC_v1.3.md`. The task
  prohibits inspecting or copying a previous Kaapi implementation.
- Decision: Use only the v1.3 specification, the Python standard library, the
  declared development tools, and (only if semantic verification becomes
  necessary) the authoritative Claude Code references named by the spec.
- Rationale: This preserves the clean-room requirement and makes the normative
  v1.3 document the sole product contract.
- Alternatives considered: Search for historical Kaapi artifacts or infer APIs
  from another implementation; rejected as explicitly out of scope.
- Affected files: Entire repository.
- Validation: Repository inventory before implementation showed only the v1.3
  specification; final inventory and scope tests will check that no excluded
  runtime or feature surface was added.

## DEC-002 — Package architecture and dependency boundary

- Date: 2026-08-29
- Context: P0 requires Python 3.11+, Hatchling, `argparse`, no runtime
  dependencies, declarative baseline loading, and deterministic local analysis.
- Decision: Implement a small `kaapi` package split into parsing/discovery,
  resolution, baseline evaluation, rendering, snapshots, and CLI modules. Store
  controls and JSON Schema as package data. Runtime code will use only the
  standard library; `pytest` and `jsonschema` will exist only in the `dev` group.
- Rationale: Module boundaries mirror the normative processing stages while
  keeping the runtime auditable, offline, and deterministic.
- Alternatives considered: A CLI framework, validation library, or database;
  rejected because each would violate or complicate the zero-runtime-dependency
  contract.
- Affected files: `pyproject.toml`, `kaapi/**`, `uv.lock`.
- Validation: Packaging tests, `uv sync --frozen --group dev`, import inspection,
  and offline socket-blocking tests.

## DEC-003 — Source discovery and staged-root layout

- Date: 2026-08-29
- Context: The spec defines precedence but does not prescribe the internal
  directory layout beneath `--env-root`.
- Decision: The canonical staged layout is `home/.claude/settings.json`,
  `project/.claude/settings.json`, `project/.claude/settings.local.json`, and
  `managed/managed-settings.json`, ordered user, shared, local, managed. For
  portability, detection also recognises unambiguous root-level equivalents
  (`.claude/...` and `managed-settings.json`) only when the canonical candidate
  for that layer is absent. Project `.mcp.json` is triage-only. Explicit settings
  paths are scanned as one observed `explicit` document and are not combined
  with unobserved discovery layers.
- Rationale: This gives deterministic fixtures while remaining useful for
  simple staged trees and never inventing source contents.
- Alternatives considered: Mirror platform absolute managed paths below the
  fixture root; rejected as platform-coupled and not specified.
- Affected files: Discovery module, `fixtures/env`, README.
- Validation: Precedence, fallback-path, verbose-path, doctor, and read-only
  checksum tests.

## DEC-004 — Supplied CLI settings layer

- Date: 2026-08-29
- Context: Vendor precedence includes a supplied `--settings` layer, while the
  Kaapi P0 CLI exposes an explicit settings path but no separate option carrying
  both discovered settings and a supplied session layer.
- Decision: Treat a direct settings-path scan as one reproducible observed
  document. Do not pretend it is merged with discovery. The merge engine will
  nevertheless expose and test an internal `supplied` layer at the normative
  position `managed > supplied > project-local > shared > user`, so supported
  observed callers can supply it without changing semantics.
- Rationale: This satisfies observed-source-only behavior and the stated
  precedence without inventing a CLI surface absent from §8.
- Alternatives considered: Reinterpret `--path` as an extra layer on top of
  auto-discovery; rejected because an explicit path is specified as one observed
  document.
- Affected files: Parser/merge module and tests.
- Validation: Direct-path and five-layer known-answer tests.

## DEC-005 — Strict JSON and source locations

- Date: 2026-08-29
- Context: Strict JSON plus deterministic JSONPath-to-line evidence is required,
  but the standard decoder does not expose node locations.
- Decision: Validate and decode with `json.loads`, then run a deterministic,
  non-evaluating JSON token walk over the same text to map every object member
  and array element JSONPath to its source line. Invalid UTF-8, JSON, top-level
  type, and supported shapes are configuration errors (exit 3). Missing
  locations remain `null`.
- Rationale: It preserves standard JSON semantics and exact line evidence
  without adding a runtime parser dependency.
- Alternatives considered: Regex-only key lookup (ambiguous with repeated keys)
  and third-party parsers (runtime dependency); rejected.
- Affected files: Parser module and parsing tests.
- Validation: Comments, trailing commas, invalid UTF-8/JSON/shapes, repeated
  nested keys, and line/column tests.

## DEC-006 — Unknown-field classification

- Date: 2026-08-29
- Context: Unknown security fields must map to the layer-specific `*-099`
  control, but the spec does not enumerate every known non-security Claude
  setting.
- Decision: Use an explicit allowlist of documented, non-security top-level
  fields as `UNSUPPORTED`; all other unknown top-level fields are conservative
  approval-layer unknowns. Unknowns below `permissions`, `sandbox`,
  `sandbox.network`, `hooks`, and MCP surfaces map to their matching layer.
  Parser-recognised P0 fields are implemented in resolution rather than merely
  labelled supported.
- Rationale: Conservative classification prevents silent security passes while
  avoiding findings for familiar display/model/telemetry configuration.
- Alternatives considered: Ignore all unknown top-level fields; rejected by
  §3.5. Treat all non-security vendor settings as known dynamically; rejected
  because it would require network/current-schema dependence.
- Affected files: Parser, resolver, baseline evaluator, tests.
- Validation: One known non-security and one unknown field per security layer,
  ordered `unknown_fields`, WARN posture, and medium gate tests.

## DEC-007 — Merge semantics and provenance

- Date: 2026-08-29
- Context: Objects/scalars use precedence, arrays combine, permission classes
  preserve deny/ask/allow order, and evidence must retain all observed sources.
- Decision: Recursively overlay object/scalar values from low to high, combine
  arrays low-to-high with stable semantic de-duplication, and keep immutable
  per-layer parsed documents and line maps alongside the merged value. Apply
  managed-only exclusion switches after merge and before rule evaluation.
- Rationale: This separates effective values from provenance and keeps both
  deterministic.
- Alternatives considered: Flatten to a single dictionary and infer provenance
  later; rejected because it loses evidence and managed-only filtering context.
- Affected files: Parser/merge, evidence helpers, tests.
- Validation: Cross-layer scalar/object/array, duplicate, managed-only, and
  lower-deny/higher-allow known-answer tests.

## DEC-008 — Permission and mode resolution

- Date: 2026-08-29
- Context: The normative model requires deny-before-ask-before-allow, shared
  rule families, scoped residual capability, seven modes, lockouts, trust
  uncertainty, and deny-aware bypass.
- Decision: Parse permission rules into normalized class/tool/specifier records;
  expand `Read` to Read/Grep/Glob/LSP, `Edit` to Edit/Write/NotebookEdit, and
  Bash to Monitor. Evaluate classes before specificity. Preserve scoped and
  residual states. Normalize `manual` to configured `default`; represent an
  absent mode as `configured_mode: null` with explicit uncertainty. In
  `dontAsk`, ask outcomes are denied. In bypass mode, applicable denies remain
  denied and allows do not alter mode behavior. Unsupported/disabled auto or
  bypass modes are reported as locked out rather than active.
- Rationale: This directly applies §§4 and 14 instead of perpetuating the listed
  old implementation mismatches.
- Alternatives considered: Whole-tool booleans or specificity-first matching;
  rejected as normatively incorrect.
- Affected files: Resolver, capability output, baseline evaluation, tests.
- Validation: Rule-family, wildcard, scoped residual, all modes, lockout,
  `dontAsk`, bypass/deny, trust uncertainty, and additional-directory tests.

## DEC-009 — Command-specific built-ins and path scope

- Date: 2026-08-29
- Context: The spec mandates mode-specific command subsets but does not include
  the vendor's complete command-name tables in the build document.
- Decision: Represent the documented concept conservatively as normalized
  categories (`shell.read_only_subset` and
  `shell.in_scope_filesystem_subset`) rather than asserting individual command
  names. General Bash remains approval-required/denied unless an observed rule
  changes it. `additionalDirectories` changes the in-scope category and is
  represented by a count, never raw path values. Plan-mode exploratory shell is
  represented as entering permission/classifier flow, not as blocked.
- Rationale: An equivalent conservative representation is explicitly allowed by
  §14.3 and avoids inventing a vendor command list not contained in the spec.
- Alternatives considered: Hard-code recalled shell utilities; rejected because
  current semantics could only be verified from authoritative docs and exact
  names are unnecessary to satisfy the static category contract.
- Affected files: Resolver, renderers, tests.
- Validation: Known-answer mode and directory-scope tests ensure no whole-shell
  overclaim.

## DEC-010 — Capability data model and verification set

- Date: 2026-08-29
- Context: Human output must describe both security controls and effective
  capabilities, while snapshot verification requires strict set reduction.
- Decision: Keep structured posture metadata separate from a normalized,
  sorted, duplicate-free set of positively available configured capabilities.
  Restrictions (for example sandbox enabled or WebFetch denied) remain
  structured metadata and do not become positive capability-set members.
  Snapshots compare only this positive set; a strict reduction means
  `current < baseline` in mathematical set terms.
- Rationale: Otherwise hardening adds restriction strings and can never be a
  strict subset of a loose snapshot.
- Alternatives considered: Compare findings or arbitrary status strings;
  rejected because the contract explicitly compares resolved/configured
  capabilities.
- Affected files: Resolver, snapshot, verify, fixtures, schema.
- Validation: Loose-to-hardened strict-subset gate plus equal and mixed-delta
  tests.

## DEC-011 — Sandbox, network, hook, and MCP boundaries

- Date: 2026-08-29
- Context: These layers must remain distinct and observed-only; several fields
  listed as supported must influence resolution.
- Decision: Model sandbox process isolation separately from tool approval;
  treat absent `allowUnsandboxedCommands` as the vendor default `true`; represent
  filesystem allow/deny/read/write fields as boundary metadata; and keep
  in-process WebFetch/WebSearch states separate from sandbox domain/socket/
  binding/proxy boundaries. Treat `deniedDomains: ["*"]` with no contrary
  allowances as a strict subprocess destination boundary. Count hooks by event,
  printable/truncated matcher, and command presence only. Resolve MCP server
  selection using enabled/disabled and allowed/denied controls; definitions
  never imply tool approval. Managed-only switches exclude non-managed hooks,
  rules, or MCP definitions as required.
- Rationale: This implements the §14 corrections and prevents runtime or
  connectivity claims from static configuration.
- Alternatives considered: One network enum, executing hooks, or probing MCP;
  rejected as incorrect or explicitly prohibited.
- Affected files: Resolver, analyzer, renderers, tests.
- Validation: Boundary combinations, all supported fields, redaction, no socket
  use, and managed-control tests.

## DEC-012 — Declarative controls and provenance

- Date: 2026-08-29
- Context: P0 mandates exactly 17 declarative controls at baseline 0.3.1 with
  complete provenance and no OWASP/Arcanum mappings.
- Decision: Ship the 17 controls in package JSON and load/validate them at
  runtime. Each control carries stable metadata, a source-specific access date,
  a canonical URL from §16, and empty `references`. Control predicates remain
  named built-in code, not executable data or user policy.
- Rationale: This keeps policy metadata declarative while avoiding executable
  user rules and preserving zero dependencies.
- Alternatives considered: Hard-code the count/metadata or implement a generic
  policy DSL; rejected by §§6 and 1.2.
- Affected files: `kaapi/data/baseline-0.3.1.json`, baseline loader/evaluator,
  tests.
- Validation: Loaded-count, complete-field, provenance URL/access-date,
  `rules`, and 17 known-answer control tests.

## DEC-013 — Redaction and fingerprints

- Date: 2026-08-29
- Context: Secrets, environment values, hook commands, MCP command/args, and
  tokens must never reach any output, snapshot, error, or example.
- Decision: Parse raw data only in memory, derive safe metadata immediately,
  and expose only redacted models to analysis/rendering. Hook and MCP values are
  replaced with `<present>` before evidence construction. Configuration
  fingerprints hash canonical JSON bytes but never reveal those bytes. Errors
  mention source/location/reason only and never echo input fragments.
- Rationale: Early redaction narrows the set of code able to leak secrets.
- Alternatives considered: Renderer-only redaction; rejected because snapshots
  and error paths could bypass it.
- Affected files: Parser safe projection, resolver, snapshot, renderers, tests.
- Validation: Canary secrets across all sensitive fields and malformed/error
  paths; full stdout/stderr/file/snapshot scans.

## DEC-014 — Deterministic output and JSON contract

- Date: 2026-08-29
- Context: Pretty section order, separators, evidence numbering, resource
  labels, actual exit code, machine decoration bans, and byte stability are
  normative; the spec requires a repository-owned schema but does not dictate
  every property name below the listed content.
- Decision: Define `check-v1.schema.json` with closed objects and explicit types
  matching the §7 finding model and §10 content. JSON uses sorted keys, two-space
  indentation, UTF-8, and one final newline. Pretty uses fixed-width `textwrap`
  at 72 columns, the exact section order/separator, and no terminal width or
  time inputs. ANSI is enabled only for TTY pretty stdout when allowed; OSC 8 is
  omitted entirely as optional decoration. Quiet, JSON, redirects, files,
  `NO_COLOR`, and `--no-color` are always undecorated.
- Rationale: A closed, versioned schema and a decoration-free deterministic
  core minimize ambiguity and accidental contract drift.
- Alternatives considered: Terminal-width adaptation and always-on links;
  rejected as nondeterministic and unnecessary.
- Affected files: Schema, renderers, CLI, tests.
- Validation: Schema validation, repeat byte comparisons, section/order/width,
  evidence/resource, exit-line, and ANSI/OSC matrix tests.

## DEC-015 — CLI argument and output behavior

- Date: 2026-08-29
- Context: P0 specifies six commands, common options, stable exits, mutually
  exclusive inputs, and unsupported P1/P2 behavior.
- Decision: Build a single `argparse` tree. Bare invocation prints help and
  exits 0. Parser/unsupported surface errors exit 2, configuration errors 3,
  findings gates 1, and internal/interrupt errors 4. `--output` writes
  atomically via a same-directory temporary file and emits no stdout. Unknown
  commands/options, `codex`, SARIF, policy/explain/future surfaces remain
  ordinary usage errors rather than stub implementations.
- Rationale: Centralized exit translation makes failures unambiguous and avoids
  partially written output.
- Alternatives considered: Placeholder future commands; rejected because the
  spec says they are unavailable and must return 2.
- Affected files: CLI, README, tests.
- Validation: Help for every command, option matrix, output/file behavior, and
  explicit unsupported-surface tests.

## DEC-016 — Fixtures, test strategy, and completion evidence

- Date: 2026-08-29
- Context: Completion requires all listed fixture outcomes plus broader
  deterministic/offline/read-only/security tests and exact README commands.
- Decision: Create only the six P0 fixture families, each with `EXPECTED.md`.
  Use subprocess tests for public CLI contracts and focused unit tests for
  semantic known answers. Monkeypatch socket creation/connect in in-process
  core tests, checksum inspected files before/after, validate JSON using the dev
  dependency, and execute README commands literally during the final gate.
- Rationale: This tests user-observable behavior and semantic internals without
  introducing excluded feature fixtures.
- Alternatives considered: Snapshot-only/golden-only tests; rejected because
  they can preserve semantic bugs while appearing stable.
- Affected files: `fixtures/**`, `tests/**`, `README.md`.
- Validation: `uv run pytest` and the exact workshop sequence from §13.

## DEC-017 — v1.2 preservation applicability

- Date: 2026-08-29
- Context: The user requests byte-identical v1.2 preservation if v1.2 is
  included. The initial repository inventory contains no v1.2 document.
- Decision: Do not create or reconstruct v1.2. Preserve the v1.3 specification
  byte-for-byte and record v1.2 preservation as not applicable.
- Rationale: Synthesizing an absent historical artifact would not be
  preservation and could violate the clean-room/source boundary.
- Alternatives considered: Download or recreate v1.2; rejected because it is
  neither present nor needed for P0.
- Affected files: None for v1.2; `docs/KAAPI_BUILD_SPEC_v1.3.md` remains
  immutable.
- Validation: Initial/final file inventory and v1.3 checksum comparison.

## DEC-018 — Authoritative vendor-semantics corrections

- Date: 2026-08-29
- Context: §14 explicitly identifies corrections to an older implementation,
  while the user requires current semantics corrections to be recorded.
- Decision: Implement all eight correction groups from §14 as normative:
  shared tool families; `dontAsk` ask denial; conservative command-specific
  mode categories; deny-aware bypass; observed trust/additional-directory/
  supplied-layer handling; split network boundaries; absent-mode uncertainty;
  and full resolution of every field labelled supported. The authoritative
  source is the final v1.3 specification, whose §16 records re-verification
  against official Claude Code documentation on 2026-08-26. No additional live
  vendor lookup is necessary unless an implementation ambiguity cannot be
  resolved from v1.3.
- Rationale: The spec says the listed mismatches are bugs, not desired behavior.
- Alternatives considered: Reproduce the documented current mismatches;
  rejected as directly contrary to the normative contract.
- Affected files: Parser, resolver, analyzer, fixtures, tests, README claims.
- Validation: Dedicated known-answer tests for every §14 correction and no
  claim of runtime behavior or unobserved trust/mode.

## DEC-019 — Initial scope deviations and limitations

- Date: 2026-08-29
- Context: The task requires deviations and technical impossibilities to be
  recorded before acting.
- Decision: There are no intentional P0 spec deviations. Runtime sandbox
  availability, actual agent behavior, actual hook/MCP execution, dynamic hook
  results, effective unobserved session mode/trust, and OS permission state are
  treated as specified observational limitations, not implementation defects.
  OSC 8 is omitted because it is optional. v1.2 preservation is inapplicable by
  DEC-017.
- Rationale: These boundaries are explicitly defined by the specification and
  preserving them prevents overclaiming.
- Alternatives considered: Probe or simulate runtime behavior; rejected as
  prohibited, nondeterministic, and potentially unsafe.
- Affected files: Capability language, README, tests.
- Validation: Claim-language assertions, blocked-network tests, no execution
  code paths, and final scope audit.

## DEC-020 — Duplicate JSON object keys

- Date: 2026-08-29
- Context: RFC JSON permits parsers to differ on duplicate object-name handling,
  while Kaapi requires strict, deterministic security configuration parsing.
- Decision: Reject duplicate keys at any object depth as a configuration parse
  error (exit 3), without echoing the associated value.
- Rationale: Last-value or first-value selection can silently change security
  semantics across parsers and makes source evidence ambiguous.
- Alternatives considered: Follow Python's last-value behavior; rejected as
  unsafe and insufficiently deterministic for a security analyser.
- Affected files: Parser and strict-parsing tests.
- Validation: Known-answer duplicate top-level and nested-key parse errors.

## DEC-021 — Sandboxed Bash auto-approval semantics

- Date: 2026-08-29
- Context: Final audit found that the v1.3 supported field
  `sandbox.autoAllowBashIfSandboxed` was retained as metadata but the spec does
  not fully spell out its permission interaction or default.
- Decision: Apply the official current behavior: when the sandbox is enabled,
  `autoAllowBashIfSandboxed` defaults to true and sandboxable Bash commands are
  auto-approved; commands that cannot be sandboxed fall back to the regular
  permission flow. Explicit deny rules remain effective, ask rules apply only
  to fallback commands, and critical-path command exceptions must not be
  overclaimed as unprompted. Represent this as the conservative normalized
  category `shell.sandboxed-subset:unprompted`, distinct from general Bash and
  from OS enforcement. It triggers `AGENT-PERM-001` because the control covers
  unprompted shell execution.
- Rationale: This consumes the supported field, retains the permission/sandbox
  distinction, and avoids incorrectly treating every Bash command as approved.
- Alternatives considered: Keep metadata-only handling or set the whole Bash
  tool to unprompted; rejected respectively as incomplete and overbroad.
- Affected files: Resolver, baseline evaluator, capability renderer, tests.
- Validation: Default-true, explicit-false, deny-preservation, ask-fallback, and
  control known-answer tests.
- Authoritative sources: Claude Code settings
  (`https://code.claude.com/docs/en/settings`), sandboxing
  (`https://code.claude.com/docs/en/sandboxing`), and permissions
  (`https://code.claude.com/docs/en/permissions`), accessed 2026-08-29.

## DEC-022 — Workspace-trust observation boundary

- Date: 2026-08-29
- Context: §4.3 requires trust-aware behavior when trust is observed, but the P0
  input/CLI contract exposes no workspace-trust document or argument and trust
  is not a recognised settings field.
- Decision: Do not infer trust from a project path, Git state, or local-settings
  presence. Mark trust as unobserved and describe project-allow applicability as
  uncertain. Keep the resolver fact explicit so a future supported observed
  source can supply trust without changing permission semantics.
- Rationale: Inferring trust would violate observed-source-only analysis and
  could turn a conditional allow into a false definitive capability claim.
- Alternatives considered: Treat any local project settings file as trusted or
  inspect Git tracking state; rejected because neither proves Claude's session
  trust state.
- Affected files: Resolver facts/capability language and tests.
- Validation: Unobserved-trust known-answer test and assertions that no project
  allow is described as definitely trust-active.
- Spec deviation: None; this is the explicitly required unobserved-state
  behavior. The absence of a P0 trust input is a known observational limitation.

## DEC-023 — Newer documented security fields outside the v1.3 surface

- Date: 2026-08-29
- Context: The official documentation consulted for DEC-021 also lists current
  security settings such as `sandbox.failIfUnavailable`,
  `sandbox.network.allowManagedDomainsOnly`, and
  `sandbox.enableWeakerNetworkIsolation` that are not in the explicit v1.3 P0
  recognised surface.
- Decision: Do not silently promote these fields into P0. Classify them through
  the existing layer-specific unknown-field behavior, produce the relevant
  medium `*-099` finding, increment `Not evaluated`, and prevent a clean PASS.
- Rationale: v1.3 is authoritative, explicitly says newer or unmodelled fields
  follow §3.5, and adding semantics opportunistically would silently expand the
  accepted P0 contract.
- Alternatives considered: Add every field currently visible in vendor docs;
  rejected as scope drift without a corresponding v1.3 contract, control
  design, and full known-answer set.
- Affected files: Existing parser classification; tests.
- Validation: Current newer sandbox and network field known-answer WARN tests.
- Authoritative source: Claude Code settings
  (`https://code.claude.com/docs/en/settings`), accessed 2026-08-29.

## DEC-024 — Output/input collision protection

- Date: 2026-08-29
- Context: `--output` is an authorised write, but allowing it to resolve to an
  inspected settings, discovery, `.mcp.json`, Codex-presence, or snapshot input
  would violate read-only inspection and could destroy evidence.
- Decision: Resolve paths without requiring existence and reject every
  output/input collision as usage error 2 before writing. This applies across
  check, doctor, baseline, and verify.
- Rationale: Read-only must hold for adversarial option combinations, not only
  the documented workshop paths.
- Alternatives considered: Document that users must avoid collisions or make a
  backup; rejected because the CLI can enforce the invariant deterministically.
- Affected files: CLI and read-only/security tests.
- Validation: One collision test for each scanning workflow plus checksum tests.

## DEC-025 — Permission-rule grammar errors

- Date: 2026-08-29
- Context: Permission arrays are supported fields and §4.1 defines each member
  as `Tool` or `Tool(specifier)`. Treating a nonconforming string as an opaque
  no-op could silently discard a security rule.
- Decision: Reject a permission `allow`, `ask`, or `deny` member that does not
  conform to that grammar as a configuration parse error (exit 3). Keep rule
  specifiers opaque and never execute or interpolate them.
- Rationale: A known field with an invalid supported value is `MALFORMED`, not a
  safe unsupported rule.
- Alternatives considered: Ignore it or classify the array path as unknown;
  rejected because either can hide an intended deny and the grammar is
  normative.
- Affected files: Parser and strict-parsing tests.
- Validation: Malformed rule syntax with safe line/path error and valid scoped,
  wildcard, WebFetch, and MCP examples.

## DEC-026 — Managed read-path filtering and supported-field projection

- Date: 2026-08-29
- Context: Final field-by-field review found that
  `sandbox.filesystem.allowManagedReadPathsOnly` was classified and reported but
  did not yet remove lower-scope `allowRead` entries. Additional-directory and
  scoped-rule effects also needed explicit machine projections rather than only
  internal facts.
- Decision: When the managed-read-only switch resolves true, retain
  `filesystem.allowRead` entries from managed layers only; continue merging
  `denyRead` from every applicable scope. Emit safe counts for additional
  directories and scoped rule classes, and label whole-tool states as residual
  when scoped exceptions exist. Raw paths and rule specifiers remain omitted
  from capability/snapshot output.
- Rationale: A supported field must alter resolution or be marked not evaluated;
  safe counts preserve its effect without leaking path or command material.
- Alternatives considered: Metadata-only reporting or exposing raw path lists;
  rejected as respectively incomplete and unnecessarily sensitive.
- Affected files: Merge engine, resolution model/schema, capability
  normalization/rendering, and tests.
- Validation: Cross-scope managed allow-read filtering, deny-read preservation,
  additional-directory count, scoped residual, schema, and secrecy tests.
- Authoritative source: Claude Code settings
  (`https://code.claude.com/docs/en/settings`), accessed 2026-08-29.
