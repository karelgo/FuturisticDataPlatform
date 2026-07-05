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

## Deploy — nothing but `oc` needed (works in the sandbox **web terminal**)

Open the web terminal (`>_` icon, top bar of the sandbox console) — or any
shell where you've run the `oc login` command — and paste:

```bash
BASE=https://raw.githubusercontent.com/karelgo/FuturisticDataPlatform/claude/futuristic-data-platform-phase-1-vn1ij2/platform/clusters/openshift-sandbox

# 1. Build the image ON the cluster from this repo (buildah, ~3–5 min):
oc apply -f $BASE/build.yaml
oc start-build carina --follow

# 2. Deploy (pre-rendered from the chart with the OpenShift overlay):
oc apply -f $BASE/deploy.yaml
oc wait --for=condition=available deploy/carina --timeout=300s

# 3. Build the lakehouse from the live CBS sources, inside the pod:
oc exec deploy/carina -- carina run

# 4. The portal URL:
echo "https://$(oc get route carina -o jsonpath='{.spec.host}')"
```

`deploy.yaml` is generated (`helm template … -f values-openshift.yaml`) so no
helm or git clone is needed cluster-side; with helm available, the equivalent
is `helm install carina charts/carina -f charts/carina/values-openshift.yaml
--set image.repository=carina --set image.tag=0.6.0`.

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
