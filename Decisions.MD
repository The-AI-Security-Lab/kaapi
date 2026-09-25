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

## DEC-033 — Composable closed-domain policy bundles

- Date: 2026-08-30
- Context: Teams need reusable restrictions for approvals, shell, filesystem,
  sandbox, network, hooks, and MCP, and must be able to apply one restriction
  or a maintained set. The initial count-only overlay could not express common
  requirements such as a named MCP allowlist.
- Decision: Extend policy schema version 1 backward-compatibly with optional
  `domain` and `runtimes` metadata and a closed, typed parameter set attached
  only to known baseline controls. Make `--policy` repeatable and add
  repeatable `--policy-dir`; directory JSON files load in filename order and
  evaluated policies sort by unique policy ID. Aggregate verdict is `FAIL` if
  any policy fails, otherwise `PERMITTED_RISK` if any policy permits a
  baseline risk, otherwise `PASS`. An unsupported runtime, unavailable
  control, or unavailable parameter fails explicitly.
- Rationale: Small domain files can be owned by different security teams and
  composed without introducing expressions, code execution, severity
  overrides, or a generic policy language.
- Alternatives considered: One monolithic policy, natural-language rules,
  executable predicates, and silent skipping of runtime-specific domains;
  rejected as respectively hard to maintain, nondeterministic, unsafe, or
  liable to false assurance.
- Affected files: Policy parser/evaluator/schema, CLI, renderers, reference
  policies, README, wiki, and policy tests.
- Validation: Single, repeated, and directory policy loading; duplicate
  rejection; deterministic bundle ordering; aggregate verdicts; runtime
  mismatch; schema validation; and baseline non-suppression.

## DEC-034 — Policy comparisons are minimized and fail closed

- Date: 2026-08-30
- Context: Named MCP allowlists, exact Claude Bash permission patterns,
  filesystem deny patterns, and network domains require comparison with raw
  configuration values. Those values can expose internal infrastructure or
  command material if copied into reports.
- Decision: Keep raw Bash patterns, filesystem paths, and network domains as
  non-serialized internal facts and expose only comparison counts, booleans,
  modes, and verdicts in the policy result. MCP server keys are matched exactly
  and case-sensitively for Claude and Codex; Claude's existing resolved MCP
  metadata may still expose selected server names, but commands, arguments,
  environment values, URLs, and other secret-bearing values retain the P0/P1
  redaction contract. Claude Bash policies compare configured
  `Bash(specifier)` allow rules and can require `dontAsk`; they do not claim
  that the configured rule is the only runtime-executable command because
  Claude has a built-in read-only command set. Codex Starlark `.rules` files
  are not an observed P1 input, so exact Codex command-pattern policies fail as
  unsupported rather than passing from `config.toml` alone.
- Rationale: This provides useful enforceable configuration restrictions while
  minimizing new report exposure and avoiding claims beyond the established
  runtime output contract.
- Alternatives considered: Echo unexpected values, hash them into output,
  treat count one as an identity allowlist, or infer Codex command rules from
  approval mode; rejected because each would leak information or produce
  misleading compliance.
- Affected files: Claude and Codex normalizers, policy evaluator, schemas,
  reference policies, documentation, and secret-safety tests.
- Validation: GitHub-only MCP known answers for both runtimes; policy-result
  count projections; Bash sentinel redaction; exact Claude pattern pass/fail;
  and explicit Codex rejection for a Claude-only shell policy.
- Authoritative sources: Claude Code permission rules
  (`https://code.claude.com/docs/en/permissions`) and OpenAI's Codex rules and
  managed-configuration description
  (`https://openai.com/index/running-codex-safely/`), accessed 2026-08-30.

## DEC-027 — P1 scope is the v1.3 roadmap, not v1.2 candidates

- Date: 2026-08-30
- Context: The implementation brief listed Codex, organisational policy,
  blast-radius, Arcanum/OWASP mapping, and SARIF as expected areas, but also
  made v1.3 authoritative. Section 15 marks only Codex configuration and custom
  organisational policies as P1. It explicitly describes blast radius,
  Arcanum/OWASP mappings, and SARIF as unavailable historical candidates that
  are not delivery commitments.
- Decision: Implement only Codex configuration support and organisational
  policy overlays. Leave blast-radius, Arcanum, OWASP, SARIF, and P2 surfaces
  unavailable.
- Rationale: This follows the user's spec-wins rule and prevents historical
  design candidates from silently becoming product commitments.
- Alternatives considered: Implement every area named in the brief summary;
  rejected because it conflicts with the exact v1.3 P1 roadmap.
- Affected files: Entire P1 change set and documentation.
- Validation: CLI tests continue to reject SARIF, OWASP, `explain`, Cursor,
  Gemini, and GitHub Copilot surfaces.

## DEC-028 — Thin Codex TOML adapter and observation boundary

- Date: 2026-08-30
- Context: P1 requires Codex configuration support without replacing the P0
  normalized core. Current Codex uses TOML layers and security semantics that
  differ from Claude Code JSON.
- Decision: Add a standard-library `tomllib` adapter for explicit
  `config.toml` files and conservative system/user discovery. Evaluate the
  observed `approval_policy`, `approvals_reviewer`, `sandbox_mode`,
  `sandbox_workspace_write`, `web_search`, `allow_login_shell`,
  `features.network_proxy`, and `mcp_servers` surfaces. Merge system below
  user values. Detect but do not apply project `.codex/config.toml` during
  discovery unless trust becomes a separately supported observed input;
  explicit project-file analysis remains supported. Unsupported security
  surfaces such as permission profiles, hooks, apps, plugins, skills, and
  other feature flags produce layer-specific unknown-field findings.
- Rationale: This provides useful P1 coverage while preserving observed-only
  reasoning and avoiding guessed trust, managed-requirements, CLI-override,
  rule, or hook semantics.
- Alternatives considered: Reinterpret Codex TOML as Claude settings; rejected
  as semantically incorrect. Load project config merely because it exists;
  rejected because official behavior requires project trust.
- Affected files: `kaapi/codex.py`, parser precedence, analysis orchestration,
  CLI runtime selection, fixtures, and tests.
- Validation: Strict TOML, explicit-path, runtime auto-selection, precedence,
  unobserved-trust, unknown-field, determinism, offline, read-only, and secret
  redaction tests.
- Authoritative sources: OpenAI Codex configuration reference
  (`https://learn.chatgpt.com/docs/config-file/config-reference`), config
  basics (`https://learn.chatgpt.com/docs/config-file/config-basic`), advanced
  configuration
  (`https://learn.chatgpt.com/docs/config-file/config-advanced`), and agent
  approvals and security
  (`https://learn.chatgpt.com/docs/agent-approvals-security`), accessed
  2026-08-30.

## DEC-029 — Codex normalization and runtime-specific baseline 0.4.0

- Date: 2026-08-30
- Context: P0's 0.3.1 baseline metadata and evidence are Claude-specific and
  must remain frozen, while common control IDs have meaningful Codex
  equivalents.
- Decision: Preserve baseline 0.3.1 byte-for-byte for Claude and add a
  declarative Codex baseline projection at version 0.4.0. Reuse stable common
  IDs for approval/sandbox bypass, automatic approval review, unprompted shell
  and writes, sandbox absence/escalation, unbounded outbound capability, MCP,
  and unknown fields. Normalize Codex into the existing `Resolution` shape
  without claiming runtime enforcement, command execution, MCP connection, or
  network activity. Apply documented web-search defaults: cached normally and
  live for a full-access sandbox when not explicitly set.
- Rationale: Runtime-specific provenance avoids falsely citing Claude sources
  for Codex findings and keeps every P0 check document unchanged.
- Alternatives considered: Mutate baseline 0.3.1 to cover Codex or hard-code
  findings outside the declarative baseline; rejected respectively as a P0
  compatibility break and an architectural regression.
- Affected files: Codex baseline data, baseline loader/evaluator, resolver
  projection, check schema, snapshot runtime handling, and `rules --runtime`.
- Validation: Codex hardened, auto, and danger known answers; baseline
  provenance validation; snapshot compatibility; JSON Schema; full P0
  regression.

## DEC-030 — Closed organisational policy schema

- Date: 2026-08-30
- Context: P1 policies must select and parameterise known controls without
  becoming a generic or executable policy engine.
- Decision: Define `policy.schema.json` with exactly `schema_version`,
  `id`, and a non-empty `requirements` array. Each requirement names one
  known control and uses expectation `pass` or `allow`. Reject duplicate
  keys, unknown object keys, duplicate or unknown control IDs, unsupported
  expectations, and every executable/script/template shape. Support only
  non-negative count parameters backed by existing normalized facts:
  `max_configured_servers` for `AGENT-MCP-001`,
  `max_excluded_commands` for `AGENT-SBOX-004`, and
  `max_command_hooks` for `AGENT-HOOK-001`.
- Rationale: The format is deterministic data and cannot create new scanner
  semantics or execute arbitrary logic.
- Alternatives considered: Python expressions, JSONPath predicates, templates,
  user-authored rules, or severity overrides; rejected because they would form
  a generic executable policy engine or permit baseline redefinition.
- Affected files: `kaapi/policy.py`, policy schema, example policies, CLI,
  and policy tests.
- Validation: Independent `policy validate`, JSON Schema examples, malformed
  and duplicate input, unknown keys/controls/parameters, executable-shape
  rejection, offline/read-only operation, collision protection, and secret-safe
  errors.

## DEC-031 — Independent policy verdict and PERMITTED_RISK

- Date: 2026-08-30
- Context: The built-in baseline answers whether a configuration is risky;
  organisation policy separately answers whether that configuration meets
  organisation requirements.
- Decision: Keep `posture`, counts, findings, severities, and passed controls
  unchanged when a policy is supplied. Add explicit `security_posture` and
  `organisation_policy.verdict` fields. A required failing control yields
  policy `FAIL`; an explicit `allow`, or a satisfied organisation count
  threshold that disagrees with a baseline finding, yields
  `PERMITTED_RISK`; otherwise policy passes. Policy `FAIL` exits 1 even when
  `--fail-on none` disables the security gate. `PERMITTED_RISK` does not
  suppress the independent baseline gate. A requirement for a control that
  does not exist in the active runtime baseline fails explicitly rather than
  being ignored or treated as satisfied.
- Rationale: The disagreement remains visible and machine-readable without
  turning baseline risk green.
- Alternatives considered: Remove permitted findings, downgrade severity, or
  combine security and compliance into one verdict; rejected by the P1 policy
  boundary.
- Affected files: Policy evaluator, CLI, pretty/quiet/JSON rendering, check
  schema, and tests.
- Validation: Byte-for-byte finding comparison with and without policy,
  separate-verdict tests, threshold and allow known answers, deterministic
  output, and JSON Schema validation.

## DEC-032 — P0 compatibility and P1 release metadata boundary

- Date: 2026-08-30
- Context: The brief freezes `v1.0.0` as the known-good P0 baseline and
  requires every P0 test and behavior to remain green. It does not assign a
  Kaapi package release number to the P1 milestone.
- Decision: Do not retag, commit, publish, or invent a new package version in
  this implementation task. Preserve the existing default Claude runtime,
  baseline 0.3.1, six P0 fixture outcomes, check JSON version 1, and
  `kaapi 1.0.0` version output. Extend existing schemas only with optional P1
  fields and runtime values. Runtime-specific Codex snapshots use baseline
  0.4.0 and cannot be compared with Claude snapshots.
- Rationale: This keeps the stable baseline reproducible while leaving release
  numbering and tagging to an explicit release decision.
- Alternatives considered: Bump the package to 1.1.0 or rewrite P0 goldens;
  rejected as an unrequested release action.
- Affected files: Package version remains unchanged; schemas and snapshots gain
  backward-compatible runtime support.
- Validation: All original P0 tests pass alongside P1 tests; specification
  checksum remains unchanged.

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

## DEC-035 — Kaapi remains independent; Charlie is a consumer

- Date: 2026-09-14
- Context: An architecture audit evaluated whether the current Kaapi P0/P1
  implementation should provide Charlie's first deterministic configured-
  authority capability. Kaapi already has an independent purpose, tested
  Claude and Codex analysis, deterministic baselines, normalized capabilities,
  evidence/provenance, organisational policy, snapshots, verification,
  discovery/precedence, doctor, and a standalone CLI.
- Decision: Kaapi remains an independent project and is not renamed Charlie,
  reduced to Charlie's backend, or narrowed to Charlie's first use case. Its
  current core primitive is deterministic static analysis of configured agent
  authority, producing normalized capabilities, baseline security findings,
  and source evidence/provenance. Charlie is a consumer of that reusable
  capability through a thin integration boundary:

  ```text
  Charlie
    → thin integration boundary
    → Kaapi
    → configured capabilities + findings + evidence
  ```

  Other tools and users must remain able to use Kaapi independently.
- Ownership boundary: Kaapi owns supported-agent parsing, configuration
  discovery and precedence/resolution, normalized configured authority,
  deterministic baseline evaluation, findings, evidence/provenance,
  organisational-policy evaluation, and deterministic CLI behavior. Charlie
  owns the Charlie web experience, paste/upload handling, user-facing
  presentation, any hosted HTTP/API boundary, configured-versus-expected
  visualization/workflow, future runtime telemetry unless separately decided,
  and orchestration of additional security components.
- Terminology: In Kaapi, `observed` refers to observed configuration/source
  inputs. It does not mean that an agent action was observed at runtime. The
  broader Charlie model distinguishes `CONFIGURED` (authority inferred from
  configuration), `EXPECTED` (authority intended or permitted by policy), and
  `OBSERVED` (runtime behavior actually seen). Kaapi currently provides strong
  `CONFIGURED` support and foundations for `EXPECTED`, but does not provide the
  `OBSERVED` runtime telemetry layer.
- Future integration direction: The currently recommended, non-implemented
  shape is a Charlie-owned backend adapter calling a stable Kaapi Python API,
  which in turn uses the existing deterministic analysis pipeline. A likely
  small Kaapi adaptation is an in-memory entry point accepting configuration
  text/bytes plus runtime information and returning the existing versioned
  structured result. This is a recommendation for future work, not an
  irreversible API or an implementation decision. CLI/subprocess integration
  remains a fallback, not the preferred boundary. Kaapi must not gain an HTTP
  service merely to serve Charlie.
- Current limitations preserved: Kaapi has no runtime telemetry, runtime
  enforcement, hosted API, or natural-language policy interpretation. It does
  not analyze Codex `.rules` files or observe project trust. Environment
  exposure is only partially modeled. Codex `allow_login_shell` is parsed and
  validated but does not currently materially affect resolution or findings.
  Codex support is tested but less extensively than Claude support.
- Rationale: This preserves Kaapi's independent product identity and tested
  security boundary while making Charlie's consumer relationship explicit.
  It prevents a future web integration from duplicating or silently narrowing
  Kaapi's deterministic analysis and keeps runtime telemetry outside the
  current static-analysis contract.
- Alternatives considered: Rename Kaapi to Charlie, move Kaapi behind a new
  Kaapi HTTP service, duplicate the analyzer in Charlie, or use only the CLI;
  rejected respectively because they erase independent identity, add an
  unneeded deployment boundary, risk semantic drift, or provide a less natural
  interactive library seam. CLI use remains available as a fallback.
- Relationship to earlier decisions: This entry clarifies and preserves
  DEC-002, DEC-003, DEC-007, DEC-010 through DEC-014, DEC-027 through DEC-034,
  and the existing P0/P1 scope. It contradicts or supersedes none of them.
- Affected files: Decision and architecture documentation only. No production
  code, tests, schemas, fixtures, or inspected configuration are changed by
  this decision-record pass.
- Validation: Documentation links/checks and the existing full P0+P1 test gate.

## DEC-036 — Stable in-memory analysis facade

- Date: 2026-09-15
- Context: DEC-035 recorded a likely future small Kaapi adaptation: an
  in-memory entry point for a Charlie-owned adapter. Kaapi's existing flow
  already separates parsing into source layers from shared resolution,
  baseline evaluation, and versioned result construction, so a true in-memory
  path is possible without temporary files or a second analysis implementation.
- Decision: Expose `kaapi.analyze_text(content, *, runtime, source=None)` as a
  deliberately small, supported public library facade. `content` accepts
  UTF-8 `str` or `bytes`; `runtime` must explicitly be `claude-code` or
  `codex`; and an optional logical `source` identifier is used for evidence.
  The default source is a deterministic synthetic in-memory identifier. The
  function returns Kaapi's existing versioned structured analysis document and
  raises the existing programmatic `ConfigError` for parse/validation errors.
  The first facade version does not add policy parameters or broaden the
  organisational-policy model.
- Implementation boundary: The facade parses directly into the existing
  `SourceLayer` model, uses the existing runtime merge functions, and calls the
  shared analysis-document builder used by the file-backed API. It does not
  write, read back, or persist a temporary configuration file. Existing CLI
  behavior and the standalone Kaapi project remain unchanged.
- Charlie relationship: Charlie is one intended consumer, but this is a
  general Kaapi capability. A future Charlie-owned HTTP/backend adapter may
  call this facade; no HTTP service, Charlie backend, or Charlie UI is added
  here. CLI/subprocess use remains a supported fallback.
- Rationale: This establishes the smallest clean in-process boundary while
  preserving identical parsing, normalization, controls, findings, evidence,
  redaction, and structured-result semantics for Claude and Codex.
- Alternatives considered: Create temporary files and reuse the path API,
  duplicate the analyzer for text input, add a broad SDK, add HTTP endpoints,
  or expand policy handling in the first facade; rejected respectively because
  they weaken the in-memory boundary, risk semantic drift, increase scope, or
  belong to a later integration decision.
- Relationship to earlier decisions: This refines the non-implemented future
  recommendation in DEC-035 and preserves DEC-002, DEC-007, DEC-010 through
  DEC-014, DEC-027 through DEC-034, and all existing P0/P1 semantics. It does
  not change any security control or baseline rule.
- Affected files: `kaapi/__init__.py`, `kaapi/analyze.py`,
  `kaapi/parser.py`, `kaapi/codex.py`, focused facade tests, and documentation.
- Validation: Focused facade tests cover Claude/Codex known answers, malformed
  input, unknown fields, deterministic execution, secret redaction, no
  persistence, and parity with CLI analysis. The complete P0+P1 suite remains
  the release gate.

## DEC-037 — Release P1 as Kaapi v1.1.0

- Date: 2026-09-24
- Context: P0 is published as Git tag `v1.0.0`. P1 adds a backward-compatible
  expansion of supported runtimes and policy analysis, plus the in-process
  analysis facade recorded in DEC-036. The release needs an application
  version distinct from the independently versioned security baselines.
- Decision: Release the completed P1 milestone as package version `1.1.0` and
  annotated Git tag `v1.1.0` from branch `p1`. The release contains Codex TOML
  analysis, organisational policy-as-code, and
  `kaapi.analyze_text(content, *, runtime, source=None)`, while preserving all
  P0 behavior. Baseline versions `0.3.1` (Claude Code) and `0.4.0` (Codex) are
  data/control versions and do not track the package version.
- Publication boundary: Publish the existing `p1` branch and the annotated
  tag to the configured Git remote. Do not merge the branch, publish to a
  package registry, create a P2 branch, or implement P2/P3 functionality as
  part of this release.
- Rationale: `1.1.0` communicates a backward-compatible capability milestone
  after `v1.0.0`, while leaving security-baseline provenance unambiguous.
- Relationship to earlier decisions: This replaces only DEC-027's temporary
  instruction to retain package version `1.0.0` until release approval. It
  preserves DEC-027's P1 implementation scope and all P0/P1 architecture and
  security decisions.
- Validation: Full P0+P1 tests, documented CLI/API/policy workflows,
  deterministic and offline checks, package build, isolated installation, and
  fresh-checkout verification are release gates.

## DEC-038 — Reclassify the post-P1 roadmap

- Date: 2026-09-24
- Context: Tech Spec v1.3 is frozen historical authority for P0/P1. After P1,
  the product priority changed from the specification's non-binding future
  feature list to integration with the AI Security Lab evaluation workflow and
  a reusable deterministic API boundary.
- Decision: Classify P2 as **Evaluation Integration & API**. Its planned scope
  is organisational-policy support through the public Python API; a small,
  versioned, deterministic HTTP API; reuse of the existing Kaapi engine;
  optional evaluation of Cloudflare as a hosting platform; integration with
  the AI Security Lab golden evaluation dataset and deterministic verification
  harness; CLI/Python/HTTP assessment equivalence for equivalent supported
  inputs; and preservation of evidence levels, limitations, and inconclusive
  or not-tested outcomes. This phase supports the methodology
  `Define -> Design Evals -> Harden -> Verify -> Monitor` without making Kaapi
  the complete evaluation or runtime-verification platform.
- P3 classification: Move model-narrated `kaapi explain`, blast-radius
  modelling, Arcanum/OWASP mappings, SARIF, additional coding-agent adapters,
  and the remaining former P2 feature backlog to P3. P3 remains an uncommitted
  backlog rather than a promise to implement every item.
- Architectural boundary: Kaapi remains a deterministic security-analysis
  engine. Neither an LLM nor runtime execution is required for P2. Runtime
  telemetry, enforcement verification, continuous monitoring, and broader
  workflow governance remain outside Kaapi's core responsibility unless a
  later decision explicitly changes that boundary.
- Specification handling: Do not rewrite Tech Spec v1.3. This decision
  supersedes only its non-binding post-P1 roadmap classification; it does not
  change the implemented P0/P1 requirements, DEC-027's P1 scope, or DEC-035
  and DEC-036's project and API boundaries.
- Implementation status: P2 and P3 are not implemented in `v1.1.0`.

## DEC-039 — P2.1 workshop integration boundary

- Date: 2026-09-25
- Context: The first P2 deliverable is the smallest reliable integration for
  the AI Security Lab coding-agent security workshop. P1 already has a
  deterministic in-memory configuration facade and a closed policy evaluator,
  but the facade does not yet accept policy input and no golden harness exists
  in the repository.
- Decision: Extend `kaapi.analyze_text(...)` with an optional `policy=` input.
  It accepts one strict policy JSON document as UTF-8 text, bytes, or a decoded
  mapping; a non-empty sequence supports the existing deterministic policy
  bundle semantics. Policy parsing uses the same validation implementation as
  file-backed CLI policies, and the CLI and Python API use one shared policy
  overlay helper. Existing callers that omit `policy` retain the exact P1
  result shape and semantics.
- Harness boundary: Add a small external-style example under
  `evaluation/p2_1/` with four declarative golden cases. The harness invokes
  the public Python API, preserves the returned policy requirement, finding
  evidence, and static-analysis limitation, and owns only the workshop grade.
  A policy requirement with status `PASS` can grade `PASS`; an evaluated
  non-pass requirement grades `FAIL`; missing required evidence grades
  `INCONCLUSIVE`; malformed/unavailable input or an unsupported runtime
  requirement grades `NOT_TESTED`.
- Rationale: This establishes the requested requirement → configuration →
  Kaapi assessment → deterministic grading path without duplicating the
  engine, changing baseline findings, adding runtime claims, or building a
  generic evaluation platform. The HTTP API, Cloudflare deployment, and
  broader P2 parity remain outside this slice.
- Alternatives considered: Passing policy file paths to the Python API,
  writing temporary policy files, duplicating policy evaluation in the
  harness, or making the Kaapi engine own workshop grading; rejected because
  they weaken the in-memory boundary, risk semantic drift, or collapse the
  distinction between analysis and evaluation.
- Relationship to earlier decisions: This implements the P2 scope recorded in
  DEC-038 while preserving DEC-030, DEC-031, DEC-035, DEC-036, and the frozen
  P0/P1 analysis and evidence boundaries. It does not implement HTTP or alter
  `PERMITTED_RISK` semantics.
- Affected files: `kaapi/analyze.py`, `kaapi/policy.py`, `kaapi/cli.py`,
  `evaluation/p2_1/**`, `tests/test_p2_1.py`, README, roadmap, and wiki log.
- Validation: The four golden cases, CLI/Python parity, deterministic repeat,
  malformed input, unsupported requirements, missing evidence, and the full
  P0/P1 regression suite.
