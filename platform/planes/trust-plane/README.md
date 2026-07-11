# trust-plane — Keycloak ⊕ OPA ⊕ OpenFGA

The identity fabric from [ADR-0009](../../../docs/adr/ADR-0009-identity-policy-fabric.md), deployed via the Applications in [`platform/clusters/local/apps/trust-plane/`](../../clusters/local/apps/trust-plane/).

| Component | What | Pin |
|---|---|---|
| Keycloak (keycloakx) | OIDC for humans **and agents** — the `carina` realm is imported from Git | chart `7.2.0` (Keycloak 26.6.2) |
| `keycloak-db` (CNPG) | Tier-0: identity database, WAL-archived like the catalog | Postgres `17.5` |
| OPA | Serves the **generated** contract policies from `policies/` (written by `carina compile`, shipped by Argo CD as a ConfigMap); decision logs → stdout → evidence plane | `1.18.2` |
| OpenFGA | ReBAC for the catalog; consumes the compiled `fga-tuples.json` | chart `0.3.10` (v1.18.1) |
| `openfga-db` (CNPG) | OpenFGA's Postgres | Postgres `17.5` |

## The one policy, twice enforced

`carina compile` turns each contract's `classification` + `access:` block into
`policy.rego`. The same semantics are enforced in-process by `carina.authz`
(the laptop profile's PEP) and by these OPA pods (the cluster PEP). The
**conformance suite** (`tests/test_policy_conformance.py`, runs in CI where
the `opa` binary is installed) evaluates both against identical inputs and
fails the build on any disagreement.

## Pointing the portal at Keycloak

```bash
export CARINA_AUTH_MODE=oidc
export CARINA_OIDC_ISSUER=http://keycloak-http.trust-plane.svc/auth/realms/carina
export CARINA_OIDC_AUDIENCE=carina-portal
carina serve
```

Or via the Helm chart: `--set auth.mode=oidc --set auth.oidcIssuer=…`.
Every `/api/metrics/*/query` call now requires a Bearer token; the actor
(subject, groups, human/agent kind) rides into the evidence chain, and
denies are logged as `authz.deny` records.

**Agents walk the same door.** The realm ships a `carina-analyst-agent`
service account whose tokens carry `carina_kind: agent`:

```bash
TOKEN=$(curl -s "$ISSUER/protocol/openid-connect/token" \
  -d grant_type=client_credentials \
  -d client_id=carina-analyst-agent -d client_secret=dev-agent-secret \
  | jq -r .access_token)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8899/api/whoami
```

## Loading the OpenFGA model + tuples

The compiler emits `products/*/compiled/fga-tuples.json` (authorization model
+ relationship tuples). Load them after the store comes up:

```bash
kubectl port-forward -n trust-plane svc/openfga 8080:8080 &
STORE=$(curl -s -X POST localhost:8080/stores \
  -d '{"name":"carina"}' | jq -r .id)
for f in products/*/compiled/fga-tuples.json; do
  MODEL=$(jq .authorization_model "$f")
  MID=$(curl -s -X POST "localhost:8080/stores/$STORE/authorization-models" \
    -d "$MODEL" | jq -r .authorization_model_id)
  jq -c '{writes: {tuple_keys: .tuples}}' "$f" \
    | curl -s -X POST "localhost:8080/stores/$STORE/write" -d @-
done
```

(Kestra automates this as a platform flow in a later increment; the artifacts
are already compile-time products.)

## Dev-only shortcuts, called out honestly

- Realm ships a `dev/dev` user, `admin/admin` bootstrap, a static agent
  secret, and wildcard redirect URIs — **local k3d only**. Production: IdP
  federation, External Secrets, exact redirect URIs.
- Browser SSO for the portal SPA goes through oauth2-proxy / Gateway API in
  front (Phase-0 ingress work); the API's Bearer path — which is also the
  agent path — is what this increment wires end to end.
- SPIFFE/SPIRE (workload identity, mTLS) is the remaining fabric strand;
  it attaches alongside Cilium in the cluster hardening pass.
