# ADR-0011: ODCS 3.1 + ODPS 1.0 Data Contracts as the Hub Artifact

**Status:** Accepted · **Date:** 2026-07

## Context

ODAP's governance was real but wired by hand: quality checks written in one place, Rego in another, catalog entries in a third, access flows in custom bridge code — with nothing keeping them consistent. The Bitol standards (Open Data Contract Standard 3.1, Open Data Product Standard 1.0, under the Linux Foundation) and datacontract-cli matured into a practical spine for compiling governance instead of wiring it.

## Decision

- Every data product is declared by an **ODCS 3.1 contract** (schema, classifications, quality SLOs, retention, owners, purposes, output ports) and an **ODPS 1.0 descriptor** (the product around it).
- **No contract, no deployment** — CI (datacontract-cli) gates every merge.
- The **contract compiler** generates everything downstream: Soda checks + SQLMesh audits, DDL, schema-registry entries (enforced broker-side at write), OPA masks, OpenFGA tuples, catalog metadata, Ceph lifecycle/tiering and snapshot-expiry schedules, GoAlert incident routing, semantic-model stubs, and the marketplace/status page.
- **Handwritten versions of any compiled artifact are a design failure** and rejected in review.

## Alternatives rejected

- **Custom contract schema:** repeats ODAP's glue mistake one level up; the standard's ecosystem (tooling, familiarity, interchange) is the value.
- **Contracts as documentation (unenforced):** contracts that don't compile into enforcement drift into fiction within a quarter.
- **Catalog-first governance (define in OpenMetadata, export outward):** puts the source of truth in a runtime UI instead of Git; loses review, versioning, and CI.

## Consequences

- One commit updates checks, masks, DDL, catalog, marketplace, and agent grounding; Argo CD reconciles the world to it.
- The contract file becomes the platform's most important interface — its scaffold quality (via `carina create`) directly determines platform joy.
- Incident reviews must merge as contract amendments, making institutional memory structural (see governance doc §5).
