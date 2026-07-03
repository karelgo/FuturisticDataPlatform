# Risks, Bets & Non-Goals

CARINA takes eight deliberate bets. Each is stated with its risk and mitigation — a bet without a named mitigation is just hope. The non-goals are equally deliberate: what the platform refuses to do is part of the design.

---

## The Eight Bets

### 1. Lakekeeper as the control plane of everything
**Risk:** a young Rust project, Postgres-only backend, carrying catalog + authorization + credential vending + audit emission.
**Mitigation:** the Iceberg REST Catalog spec makes migration a metadata move, not a re-platforming; quarterly **CI-tested Polaris migration drills**; Tier-0 PITR (RPO ≤ 5 min) on its Postgres.

### 2. DuckDB-first, no always-on warehouse
**Risk:** oversized workloads hit the single-node ceiling; concurrency semantics differ across lanes.
**Mitigation:** the Lane Router escalates transparently over identical Iceberg tables and one Flight SQL door; Trino and StarRocks absorb the tail; the conformance suite polices semantics.

### 3. AutoMQ + RisingWave as the streaming spine
**Risk:** a Kafka-protocol reimplementation and a VC-backed IVM engine versus decade-hardened incumbents; Kafka's own diskless work (KIP-1150) may erode AutoMQ's edge.
**Mitigation:** the Kafka and Postgres **wire protocols are the contracts** — broker or engine swaps don't touch producers or BI; Flink 2.x is retained for the heavyweight tier.

### 4. Raw text-to-SQL banned; the semantic layer is the only AI path
**Risk:** semantic coverage becomes the bottleneck; the OSI interchange standard is young (v0.1).
**Mitigation:** stubs scaffold from contracts so coverage starts at day one; the Steward flywheel converts query misses into model-extension PRs; honest refusal beats confident hallucination.

### 5. Agents operate the platform via Git PRs only
**Risk:** PR latency for urgent fixes; agent noise overwhelming reviewers.
**Mitigation:** pre-approved **auto-merge classes** for bounded reversible actions; per-agent noise budgets tracked as SLOs.

### 6. The bespoke evidence plane
**Risk:** the one large custom build (~4 engineer-years); regulatory targets move (EUCS deadlocked, AI-Act high-risk timelines shifting).
**Mitigation:** every ingredient is standard (CloudEvents, OPA decision logs, OTel, Iceberg) — only the assembly is ours, and the assembly is the moat; scope is phased (v1 in Phase 2, certificates and consent claims in Phase 3).

### 7. Cross-lane SQL dialect drift — the spine's biggest silent risk
**Risk:** SQLGlot-transpiled semantics diverge across DuckDB/Trino/StarRocks/Spark and corrupt answers quietly.
**Mitigation:** the **Cross-Lane Conformance Suite** — a canonical query corpus with cell-level result diffing — runs nightly and gates every engine and SQLGlot upgrade, alongside TPC-DS-derived and production-replay performance-regression gates.

### 8. SQLMesh + marimo retraining tax
**Risk:** dbt and Jupyter muscle memory slows adoption; transform-market consolidation (the Fivetran/dbt-era churn) creates uncertainty.
**Mitigation:** dbt-project and Jupyter-kernel compatibility retained as escape hatches; migration clinics and the Carina Academy budgeted in Phases 2–3; Linux Foundation governance of SQLMesh as the safe harbor.

---

## Non-Goals

- **No proprietary control-plane dependencies, ever** — no component whose absence breaks portability off any single provider.
- **No raw text-to-SQL interface**, even as an "expert mode." Unmapped questions are refused and fed to the flywheel.
- **No house agent framework.** CARINA builds governed tools and context, not another orchestration loop; Multica/Nanitics-style bespoke runtimes stay retired.
- **No engine chooser UI.** Lane selection is the router's job; exposing it would be a design regression.
- **No iframe portal, ever again.** Surfaces compose through shared specs and SSO or they don't ship.
- **No turnkey MDM suite.** CARINA ships the golden-record *pattern* (Splink + contracted `party-master` products), not an enterprise MDM monolith.
- **No frontier-LLM pretraining and no general ML research platform.** CARINA fine-tunes, serves, and governs models; it does not pretrain them.
- **No promise of zero JVM.** Trino, Flink, and Spark remain where irreplaceable — contained behind protocol seams.
- **No "small install" of everything.** The Sloop profile deliberately excludes StarRocks, Flink, GPU serving, and vCluster; minimalism is a supported product, not a degraded one.
- **No compliance theater.** If a control isn't compiled from a contract and evidenced in the hash-chained tables, CARINA does not claim it.
