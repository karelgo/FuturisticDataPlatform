# compute-plane — the lanes behind the router

[ADR-0004](../../../docs/adr/ADR-0004-compute-lanes.md): nobody chooses an
engine. The Lane Router (in `carina` itself) owns the decision; this plane
provides the scale-out lanes it can route to.

| Component | What | Pin |
|---|---|---|
| Trino | The first scale-out lane; reads the published Iceberg tables through Lakekeeper (REST catalog, **vended credentials** — Trino holds no storage keys) | chart `1.42.2` (Trino 480) |

The DuckDB lane needs no deployment — it lives inside the `carina` pod,
scale-to-zero by construction. StarRocks (serving lane) and Spark Connect
arrive in SAILS/HORIZON per the [roadmap](../../../docs/roadmap.md).

## Attaching the lane

```bash
# In the carina chart (or env), point the router at the Trino service:
--set trinoDsn=trino.compute-plane.svc.cluster.local:8080/iceberg/<schema>
```

From that moment `carina lanes` shows `trino [attached]`, queries whose
estimated scan exceeds `CARINA_LANE_ESCALATE_ROWS` route there (with graceful
fallback), and semantic SQL is **transpiled DuckDB→Trino by SQLGlot** on the
way out. Every answer's provenance names the lane and the reason.

## Two integration notes, stated honestly

1. **Namespace mapping.** `carina publish` writes nested Iceberg namespaces
   (`carina.<product>.<layer>`). Trino addresses schemas as a single level —
   nested namespaces appear as quoted dotted schemas where supported. Pick
   per environment: either point the DSN's schema at a quoted nested
   namespace, or publish to a flattened namespace for the serving schema.
   Validating this mapping is part of the cluster bring-up checklist below.
2. **The conformance suite is the gate.** SQLGlot transpilation is tested,
   but only the [Cross-Lane Conformance Suite](../../../conformance/corpus.yaml)
   proves the answers match cell-for-cell. It runs nightly
   ([workflow](../../../.github/workflows/conformance.yml)); set the
   `CARINA_TRINO_DSN` repo variable (or run on a self-hosted runner with
   cluster access) to turn the nightly from single-lane corpus validation
   into the real cross-engine diff.

## Bring-up checklist (after data-plane + this plane sync)

```bash
kubectl port-forward -n compute-plane svc/trino 8080:8080 &
# 1. Trino sees the catalog:
#      SHOW SCHEMAS FROM iceberg;
# 2. Trino reads a published table (adjust schema per note 1):
#      SELECT count(*) FROM iceberg."carina.wages_nl.gold".gold_wages_monthly;
# 3. Attach the lane and prove parity end to end:
CARINA_TRINO_DSN=localhost:8080/iceberg/... carina conformance
```
