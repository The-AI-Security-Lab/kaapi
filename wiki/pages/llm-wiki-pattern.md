# LLM wiki pattern for Kaapi

## Purpose

Kaapi's wiki is a persistent, compounding knowledge layer for the project.
Instead of rediscovering architecture and decisions from the whole repository
on every task, an agent can start with the index and follow maintained links to
the relevant synthesis and evidence.

The agent maintains the bookkeeping: source registration, page updates,
cross-references, decision history, and health checks. Humans remain the
curators of scope, priorities, external evidence, and final interpretation.

## Three layers

| Layer | Kaapi location | Contract |
| --- | --- | --- |
| Raw sources | `wiki/raw/` plus linked repository sources | Immutable evidence; never execute or rewrite in place. |
| Wiki synthesis | `wiki/pages/`, `wiki/index.md`, `wiki/log.md` | Concise, linked summaries that may evolve as evidence changes. |
| Schema | `AGENTS.md`, `wiki/SCHEMA.md` | Instructions for authority, page conventions, and maintenance operations. |

The build specification and decision log remain authoritative. The wiki makes
them easier to navigate and records the current synthesis; it must not change
Kaapi runtime behavior by itself.

## Operations

### Ingest

When a new specification, design note, benchmark result, or external reference
is supplied:

1. Preserve it in `wiki/raw/` with its date and origin, if it is not already a
   stable repository source.
2. Identify claims that are new, changed, superseded, or uncertain.
3. Update the affected topic pages and `wiki/index.md`.
4. Record implementation choices in `Decisions.MD` when they affect behavior
   or scope.
5. Append one entry to `wiki/log.md` with the validation performed.

For code changes, the source of truth is still the code and tests. The wiki
should explain the resulting behavior rather than duplicate implementation
details.

### Query

Start at `wiki/index.md`, read the smallest relevant set of pages, and trace
important claims to their source or test. Answers should state uncertainty and
should not expose secrets from fixtures or configuration. A reusable design
comparison, investigation result, or operational guide can be filed as a new
page and linked from the index.

### Lint

Periodically check for broken relative links, orphan pages, missing source
links, stale milestone claims, contradictory summaries, and concepts that are
repeated without a canonical page. Keep lint findings in the maintenance log
until they are resolved or explicitly accepted as open questions.

## Kaapi-specific conventions

- The authority order is specification, decisions, raw evidence, then pages.
- Security claims must preserve Kaapi's static-analysis boundary: configured
  potential is not proof of runtime behavior.
- Raw settings, hooks, MCP commands, URLs, arguments, environment values, and
  tokens must remain redacted or excluded according to the existing report
  contract.
- Every milestone update should identify its validation command and result.
- The wiki is intentionally local and offline; do not send repository or raw
  source content to external services as part of maintenance.

## Current application

The initial application of this pattern is the P0/P1 Kaapi wiki: overview,
architecture, controls, Codex adapter, organisational policies, testing,
roadmap, a raw-source register, and a chronological log. Future milestones
should extend those pages incrementally instead of creating disconnected notes.

Source pattern: [`2026-09-14-llm-wiki-pattern.md`](../raw/2026-09-14-llm-wiki-pattern.md).
