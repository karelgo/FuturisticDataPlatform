# ADR-0005: SQLMesh for Transformation; dbt Compatibility as a Bridge

**Status:** Accepted · **Date:** 2026-07

## Context

ODAP used dbt-trino with astronomer-cosmos. The transformation market consolidated sharply (dbt Labs/Fivetran-era churn), while SQLMesh moved to Linux Foundation governance and matured its distinguishing capabilities: **virtual data environments** (per-PR environments and blue-green promotion without data copies), column-level lineage as a first-class citizen, and native multi-dialect support via SQLGlot.

## Decision

- **SQLMesh** is the transformation framework, run in dbt-project compatibility mode during migration.
- **SQLGlot** is the platform-wide SQL intermediate representation — parsing, transpilation across the four lanes, column-level lineage, and conformance checking.
- **Recce** provides merge-blocking lineage + data diffs on every PR.
- **Write-Audit-Publish** on Iceberg branches is the promotion pattern; contract-compiled Soda checks and SQLMesh audits are the gate.

## Alternatives rejected

- **dbt (Core or Fusion):** the Fusion engine is a real advance, but governance/licensing sits with a consolidating vendor; LF governance of SQLMesh is the safe harbor. dbt-project compatibility keeps the escape hatch open in both directions.
- **Handwritten Spark/SQL pipelines:** forfeits environments, lineage, and testability.

## Consequences

- Retraining tax for dbt muscle memory — budgeted via migration clinics and the Carina Academy (Phases 2–3).
- SQLGlot becomes load-bearing infrastructure; its upgrades are gated by the Cross-Lane Conformance Suite (see ADR-0004).
- Per-PR virtual environments + Recce + WAP give the platform blue-green *data* deployments the same way Argo gives blue-green *service* deployments — deployment discipline becomes uniform across code and data.
