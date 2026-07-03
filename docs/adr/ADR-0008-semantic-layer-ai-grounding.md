# ADR-0008: The Semantic Layer Is the Only AI Path to Data; Raw Text-to-SQL Is Banned

**Status:** Accepted · **Date:** 2026-07

## Context

ODAP had no semantic layer — its most consequential gap: every dashboard, notebook, and ad-hoc query re-derived business logic, and there was no safe grounding for AI access. Benchmark evidence through 2025–2026 (Spider 2.0-class enterprise workloads) shows raw schema-to-SQL generation plateauing far below decision-grade accuracy, while semantic-layer-grounded natural-language query reaches production-trustworthy accuracy — because the hard part (what does "net revenue" mean?) is resolved once, by humans, in a reviewed artifact.

## Decision

- **Cube** (OSS core) serves governed metrics over MCP, Postgres-wire SQL, and REST/GraphQL — to BI tools, notebooks, and agents identically.
- Definitions are authored as **MetricFlow YAML** (Apache 2.0), versioned in Git beside the contracts they draw from; **Open Semantic Interchange (OSI)** is the interchange format.
- **Raw text-to-SQL is banned platform-wide, including as an "expert mode."** The Analyst agent resolves questions only against governed metrics; unmapped questions get an honest refusal.
- The refusal stream is product input: the **Steward flywheel** turns query-miss telemetry into proposed semantic-model extensions as reviewed PRs.
- Semantic-model stubs are **compiled from data contracts**, so every product is minimally conversable at ship time.

## Alternatives rejected

- **Raw text-to-SQL with guardrails:** the failure mode is a confident, plausible, wrong answer shown to a decision-maker — the worst outcome a data platform can produce.
- **dbt Semantic Layer as served runtime:** MetricFlow the *language* is adopted; the served runtime ties to a consolidating vendor. Cube serves; MetricFlow defines; OSI keeps the definitions portable.
- **BI-tool-local semantics (LookML-style):** re-fragments the metric truth per tool.

## Consequences

- Semantic coverage becomes the platform's real bottleneck — accepted, made visible (coverage is a tracked metric), and self-improving via the flywheel.
- Every AI answer can render the "why you can trust this" panel because every number resolves to a versioned, owned, quality-checked definition.
- Metric change management (versioning, 90-day deprecation windows, consumer notification, CI blocks on deprecated consumption) is governed like schema change.
