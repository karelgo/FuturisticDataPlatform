# ADR-0001: Apache Iceberg v3 as the Canonical Table Format; Lance for AI Data

**Status:** Accepted · **Date:** 2026-07

## Context

ODAP standardized on Delta Lake with Iceberg "covered through abstraction" (its ADR-0006). Since then the format war effectively resolved: the Iceberg REST Catalog became the interop standard every engine speaks; Iceberg v3 shipped deletion vectors, row lineage, and the VARIANT type; and the announced v4/Delta convergence means the formats are merging at the spec level. Meanwhile AI workloads (embeddings, documents, training corpora) need random access and versioning that Parquet-based table formats don't serve well.

## Decision

- **Apache Iceberg v3 on Parquet** is the single canonical table format for all analytical data.
- **Lance** is the second, AI-native format for embeddings/multimodal/training data — same buckets, same catalog, same contracts and masks.
- **Apache Amoro** provides continuous compaction and table maintenance from day 1.
- No dual-format abstraction layer: abstraction across table formats (ODAP's approach) costs complexity and forfeits format-specific features.

## Alternatives rejected

- **Delta Lake:** excellent format, but its center of gravity is one vendor, and the ecosystem's neutral interchange (REST catalog, engine support breadth) consolidated on Iceberg.
- **Apache Hudi / Paimon:** strong in niches (record-level upserts, streaming-first); insufficient breadth of engine and catalog support for a platform spine.
- **Vortex/Nimble as file format:** promising, not yet load-bearing; tracked for a future file-format swap beneath Iceberg.

## Consequences

- Row lineage and deletion vectors enable the erasure pipeline (ADR-0010's evidence plane and the GDPR erasure service depend on them).
- Streaming-born small files are a standing tax → Amoro is non-optional and budgeted.
- Delta→Iceberg migration for ODAP tables: Apache XTable in-place metadata conversion where history is clean; rewrite otherwise (Phase 1).
- Lance's non-foundation governance is a tracked risk; its role is contained to the AI data slot.
