# Kaapi architecture

Kaapi follows a deterministic, local-only pipeline:

| Stage | Responsibility |
| --- | --- |
| Discovery | Locate explicitly supplied settings or staged environment layers. |
| Parsing | Load strict Claude JSON or Codex TOML, preserve source paths, and classify unknown fields. |
| Runtime adapter | Normalize observed Claude or Codex facts without equating their platform semantics. |
| Merge and resolution | Apply runtime-specific layer precedence and capability semantics. |
| Analysis | Derive configured capabilities and evaluate versioned controls. |
| Policy overlay | Compose closed domain policies, compare internal normalized facts, and derive an independent organisation verdict. |
| Rendering | Produce stable pretty or JSON output with evidence, remediation, and resources. |
| Snapshot and verification | Write secret-safe baselines and compare later observations. |
| CLI | Expose `check`, `doctor`, `baseline`, `verify`, `rules`, `policy validate`, and `version`. |

The Python package is under `kaapi/`; baseline data and schemas are package
data. Runtime analysis uses the standard library only. Development dependencies
are isolated in the `dev` group.

## Product boundary and ownership

Kaapi remains an independent project. It is not being renamed Charlie or
reduced to Charlie's backend. Its reusable primitive is:

> Deterministic static analysis of configured agent authority, producing
> normalized capabilities, baseline security findings, and source
> evidence/provenance.

The current working relationship is:

```text
Charlie
  → thin integration boundary
  → Kaapi
  → configured capabilities + findings + evidence
```

Kaapi owns supported configuration parsing, discovery and precedence,
resolution, normalized configured authority, deterministic baseline findings,
evidence/provenance, organisational-policy evaluation, and CLI behavior.
Charlie owns the Charlie web UX, paste/upload experience, user-facing
presentation, any hosted HTTP/API boundary, configured-versus-expected
workflow, future runtime telemetry unless separately decided, and orchestration
of additional security components. Other tools and users remain free to use
Kaapi without Charlie.

## Source precedence

The canonical staged discovery layout is documented in the README and build
specification. Supported layers resolve from managed settings through supplied,
project-local, shared-project, and user settings. Arrays combine across
applicable scopes; deny, ask, and allow classes are evaluated in that order.

Codex system configuration is lower precedence than user configuration.
Project `.codex/config.toml` is detected but not automatically applied while
project trust is unobserved. An explicitly supplied TOML file is analyzed as
one reproducible observed document.

## Policy separation

The built-in baseline and organisation policy share normalized facts but not a
verdict:

```text
baseline posture       -> Is the observed capability risky?
organisation policy    -> Does it meet organisation requirements?
```

The policy layer never edits baseline findings, counts, severities, or passed
controls. A permitted disagreement is rendered as `PERMITTED_RISK`. Repeated
`--policy` inputs and sorted `--policy-dir` files produce one deterministic
bundle verdict. Raw names and patterns used for comparison remain internal.

## Configured, expected, and observed

Kaapi's existing `observed` terminology means that a configuration or source
layer was observed and read. It does not mean that an agent action was observed
at runtime.

Charlie may present the broader model as:

```text
CONFIGURED = authority inferred from configuration
EXPECTED   = authority intended or permitted by policy
OBSERVED   = runtime behavior actually seen
```

Kaapi currently provides strong CONFIGURED analysis and foundations for
EXPECTED through its closed organisational-policy overlay. Runtime OBSERVED
telemetry is not part of Kaapi today.

## Charlie integration boundary

The stable in-process Kaapi API is implemented. A future Charlie-owned backend
adapter can call it without moving HTTP or UI responsibilities into Kaapi:

```text
Charlie
  → Charlie-owned HTTP/backend adapter
  → stable Kaapi Python API
  → existing deterministic analysis pipeline
```

The supported entry point is `kaapi.analyze_text(content, runtime=...,
source=..., policy=...)`; it is a general Kaapi library capability, not a
Charlie-specific fork. It uses the existing parsers, policy evaluator, and
analysis pipeline and does not write a temporary configuration file. Policy
input is optional and accepts the same closed policy shapes supported by the
P2.1 in-memory boundary. P2.2A also provides an optional local FastAPI
transport at `POST /v1/analyze`; hosted deployment, authentication, upload,
and browser boundaries remain consumer responsibilities.
CLI/subprocess integration remains a possible fallback when process isolation
or independent deployment is more important, but it is not the preferred seam.

## P2 integration boundary

P2.1 implements the in-memory organisational-policy evaluation boundary and a
small external-style four-case workshop harness under `evaluation/p2_1/`. The
harness owns grading while Kaapi owns deterministic analysis, policy results,
findings, evidence, and static-analysis limitations.

P2.2A implements the small versioned and deterministic local HTTP adapter and
demonstrates equivalent assessments through the Python and HTTP APIs.
Remaining P2 work is portable Docker packaging, hosting feasibility, and full
AI Security Lab golden evaluation dataset integration.

The HTTP layer will reuse the existing analysis engine; it will not introduce
a second implementation. Cloudflare may be evaluated as an optional hosting
platform, but hosted deployment will not be required for local Kaapi use.
Kaapi remains deterministic and model-free: P2 requires neither an LLM nor
runtime execution. The former feature backlog (additional agent adapters,
SARIF, mappings, blast-radius modelling, and model-narrated explanation) is
classified as P3 and is not implemented.

## Current limitations relevant to Charlie

- No runtime telemetry or runtime enforcement.
- No hosted API, full evaluation-dataset integration, or natural-language
  policy interpretation.
- No Codex `.rules` analysis or project-trust observation.
- Environment exposure is only partially modeled.
- Codex `allow_login_shell` is parsed and validated but does not currently
  materially affect resolution or findings.
- Codex support is tested, but less extensively than Claude support.

## Trust boundary

Kaapi observes configuration statically. It does not run hooks, MCP servers,
shell commands, helper scripts, or network requests described by a settings
file. File contents are evidence, not instructions.

## References

- [Build specification v1.3](../../docs/KAAPI_BUILD_SPEC_v1.3.md)
- [P0 controls](p0-controls.md)
