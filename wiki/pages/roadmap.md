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

**Status:** Planned. Not implemented.

- Complete organisational-policy support through the public Python API.
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
