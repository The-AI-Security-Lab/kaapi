# Kaapi wiki maintenance log

This log is append-only. Superseded statements remain discoverable through the
commits and later entries that explain the change.

## [2026-08-29] initialize | P0 snapshot

- Indexed the v1.3 build specification, decision log, P0 package, fixtures, and
  tests.
- Added overview, architecture, controls, testing, and roadmap pages.
- Recorded the external Claude Settings Test Suite as a separate, non-gating
  benchmark.
- Validation: P0 test suite passed (`96 passed`).

## [2026-08-30] milestone | P1 Codex and policy

- Confirmed the exact v1.3 P1 scope and excluded non-committed v1.2 candidates.
- Added the P1 Codex adapter, runtime baseline projection, fixtures, and
  supported/unsupported boundary.
- Added the closed organisational policy schema, examples, validation,
  independent verdicts, and `PERMITTED_RISK`.
- Updated overview, architecture, testing, roadmap, source register, and wiki
  index pages.
- Validation: complete P0+P1 suite passed (`114 passed`); specification
  checksum and all original P0 behavior tests remained green.

## [2026-08-30] enhance | Composable domain policies

- Added repeatable `--policy` and sorted `--policy-dir` composition.
- Added closed restrictions for approvals, named MCP servers, Claude Bash
  patterns, filesystem paths, sandbox, network, and hooks.
- Added common, Claude-specific, and Codex-specific reference policies plus a
  strict cross-runtime bundle.
- Kept compared names and patterns internal and documented the Codex `.rules`
  and Claude built-in read-only command boundaries.
- Validation: complete P0+P1 suite passed (`118 passed`); all original P0 and
  initial P1 tests remained green.

## [2026-09-14] ingest | LLM wiki pattern

- Preserved the user-supplied LLM wiki pattern as immutable raw evidence.
- Added the project-specific adaptation page and linked it from the wiki index.
- Added the root `AGENTS.md` maintenance contract so future agents can use the
  wiki consistently while respecting the specification, decision log, and
  raw-source authority order.
- Validation: documentation links and required wiki files checked; no runtime
  code or inspected configuration changed.

## [2026-09-14] decide | Kaapi/Charlie boundary

- Recorded that Kaapi remains an independent project and that Charlie is a
  consumer of its deterministic configured-authority analysis.
- Documented ownership, CONFIGURED/EXPECTED/OBSERVED terminology, the
  Charlie-owned future integration direction, and the preserved limitations.
- Corrected Codex documentation so `allow_login_shell` is described as parsed
  and validated rather than materially resolved.
- Validation: full P0+P1 test gate passed; no production code changed.

## [2026-09-15] implement | In-memory analysis facade

- Added the small public `kaapi.analyze_text` entry point for UTF-8 Claude JSON
  and Codex TOML content, with deterministic synthetic source evidence and no
  temporary configuration persistence.
- Reused the existing parsers, resolution, baseline evaluation, redaction, and
  structured-result construction; did not add HTTP, telemetry, enforcement,
  new controls, or policy semantics.
- Added focused parity, error, determinism, redaction, and no-persistence tests.
- Validation: focused facade tests passed (`15 passed`); full P0+P1 suite passed
  (`133 passed`); no Charlie repository or UI/backend files changed.

## [2026-09-24] validate | P1 release candidate

- Reconciled the working implementation with the v1.3 P1 roadmap and
  DEC-027 through DEC-036; no unrecorded P1 requirement is missing.
- Updated the README, roadmap, testing, overview, and architecture pages to
  report the 133-test gate and distinguish the in-process Python facade from
  an HTTP or hosted API.
- Re-ran the documented Claude, Codex, policy, snapshot, and verification
  workflows and the focused API, parity, determinism, offline, and P0
  regression tests.
- Built the source distribution and wheel offline, installed the wheel into an
  isolated environment, and exercised the installed CLI and Python facade.
- Validation: full suite passed (`133 passed`); candidate artifacts still use
  package version `1.0.0` pending release-version approval. No commit, push,
  merge, or tag was performed.

## [2026-09-24] release | P1 v1.1.0

- Approved package version `1.1.0` and annotated Git tag `v1.1.0`; kept the
  Claude `0.3.1` and Codex `0.4.0` baseline versions independent.
- Recorded the post-P1 roadmap: P2 is Evaluation Integration & API, while the
  previous feature backlog is now P3. Neither planned phase is implemented.
- Updated the README, architecture, roadmap, testing guidance, source
  register, and decision log for the release boundary.
- Validation: complete P0+P1 suite passed (`133 passed`); documented Claude
  and Codex smoke tests, all 21 shipped policy files, Python API/parity tests,
  deterministic and offline checks, and snapshot reduction passed. The
  `1.1.0` source distribution and wheel built offline, and the wheel installed
  and ran successfully in an isolated environment. Fresh-checkout validation
  is the post-publication gate.
