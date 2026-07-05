# Deploying to an OpenShift trial (Developer Sandbox)

The [Developer Sandbox](https://developers.redhat.com/developer-sandbox) is a
free 30-day namespace on a shared OpenShift cluster — **no cluster-admin**.
That means the full `platform/` GitOps tree (operators, CNPG, Kyverno, plane
namespaces) doesn't apply there; what deploys is the **Phase-0 shape**: the
containerized reference app, built on the cluster, behind a TLS Route. That
is exactly the implementation plan's "the demo, but on a cluster" milestone,
and it exercises the OpenShift-specific bits (SCC-assigned UIDs, Routes) that
a full trial/ROSA cluster will reuse.

## Prerequisites

1. Sign up: <https://developers.redhat.com/developer-sandbox> → *Start your
   sandbox for free* (Red Hat account required).
2. From the sandbox web console: click your username (top right) → *Copy
   login command* → grab the `oc login --token=sha256~… --server=https://api.…`
   line. Tokens last ~24 h.

## Deploy (four commands)

```bash
oc login --token=sha256~REDACTED --server=https://api.sandbox-....openshiftapps.com:6443

# 1. Build the image on the cluster from this repo (buildah, ~3–5 min):
oc apply -f platform/clusters/openshift-sandbox/build.yaml
oc start-build carina --follow

# 2. Install the chart with the OpenShift overlay (SCC-safe contexts + Route):
helm install carina charts/carina \
  -f charts/carina/values-openshift.yaml \
  --set image.repository=image-registry.openshift-image-registry.svc:5000/$(oc project -q)/carina \
  --set image.tag=0.6.0

# 3. Build the lakehouse from the live CBS sources, inside the pod:
oc wait --for=condition=available deploy/carina --timeout=180s
oc exec deploy/carina -- carina run

# 4. Open the portal:
echo "https://$(oc get route carina -o jsonpath='{.spec.host}')"
```

`/api/whoami`, the dashboard, trust drawers, lineage, and the evidence
explorer are all live at that URL. Optional extras:

```bash
oc exec deploy/carina -- carina evidence anchor     # anchor the audit chain
oc exec deploy/carina -- carina conformance          # corpus on the pod's lane
helm upgrade carina charts/carina -f charts/carina/values-openshift.yaml \
  --reuse-values --set jobs.refresh.enabled=true     # nightly re-ingest CronJob
```

## Sandbox constraints, stated honestly

- **One namespace, no operators**: Lakekeeper/CNPG/Keycloak/Trino/Argo CD
  need cluster scope or their own namespaces — that's the full-trial or
  ROSA/ARO path (`platform/clusters/local/` shows the tree that applies).
- **SCC-assigned UID**: the overlay nulls `runAsUser`/`fsGroup`; the image is
  group-0-writable, so the random UID works. Don't "fix" a CrashLoop by
  re-pinning the UID — that's the wrong direction on OpenShift.
- **Auto-idling**: sandbox pods idle after ~8 h without traffic and wake on
  the next request; the PVC keeps the lakehouse (and evidence chain) across
  restarts.
- **Auth**: the app runs `CARINA_AUTH_MODE=none` (dev identity) here; there's
  no Keycloak on a sandbox. Point `auth.*` values at any reachable OIDC
  issuer to turn enforcement on.
