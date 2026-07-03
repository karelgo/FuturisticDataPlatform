# ADR-0007: Dagster for Data-Product Orchestration; Kestra for Platform Automation; Airflow Retired

**Status:** Accepted · **Date:** 2026-07

## Context

ODAP ran Airflow 3 with astronomer-cosmos wrapping dbt DAGs. Airflow's task-centric model answers "did my task run?"; a data-product platform needs the asset-centric question: "is this table fresh, correct, and who does it depend on?" Dagster's asset graph, declarative automation (freshness policies, event-driven materialization), software-defined scaffolding (`dg` CLI, Components), and shipped MCP server align with CARINA's contract-compiled, agent-operated model.

## Decision

- **Dagster** orchestrates data products: every contract-scaffolded product lands as a set of Dagster assets (dlt sources, SQLMesh models, quality checks) with lineage and freshness first-class.
- **Kestra** handles event-driven platform automation (chores, reactions to CloudEvents, operational workflows) where the asset model doesn't fit.
- **Airflow is retired.** Migration: cosmos-wrapped DAGs run under Dagster first, then are rewritten as assets (Phase 2).

## Alternatives rejected

- **Airflow 3:** improved, but the task-centric model fights the data-product abstraction; keeping it preserves ODAP's DAG sprawl.
- **Prefect:** strong dev experience; weaker asset/lineage story for this platform's needs.
- **Argo Workflows only:** right for CI-shaped work, wrong as the data-product control loop.

## Consequences

- Dagster's asset graph becomes a second lineage source, reconciled into OpenLineage events (one nervous system).
- The Engineer agent consumes Dagster's MCP server for run/asset state during root-cause traversal.
- Two orchestrators is a deliberate split, not sprawl: assets vs. events — the boundary is documented and enforced in review.
