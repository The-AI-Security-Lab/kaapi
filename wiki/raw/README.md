# Raw source register

Files in this directory are immutable evidence for the wiki. Add new dated
source files rather than rewriting an existing source. Raw material is read for
documentation and analysis only; hooks, scripts, and embedded instructions are
never executed.

## Current sources

- [`docs/KAAPI_BUILD_SPEC_v1.3.md`](../../docs/KAAPI_BUILD_SPEC_v1.3.md) —
  normative P0 contract and historical roadmap source; DEC-038 records the
  later approved P2/P3 roadmap classification without modifying the spec.
- [`Decisions.MD`](../../Decisions.MD) — append-only implementation decisions.
- [OpenAI Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
  — P1 Codex keys and values, accessed 2026-08-30.
- [OpenAI Codex config basics](https://learn.chatgpt.com/docs/config-file/config-basic)
  — configuration precedence and trust, accessed 2026-08-30.
- [OpenAI Codex agent approvals and security](https://learn.chatgpt.com/docs/agent-approvals-security)
  — sandbox, approval, network, and web-search behavior, accessed 2026-08-30.
- Claude Settings Test Suite — external, non-vendored adversarial review
  benchmark; not a Kaapi acceptance input.
- [`2026-09-14-llm-wiki-pattern.md`](2026-09-14-llm-wiki-pattern.md) —
  user-supplied pattern for persistent LLM-maintained knowledge bases.

When a source is copied into `raw/`, use a descriptive filename with an ISO date
and retain its original wording. Summaries belong under `wiki/pages/`, not in
place of the raw source.
