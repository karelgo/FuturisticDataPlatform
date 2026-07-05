# Security Policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately via
**GitHub Security Advisories** ("Report a vulnerability" on this repository's
Security tab). Do not open public issues for security reports.

You can expect an acknowledgement within **72 hours** and a status update at
least every **14 days** until resolution. Coordinated disclosure: we ask for
up to 90 days before public disclosure.

## Scope

- The `carina` platform code (`src/carina/`), the CLI, API, and Flight surfaces
- The compiled-artifact chain (contracts → checks/DDL/Rego/tuples/catalog)
- The deployment scaffolding (`Dockerfile`, `charts/`, `platform/`, workflows)

## Supported versions

Pre-1.0: only the latest tagged release receives fixes.

## Known dev-only tradeoffs (not vulnerabilities)

The **laptop/k3d profile intentionally ships static development credentials in
Git** (Garage keys, Keycloak realm/client secrets, oauth2-proxy cookie secret)
so a local cluster reproduces from Git alone. Each is marked `DEV ONLY` in the
manifests, and the production path (External Secrets Operator + OpenBao) is
documented in `platform/planes/security-baseline/README.md`. Reports that
these values are committed are appreciated but expected; reports of any such
value being *required* (rather than replaceable) in a non-dev path are in scope.

## Supply chain

Releases are built by `.github/workflows/release.yml`: multi-arch images with
an SPDX SBOM, trivy-scanned (CRITICALs block), and **cosign keyless-signed**
(identity: that workflow at a version tag). Verify:

```bash
cosign verify ghcr.io/karelgo/carina:<version> \
  --certificate-identity-regexp 'https://github.com/karelgo/FuturisticDataPlatform/.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```
