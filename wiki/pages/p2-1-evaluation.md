# P2.1 workshop evaluation integration

## Scope and status

P2.1 is the first implemented slice of the approved P2 Evaluation Integration
& API roadmap. It is present on the current development branch, not in the
released `v1.1.0` tag. The slice connects a workshop security requirement to a
configuration, Kaapi's deterministic assessment, and an external-style grade
without adding runtime execution or an HTTP service.

## Analysis boundary

`kaapi.analyze_text(...)` now accepts an optional closed organisational-policy
document as UTF-8 text, bytes, a decoded mapping, or a non-empty deterministic
sequence of those inputs. It reuses the same validation, policy evaluator, and
overlay helper as the CLI. Existing callers that omit `policy` retain the P1
result shape and semantics.

The API returns Kaapi's security posture and organisation-policy result
separately. The result remains static configuration analysis: it establishes
configured authority and resolved capability, but does not verify runtime
enforcement, agent behaviour, hooks, MCP execution, or network activity.

## Workshop harness

The external-style harness lives under `evaluation/p2_1/`. It owns only the
workshop grade; Kaapi owns parsing, policy evaluation, findings, evidence, and
limitations. Four declarative golden cases cover insecure and hardened Claude
JSON plus insecure and hardened Codex TOML:

| Case | Runtime | Expected grade |
| --- | --- | --- |
| `claude-insecure` | Claude Code | `FAIL` |
| `claude-hardened` | Claude Code | `PASS` |
| `codex-insecure` | Codex | `FAIL` |
| `codex-hardened` | Codex | `PASS` |

The harness also fails closed:

- `INCONCLUSIVE` means a matching result exists but required evidence is
  missing;
- `NOT_TESTED` means the manifest, configuration, policy, or runtime/control
  support is unavailable or malformed;
- `PASS` requires the selected policy requirement to pass;
- `FAIL` represents an evaluated non-pass requirement.

Run one checked-in case with:

```console
uv run python -m evaluation.p2_1.harness \
  evaluation/p2_1/golden/claude-insecure
```

## Remaining P2 work

The versioned HTTP adapter, hosted-deployment evaluation, full AI Security Lab
golden dataset integration, and CLI/Python/HTTP equivalence checks remain
planned P2 work. P3 remains the deferred adapter, mapping, SARIF,
blast-radius, and model-narrated explanation backlog.

## References

- [Roadmap](roadmap.md)
- [Testing and fixtures](testing-and-fixtures.md)
- [Architecture](architecture.md)
- [Decision log, DEC-039](../../Decisions.MD)
- [P2.1 harness README](../../evaluation/p2_1/README.md)
