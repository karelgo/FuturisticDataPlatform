"""The API front door under OIDC: 401 without a badge, 403 against policy,
200 with provenance when the contracts allow it — and denies in evidence."""

import duckdb
import pytest
import yaml
from fastapi.testclient import TestClient

from carina import api, auth, config

from .conftest import ISSUER

INTERNAL_CONTRACT = {
    "apiVersion": "odcs/v3.1-carina",
    "id": "secret-source",
    "name": "Internal source",
    "owner": "owners@carina.local",
    "classification": "internal",
    "source": {"type": "cbs-odata", "table": "00000SEC",
               "url": "https://example.invalid"},
    "silver": {"table": "silver_secret",
               "columns": [{"name": "value", "from": "V1", "type": "DOUBLE"}]},
    "quality": {"key": ["date"], "checks": []},
}

SEMANTIC = {
    "models": {
        "secret": {"table": "gold_secret", "time": "date", "grain": "monthly",
                   "contracts": ["secret-source"], "dimensions": {}},
    },
    "metrics": {
        "secret_value": {"model": "secret", "expr": "value",
                         "title": "Secret value", "unit": ""},
    },
}


@pytest.fixture
def client(tmp_root, fake_issuer, monkeypatch):
    pdir = tmp_root / "products" / "secret-product"
    (pdir / "contracts").mkdir(parents=True)
    (pdir / "semantic").mkdir()
    (pdir / "product.yaml").write_text(yaml.safe_dump({"id": "secret-product"}))
    (pdir / "contracts" / "secret-source.yaml").write_text(yaml.safe_dump(INTERNAL_CONTRACT))
    (pdir / "semantic" / "metrics.yaml").write_text(yaml.safe_dump(SEMANTIC))

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    seed = duckdb.connect(str(config.DB_PATH))
    seed.execute("CREATE TABLE gold_secret AS SELECT make_date(2024,1,1) AS date, 42.0 AS value")
    seed.close()

    monkeypatch.setenv("CARINA_AUTH_MODE", "oidc")
    monkeypatch.setenv("CARINA_OIDC_ISSUER", ISSUER)
    auth.reset()
    auth._verifier = auth.OIDCVerifier(ISSUER, auth.audience(),
                                       transport=fake_issuer.transport())
    api._con = None
    yield TestClient(api.app)
    api._con = None
    auth.reset()


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_no_token_is_401(client):
    r = client.get("/api/whoami")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_whoami_reflects_token(client, fake_issuer):
    r = client.get("/api/whoami",
                   headers=_bearer(fake_issuer.mint("alice", groups=["g1"])))
    assert r.status_code == 200
    assert r.json()["actor"] == {"subject": "alice", "groups": ["g1"],
                                 "authenticated": True, "kind": "human"}


def test_internal_metric_denied_for_outsider_and_logged(client, fake_issuer):
    r = client.get("/api/metrics/secret_value/query",
                   headers=_bearer(fake_issuer.mint("bob", groups=["elsewhere@x"])))
    assert r.status_code == 403
    assert r.json()["detail"]["denied"][0]["contract"] == "secret-source"

    ev = client.get("/api/evidence?action=authz.deny",
                    headers=_bearer(fake_issuer.mint("bob"))).json()
    assert ev["total"] == 1
    assert ev["records"][0]["actor"] == "bob"


def test_internal_metric_allowed_for_owner_with_provenance(client, fake_issuer):
    token = fake_issuer.mint("eng", groups=["owners@carina.local"])
    r = client.get("/api/metrics/secret_value/query", headers=_bearer(token))
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["points"] == [["2024-01-01", 42.0]]
    assert body["provenance"]["lane"] == "duckdb-local"


def test_agent_walks_the_same_door(client, fake_issuer):
    token = fake_issuer.mint("analyst-agent", groups=["owners@carina.local"],
                             kind="agent")
    r = client.get("/api/metrics/secret_value/query", headers=_bearer(token))
    assert r.status_code == 200
    r = client.get("/api/whoami", headers=_bearer(token))
    assert r.json()["actor"]["kind"] == "agent"
