# CARINA Component Registry

Every component in the platform: its layer, role, and what it replaced from [ODAP](https://github.com/karelgo/open-data-analytics-platform) and why. Versions and project statuses are as of **July 2026**.

Selection criteria applied throughout: (1) composes over the platform's five connective protocols (Iceberg REST Catalog, Arrow, the identity fabric, spec YAML in Git, CloudEvents/OpenLineage/OTLP/MCP); (2) open governance (ASF/LF/CNCF) or a drilled exit path — the MinIO archive proved rug-pulls are a first-order risk; (3) Rust/Go-first for anything that must scale to zero; (4) EU-sovereign deployable.

| Layer | Component | Version/Status | Role | Replaces (ODAP) & Why |
|---|---|---|---|---|
| Storage | Rook-Ceph (RGW) | v1.15+, CNCF | Production S3 object store, tiered pools (hot/warm/cold) | MinIO — repo archived Apr 2026; foundation governance now mandatory |
| Storage | Garage | v1.x, stable | Laptop/edge S3 profile | MinIO (dev) — EU-built, tiny footprint |
| Table format | Apache Iceberg | v3, ASF | Canonical table format | Delta Lake — ecosystem-neutral, row lineage, deletion vectors; v4/Delta convergence de-risks |
| AI format | Lance | stable | Embeddings / multimodal / training data | *(none)* — new AI-native slot |
| Table maintenance | Apache Amoro | ASF incubating | Continuous compaction & optimization | *(none)* — small-files tax budgeted day 1 |
| Catalog | Lakekeeper | 0.x, EU-backed | Iceberg REST Catalog control plane: credential vending, OpenFGA ReBAC, CloudEvents | Hive Metastore — passive Thrift phonebook → active border control |
| Catalog fallback | Apache Polaris | ASF TLP | Quarterly CI-drilled migration target | — insurance on the Lakekeeper bet |
| Context catalog | OpenMetadata | 1.13+ | Business catalog, lineage, glossary, MCP grounding for agents | Kept and promoted; enforcement role removed |
| Query (interactive) | DuckDB | 1.5.x | Default lane; ephemeral pods, embedded, Wasm; scale-to-zero | Trino-as-center — cost and joy |
| Query (federation) | Trino | 48x | OPA-enforced federation; contained, autoscaled | Kept but demoted from center of gravity |
| Query (serving) | StarRocks | 4.x | Sub-second, high-concurrency OLAP directly on Iceberg | *(none)* — new serving lane |
| ETL engine | Spark 4.x + Gluten/Velox; LakeSail Sail pilot | GA / pilot | Heavy batch behind the Spark Connect seam | Spark-everywhere — the engine becomes a URL |
| Dataframes | Polars, Daft-on-Ray, Ibis | GA | Python/AI lane with a portable API | JupyterHub+PySpark coupling |
| Query routing | Lane Router | bespoke (small) | Transparent DuckDB → Trino → StarRocks/Spark escalation on the Flight SQL front door | *(none)* — nobody chooses an engine |
| Streaming broker | AutoMQ | Apache 2.0 | Diskless Kafka-protocol broker on S3; Table Topics → Iceberg in-broker | Disabled NiFi/Kafka templates — streaming becomes the default path |
| Stream SQL | RisingWave | GA | Incremental view maintenance, Postgres wire protocol, native CDC | *(none)* |
| Stream heavy | Apache Flink | 2.x | CEP, whole-database sync, Materialized Tables | Spark Structured Streaming file ingest |
| CDC | Debezium | 3.4+ | Change-event lingua franca | *(none — templates were disabled)* |
| SaaS EL | dlt | GA | Salesforce/Stripe/GA4/long-tail extract-load, scaffolded into the golden path | *(none)* — closes the SaaS-ingestion gap |
| Reverse ETL | Multiwoven | OSS (AGPL, isolated deployment) | Governed activation to CRMs / ad platforms from contract output ports | *(none)* — closes the activation gap |
| Transformation | SQLMesh | Linux Foundation, GA | Virtual data environments, column-level lineage; dbt-project compatible | dbt-trino — LF governance amid vendor consolidation; per-PR envs for free |
| SQL IR | SQLGlot | GA | Parse / transpile / lineage / conformance across all lanes | *(none)* |
| PR data review | Recce | GA | Merge-blocking lineage + data diffs on every PR | *(none)* |
| Contracts | ODCS 3.1 + ODPS 1.0 + datacontract-cli | Bitol / LF | The hub artifact; CI compilation gate | Custom OM→Keycloak→OPA bridge — specs replace glue |
| Quality | Soda Core + Elementary | GA | Contract-compiled checks + ML anomaly detection | Hand-wired OpenMetadata quality |
| Orchestration | Dagster | 1.13+ | Asset-oriented orchestration, `dg` scaffolding, MCP server | Airflow 3 + cosmos — the asset model fits data products |
| Platform automation | Kestra | GA | Event-driven platform chores | *(none)* |
| Semantic layer | Cube + MetricFlow YAML + OSI | GA / Apache 2.0 / v0.1 | One metric truth for humans and agents; the only AI path to data | *(none)* — ODAP's most consequential gap |
| BI | Rill; Evidence; Superset 6 | GA | Exploratory BI-as-code; narrative products; classic fallback | Superset-as-primary |
| Notebooks | marimo | GA | Reactive, git-native, deploys as app | JupyterHub + KubeSpawner |
| Publishing | Quarto | GA | Reports/sites from notebooks and markdown | *(none)* |
| Portal | Backstage + Data Product Portal (Dataminded) | GA / Apache 2.0 | Engineer spine + business marketplace + status pages | Astro iframe portal |
| Agent runtime | LangGraph + Pydantic AI | GA | Analyst / Engineer / Steward agent runtimes | Multica / Nanitics — retired |
| Agent protocol | MCP + private registry | spec 2025-11-25 | Governed tool plane with per-tool approval tiers | *(none)* |
| Inference | vLLM + llm-d + KServe + Kueue/DRA | GA | Sovereign LLM serving; Mistral 3 weights (+ Apertus/EuroLLM) | *(none)* |
| Vectors | Qdrant (+ pgvector) | GA | Latency tier over Lance system-of-record | *(none)* |
| ML lifecycle | MLflow 3 + Feast | GA | Model registry, evals, feature store | *(none)* |
| AI observability | OpenLLMetry → Langfuse | GA, self-hosted | Agent traces, evals, AI-Act Art. 12 logs | *(none)* |
| Identity | Keycloak + SPIFFE/SPIRE | GA; hourly SVID rotation | Humans, agents, and workloads on one fabric | Keycloak kept; SPIRE new |
| Authorization | OpenFGA + OPA (generated Rego) | GA | ReBAC at the catalog + row/column/purpose at query time | Handwritten Rego + custom bridge |
| Evidence | Hash-chained Iceberg audit tables | bespoke (~4 eng-years, Phases 2–3) | Continuous GDPR/NIS2/AI-Act evidence | *(none)* — the one big custom component |
| Erasure | Erasure service + crypto-shredding | bespoke | SLO'd GDPR erasure with signed completion certificate | Runbooks |
| Synthetic data | SDV / MOSTLY AI SDK | GA | Instant synthetic twin during access approval | *(none)* |
| Privacy tech | OpenDP / Tumult Analytics | GA | Differentially private outputs | *(none)* |
| Confidential compute | Confidential Containers (AMD SEV-SNP / Intel TDX) | GA | Optional tier for infrastructure-operator threat models | *(none)* |
| Entity resolution | Splink | GA | Probabilistic linkage on DuckDB/Spark; golden-record pattern | *(none)* — closes the MDM gap |
| GitOps | Argo CD 3.x + Rollouts | GA | The only write path to production; shadow-replay canaries | Terraform+Helm+Make sprawl |
| Composition | Crossplane 2.0 + vCluster | GA | "Data-product workspace" as a K8s API + tenant/agent sandboxes | *(none)* |
| Scheduling & scaling | Kueue/DRA + Karpenter + KEDA (carbon-aware pattern in-repo) | K8s ≥ 1.34 | Fair sharing, spot-first, scale-to-zero, low-carbon windows | Static sizing |
| Databases | CloudNativePG | GA | Every platform Postgres; PITR via barman-cloud | Unmanaged Postgres |
| Secrets | External Secrets Operator + OpenBao | GA | EU-safe secret management | Assorted |
| Observability | OpenTelemetry + eBPF instrumentation + ClickStack | GA | One SQL-queryable columnar signal store | Vector/Prometheus/OpenSearch sprawl |
| FinOps / GreenOps | OpenCost + Kepler | GA | Cost-per-query and gCO₂-per-pipeline as semantic-layer metrics | *(none)* |
| Incidents | GoAlert + portal status pages | GA / bespoke render | Paging routed from the contract `owner` field; product status pages | *(none)* — closes the incident gap |
| Chaos & conformance | LitmusChaos + Cross-Lane Conformance Suite | GA / bespoke | Resilience testing + SQL-dialect-drift defense | *(none)* |
| K8s operators | Stackable operators (where they fit) | GA | Trino and friends under operator management | Kept, scoped down |

## The bespoke inventory (kept deliberately short)

Everything custom-built in CARINA, in one list — if it's not here, it's off-the-shelf:

1. **The contract compiler** (ODCS/ODPS → checks, DDL, masks, tuples, lifecycle, routing, pages). Small, mostly generation logic over datacontract-cli.
2. **The Lane Router** (routing decisions over SQLGlot + statistics + telemetry). Small.
3. **The evidence plane** (hash-chained audit tables + standing compliance queries). The one large build, ~4 engineer-years; every ingredient is standard — only the assembly is ours, and the assembly is the moat.
4. **The erasure service** (lineage-driven propagation + crypto-shredding + certificates).
5. **The Cross-Lane Conformance Suite** (canonical corpus, cell-level diffing).
6. **The `carina` CLI** (thin wrapper over scaffolds, SQLMesh, Dagster, and the portal APIs).
7. **The carbon-aware KEDA scaling pattern** (~200 lines, owned in-repo).

ODAP's bespoke inventory (the om-access-bridge, portal iframe shell, Make/scripts sprawl, custom quality wiring) is retired in full.
