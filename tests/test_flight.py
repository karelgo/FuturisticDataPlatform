"""The Arrow Flight front door: metrics in, Arrow + provenance out,
same badge and same policy as REST."""

import json
import threading

import duckdb
import pytest
import yaml

pa = pytest.importorskip("pyarrow")
import pyarrow.flight as fl  # noqa: E402

from carina import auth, config, flight  # noqa: E402

from .conftest import ISSUER  # noqa: E402

PRODUCT_SEMANTIC = {
    "models": {
        "m": {"table": "gold_flight", "time": "date", "grain": "monthly",
              "contracts": ["flight-source"], "dimensions": {}},
    },
    "metrics": {
        "flight_value": {"model": "m", "expr": "value", "title": "Flight value"},
    },
}

CONTRACT = {
    "apiVersion": "odcs/v3.1-carina",
    "id": "flight-source",
    "owner": "owners@carina.local",
    "classification": "internal",
    "source": {"type": "cbs-odata", "table": "00000FLT", "url": "https://x.invalid"},
    "silver": {"table": "silver_flight",
               "columns": [{"name": "value", "from": "V", "type": "DOUBLE"}]},
    "quality": {"key": ["date"], "checks": []},
}


@pytest.fixture
def server(tmp_root, fake_issuer, monkeypatch):
    pdir = tmp_root / "products" / "flight-product"
    (pdir / "contracts").mkdir(parents=True)
    (pdir / "semantic").mkdir()
    (pdir / "product.yaml").write_text(yaml.safe_dump({"id": "flight-product"}))
    (pdir / "contracts" / "flight-source.yaml").write_text(yaml.safe_dump(CONTRACT))
    (pdir / "semantic" / "metrics.yaml").write_text(yaml.safe_dump(PRODUCT_SEMANTIC))

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    seed = duckdb.connect(str(config.DB_PATH))
    seed.execute(
        "CREATE TABLE gold_flight AS SELECT make_date(2024,1,1) AS date, 7.0 AS value")
    seed.close()

    monkeypatch.setenv("CARINA_AUTH_MODE", "oidc")
    monkeypatch.setenv("CARINA_OIDC_ISSUER", ISSUER)
    auth.reset()
    auth._verifier = auth.OIDCVerifier(ISSUER, auth.audience(),
                                       transport=fake_issuer.transport())
    srv = flight.make_server(str(config.DB_PATH), port=0)
    threading.Thread(target=srv.serve, daemon=True).start()
    yield srv, fake_issuer
    srv.shutdown()
    auth.reset()


def _client(srv, token=None):
    client = fl.connect(f"grpc://127.0.0.1:{srv.port}")
    options = fl.FlightCallOptions(
        headers=[(b"authorization", f"Bearer {token}".encode())] if token else [])
    return client, options


def _ticket(**req):
    return fl.Ticket(json.dumps(req).encode())


def test_no_token_is_unauthenticated(server):
    srv, _ = server
    client, options = _client(srv)
    with pytest.raises(fl.FlightUnauthenticatedError):
        client.do_get(_ticket(metric="flight_value"), options).read_all()


def test_wrong_group_is_denied(server):
    srv, issuer = server
    client, options = _client(srv, issuer.mint("bob", groups=["elsewhere@x"]))
    with pytest.raises(fl.FlightError, match="allow.*false|Unauthorized|denied|flight-source"):
        client.do_get(_ticket(metric="flight_value"), options).read_all()


def test_owner_gets_arrow_with_provenance(server):
    srv, issuer = server
    client, options = _client(srv, issuer.mint("eng", groups=["owners@carina.local"]))
    table = client.do_get(_ticket(metric="flight_value"), options).read_all()
    assert table.num_rows == 1
    assert table.column_names == ["t", "value"]
    prov = json.loads(table.schema.metadata[b"carina.provenance"])
    assert prov["metric"] == "flight_value"
    assert prov["lane"] == "duckdb-local"
    assert prov["contracts"] == ["flight-source"]
    assert prov["evidence_head"]


def test_list_flights_names_metrics(server):
    srv, issuer = server
    client, options = _client(srv, issuer.mint("eng", groups=["owners@carina.local"]))
    cmds = [json.loads(f.descriptor.command) for f in client.list_flights(options=options)]
    assert {"metric": "flight_value"} in cmds
