"""Ops console: read-only SQL lane, component inventory, logs, traces,
and the operator-group guard."""

import logging

import duckdb
import pytest
import yaml
from fastapi.testclient import TestClient

from carina import api, auth, config, ops

from .conftest import ISSUER


@pytest.mark.parametrize("sql", [
    "SELECT 1",
    "SELECT * FROM t WHERE x > 0 ORDER BY x",
    "WITH c AS (SELECT 1 AS a) SELECT * FROM c",
    "DESCRIBE t",
])
def test_readonly_accepts_reads(sql):
    ops.validate_readonly(sql)


@pytest.mark.parametrize("sql", [
    "DROP TABLE t",
    "INSERT INTO t VALUES (1)",
    "UPDATE t SET x = 1",
    "DELETE FROM t",
    "CREATE TABLE evil AS SELECT 1",
    "SELECT 1; DROP TABLE t",
])
def test_readonly_rejects_writes(sql):
    with pytest.raises(ValueError):
        ops.validate_readonly(sql)


def test_run_query_caps_rows_and_logs_evidence(con):
    con.execute("CREATE TABLE big AS SELECT * FROM range(1000)")
    r = ops.run_query(con, "SELECT * FROM big", "op@test")
    assert r["row_count"] == ops.QUERY_ROW_CAP
    assert r["truncated"] is True
    ev = con.execute(
        "SELECT actor FROM main.evidence WHERE action = 'ops.query'").fetchone()
    assert ev[0] == "op@test"


def test_components_inventory(con, tmp_root, monkeypatch):
    monkeypatch.setenv("CARINA_WAREHOUSE", str(tmp_root / "wh"))
    con.execute("CREATE TABLE gold_x AS SELECT 1 AS a")
    comps = {c["id"]: c for c in ops.components(con)}
    assert comps["lakehouse"]["status"] == "ok"
    assert comps["evidence"]["detail"]["chain_ok"] is True
    assert comps["lane-duckdb-local"]["status"] == "ok"
    assert comps["lane-trino"]["status"] == "off"
    assert comps["identity"]["detail"]["auth_mode"] == "none"


def test_log_ring_buffer():
    ops.install_log_capture()
    logging.getLogger("carina.test-component").info("hello ops")
    rows = ops.recent_logs("carina.test-component")
    assert rows and rows[0]["message"] == "hello ops"
    assert "carina.test-component" in ops.log_components()


def test_trace_spans_nest_and_record():
    with ops.trace("GET /api/x", method="GET"):
        with ops.span("child.step", detail=1):
            pass
    t = ops.recent_traces(1)[0]
    assert t["name"] == "GET /api/x"
    names = [s["name"] for s in t["spans"]]
    assert names == ["GET /api/x", "child.step"]
    assert t["spans"][1]["parent_id"] is not None
    assert "_t0" not in t


def test_span_outside_trace_is_noop():
    with ops.span("orphan") as s:
        assert s is None


@pytest.fixture
def ops_client(tmp_root, fake_issuer, monkeypatch):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    seed = duckdb.connect(str(config.DB_PATH))
    seed.execute("CREATE TABLE gold_ops AS SELECT 42 AS answer")
    seed.close()
    monkeypatch.setenv("CARINA_AUTH_MODE", "oidc")
    monkeypatch.setenv("CARINA_OIDC_ISSUER", ISSUER)
    auth.reset()
    auth._verifier = auth.OIDCVerifier(ISSUER, auth.audience(),
                                       transport=fake_issuer.transport())
    api._con = None
    yield TestClient(api.app), fake_issuer
    api._con = None
    auth.reset()


def test_ops_requires_operator_group(ops_client):
    client, issuer = ops_client
    outsider = issuer.mint("bob", groups=["analysts@carina.local"])
    r = client.get("/api/ops/components",
                   headers={"Authorization": f"Bearer {outsider}"})
    assert r.status_code == 403

    operator = issuer.mint("sre", groups=["platform-team@carina.local"])
    r = client.post("/api/ops/query", json={"sql": "SELECT answer FROM gold_ops"},
                    headers={"Authorization": f"Bearer {operator}"})
    assert r.status_code == 200
    assert r.json()["rows"] == [["42"]]


def test_ops_query_rejects_writes_over_http(ops_client):
    client, issuer = ops_client
    operator = issuer.mint("sre", groups=["platform-team@carina.local"])
    r = client.post("/api/ops/query", json={"sql": "DELETE FROM gold_ops"},
                    headers={"Authorization": f"Bearer {operator}"})
    assert r.status_code == 400
    assert "not allowed" in r.json()["detail"]


def test_requests_produce_traces(ops_client):
    client, issuer = ops_client
    operator = issuer.mint("sre", groups=["platform-team@carina.local"])
    client.get("/api/lanes")  # traced but unauthenticated endpoint → 401 is fine
    r = client.get("/api/ops/traces",
                   headers={"Authorization": f"Bearer {operator}"})
    assert r.status_code == 200
    assert any(t["name"].startswith("GET /api/") for t in r.json()["traces"])