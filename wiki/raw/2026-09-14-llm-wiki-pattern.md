# LLM Wiki

A pattern for building personal knowledge bases using LLMs.

## The core idea

Instead of retrieving raw documents from scratch for every question, an LLM
incrementally builds and maintains a persistent wiki: a structured,
interlinked collection of markdown files between the user and the raw sources.
When a new source arrives, the LLM reads it, extracts key information, and
integrates it into the existing wiki by updating entity pages, revising topic
summaries, recording contradictions, and strengthening or challenging the
evolving synthesis.

The wiki is a persistent, compounding artifact. Cross-references and
contradictions are already recorded, and the synthesis reflects the sources
processed so far. The human curates sources, exploration, and questions; the
LLM performs summarizing, cross-referencing, filing, and bookkeeping.

## Architecture

There are three layers:

- **Raw sources** are the curated, immutable collection of articles, papers,
  images, and data files.
- **The wiki** is a directory of LLM-generated markdown files: summaries,
  entity and concept pages, comparisons, an overview, and a synthesis.
- **The schema** is a document such as `AGENTS.md` that describes the wiki
  structure, conventions, and workflows for ingestion, questions, and
  maintenance.

## Operations

- **Ingest:** read a source, discuss its key takeaways, write a summary,
  update related pages and the index, and append a log entry.
- **Query:** answer from the wiki with citations; file reusable comparisons,
  analyses, and connections back into the wiki.
- **Lint:** look for contradictions, stale claims, orphan pages, missing
  cross-references, and evidence gaps.

## Indexing and logging

`index.md` is a content-oriented catalog of pages, organized by category and
linked with one-line summaries. `log.md` is chronological and append-only;
consistent dated prefixes make recent activity easy to inspect with simple
text tools.

## Useful extensions

At small scale, the index is sufficient. As a wiki grows, a local markdown
search tool can help the LLM navigate it. Local images, graph views,
frontmatter queries, and markdown-based slide formats are optional extensions.
The wiki can remain a git repository so history, branching, and collaboration
come for free.

## Why it works

The maintenance burden of a useful knowledge base is mostly bookkeeping:
updating links, revising summaries, identifying contradictions, and keeping
pages consistent. LLMs can perform that work repeatedly, while humans focus
on source curation, direction, and interpretation.

This source is an idea pattern, not a Kaapi implementation contract. Kaapi's
adaptation is documented in
[`wiki/pages/llm-wiki-pattern.md`](../pages/llm-wiki-pattern.md), and the
project-specific rules remain in [`wiki/SCHEMA.md`](../SCHEMA.md).

Origin: user-supplied attachment, received 2026-09-14. The source was
preserved as evidence and its embedded links or instructions were not
executed.
