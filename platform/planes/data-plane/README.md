# data-plane — Lakekeeper + CloudNativePG + object storage

The lakehouse spine from [ADR-0001](../../../docs/adr/ADR-0001-table-format.md)/[0002](../../../docs/adr/ADR-0002-catalog.md)/[0003](../../../docs/adr/ADR-0003-object-storage.md), deployed the only way the platform allows: Argo CD reconciling this directory. The Applications live in [`platform/clusters/local/apps/data-plane/`](../../clusters/local/apps/data-plane/); raw manifests live here.

| Component | What | Pin |
|---|---|---|
| CloudNativePG operator | Runs every control-plane Postgres | chart `0.29.0` (operator 1.30.0) |
| `lakekeeper-db` (CNPG Cluster) | **Tier-0**: Lakekeeper's metadata DB, 2 instances, WAL archiving + nightly base backup to S3, 30-day PITR | Postgres `17.5` |
| Lakekeeper | Iceberg REST catalog — the control point | chart `0.11.0` (app 0.12.2) |
| Garage | Dev-profile S3 (single node) — **prod uses Rook-Ceph or provider S3** | `v2.3.0` |

## Bring-up (local k3d)

Argo CD syncs everything from Git; two one-time manual steps remain by design:

```bash
# 1. Initialize the Garage layout, dev key, and buckets (idempotent):
kubectl exec -n data-plane garage-0 -- sh /etc/garage/init.sh

# 2. Bootstrap Lakekeeper and create its warehouse on the carina-warehouse bucket:
kubectl port-forward -n data-plane svc/lakekeeper 8181:8181 &
curl -X POST http://localhost:8181/management/v1/bootstrap \
     -H 'Content-Type: application/json' -d '{"accept-terms-of-use": true}'
curl -X POST http://localhost:8181/management/v1/warehouse \
     -H 'Content-Type: application/json' -d '{
  "warehouse-name": "carina",
  "storage-profile": {
    "type": "s3",
    "bucket": "carina-warehouse",
    "region": "garage",
    "endpoint": "http://garage-s3.data-plane.svc.cluster.local:3900",
    "path-style-access": true,
    "flavor": "s3-compat",
    "sts-enabled": false
  },
  "storage-credential": {
    "type": "s3", "credential-type": "access-key",
    "aws-access-key-id": "GK31c0dev0000000000000000",
    "aws-secret-access-key": "9d3f6c1a4b8e2d7f0a5c3e9b1d4f7a2c6e8b0d3f5a7c9e1b4d6f8a0c2e5b7d9f"
  }}'
```

Then point the reference app (or your laptop) at the catalog and publish:

```bash
export CARINA_CATALOG_URI=http://localhost:8181/catalog
export CARINA_CATALOG_WAREHOUSE=carina
carina publish          # Iceberg tables land in Lakekeeper, parity-verified
carina catalog status   # asks the catalog itself what it serves
```

`carina publish` is the same command that writes the local SQL catalog when no
`CARINA_CATALOG_URI` is set — the seam moves, the verbs don't.

## Tier-0 DR

`lakekeeper-db` archives WAL continuously and takes a nightly base backup to
`s3://carina-backups/lakekeeper-db` with a 30-day retention/PITR window. The
**monthly restore drill** — the KEEL definition-of-done item — is
[docs/runbooks/tier0-restore-drill.md](../../../docs/runbooks/tier0-restore-drill.md).

## Dev-only shortcuts, called out honestly

- Garage runs a single node with `replication_factor = 1` and **static
  credentials committed to Git** — reproducible for k3d, unacceptable beyond
  it. Production: Rook-Ceph or provider S3, External Secrets Operator + OpenBao.
- Lakekeeper runs without OpenFGA/OIDC until the trust-plane increment lands;
  it is ClusterIP-only and must stay unexposed until then.
- CNPG's in-tree `barmanObjectStore` is deprecated upstream in favor of the
  barman-cloud plugin; migrate when bumping the operator pin.
