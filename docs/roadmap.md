# Roadmap

Four phases over ~24 months, each with a hard definition of done. The ODAP migration is woven through all phases — coexistence and dual-running, never a big bang. Phase names follow the ship: keel first, then sails, then crew, then the horizon.

> This is the **product** roadmap (what ships, when). For the **engineering delivery & deployment** view — how to build and run this on Kubernetes on any cloud, enterprise-ready, starting from the reference implementation — see [implementation-plan.md](implementation-plan.md), which adds a **Phase 0 (Deployable MVP)** ahead of KEEL.

---

## Phase 1 — KEEL (months 0–5): the spine and the golden path

**Scope**
- Rook-Ceph (prod) / Garage (dev); **Lakekeeper + CloudNativePG with Tier-0 DR from day one**; Apache Iceberg v3.
- DuckDB + Trino lanes with a v1 Lane Router on the Flight SQL front door.
- SQLMesh + SQLGlot + Recce + Write-Audit-Publish on Iceberg branches; Dagster; **dlt SaaS ingestion in the scaffold**.
- **Contract compiler v1** (ODCS/ODPS → checks, DDL, masks, catalog).
- Identity fabric: Keycloak + SPIFFE/SPIRE + OpenFGA + generated OPA.
- Backstage + `carina` CLI golden path; OTel → ClickStack; **Argo CD as the only write path**.

**ODAP migration begins**
- Dual-run environment stood up.
- Delta→Iceberg conversion of the 20 highest-value tables: in-place metadata conversion via Apache XTable where clean; rewrite where deletion-vector history requires it.
- Hive-Metastore→Lakekeeper metadata migration tooling built and rehearsed.

**Definition of done**
- A new data product ships end-to-end in **under 60 minutes, measured**.
- ODAP's top-20 tables queryable through Lakekeeper with **row-level parity checks green for 30 consecutive days**.
- Tier-0 restore drill passed.

## Phase 2 — SAILS (months 5–10): motion, semantics, experience

**Scope**
- Streaming by default: Debezium → AutoMQ Table Topics + RisingWave + Amoro as the standard ingestion path; StarRocks serving lane.
- **Cube + MetricFlow** semantic layer with the metric-versioning workflow.
- Experience wave: Rill, Evidence, marimo, Data Product Portal with status pages.
- **Multiwoven reverse ETL** on contract output ports.
- **Evidence plane v1**: hash-chained audit tables fed by CloudEvents + OPA decision logs.
- **Cross-Lane Conformance Suite v1** running nightly.
- Incident lifecycle live: GoAlert routing compiled from contract owners.

**ODAP migration**
- Airflow DAG→Dagster asset porting (cosmos-wrapped DAGs run under Dagster first, then rewritten as assets).
- dbt projects run under SQLMesh compatibility mode.
- Dual-running validation compares outputs table-by-table.
- Analyst retraining wave 1 (Rill/metrics); Superset dashboards inventoried, top 50 rebuilt on governed metrics.

**Definition of done**
- Streaming is the default ingestion for new sources.
- One metric definition demonstrably identical across Rill, Evidence, the SQL API, and chat.
- ODAP Airflow shut off for migrated domains.
- The conformance suite has caught real dialect drift (≥ 1 prevented regression, documented).

## Phase 3 — CREW (months 10–16): the agents and the trust product

**Scope**
- **Analyst, Engineer, Steward agents GA**, with the private MCP registry and auto-merge classes.
- Sovereign inference stack: vLLM + llm-d + KServe, Mistral 3 weights.
- **"Why you can trust this" panel** on every AI answer; the proactive Monday brief.
- **Erasure as an SLO'd operation** with signed certificates; consent/purpose token claims enforced end to end; the synthetic-data twin service.
- Splink golden-record pattern with the first `party-master` data product.
- LitmusChaos suite and quarterly DR game days operational; first Lakekeeper→Polaris drill in CI.

**ODAP migration**
- Remaining Delta tables converted; **Hive Metastore decommissioned**.
- JupyterHub sunset with marimo migration clinics.
- The ODAP portal redirects to the Carina portal.

**Definition of done**
- An erasure request completes within SLO with a certificate, demonstrated on real lineage 3+ hops deep.
- The Engineer agent's first auto-merged remediation **and** first human-approved fix are both in production.
- ODAP is formally read-only.

## Phase 4 — HORIZON (months 16–24): scale, residency, self-improvement

**Scope**
- Multi-region residency topology: per-region Lakekeeper, federated catalog metadata, residency-aware routing.
- **Sail promoted or rejected** on the Spark Connect seam, decided by conformance + performance evidence.
- Flink heavyweight streaming tier where CEP demands it; confidential-computing tier.
- Steward flywheel measured on semantic coverage growth.
- Performance-regression suite (TPC-DS-derived + production query replay) gating every engine upgrade via Argo Rollouts shadow replay.
- **Sloop profile GA**: the smallest credible production install — 3 nodes, ~64 vCPU / 256 GB / 20 TB, ~20 components, run by a 3-person team.
- **Clipper operating model documented**: 6–8 platform FTE (2 infra SRE, 2 data platform, 1 governance engineer, 1 DX/enablement, + rotation); one-week on-call where agents file the first PR before paging.

**Definition of done**
- ODAP decommissioned entirely.
- A second region serving residency-scoped products.
- A Sloop install deployed **from docs alone** by a team that didn't build the platform, in under one week.

---

## Migration Doctrine (ODAP → CARINA)

1. **Coexist, don't cut over.** Dual-run with table-by-table parity validation; consumers move when their products are green, not when a date arrives.
2. **Convert metadata before data.** XTable in-place conversion where table history allows; rewrite only where it doesn't.
3. **Compatibility modes as bridges, not destinations.** dbt-on-SQLMesh and cosmos-DAGs-on-Dagster are transition states with sunset dates.
4. **Retraining is budgeted work.** Migration clinics (marimo, Rill, metrics-first analytics) and the Carina Academy curriculum are Phase 2–3 line items, not goodwill.
5. **Every migration step is reversible until its parity gate passes.** The old path stays warm until 30 consecutive green days.
