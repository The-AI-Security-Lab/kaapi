# Kaapi roadmap

Tech Spec v1.3 remains frozen. DEC-038 records the later approved roadmap
change below without rewriting that historical specification.

## P0 — Deterministic security-analysis foundation

**Status:** Complete.
**Release:** `v1.0.0`.

Claude Code configuration analysis, capability resolution, security baseline,
bypass detection, and before/after verification.

## P1 — Expanded coding-agent and organisational policy analysis

**Status:** Complete.
**Release:** `v1.1.0`.

Codex configuration support, organisational policy-as-code, independent
security and compliance verdicts, expanded policy analysis, and the public
in-process Python API. The verified release suite passes with 133 tests.

## P2 — Evaluation Integration & API

**Status:** P2.1 and P2.2A are complete. P2.1 was workshop-validated at commit
`9a0bc6ba34576782675aded9e16b718c24fea9bd`; P2.2A passed independent
acceptance on the current branch. The current development suite passes with
175 tests. P2.2B is next; P2.3–P2.4 remain planned.

- ~~Complete organisational-policy support through the public Python API.~~
  Completed in P2.1 through the in-memory `policy=` boundary.
- Provide a small, versioned, deterministic HTTP API for independent
  applications and evaluation harnesses.
- Reuse the existing Kaapi engine rather than introducing another analysis
  implementation.
- Evaluate Cloudflare as a possible hosting platform without making hosted
  deployment a dependency of local Kaapi usage.
- Integrate with the AI Security Lab golden evaluation dataset and
  deterministic verification harness.
- Demonstrate equivalent assessments through the CLI, Python API, and HTTP API
  for equivalent supported inputs.
- Preserve evidence levels, assessment limitations, and inconclusive or
  not-tested outcomes where required.

### P2.1 — Workshop Evaluation Integration

The completed P2.1 slice extends `kaapi.analyze_text(...)` with the existing
closed organisational-policy evaluator and adds four small golden cases:
insecure and hardened Claude Code JSON plus insecure and hardened Codex TOML.
The external-style harness in `evaluation/p2_1/` owns grading. It reports
`PASS`, `FAIL`, `INCONCLUSIVE`, or `NOT_TESTED` and preserves Kaapi evidence and
the limitation that configuration analysis does not verify runtime enforcement
or agent behaviour.

Workshop consumer validation passed for public Python API consumption,
malformed and insufficient-evidence handling, determinism, and preservation of
the configuration-versus-runtime evidence boundary. A stable/documented public
exception contract for malformed API input is a non-blocking P2.2A follow-up.

### P2.2A — Local FastAPI REST API

Complete and independently accepted on the development branch as a thin
optional FastAPI transport at
`POST /v1/analyze`. It accepts supported Claude JSON, Codex TOML, and P2.1
policy input, returns the existing structured Kaapi document, preserves
Python/HTTP assessment parity, limits request bodies to 1 MiB, and exposes
stable client-facing errors. It does not execute agents or verify runtime
enforcement. Independent verification covered all four golden cases, real
Uvicorn/curl traffic, malformed/unsupported input, deterministic repetition,
and side-effect boundaries. The stable public exception contract is
`ConfigError` and `PolicyError` exported from `kaapi`.

### P2.2B — Portable Docker service — NEXT / NOT STARTED

Package the local API as a portable Docker service without adding a second
analysis engine or making hosted deployment a local dependency.

### P2.3 — Golden dataset and evidence/evaluation expansion

Expand the versioned golden dataset and evidence-backed evaluation integration
after the workshop slice.

### P2.4 — Hosting, distribution, documentation and release readiness

Evaluate hosting, distribution, documentation, and release readiness after the
local API and portable service are validated.

P2 supports the AI Security Lab methodology:

```text
Define → Design Evals → Harden → Verify → Monitor
```

Kaapi contributes configuration and resolved-capability evidence. It does not
become the complete evaluation or runtime-verification platform. Kaapi remains
a deterministic security-analysis engine; P2 requires neither an LLM nor
runtime execution.

## P3 — Deferred capabilities and product enhancements

**Status:** Planned backlog. Not implemented.

- Model-narrated `kaapi explain`.
- Blast-radius modelling.
- Arcanum and OWASP mappings.
- SARIF output.
- Additional coding-agent adapters, including Cursor, Gemini, and GitHub
  Copilot.
- Other deferred analysis, reporting, and usability enhancements.

P3 is a backlog, not a commitment to implement every feature. Runtime
execution, runtime-enforcement verification, continuous runtime monitoring,
and broader agent-workflow governance remain outside Kaapi's core
responsibility.
