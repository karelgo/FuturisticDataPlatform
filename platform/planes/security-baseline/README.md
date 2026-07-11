# security-baseline — the cluster's default posture

Implements the implementation-plan §3.1 baseline as Git-managed manifests
(Applications in [`platform/clusters/local/apps/security/`](../../clusters/local/apps/security/)).

| Piece | What it enforces | Pin |
|---|---|---|
| [`namespaces.yaml`](namespaces.yaml) | The four plane namespaces with **Pod Security Standards** labels (`restricted` enforced; compute-plane at `baseline` until Trino's contexts are validated) | — |
| [`network-policies.yaml`](network-policies.yaml) | **Default-deny** ingress+egress per plane, DNS + intra-plane allowed, every cross-plane flow enumerated with its reason (catalog/S3, identity, lanes, backups, portal, CBS egress on 443) | — |
| Kyverno + [policies](kyverno-policies/) | Admission control: **only images signed by the release workflow** (cosign keyless, identity = the GitHub Actions workflow) and **no `:latest` tags**. Both start in `Audit`; flip to `Enforce` after one green release deploys through them | chart `3.8.1` |
| cert-manager | TLS issuance for the edge | chart `v1.20.3` |
| External Secrets Operator | The exit path from dev-static secrets in Git | chart `2.7.0` |
| oauth2-proxy | **Browser SSO** for the portal: authenticates against the `carina` realm and forwards the user's access token as the `Authorization` header, so the SPA's API calls carry the same Bearer identity as a CLI or agent | chart `10.7.0` |

## Secrets: the migration path off the dev statics

The dev profile deliberately commits static credentials (Garage keys, realm
client secrets) so a laptop/k3d cluster reproduces from Git alone. Anything
shared replaces them with ExternalSecrets against OpenBao/Vault:

```yaml
apiVersion: external-secrets.io/v1
kind: SecretStore
metadata: {name: openbao, namespace: data-plane}
spec:
  provider:
    vault:
      server: https://openbao.example.internal
      path: kv
      auth: {kubernetes: {mountPath: kubernetes, role: carina-data-plane}}
---
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata: {name: garage-credentials, namespace: data-plane}
spec:
  secretStoreRef: {name: openbao, kind: SecretStore}
  target: {name: garage-credentials}
  data:
    - {secretKey: access-key, remoteRef: {key: carina/garage, property: access-key}}
    - {secretKey: secret-key, remoteRef: {key: carina/garage, property: secret-key}}
```

Same pattern for `keycloak` admin, `dev-agent-secret`, `dev-proxy-secret`,
and the oauth2-proxy cookie secret. The dev-only values are grep-able:
`git grep -n "DEV ONLY\|DEV-ONLY\|dev-"`.

## What this baseline is not

- Not mTLS: SPIFFE/SPIRE + Cilium remain the cluster-hardening pass.
- Not a tested perimeter: the NetworkPolicies encode the *intended* flows;
  validating them (and the PSS `restricted` fit of every third-party chart)
  is part of cluster bring-up, with Hubble/`kubectl exec` connectivity checks.
- Not runtime detection: Falco/Tetragon land with the ops-plane.
