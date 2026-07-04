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
| Identity fabric (Keycloak + SPIFFE/SPIRE + OpenFGA + generated OPA) | 🟡 **Policy compilation built; enforcement attaches.** The compiler generates the Rego policies and FGA tuples from contracts (`access:` blocks supported: consumers + column masks). Keycloak/SPIRE/OPA deployments consume these artifacts in the cluster profile — that's the trust-plane chart in `platform/`. | `products/*/compiled/*/policy.rego`, `compiled/fga-tuples.json` |
| Rook-Ceph / Garage; Lakekeeper + CNPG; Iceberg v3 | 🟡 **Seam defined; attaches on cluster.** The catalog entries the compiler emits are Lakekeeper-shaped; the router is where Iceberg-backed lanes plug in. Deployment scaffolding (Dockerfile, Helm chart, Argo CD app-of-apps) is in place — the data-plane charts are the next increment. | [`charts/`](../charts/), [`platform/`](../platform/) |
| SQLMesh + SQLGlot + Recce; Dagster; dlt | ⬜ **Not yet.** WAP semantics are in place so these swap in behind an existing behavior, not a new one. |
| OTel → ClickStack; Argo CD as the only write path | 🟡 **Argo CD layout committed** (`platform/clusters/local/apps/`, app-of-apps, automated sync + prune). OTel wiring is Phase-0 cluster work. | [`platform/`](../platform/) |

## Definition of done — tracker

| DoD item | State |
|---|---|
| A new data product ships end-to-end in **< 60 min, measured** | ✅ Demonstrated: `wages-nl` scaffold→live in **4.6 min**, recorded as `golden_path.ship` in the evidence chain |
| Top tables queryable with **row-level parity green 30 consecutive days** | 🟡 Mechanic built (`carina parity` + streak-from-evidence); needs the dual-run environment to start the clock |
| **Tier-0 restore drill passed** | ⬜ Requires the CNPG/Lakekeeper deployment (cluster profile) |

## What shipped in this increment

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
