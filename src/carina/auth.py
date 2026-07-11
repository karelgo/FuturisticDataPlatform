"""Authentication — one front door for humans and agents (ADR-0009).

CARINA_AUTH_MODE:
  none (default) — laptop dev mode: every caller is the dev identity.
                   Loudly not for anything shared.
  oidc           — validate Bearer JWTs against CARINA_OIDC_ISSUER (a
                   Keycloak realm): issuer + audience + signature via the
                   issuer's published JWKS. Groups come from the `groups`
                   claim (the realm mapper ships in the trust-plane realm);
                   agents carry `carina_kind: agent` and are verified by the
                   exact same path — same badge, same policies, same audit.

Requires the auth extra: pip install 'carina-platform[auth]'.
"""

from __future__ import annotations

import os

import httpx

from .authz import Actor


class AuthError(Exception):
    """Authentication failed — maps to HTTP 401."""


def mode() -> str:
    return os.environ.get("CARINA_AUTH_MODE", "none")


def issuer() -> str | None:
    return os.environ.get("CARINA_OIDC_ISSUER") or None


def audience() -> str:
    return os.environ.get("CARINA_OIDC_AUDIENCE", "carina-portal")


class OIDCVerifier:
    """Verifies RS256 Bearer tokens against an OIDC issuer's JWKS."""

    def __init__(self, issuer_url: str, audience: str, transport=None):
        self.issuer = issuer_url.rstrip("/")
        self.audience = audience
        self._client = httpx.Client(timeout=10.0, transport=transport)
        self._keys: dict[str, object] = {}

    def _fetch_keys(self) -> None:
        import jwt

        r = self._client.get(f"{self.issuer}/.well-known/openid-configuration")
        r.raise_for_status()
        jwks_uri = r.json()["jwks_uri"]
        r = self._client.get(jwks_uri)
        r.raise_for_status()
        self._keys = {
            k["kid"]: jwt.algorithms.RSAAlgorithm.from_jwk(k)
            for k in r.json().get("keys", [])
            if k.get("kty") == "RSA"
        }

    def _key_for(self, kid: str):
        if kid not in self._keys:
            self._fetch_keys()  # unknown kid → refresh once (key rotation)
        if kid not in self._keys:
            raise AuthError(f"no JWKS key for kid {kid!r}")
        return self._keys[kid]

    def verify(self, token: str) -> Actor:
        import jwt

        try:
            kid = jwt.get_unverified_header(token).get("kid")
            claims = jwt.decode(
                token,
                key=self._key_for(kid),
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
            )
        except AuthError:
            raise
        except Exception as e:
            raise AuthError(f"token rejected: {type(e).__name__}: {e}") from e
        return Actor(
            subject=claims.get("preferred_username") or claims["sub"],
            groups=list(claims.get("groups", [])),
            authenticated=True,
            kind=claims.get("carina_kind", "human"),
        )


_verifier: OIDCVerifier | None = None


def _get_verifier() -> OIDCVerifier:
    global _verifier
    if _verifier is None:
        if not issuer():
            raise AuthError("CARINA_AUTH_MODE=oidc but CARINA_OIDC_ISSUER is not set")
        _verifier = OIDCVerifier(issuer(), audience())
    return _verifier


def reset() -> None:
    """Drop cached verifier state (tests, config reload)."""
    global _verifier
    _verifier = None


def actor_from_authorization(authorization: str | None) -> Actor:
    """Resolve the caller's identity from an Authorization header."""
    if mode() == "none":
        return Actor.dev()
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("missing Bearer token")
    return _get_verifier().verify(authorization.split(None, 1)[1])
