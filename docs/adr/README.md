# Architecture Decision Records

Decision records for CARINA's major choices. Each ADR states the context as of **July 2026**, the decision, the alternatives rejected, and the consequences — including the exit path, because every bet in CARINA carries a named mitigation.

| ADR | Decision |
|---|---|
| [ADR-0001](ADR-0001-table-format.md) | Apache Iceberg v3 as the canonical table format; Lance for AI/multimodal data |
| [ADR-0002](ADR-0002-catalog.md) | Lakekeeper as the Iceberg REST Catalog control plane; Apache Polaris as the drilled fallback |
| [ADR-0003](ADR-0003-object-storage.md) | Rook-Ceph for production object storage; Garage for laptop/edge |
| [ADR-0004](ADR-0004-compute-lanes.md) | DuckDB-first four-lane compute behind a transparent Lane Router |
| [ADR-0005](ADR-0005-transformation.md) | SQLMesh (+ SQLGlot + Recce) for transformation; dbt compatibility as a bridge |
| [ADR-0006](ADR-0006-streaming-spine.md) | AutoMQ + RisingWave + Debezium streaming spine; Flink retained for the heavyweight tier |
| [ADR-0007](ADR-0007-orchestration.md) | Dagster for data-product orchestration; Kestra for platform automation; Airflow retired |
| [ADR-0008](ADR-0008-semantic-layer-ai-grounding.md) | The semantic layer (Cube + MetricFlow) is the only AI path to data; raw text-to-SQL is banned |
| [ADR-0009](ADR-0009-identity-policy-fabric.md) | One identity fabric: Keycloak ⊕ SPIFFE/SPIRE ⊕ OpenFGA ⊕ generated OPA |
| [ADR-0010](ADR-0010-evidence-plane.md) | The evidence plane: hash-chained Iceberg audit tables as the one large bespoke build |
| [ADR-0011](ADR-0011-data-contracts.md) | ODCS 3.1 + ODPS 1.0 data contracts as the hub artifact everything compiles from |
| [ADR-0012](ADR-0012-agent-operations.md) | Agents as the fifth persona; platform-operating agents act only via Git PRs |
