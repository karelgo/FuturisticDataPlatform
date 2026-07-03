# Governance, Trust & Sovereignty

CARINA's governance stance is **governance-by-construction**: if a control is not compiled from a contract and evidenced in the hash-chained audit tables, the platform does not claim it. Compliance (GDPR, NIS2, ISO 27001/27002, SOC 2-aligned controls, EU AI Act) is a continuous query over evidence the platform generates as a side effect of operating — not a documentation project.

---

## 1. Governance-by-Construction, End to End

The pipeline from declaration to proof:

```
contract (Git) → compilation → catalog enforcement → query-time enforcement → evidence
```

**(1) Contract.** The ODCS 3.1 file declares schema, classifications, quality SLOs, retention, owners, purposes, and output ports; ODPS 1.0 describes the product around it. CI (datacontract-cli) gates merges: **no contract, no deployment**.

**(2) Compilation.** One pipeline compiles the contract into: Soda checks and SQLMesh audits; DDL; schema-registry entries (enforced broker-side at write); generated Rego masks; OpenFGA relationship tuples; catalog metadata; Ceph lifecycle/tiering rules; Iceberg snapshot-expiry schedules; GoAlert routing from the `owner` field; and the marketplace page. Handwritten policy is a design failure.

**(3) Catalog enforcement.** Lakekeeper vends **short-lived, table-scoped credentials** only after OpenFGA authorization. No engine, human, or agent ever holds storage keys. The catalog is border control.

**(4) Query-time enforcement.** OPA evaluates generated Rego with the caller's OIDC token, whose claims carry **consent and purpose**. The same decision masks a column for an analyst in Rill and for an agent's MCP call. There is no parallel access path, structurally.

**(5) Evidence.** Every catalog CloudEvent, OPA decision, OpenLineage event, and agent trace flows into **append-only, hash-chained Iceberg audit tables** (Merkle roots anchored per batch), retained ≥ 6 months. GDPR accountability, NIS2 logging, and AI-Act Articles 10/12 evidence are standing queries — auditors get a read-scoped account, not a project.

## 2. Access Self-Service

Access requests are product features, not tickets:

- A consumer requests access to a data product in the Data Product Portal; the contract's terms and the requester's purpose claim decide. Auto-approvable purposes grant in minutes (OpenFGA tuple written, evidence logged); others route to the owner/DPO.
- While a **sensitive-data request** is pending, the platform offers a **synthetic-data twin** (SDV / MOSTLY AI SDK) instantly — governance latency becomes a product feature, not a blocker.
- Differentially private aggregate access (OpenDP / Tumult Analytics) is available as a standing low-friction tier for exploratory questions on sensitive data.

## 3. GDPR Mechanics

- **Erasure is an SLO'd platform operation**, not a runbook: `carina erase --subject <id>` runs DELETE → Amoro compaction → snapshot expiry; propagates along OpenLineage to derived tables **and outbound activation targets** (Multiwoven syncs deletions to CRMs/ad platforms); crypto-shreds stream segments and backups; and issues a **signed completion certificate**. SLO: 72 hours, demonstrated on lineage 3+ hops deep before the capability is called done.
- **Subject-keyed table layouts** are part of the golden-path scaffold so erasure is tractable by construction.
- **Consent changes propagate as data** and take effect at the next query, because enforcement is query-time — no re-materialization wave required.
- **Purpose limitation** is enforced per query: the purpose claim in the token must match the purposes declared in the contract, for humans and agents identically.

## 4. AI Governance (EU AI Act)

- Every agent interaction is an OpenLLMetry trace in the evidence plane (Article 12 logging).
- Training-data lineage for models is auto-attached from the catalog (Article 10), with model cards as OpenMetadata entities.
- The **"why you can trust this" panel** renders on every AI answer: source contracts, quality status, freshness, and the exact policy decisions applied.
- Raw text-to-SQL is banned platform-wide; AI answers are grounded in versioned, governed metric definitions ([ADR-0008](adr/ADR-0008-semantic-layer-ai-grounding.md)). Unmapped questions get an honest refusal.
- Frontier (non-sovereign) LLM APIs are a **policy-gated tier by data classification**; sovereign deployments run entirely on open weights served in-platform.

## 5. Incident Lifecycle

Governance for operations — detection to institutional memory:

1. **Detect:** Elementary anomaly (freshness/volume) or ClickStack alert.
2. **Open:** an incident record is opened in Git.
3. **Page:** GoAlert pages the team named in the contract's `owner` field. Triage SLA by product tier (P1: 15-minute ack).
4. **Communicate:** the product's **status page** in the Data Product Portal updates automatically; subscribed consumers are notified. Business users see degraded state and an ETA — not a silently wrong dashboard.
5. **Learn:** the post-incident review must merge as a PR that **amends the contract** (a new quality check, an adjusted SLO). Incidents feed contracts, permanently.

The Engineer agent participates in this loop: it files the first remediation PR before paging a human where the fix falls in a pre-approved class (see [ai-native.md](ai-native.md)).

## 6. Semantic Change Management

Metrics live for years; renames and redefinitions are governed like schema changes:

- Metrics carry explicit **versions**. A changed definition ships as `metric_v2` beside `v1`; the contract marks `v1` deprecated with a **90-day window**.
- The Data Product Portal **notifies every subscribed consumer**; the Steward agent opens PRs against downstream BI configs still pinned to v1.
- CI **blocks new consumers** of deprecated metrics; at sunset, v1 is removed and the evidence plane records who migrated when.

## 7. Sovereignty Tiers

| Tier | Name | Definition |
|---|---|---|
| **S1** | Sovereign | EU providers (StackIT SKE, OVHcloud, Scaleway; Outscale for SecNumCloud contexts) or on-prem Rook-Ceph; **all inference on-platform** (Mistral/Apertus/EuroLLM weights); zero US-jurisdiction dependencies. Designed to survive a fall of the EU–US Data Privacy Framework. |
| **S2** | Hybrid | Hyperscaler infrastructure with open formats and **zero proprietary control-plane dependencies** (Data-Act-grade portability); frontier LLM APIs policy-gated per data classification. |
| **S3** | Laptop / edge | k3d + Garage, full-fidelity local profile. |

**Residency.** Each region runs its own Lakekeeper and buckets. Contracts carry a `residency` field honored by both the Crossplane workspace API and the Lane Router — a query against EU-only data never leaves the EU region. Cross-region access federates through Trino with policies evaluated at the data's **home** region; OpenMetadata federates catalog *metadata* (never data) across regions.

**Workload identity.** SPIFFE/SPIRE SVIDs with hourly rotation; mTLS everywhere; External Secrets Operator + OpenBao for secrets. Zero-trust is the default posture, including between platform components.

**Confidential tier.** Confidential Containers (AMD SEV-SNP / Intel TDX) available for workloads whose threat model includes the infrastructure operator.

## 8. Disaster Recovery & Backup

Doctrine: **Iceberg snapshots are not backups** — they live in the same bucket and die with it. True backup is cross-site replication plus a catalog PITR consistency point, reconciled by a documented, tested procedure.

| Tier | Scope | Mechanism | RPO | RTO |
|---|---|---|---|---|
| **0** | Control-plane Postgres: **Lakekeeper (the crown jewels)**, Keycloak, OpenMetadata, Dagster, OpenFGA stores | CloudNativePG synchronous replicas; continuous WAL archiving (barman-cloud) to a **separate Ceph zone**; 30-day PITR | ≤ 5 min | ≤ 30 min |
| **1** | Contracted gold/silver Iceberg products | Ceph RGW multisite async replication to a second site | ≤ 15 min | ≤ 4 h |
| **2** | Bronze/raw + AutoMQ segments | Replication; re-ingestable sources documented as such | ≤ 1 h | ≤ 24 h |
| **3** | Scratch/dev | None | — | — |

**Drills:** monthly Tier-0 restore drill; quarterly full DR game day; quarterly **CI-tested Lakekeeper→Polaris catalog-migration drill** against a snapshot of production metadata. All drills publish RTO scorecards. A backup that has never been restored is a hypothesis, not a control.

## 9. FinOps & GreenOps as Governance

Cost and carbon are governed metrics, not spreadsheets:

- **OpenCost** attributes cost per namespace, per query lane, and per data product; **Kepler** attributes energy/gCO₂. Both land in the semantic layer, queryable next to business metrics and renderable on every product page.
- Chargeback/showback tags come from the ODPS descriptor.
- **Karpenter** runs compute spot-first; **KEDA** scales to zero; the in-repo carbon-aware scaling pattern shifts deferrable batch into low-carbon windows.
- Agents propose right-sizing and low-carbon scheduling changes as quantified Git PRs (see [ai-native.md](ai-native.md)).
