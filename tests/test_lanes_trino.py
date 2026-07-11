"""The Trino lane seam: DSN parsing, dialect transpilation, client wiring."""

import sys
import types

import pytest

from carina import lanes


def test_dsn_parsing_defaults():
    assert lanes.parse_trino_dsn("trino.compute:8080/iceberg/gold") == \
        ("trino.compute", 8080, "iceberg", "gold")
    assert lanes.parse_trino_dsn("trino.compute") == \
        ("trino.compute", 8080, "iceberg", "carina")
    assert lanes.parse_trino_dsn("host:9999/hive") == ("host", 9999, "hive", "carina")


def test_transpile_duckdb_is_identity():
    sql = "SELECT regexp_matches(s, '^[A-Z] ') FROM t"
    assert lanes.transpile_for("duckdb-local", sql) == sql


def test_transpile_rewrites_duckdb_isms_for_trino():
    out = lanes.transpile_for(
        "trino", "SELECT regexp_matches(sector, '^[A-Z] ') FROM t")
    assert "REGEXP_LIKE" in out
    assert "regexp_matches" not in out


def test_execute_trino_uses_client_and_transpiles(con, monkeypatch):
    """Inject a fake `trino` module and verify connection params + SQL."""
    seen = {}

    class FakeCursor:
        def execute(self, sql, params=None):
            seen["sql"], seen["params"] = sql, params

        def fetchall(self):
            return [(1,)]

    class FakeConn:
        def cursor(self):
            return FakeCursor()

    fake = types.ModuleType("trino")
    fake.dbapi = types.SimpleNamespace(
        connect=lambda **kw: seen.update(conn=kw) or FakeConn())
    monkeypatch.setitem(sys.modules, "trino", fake)
    monkeypatch.setenv("CARINA_TRINO_DSN", "trino.test:8443/iceberg/gold")
    monkeypatch.setenv("CARINA_TRINO_USER", "svc-carina")

    rows = lanes.LaneRouter(con).run_on_lane(
        "trino", "SELECT regexp_matches(s, 'x') FROM t")
    assert rows == [(1,)]
    assert seen["conn"] == {"host": "trino.test", "port": 8443,
                            "catalog": "iceberg", "schema": "gold",
                            "user": "svc-carina"}
    assert "REGEXP_LIKE" in seen["sql"]


def test_run_on_lane_rejects_unknown(con):
    with pytest.raises(ValueError, match="unknown lane"):
        lanes.LaneRouter(con).run_on_lane("starrocks", "SELECT 1")
