"""Shared fixtures: an in-memory lakehouse and a temp product tree."""

from __future__ import annotations

import duckdb
import pytest

from carina import config
from carina.contracts import Contract, Product

CONTRACT_RAW = {
    "apiVersion": "odcs/v3.1-carina",
    "id": "test-source",
    "name": "Test source",
    "owner": "team-test@carina.local",
    "classification": "public",
    "source": {
        "type": "cbs-odata",
        "table": "00000TEST",
        "url": "https://example.invalid/odata/00000TEST",
        "license": "CC BY 4.0",
    },
    "silver": {
        "table": "silver_test",
        "columns": [
            {"name": "value", "from": "Value_1", "type": "DOUBLE",
             "description": "A measured value", "unit": "x1000"},
        ],
    },
    "quality": {
        "key": ["date"],
        "checks": [
            {"type": "not_null", "columns": ["date"]},
            {"type": "unique", "columns": ["date"]},
            {"type": "min_rows", "value": 2},
            {"type": "range", "column": "value", "min": 0, "max": 100},
        ],
    },
}


@pytest.fixture
def con():
    return duckdb.connect()


@pytest.fixture
def tmp_root(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "BRONZE_DIR", tmp_path / "data" / "bronze")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "data" / "lakehouse.duckdb")
    monkeypatch.setattr(config, "PRODUCTS_DIR", tmp_path / "products")
    (tmp_path / "products").mkdir()
    return tmp_path


def make_product(pdir, raw=None, contracts=None) -> Product:
    product = Product(id="test-product", path=pdir, raw=raw or {"id": "test-product"})
    for craw in contracts or []:
        product.contracts.append(
            Contract(id=craw["id"], path=pdir / "contracts" / f"{craw['id']}.yaml",
                     raw=craw, product_id=product.id)
        )
    return product


@pytest.fixture
def contract() -> Contract:
    return Contract(id=CONTRACT_RAW["id"], path=None, raw=CONTRACT_RAW,
                    product_id="test-product")


# ---- OIDC test rig: a throwaway issuer with real RS256 keys ---------------

ISSUER = "https://keycloak.test/realms/carina"
AUDIENCE = "carina-portal"


class FakeIssuer:
    """Mints real RS256 tokens and serves the matching JWKS over a mock
    transport — the API can't tell it from Keycloak."""

    def __init__(self):
        from cryptography.hazmat.primitives.asymmetric import rsa
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = "test-key-1"

    def jwks(self) -> dict:
        import json as _json

        import jwt as _jwt
        jwk = _json.loads(_jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        jwk.update({"kid": self.kid, "use": "sig", "alg": "RS256"})
        return {"keys": [jwk]}

    def mint(self, subject="alice", groups=(), audience=AUDIENCE, issuer=ISSUER,
             expired=False, kind=None, kid=None) -> str:
        import time

        import jwt as _jwt
        now = int(time.time())
        claims = {
            "sub": subject, "preferred_username": subject,
            "groups": list(groups), "aud": audience, "iss": issuer,
            "iat": now - 10, "exp": now - 5 if expired else now + 600,
        }
        if kind:
            claims["carina_kind"] = kind
        return _jwt.encode(claims, self.key, algorithm="RS256",
                           headers={"kid": kid or self.kid})

    def transport(self):
        import httpx

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/.well-known/openid-configuration"):
                return httpx.Response(200, json={"jwks_uri": f"{ISSUER}/jwks"})
            if request.url.path.endswith("/jwks"):
                return httpx.Response(200, json=self.jwks())
            return httpx.Response(404)
        return httpx.MockTransport(handler)


@pytest.fixture
def fake_issuer():
    return FakeIssuer()
