# platform/ — the GitOps tree

This directory is the start of the repository layout described in
[docs/implementation-plan.md §2](../docs/implementation-plan.md#gitops-repository-layout):
**nothing about a CARINA environment exists outside Git**, and Argo CD is the
only write path to a cluster.

```
platform/
  clusters/            # one directory per cluster
    local/apps/        # Argo CD Applications for a local k3d cluster (app-of-apps)
  planes/              # Helm values per plane, per environment overlay (grows in Phase 1+)
charts/                # Helm charts for CARINA-authored components
products/              # the data products (contracts, transforms, semantic) — as today
policies/              # compiled cluster policies land here in Phase 1+
```

## Deploy the reference app to a local cluster

```bash
k3d cluster create carina
docker build -t carina:0.6.0 . && k3d image import carina:0.6.0 -c carina

# Option A — plain Helm (no GitOps):
helm install carina charts/carina --set image.repository=carina --set image.tag=0.6.0

# Option B — the real write path: install Argo CD, then let it reconcile this repo:
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl apply -n argocd -f platform/clusters/local/apps/root.yaml
```

The pod serves the portal on port 8899 (`kubectl port-forward svc/carina 8899:8899`),
runs `carina run` on demand (`kubectl exec deploy/carina -- carina run`), and keeps
its lakehouse on an `emptyDir` unless `persistence.enabled=true`.

## What attaches next (per the [roadmap](../docs/roadmap.md))

| Phase | What lands in this tree |
|---|---|
| KEEL | ✅ [`planes/data-plane/`](planes/data-plane/) (Lakekeeper + CloudNativePG + Garage, Tier-0 backups) · ✅ [`planes/trust-plane/`](planes/trust-plane/) (Keycloak realm-as-code, OPA serving the generated `policies/` bundle, OpenFGA) · ✅ [`planes/compute-plane/`](planes/compute-plane/) (Trino on Lakekeeper vended credentials) |
| SAILS | `planes/motion-plane/` (Debezium, AutoMQ, RisingWave, Dagster), evidence-plane sink |
| CREW | `planes/intelligence-plane/` (agents, vLLM/KServe) |

The compiled artifacts under `products/*/compiled/` (Rego policies, OpenFGA
tuples, catalog entries) are exactly what those planes consume — the contract
compiler already produces them.
