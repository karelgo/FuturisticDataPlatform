# CARINA vs. ODAP — the Full Delta

[ODAP](https://github.com/karelgo/open-data-analytics-platform) was the 2022-era blueprint executed well: a compliant, Kubernetes-native, open-source lakehouse. CARINA is not an upgrade of ODAP — it is a re-founding on different first principles. This document records what was kept, what was replaced, what is new, and the reasoning pattern behind each.

## The Diagnosis

ODAP's architecture worked, but four structural patterns limited it:

1. **Glue instead of specs.** The om-access-bridge (OpenMetadata task → Keycloak role → OPA grant) is emblematic: real governance built as custom, unportable wiring. CARINA replaces the pattern itself — contracts compile into enforcement.
2. **A passive catalog.** Hive Metastore answers "where is the table?" but enforces nothing. CARINA's catalog vends credentials, evaluates authorization, and emits audit events — it is the control point.
3. **Always-on JVM economics.** Spark, Trino, Airflow, and friends idle expensively. CARINA is scale-to-zero by default (DuckDB lane, KEDA, diskless streaming) with the JVM contained behind protocol seams.
4. **AI at the edge.** Multica/Nanitics were exploratory sidecars outside the governance flow. CARINA's agents are inside the same identity, policy, and audit fabric as every human.

## Kept (and why)

| Component | Role in CARINA | Why it stays |
|---|---|---|
| **Keycloak** | Identity for humans *and* agents | Proven, OIDC-standard, now extended with CIMD/OAuth for agents |
| **Trino** | Lane 2: governed federation | Best-in-class federation + mature OPA integration; demoted from center of gravity to one lane among four |
| **OPA** | Query-time row/column/purpose decisions | The engine stays; the Rego is now *generated* from contracts, never handwritten |
| **OpenMetadata** | Business/context catalog + agent grounding (MCP) | Strong catalog; its enforcement ambitions are removed — it informs, Lakekeeper/OPA enforce |
| **Spark** | Heavy ETL behind Spark Connect | Irreplaceable for the heaviest batch; now vectorized (Gluten/Velox) and hidden behind a URL |
| **Superset** | On-demand classic BI | Kept as fallback; Rill/Evidence take the primary seats |
| **Stackable operators** | Operator management where they fit | Kept, scoped down |
| **Kubernetes-native, GitOps, synthetic-data-only doctrine** | Foundation | ODAP got these right |

## Replaced (and why)

| ODAP | CARINA | Why |
|---|---|---|
| MinIO | **Rook-Ceph** (prod) / **Garage** (dev) | MinIO OSS archived April 2026; foundation governance is now a hard selection criterion |
| Delta Lake | **Apache Iceberg v3** (+ **Lance** for AI data) | Ecosystem-neutral ASF format; REST catalog standard; row lineage; v4/Delta convergence de-risks |
| Hive Metastore | **Lakekeeper** (Polaris fallback, drilled quarterly) | Phonebook → border control: credential vending, ReBAC, CloudEvents audit |
| Spark Structured Streaming file ingest | **Debezium → AutoMQ Table Topics → Iceberg** + **RisingWave** (+ Flink heavyweight tier) | Streaming becomes the default path, with S3 as the only broker state |
| NiFi templates (disabled) | **dlt** (SaaS EL) + object-store drop zones | The actual long tail of ingestion, contract-governed, in the golden path |
| dbt-trino | **SQLMesh + SQLGlot + Recce** | Virtual per-PR environments, column-level lineage, merge-blocking data diffs; LF governance |
| Airflow 3 + cosmos | **Dagster** (+ **Kestra**) | Asset-oriented model matches data products; MCP server for agents |
| JupyterHub + KubeSpawner | **marimo** | Reactive, git-native, reproducible by construction, deploys as an app |
| Superset-as-primary | **Rill + Evidence** (+ Superset on demand) | BI-as-code, versioned like everything else |
| Astro/React iframe portal | **Backstage + Data Product Portal** | Real composition over shared specs and SSO — no iframes, structurally |
| om-access-bridge (custom glue) | **Contract compiler** (ODCS → OpenFGA tuples + generated Rego) | Specs replace glue; access is a product feature with policy-decided self-service |
| Vector + Prometheus + OpenSearch sprawl | **OpenTelemetry + eBPF → ClickStack** | One SQL-queryable columnar signal store; completes ODAP's half-wired OTel ambition |
| Terraform + Helm + Make sprawl | **Argo CD + Crossplane + vCluster** | One write path (Git), workspaces as an API, tenant isolation |
| Multica + Nanitics (exploratory) | **Analyst / Engineer / Steward on LangGraph + MCP** | Agents as governed products inside the trust fabric, not sidecars outside it |

## New (no ODAP counterpart)

- **The contract compiler** — ODCS 3.1/ODPS 1.0 as the hub artifact everything compiles from.
- **The semantic layer** (Cube + MetricFlow + OSI) — ODAP's most consequential gap; now the only AI path to data.
- **The Lane Router** — nobody chooses an engine.
- **StarRocks serving lane** — sub-second concurrent OLAP on Iceberg.
- **Reverse ETL** (Multiwoven) — governed activation back to operational systems.
- **The evidence plane** — hash-chained audit tables; compliance as a continuous query.
- **Erasure as an SLO'd operation** with signed certificates and lineage-driven propagation.
- **Synthetic-data twins** during access approval; differential-privacy tier.
- **Sovereign inference** (vLLM/llm-d/KServe + EU-usable open weights) and the private MCP registry.
- **SPIFFE/SPIRE workload identity**; OpenFGA ReBAC.
- **Incident lifecycle** with contract-routed paging and product status pages.
- **Cross-Lane Conformance Suite**, chaos testing, DR tiers with drilled RPO/RTO.
- **FinOps/GreenOps as governed metrics** (OpenCost + Kepler in the semantic layer).
- **Entity resolution pattern** (Splink `party-master`).
- **Sloop minimal profile** and a stated platform-team operating model.

## What ODAP Taught Us

The deepest lesson is not any component swap: it is that **every place ODAP wrote custom glue, a spec now exists** — ODCS for contracts, IRC for catalogs, MCP for tools, OpenLineage for lineage, CloudEvents for events, OSI for semantics. The 2026 platform's job is to pick the specs, compile from them, and keep the bespoke inventory down to the seven items listed in [components.md](components.md#the-bespoke-inventory-kept-deliberately-short). ODAP's compliance-first instinct, Kubernetes-native posture, and synthetic-data doctrine carry forward unchanged — they were right; the implementation generation beneath them simply turned over.
