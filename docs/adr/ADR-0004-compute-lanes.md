# ADR-0004: DuckDB-First Four-Lane Compute Behind a Transparent Lane Router

**Status:** Accepted · **Date:** 2026-07

## Context

ODAP put Trino at the center: every query, however small, paid for an always-on JVM cluster. Meanwhile the single-node revolution (DuckDB), vectorized Spark (Gluten/Velox), Rust reimplementations (LakeSail Sail), and Iceberg-native real-time OLAP (StarRocks) made "one engine for everything" the wrong trade in every direction at once. The counter-risk of multiple engines is fragmentation: users forced to choose, and SQL semantics drifting between lanes.

## Decision

Four lanes, one substrate (Iceberg via Lakekeeper), one Arrow Flight SQL front door:

1. **DuckDB fleet** (ephemeral pods / embedded / Wasm) — the default lane; scale-to-zero by construction.
2. **Trino** (one contained autoscaled cluster) — governed federation, OPA-heavy ad-hoc.
3. **Spark Connect endpoint** — heavy ETL on Spark 4.x + Gluten/Velox, with **Sail** piloted behind the same URL; the engine is a URL, not a commitment.
4. **StarRocks** — sub-second, high-concurrency serving directly on Iceberg.

A small bespoke **Lane Router** on the front door (SQLGlot parse + Lakekeeper statistics + ClickStack telemetry) routes and escalates queries transparently. **No user, notebook, dashboard, or agent ever selects an engine.** Python dataframes run Polars / Daft-on-Ray behind Ibis.

## Alternatives rejected

- **Trino-only (ODAP model):** pays always-on JVM economics for interactive workloads DuckDB serves in milliseconds at near-zero cost.
- **DuckDB-only:** single-node ceiling is real; federation and high-concurrency serving need Trino/StarRocks.
- **Exposing engine choice to users:** every consulted persona journey got worse; engine choice is operational detail, not user intent.

## Consequences

- **Dialect drift is the design's biggest silent risk** → the Cross-Lane Conformance Suite (canonical corpus, cell-level diffing) runs nightly and gates engine/SQLGlot upgrades; TPC-DS-derived + production-replay perf gates guard upgrades via Argo Rollouts shadow replay.
- The Lane Router is bespoke and must stay small (routing policy over parse + stats + history — not an optimizer).
- Escalations are observable (own OTel span), so cost attribution per lane lands in OpenCost cleanly.
