# Runbook: Tier-0 restore drill (monthly)

**Why this exists.** The Lakekeeper metadata database is the platform's crown
jewels: lose it and every Iceberg table still exists in the object store but
nothing knows where. Tier-0 promises **RPO ≤ 5 min, RTO ≤ 30 min**
([governance §8](../governance-and-sovereignty.md#8-disaster-recovery--backup)),
and the KEEL definition of done requires this drill to have *passed*, not to
exist on paper. A backup never restored is a hypothesis, not a control.

**Cadence:** monthly, scheduled; run it like an incident (timer on, no peeking
at the primary). Quarterly, fold it into the full DR game day.

## Preconditions

- `lakekeeper-db` (CNPG Cluster) archiving WAL to `s3://carina-backups/lakekeeper-db`
  with nightly base backups (see [data-plane README](../../platform/planes/data-plane/README.md)).
- A scratch namespace `dr-drill` with enough quota for one Postgres instance.

## Drill procedure

**T0 — start the timer.** Record the current evidence head and the row counts
you will verify against:

```bash
kubectl exec -n data-plane lakekeeper-db-1 -- psql -U postgres lakekeeper \
  -c "SELECT count(*) FROM tabular;"   # Lakekeeper's table-of-tables
```

**1. Restore into the scratch namespace** (point-in-time, 10 minutes ago):

```yaml
# dr-drill/restore-cluster.yaml — apply with kubectl -n dr-drill apply -f
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: lakekeeper-db-drill
spec:
  instances: 1
  imageName: ghcr.io/cloudnative-pg/postgresql:17.5
  storage: {size: 5Gi}
  bootstrap:
    recovery:
      source: origin
      recoveryTarget:
        targetTime: "<RFC3339 timestamp, T0 minus 10 minutes>"
  externalClusters:
    - name: origin
      barmanObjectStore:
        destinationPath: s3://carina-backups/lakekeeper-db
        endpointURL: http://garage-s3.data-plane.svc.cluster.local:3900
        s3Credentials:
          accessKeyId: {name: garage-credentials, key: access-key}
          secretAccessKey: {name: garage-credentials, key: secret-key}
```

**2. Verify the restored catalog serves.** Point a scratch Lakekeeper at the
restored DB (helm install into `dr-drill` with `externalDatabase.host_write:
lakekeeper-db-drill-rw.dr-drill.svc`), then:

```bash
curl -fsS http://lakekeeper-drill:8181/catalog/v1/config
carina catalog status   # with CARINA_CATALOG_URI pointed at the drill instance
```

**3. Verify data-level parity.** The catalog must resolve every table it
resolved at T0; spot-check the flagship product's tables end to end:

```bash
carina parity gold_labour_market_monthly <drill-lane table> --key date
```

**4. Stop the timer. Record the scorecard.**

| Field | Value |
|---|---|
| Drill date / operator | |
| Backup used (base + WAL end) | |
| Recovery target time | |
| **RTO measured** (T0 → catalog serving) | target ≤ 30 min |
| **RPO measured** (data loss window) | target ≤ 5 min |
| Table count at T0 vs restored | |
| Parity spot-checks | |
| Surprises / actions | |

**5. Log it to the evidence chain** so the drill is auditable, not folklore:

```bash
python - <<'EOF'
import duckdb
from carina import config, evidence
con = duckdb.connect(str(config.DB_PATH))
evidence.record(con, "dr.tier0_drill", "lakekeeper-db", {
    "rto_minutes": 0.0,   # fill in
    "rpo_minutes": 0.0,   # fill in
    "passed": True,       # both within target
    "scorecard": "link-or-path",
}, actor="platform.sre")
EOF
```

**6. Tear down** the `dr-drill` namespace. The drill is green only if both
targets were met **and** every verification step passed. A red drill opens an
incident, not a retry-next-month.
