# P2.2A local FastAPI REST API

## Scope and status

P2.2A is complete and independently accepted on the development branch as a
thin local transport around the existing deterministic Kaapi engine. It does
not add Docker, hosted infrastructure, authentication, persistence, runtime
execution, or a second analysis engine.

## Request contract

`POST /v1/analyze` accepts a JSON object:

```json
{
  "runtime": "claude-code",
  "config": "{\"sandbox\":{\"enabled\":true}}",
  "policy": {
    "schema_version": "1",
    "id": "example-policy",
    "requirements": [
      {
        "control_id": "AGENT-SBOX-001",
        "expectation": "pass",
        "parameters": {"require_enabled": true}
      }
    ]
  },
  "source": "optional-display-label"
}
```

`runtime` is `claude-code` or `codex`; `config` is Claude JSON or Codex TOML
text; `policy` uses the same closed policy document, mapping, or deterministic
bundle shapes accepted by `kaapi.analyze_text(...)`; and `source` is an
optional display identifier. Request bodies are limited to 1 MiB.

## Response and errors

A valid request returns the existing versioned Kaapi analysis document without
an HTTP-specific assessment model. Security `posture` and
`organisation_policy.verdict` remain independent. An adverse assessment is a
successful HTTP response, not a transport error.

Invalid requests return a stable envelope such as:

```json
{
  "error": {
    "code": "invalid_configuration",
    "message": "The configuration input is invalid."
  }
}
```

The defined codes are `invalid_request`, `invalid_configuration`,
`invalid_policy`, `request_too_large`, and `internal_error`. Responses do not
expose stack traces, filesystem details, or private parser exception types.
The public Python boundary exports `ConfigError` and `PolicyError` from
`kaapi` for callers that need typed input failures.

## Evidence and security boundary

The service only establishes configured authority and resolved permitted
capabilities. It does not observe agent runtime behaviour, enforce controls,
verify outcomes, execute commands, fetch remote URLs, or read request-
controlled filesystem paths.

The adapter is exercised by the HTTP tests in `tests/test_http_api.py`, which
cover all four P2.1 golden cases, Python/HTTP parity, malformed and
unsupported input, oversize requests, fail-closed policy runtime handling,
determinism, and safe errors. A separate `curl` invocation against a running
service is the black-box boundary check. The acceptance review recorded 25
focused tests and 175 total tests passed, with one non-blocking Starlette/httpx
deprecation warning.

## Next stages

- P2.2B — Portable Docker service (next; not started).
- P2.3 — Golden dataset and evidence/evaluation expansion.
- P2.4 — Hosting, distribution, documentation, and release readiness.
