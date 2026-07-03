# ADR-0003: Rook-Ceph for Production Object Storage; Garage for Laptop/Edge

**Status:** Accepted · **Date:** 2026-07

## Context

ODAP used MinIO. MinIO's open-source edition was progressively wound down: management features stripped from the community console (mid-2025), binary releases stopped, maintenance mode (Dec 2025), and the `minio/minio` repository archived read-only on April 25, 2026 (verified on GitHub; last release Oct 2025). The commercial replacement (AIStor) starts around $96k/year. The episode elevated **foundation governance from nice-to-have to hard selection criterion** for an EU-sovereignty platform that cannot fall back to a US-managed service.

## Decision

- **Rook-Ceph (RGW/S3)** is production object storage: LGPL, CNCF-graduated orchestration, battle-tested at petabyte scale, with pool-level tiering (hot NVMe replicated / warm HDD erasure-coded / cold EC+compression) driven by contract-compiled lifecycle rules, and RGW multisite replication for DR.
- **Garage** (EU-built, lightweight) serves the laptop/edge/Sloop profile.
- EU-provider S3 (StackIT, OVHcloud, Scaleway) is a first-class substitution because the platform's storage contract is only **"any S3 API + Iceberg REST Catalog."**

## Alternatives rejected

- **MinIO:** archived. **OpenMaxIO:** a fork of an abandoned AGPL codebase — inherits the risk without the community.
- **SeaweedFS:** attractive and Apache-2.0, but thinner operational track record at the scale and durability posture CARINA targets.
- **Apache Ozone:** viable, but Hadoop-lineage operational burden and a thinner Kubernetes story.

## Consequences

- Ceph demands real operations (≥3 nodes, capacity planning) — accepted for Clipper; Sloop runs Garage, provider S3, or at most a single-site Ceph.
- Storage tiering/retention become compiler outputs from ODCS `retention`/`slaProperties` fields — lifecycle is governance, not ops improvisation.
- Vendor-rug-pull defense generalizes: every component selection in [components.md](../components.md) now records governance posture and exit path.
