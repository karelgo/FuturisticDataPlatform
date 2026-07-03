# ADR-0002: Lakekeeper as the Catalog Control Plane; Polaris as the Drilled Fallback

**Status:** Accepted · **Date:** 2026-07

## Context

ODAP used a Postgres-backed Hive Metastore: a passive Thrift phonebook that enforces nothing, audits nothing, and vends nothing. The Iceberg REST Catalog (IRC) spec turned the catalog slot into the natural control point of a lakehouse: the one place every engine already has to call, and therefore the one place authorization, credential vending, and audit emission can live without per-engine integration work.

## Decision

**Lakekeeper** (Rust, EU-backed, Apache 2.0) is the platform's data control plane:

- **Credential vending** — engines receive short-lived, table-scoped storage credentials; no engine, human, or agent ever holds bucket keys.
- **Built-in OpenFGA** ReBAC authorization, plus the OPA bridge for Trino's finer-grained needs.
- **Exactly-once CloudEvents** emission on every commit/access — the feed for the evidence plane.
- Multi-table commits; Postgres backend managed by CloudNativePG.

**Apache Polaris** (ASF) is the designated fallback, and the fallback is *operational*: a quarterly, CI-tested Lakekeeper→Polaris migration drill runs against a snapshot of production metadata.

## Alternatives rejected

- **Hive Metastore:** legacy in every dimension; no vending, no authz, no events.
- **Apache Polaris as primary:** strong ASF governance, but Lakekeeper's built-in ReBAC + CloudEvents + Rust operational profile fit CARINA's trust plane better today; Polaris is the insurance policy.
- **Apache Gravitino / Unity Catalog OSS / Nessie:** unified-metadata and git-for-data are attractive; none combines vending + ReBAC + events + IRC maturity in one deployable unit yet.

## Consequences

- Lakekeeper's Postgres becomes the platform's **crown jewels**: DR Tier 0 (RPO ≤ 5 min, RTO ≤ 30 min, monthly restore drills).
- Young-project risk is real and accepted — mitigated by the IRC spec (migration is a metadata move) and the drilled fallback.
- Every engine integration reduces to "mount the IRC endpoint," which is what keeps the four-lane compute design (ADR-0004) cheap to operate.
