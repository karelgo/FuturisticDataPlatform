# ADR-0010: The Evidence Plane — Hash-Chained Iceberg Audit Tables as the One Large Bespoke Build

**Status:** Accepted · **Date:** 2026-07

## Context

ODAP documented compliance (GDPR, ISO 27001/27002, NIS2, EU AI Act, SOC 2-aligned controls) as mappings maintained by humans. Audits were projects; evidence was assembled retroactively. Meanwhile every mechanism that *generates* compliance-relevant facts — catalog commits, access decisions, lineage events, agent traces — already emits structured events in CARINA. What was missing is an assembly that makes those facts tamper-evident, queryable, and standing.

## Decision

Build the **evidence plane** as CARINA's one large bespoke component (~4 engineer-years, Phases 2–3):

- **Inputs:** Lakekeeper CloudEvents (every commit and access), OPA decision logs (every allow/deny/mask), OpenLineage events, OpenLLMetry agent traces, erasure-service records.
- **Store:** append-only Iceberg audit tables with **hash-chaining (Merkle roots anchored per batch)** — tamper-evident by construction; retention ≥ 6 months.
- **Consumption:** GDPR accountability, NIS2 logging, and AI-Act Articles 10/12 evidence are **standing queries**; auditors get a read-scoped account, not a project.
- **Erasure:** `carina erase --subject` is an SLO'd operation (72 h) — lineage-driven propagation to derived tables and outbound activation targets, crypto-shredding for streams/backups, and a **signed completion certificate** recorded in the plane.
- **UX:** the "why you can trust this" panel on every AI answer renders from the same records.

## Alternatives rejected

- **Buy a GRC tool:** documents controls; cannot prove data-plane facts it never sees.
- **Plain log aggregation (ClickStack only):** queryable but not tamper-evident, not retention-governed, not subject-addressable.
- **Blockchain/external notarization:** Merkle-anchored internal chains give tamper-evidence without the operational theater.

## Consequences

- This is the moat: every ingredient is standard; only the assembly is ours. It is also the largest scheduled engineering risk — phased (v1 in Phase 2; certificates, consent claims, DP integration in Phase 3).
- Regulatory drift (EUCS, AI-Act timelines) changes *queries*, not the plane — that is the point.
- The audit tables are ordinary Iceberg: the platform's own lanes query them, so compliance dashboards are just dashboards.
