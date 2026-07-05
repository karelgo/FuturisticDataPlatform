# Phase 1 — KEEL: build status

Tracking the [roadmap's Phase 1](roadmap.md#phase-1--keel-months-05-the-spine-and-the-golden-path) scope against what is now **real, running code** in this repository. The laptop profile is the vehicle: every KEEL mechanism is built and tested here first, then the production component attaches behind the same seam (per the [shim → production map](implementation-plan.md#0-where-we-start-and-what-the-rest-is)).

## Scope: built vs. attaching

| KEEL scope item | Status | Where |
|---|---|---|
| **Contract compiler v1** (ODCS/ODPS → checks, DDL, masks, catalog) | ✅ **Built.** `carina compile` emits, per contract: silver DDL, quality-check SQL, generated **OPA Rego** policy, **OpenFGA** relationship tuples, and an Iceberg-REST-shaped **catalog entry**. Artifacts are committed under `products/*/compiled/` so drift shows in review; `carina compile --check` is the CI gate. The ingest and quality runner execute *the same compiled SQL* — one source of truth. | [`src/carina/compiler.py`](../src/carina/compiler.py), [`products/labour-market-nl/compiled/`](../products/labour-market-nl/compiled/) |
| **Lane Router v1** on the query front door | ✅ **Built.** Every semantic-layer query routes through the registry (`duckdb-local` always attached; `trino` attaches via `CARINA_TRINO_DSN`). Estimate-based escalation with graceful fallback; the full decision (lane, reason, estimate, candidates) travels in provenance and evidence. `carina lanes` / `GET /api/lanes` show router state. Flight SQL replaces the in-process seam when the fleet arrives. | [`src/carina/lanes.py`](../src/carina/lanes.py) |
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
| **Tier-0 restore drill passed** | 🟡 Backup manifests (CNPG WAL archiving + nightly base backup, 30-day PITR) and the [monthly drill runbook](runbooks/tier0-restore-drill.md) with its RTO/RPO scorecard are committed; the pass itself needs the cluster |

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
