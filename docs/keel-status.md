# Phase 1 — KEEL: build status

Tracking the [roadmap's Phase 1](roadmap.md#phase-1--keel-months-05-the-spine-and-the-golden-path) scope against what is now **real, running code** in this repository. The laptop profile is the vehicle: every KEEL mechanism is built and tested here first, then the production component attaches behind the same seam (per the [shim → production map](implementation-plan.md#0-where-we-start-and-what-the-rest-is)).

## Scope: built vs. attaching

| KEEL scope item | Status | Where |
|---|---|---|
| **Contract compiler v1** (ODCS/ODPS → checks, DDL, masks, catalog) | ✅ **Built.** `carina compile` emits, per contract: silver DDL, quality-check SQL, generated **OPA Rego** policy, **OpenFGA** relationship tuples, and an Iceberg-REST-shaped **catalog entry**. Artifacts are committed under `products/*/compiled/` so drift shows in review; `carina compile --check` is the CI gate. The ingest and quality runner execute *the same compiled SQL* — one source of truth. | [`src/carina/compiler.py`](../src/carina/compiler.py), [`products/labour-market-nl/compiled/`](../products/labour-market-nl/compiled/) |
| **Lane Router v1** on the query front door | ✅ **Built.** Every semantic-layer query routes through the registry (`duckdb-local` always attached; `trino` attaches via `CARINA_TRINO_DSN`). Estimate-based escalation with graceful fallback; the full decision (lane, reason, estimate, candidates) travels in provenance and evidence. Outbound SQL is **transpiled per lane by SQLGlot** (DuckDB → Trino). `carina lanes` / `GET /api/lanes` show router state. | [`src/carina/lanes.py`](../src/carina/lanes.py) |
| **Arrow front door** (`carina flight`) | ✅ **Built.** The semantic layer served over **Arrow Flight**: clients ask for a *metric* (never SQL), the ticket compiles through the same semantic layer, the router picks the lane, and the Arrow table comes back with full provenance in its schema metadata. Same OIDC badge and contract policy as REST — denies are evidence-logged. Full Flight SQL command-set compatibility is the follow-on at this seam. | [`src/carina/flight.py`](../src/carina/flight.py) |
| **Cross-Lane Conformance Suite v1** | ✅ **Built, armed nightly.** A canonical corpus of dialect-drift-prone queries (regexp, date_trunc, windows, NULL-safe division, DISTINCT aggregates) runs on every attached lane, normalized and **diffed cell-by-cell** against the DuckDB baseline; drift or lane errors turn the suite red and the run is evidence-logged. The [nightly workflow](../.github/workflows/conformance.yml) rebuilds the lakehouse from live CBS sources and runs the corpus; pointing `CARINA_TRINO_DSN` at a cluster makes it the real cross-engine gate. | [`conformance/corpus.yaml`](../conformance/corpus.yaml), [`src/carina/conformance.py`](../src/carina/conformance.py) |
| Trino deployment (the scale-out lane) | 🟡 **Manifests committed; needs a cluster.** Trino chart 1.42.2 reading the published Iceberg tables through Lakekeeper with **vended credentials** (Trino holds no storage keys). Bring-up checklist incl. the namespace-mapping decision and an end-to-end `carina conformance` run is in the plane README. | [`platform/planes/compute-plane/`](../platform/planes/compute-plane/) |
| **Write–Audit–Publish** transformations | ✅ **Built.** Gold transforms stage in a `wap` schema (the laptop stand-in for an Iceberg branch), compiled audits run against staging (built-in nonempty + the product's `audits:` block), and only green audits publish atomically. A red audit aborts with production untouched — demonstrated live when a CBS source turned out to be discontinued. SQLMesh/Recce attach here in the production profile. | [`src/carina/transform.py`](../src/carina/transform.py) |
| **Golden path**: `carina` CLI scaffold → live | ✅ **Built & measured.** `carina create data-product <id>` scaffolds contract, transforms, semantic stub, and descriptor; the first fully green `carina run --product <id>` writes a `golden_path.ship` evidence record with the measured scaffold→live time. **The `wages-nl` product shipped in 4.6 minutes** — the DoD's 60-minute bar, measured not claimed. Backstage wraps this CLI in the production profile. | [`src/carina/scaffold.py`](../src/carina/scaffold.py), evidence `golden_path.ship` |
| **Parity checks** (ODAP dual-run migration gate) | ✅ **Built.** `carina parity <a> <b> --key …` runs row-level diffs (counts, key coverage, cell-exact EXCEPT both ways); every run is evidence-logged and the **consecutive-green streak** (runs + days, 30-day gate) is computed from the chain itself. This is the mechanic behind "parity checks green for 30 consecutive days". | [`src/carina/parity.py`](../src/carina/parity.py) |
| Identity fabric (Keycloak + SPIFFE/SPIRE + OpenFGA + generated OPA) | ✅ **Built** (SPIRE remains). **Authentication:** the API validates OIDC Bearer tokens against Keycloak's JWKS (`CARINA_AUTH_MODE=oidc`); humans and agents walk the same door — agent tokens carry `carina_kind: agent` — and the actor rides into every evidence record. **Authorization:** the data path (`/api/metrics/*/query`) is contract-governed; denies are evidence-logged (`authz.deny`), the laptop stand-in for OPA decision logs. **One policy, two evaluators:** `carina compile` emits the Rego bundle to `policies/` for the in-cluster OPA, `carina.authz` enforces identically in-process, and a **conformance suite runs both against the same inputs in CI** — drift fails the build. `carina authz simulate` answers "who can read this table" from the terminal. Trust-plane manifests: Keycloak (realm-as-code incl. the agent service account), OPA 1.18.2 serving the generated bundle, OpenFGA on CNPG. SPIFFE/SPIRE attaches with the cluster-hardening pass. | [`src/carina/auth.py`](../src/carina/auth.py), [`src/carina/authz.py`](../src/carina/authz.py), [`policies/`](../policies/), [`platform/planes/trust-plane/`](../platform/planes/trust-plane/) |
| **Iceberg + catalog** (the table format and control point) | ✅ **Built.** `carina publish` writes the lakehouse out as **real Apache Iceberg tables** (pyiceberg): a local SQL catalog under `CARINA_WAREHOUSE` by default, or **Lakekeeper via the Iceberg REST API** when `CARINA_CATALOG_URI` is set — same verb, the seam moves. Contract metadata (owner, classification, license, SLA) lands in the table properties. Every publish is **round-trip parity-verified** and evidence-logged; `carina catalog status` asks the catalog itself what it serves. | [`src/carina/warehouse.py`](../src/carina/warehouse.py), [`src/carina/catalog.py`](../src/carina/catalog.py) |
| Rook-Ceph / Garage; Lakekeeper + CNPG deployments | 🟡 **Manifests committed; needs a cluster to run.** The data-plane GitOps tree pins CloudNativePG (chart 0.29.0) with a **Tier-0 `lakekeeper-db` cluster** (WAL archiving + nightly base backups to S3, 30-day PITR), Lakekeeper (chart 0.11.0) on that database, and a dev-profile Garage (v2.3.0). Bring-up is two documented commands past `git push`. | [`platform/planes/data-plane/`](../platform/planes/data-plane/), [`platform/clusters/local/apps/data-plane/`](../platform/clusters/local/apps/data-plane/) |
| SQLMesh + SQLGlot + Recce; Dagster; dlt | ⬜ **Not yet.** WAP semantics are in place so these swap in behind an existing behavior, not a new one. |
| OTel → ClickStack; Argo CD as the only write path | 🟡 **Argo CD layout committed** (`platform/clusters/local/apps/`, app-of-apps, automated sync + prune). OTel wiring is Phase-0 cluster work. | [`platform/`](../platform/) |

## Definition of done — tracker

| DoD item | State |
|---|---|
| A new data product ships end-to-end in **< 60 min, measured** | ✅ Demonstrated: `wages-nl` scaffold→live in **4.6 min**, recorded as `golden_path.ship` in the evidence chain |
| Top tables queryable with **row-level parity green 30 consecutive days** | 🟡 Mechanic built (`carina parity` + streak-from-evidence); needs the dual-run environment to start the clock |
| **Conformance suite running nightly** | ✅ Armed: [nightly workflow](../.github/workflows/conformance.yml) rebuilds from live sources and runs the corpus; becomes cross-engine the moment a Trino DSN is configured |
| **Tier-0 restore drill passed** | 🟡 Backup manifests (CNPG WAL archiving + nightly base backup, 30-day PITR) and the [monthly drill runbook](runbooks/tier0-restore-drill.md) with its RTO/RPO scorecard are committed; the pass itself needs the cluster |

## What shipped in increment 6 (ops console)

- **One pane for the whole platform** (`#/ops` in the portal): every component — lakehouse, evidence chain + anchors, each compute lane, catalog seam, warehouse, identity, policy, every product's WAP/checks state, conformance — reporting its **own live status**, grouped by plane
- **SQL workbench**: an operator lane that is read-only *by construction* (sqlglot whitelist: single SELECT/DESCRIBE/SHOW only), row-capped, routed through the lane router, and **evidence-logged as `ops.query` with the operator's identity**. Consumers still never get SQL (ADR-0008); operators do, audited
- **Logs pane**: structured in-process ring buffer (uvicorn + carina loggers), filterable per component — the laptop stand-in for ClickStack/HyperDX behind the same pane
- **Traces pane**: one trace per API request with child spans for authz decisions, semantic compilation, and lane execution, rendered as a waterfall — the in-process stand-in wearing OTel's shape
- **Operator guard**: under OIDC the `/api/ops/*` surface requires membership of `CARINA_OPS_GROUPS` (default `platform-team@carina.local`); denies are evidence-logged like every other policy decision
- 18 new tests (105 passing + 4 CI-only)

## What shipped in increment 5 (enterprise hardening — implementation-plan §3)

- **Release engineering**: tagging `v*` now produces a **multi-arch image on ghcr** with an SPDX **SBOM** (syft), a **trivy scan that blocks on CRITICALs**, **cosign keyless signing + SBOM attestation**, and the Helm chart published as an **OCI artifact** — clusters consume exactly what the workflow attested
- **Evidence anchoring** (`carina evidence anchor|verify|status`): not-yet-anchored evidence exports as canonical JSONL segments into the warehouse (a different failure domain than the lakehouse file), covered by a hash-chained anchor log; verification cross-checks segments, anchors, and the database against each other — losing the DB, editing a segment, or rewriting history are all detectable. Ships as an optional CronJob in the chart
- **Chart hardening**: restricted-PSS-compliant pod/container contexts (non-root, seccomp, no privilege escalation, **read-only rootfs** with explicit data/tmp volumes, all capabilities dropped), `extraEnv` passthrough, and optional CronJobs for scheduled `carina run` + evidence anchoring
- **Security baseline** (`platform/planes/security-baseline/`): plane namespaces with **Pod Security Standards** labels, **default-deny NetworkPolicies** with every cross-plane flow enumerated and justified, **Kyverno** (3.8.1) with signed-image verification (identity = the release workflow) and no-`:latest` policies in Audit-first mode, **cert-manager** (v1.20.3), **External Secrets Operator** (2.7.0) with the documented OpenBao migration off dev-static secrets, and **oauth2-proxy** (10.7.0) giving the portal SPA browser SSO that forwards the user's Bearer token to the API
- **Repo hygiene**: SECURITY.md (private disclosure, response SLAs, cosign verify instructions, honest dev-only tradeoffs), CODEOWNERS on the trust surfaces, Renovate keeping the pinned stack from rotting (Argo CD chart pins included)
- 6 new tests (87 passing + 4 CI-only)

## What shipped in increment 4 (compute plane)

- **Arrow Flight front door** (`carina flight`): metrics in, Arrow tables out, provenance in the schema metadata; same OIDC badge and contract policy as REST, verified by in-process Flight-client tests
- **Cross-Lane Conformance Suite v1**: 8-query canonical corpus over the live gold tables, per-lane execution via `LaneRouter.run_on_lane`, order-insensitive cell-exact diffs with normalization (dates/decimals/NULLs), `conformance.run` evidence records, `carina conformance` CLI, and the **nightly workflow** that rebuilds from live CBS and runs the corpus
- **SQLGlot transpilation** on the Trino lane (DuckDB → Trino on the way out, e.g. `regexp_matches` → `REGEXP_LIKE`), DSN parsing hardened, client wiring locked by tests against an injected fake `trino` module
- Compute-plane GitOps manifests: Trino chart 1.42.2 with the Iceberg REST catalog pointed at Lakekeeper, **vended credentials** (no storage keys in Trino), bring-up checklist ending in an end-to-end `carina conformance`
- `semantic.compile_metric_sql` extracted so every surface (REST, Flight, agents) compiles through one path; 16 new tests (81 passing + 4 CI-only)

## What shipped in increment 3 (trust plane)

- **OIDC on the front door**: Bearer-token validation against Keycloak JWKS (`carina.auth`), `/api/whoami`, 401/403 semantics on the data path; the verified actor (subject, groups, human/agent) lands in the evidence chain
- **Policy enforcement point** (`carina.authz`) enforcing exactly the semantics of the generated Rego — default deny, owner read/write, public-requires-authentication, contract-declared consumers, column masks — with `authz.deny` evidence records
- **Rego/Python conformance suite**: the same inputs evaluated by `opa eval` and by `carina.authz` must agree, and the generated Rego must pass `opa check`; runs in CI (OPA 1.18.2 installed there)
- `carina compile` now also writes the **OPA bundle** to `policies/` (per-contract Rego + the kustomization that ships it as the `opa-policies` ConfigMap); the `--check` gate covers it
- `carina authz simulate <table> --groups …` — policy answers from the terminal
- Trust-plane GitOps manifests, pinned: Keycloak via keycloakx 7.2.0 with the **`carina` realm as code** (groups claim, audience mapper, dev user, and a `carina-analyst-agent` service account whose tokens say so), Tier-0 `keycloak-db` on CNPG, OPA 1.18.2 serving the generated bundle with decision logs to stdout, OpenFGA chart 0.3.10 on its own CNPG cluster + tuple-loading procedure from the compiled artifacts
- 21 new tests (65 passing + 4 CI-only conformance)

## What shipped in increment 2 (data plane)

- `carina publish` — the lakehouse exported as **Apache Iceberg tables** (or plain Parquet without the extra), each table round-trip **parity-verified** on every publish; contract properties travel into the catalog
- `carina catalog status` — catalog state asked of the catalog itself (Lakekeeper REST when configured, the local SQL catalog otherwise)
- Data-plane GitOps manifests, pinned: CNPG operator 0.29.0, **Tier-0 `lakekeeper-db`** (2 instances, WAL archiving + nightly backups to S3, 30-day PITR), Lakekeeper chart 0.11.0 on CNPG, Garage v2.3.0 dev-profile object store
- [Tier-0 restore drill runbook](runbooks/tier0-restore-drill.md) with the RTO/RPO scorecard and evidence-chain logging
- 8 new tests (44 total) covering publish round-trips, schema evolution, and the REST client against a mocked Lakekeeper

## What shipped in increment 1

- `carina compile [--check]` — contract compiler v1 (5 artifact kinds per product)
- `carina create data-product` + measured golden path (`--product` filters on every verb)
- Write–Audit–Publish on all gold transforms, with product-declared `audits:`
- Lane Router v1 with routing provenance on every semantic answer + `/api/lanes`
- `carina parity` with evidence-backed green-streak tracking
- A second live data product, **`wages-nl`** (CBS CAO wages), shipped via the golden path
- Evidence-plane hardening: the chain is now schema-pinned to `main.evidence` (a WAP-discovered fork bug, caught by tests)
- `tests/` (36 tests, network-free) + GitHub Actions CI (tests, contract-drift gate, image build + smoke)
- `Dockerfile`, `charts/carina` Helm chart, `platform/` Argo CD app-of-apps layout

## Field note: the gates worked

While shipping `wages-nl`, the contract initially pointed at CBS table `82838ENG`. The freshness check failed (source last modified 2023) and WAP aborted the gold publish — the dataset had been **discontinued and replaced** by `85663ENG` (2020=100 rebase). Re-pointing the contract was a two-line diff; nothing stale ever reached a consumer. That is the KEEL loop doing its job: *the contract failed loudly at build time instead of the dashboard lying quietly at read time.*
