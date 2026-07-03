# Persona Journeys

CARINA is designed for five personas — four human, one artificial — and its joy claims are measurable: **a governed data product in under 60 minutes; local builds in seconds; decision-grade answers in under 30 seconds; GPU workspaces in under 5 minutes; instant synthetic twins while approvals run.** These journeys are the acceptance tests for the platform experience.

---

## Data Engineer — Ingrid

**Day 1 (09:04–10:02 — production in under an hour).**
`carina create data-product orders-eu --source postgres-cdc --source stripe` scaffolds everything: repo, ODCS contract, ODPS descriptor, SQLMesh project, Dagster assets, a dlt pipeline for Stripe, Debezium→AutoMQ Table Topic configuration for the orders database, a Cube semantic stub, an Evidence page, and a status-page entry.

`carina run` builds the whole project on DuckDB against policy-scoped real Iceberg data in **8 seconds**. Her PR shows three panes — code diff, Recce data diff, contract diff (non-breaking) — and CI compiles the contract into Soda checks, masks, and registry entries. Merge fast-forwards the Write-Audit-Publish branch; the product is live, governed, and discoverable before stand-up. She has not opened a single ticket, chosen a single engine, or written a single line of YAML that wasn't scaffolded.

**Day 30.**
A supplier schema drifted overnight. The **Engineer agent** traced the Elementary anomaly through OpenLineage to the source column and opened a fix PR with a passing Recce report at 03:12. The bounded part (a retry + compaction trigger, pre-approved auto-merge class) merged itself; the mapping change waited for her review at 09:00. Her post-incident review is itself a PR: a new ODCS quality check so this class of drift pages nobody again. She has still never filed a ticket.

## Analyst — Tomás

**Day 1.**
One Keycloak login. He explores `orders-eu` in Rill on the DuckDB lane — sub-second response. He adds `net_revenue_eur` to the MetricFlow YAML, tests locally, opens a PR; Recce shows exactly which dashboards shift before anything merges. After merge, the metric is **identical** in Rill, Evidence, the Cube SQL API, and the Analyst agent's chat. **Time from question to governed metric: under 2 hours.**

**Day 30.**
He needs to change the semantics of `net_revenue_eur`. He publishes **v2** beside v1; the contract marks v1 deprecated with a 90-day window; the Data Product Portal notifies every subscribed consumer; the Steward agent opens PRs against downstream Rill/Evidence configs still pinned to v1; CI blocks new consumers of the deprecated version; at sunset v1 is removed and the evidence plane records who migrated when. Meanwhile a federated join to CRM data quietly escalated DuckDB→Trino via the Lane Router; he never noticed, because escalation is not his job.

## Data Scientist — Amara

**Day 1.**
`carina workspace create --gpu 4` returns a vCluster with Ray, Kueue-admitted GPUs via Dynamic Resource Allocation — **under 5 minutes, no ticket**. Her churn training corpus lives in **Lance** beside the Iceberg facts: same bucket, same catalog, same access policy. Ibis code prototyped on DuckDB retargets Daft-on-Ray unchanged.

She requests a sensitive behavioral dataset; approval needs a DPO sign-off, so the platform offers the **SDV synthetic twin instantly** — she starts feature engineering while the approval runs, and swaps to the real grant when it lands.

**Day 30.**
Her model trains with MLflow 3 logging and lineage to the training tables — AI-Act Article 10 evidence auto-attached by the Steward agent. The model card is an OpenMetadata entity; deployment is a KServe CR in a Git PR; Langfuse traces every inference. Golden-record customer IDs come from the `party-master` data product, where **Splink** probabilistic linkage (running on the DuckDB lane) stitches identities across domains, with match scores exposed as contract quality metrics.

## Business User — Femke

**Day 1.**
One portal, one login. She types: *"How did Benelux returns trend since the packaging change?"* The Analyst agent resolves governed Cube metrics, checks freshness and known issues via OpenMetadata, and answers in **22 seconds** — with the **"why you can trust this"** panel: source contracts, quality status, applied policy decisions, and a lineage link. She requests a restricted drill-down; the contract's terms auto-approve her purpose claim; OpenFGA grants access in **under 5 minutes**, masks applied.

**Day 30.**
Monday 08:30: the platform has already prepared her weekly brief — what changed in her products, why (lineage-linked root causes), what to watch, and one anomaly the Engineer agent already fixed, with the PR linked. When the returns pipeline degraded on the 23rd, she saw it first on the product's **status page**, with an ETA and the owning team — not in a silently broken dashboard.

## AI Agent — the Steward (fifth persona)

**Day 1.**
The Steward authenticates via Keycloak (its own service identity, incremental OAuth scopes), discovers tools only through the private MCP registry, and sees data only through Cube and OpenMetadata's MCP servers — under the same masks as any human with its grant set. Its first shift: it proposes PII classifications for three new columns in `orders-eu` (human approval required), drafts missing documentation, and flags a contract drift between the Stripe dlt schema and the declared ODCS schema.

**Day 30.**
Its query-miss flywheel is spinning: 14 unanswerable business questions last week became 3 proposed semantic-model extension PRs (2 merged). It proposed a retention-policy correction compiled from an updated contract, and escalated one erasure-propagation gap to the governance engineer. Every action it took exists as a Git PR or an approved suggestion; every tool call is an OpenLLMetry trace in the evidence plane. It has **no path** to act outside Git — structurally, not by policy.

---

## The Moments of Joy, as SLOs

| Moment | Persona | Target | Measured by |
|---|---|---|---|
| Governed data product shipped | Engineer | < 60 min | Scaffold-to-live telemetry |
| Full local project build | Engineer | seconds | `carina run` timing |
| Question → governed metric | Analyst | < 2 h | PR cycle telemetry |
| GPU workspace | Scientist | < 5 min, no ticket | Workspace API telemetry |
| Sensitive data: something to work with | Scientist | instant (synthetic twin) | Portal access-request / synthetic-twin service telemetry |
| Decision-grade answer | Business user | < 30 s | Analyst-agent traces |
| Access request (auto-approvable purpose) | Business user | < 5 min | OpenFGA grant telemetry |
| First remediation PR on an incident | Platform / agent | before a human is paged | Incident timeline |

These are tracked as platform SLOs on the Operations dashboard, next to uptime. A platform that misses its joy SLOs is degraded, even at 100% availability.
