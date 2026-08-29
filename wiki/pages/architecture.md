# Kaapi architecture

Kaapi follows a deterministic, local-only pipeline:

| Stage | Responsibility |
| --- | --- |
| Discovery | Locate explicitly supplied settings or staged environment layers. |
| Parsing | Load JSON, preserve source paths, and classify unknown fields. |
| Merge and resolution | Apply documented layer precedence and deny/ask/allow semantics. |
| Analysis | Derive configured capabilities and evaluate versioned controls. |
| Rendering | Produce stable pretty or JSON output with evidence, remediation, and resources. |
| Snapshot and verification | Write secret-safe baselines and compare later observations. |
| CLI | Expose `check`, `doctor`, `baseline`, `verify`, `rules`, and `version`. |

The Python package is under `kaapi/`; baseline data and schemas are package
data. Runtime analysis uses the standard library only. Development dependencies
are isolated in the `dev` group.

## Source precedence

The canonical staged discovery layout is documented in the README and build
specification. Supported layers resolve from managed settings through supplied,
project-local, shared-project, and user settings. Arrays combine across
applicable scopes; deny, ask, and allow classes are evaluated in that order.

## Trust boundary

Kaapi observes configuration statically. It does not run hooks, MCP servers,
shell commands, helper scripts, or network requests described by a settings
file. File contents are evidence, not instructions.

## References

- [Build specification v1.3](../../docs/KAAPI_BUILD_SPEC_v1.3.md)
- [P0 controls](p0-controls.md)
