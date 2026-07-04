from carina import lanes


def test_single_lane_routes_local(con):
    con.execute("CREATE TABLE t AS SELECT 1 AS a")
    router = lanes.LaneRouter(con)
    d = router.route(["t"])
    assert d.lane == "duckdb-local"
    assert d.reason == "only attached lane"
    assert d.candidates == ["duckdb-local"]


def test_escalates_past_threshold_when_trino_attached(con, monkeypatch):
    monkeypatch.setenv("CARINA_TRINO_DSN", "trino.example:8080/iceberg/carina")
    monkeypatch.setenv("CARINA_LANE_ESCALATE_ROWS", "10")
    con.execute("CREATE TABLE big AS SELECT * FROM range(100)")
    router = lanes.LaneRouter(con)
    d = router.route(["big"])
    assert d.lane == "trino"
    assert "exceeds escalation threshold" in d.reason
    assert d.candidates == ["duckdb-local", "trino"]


def test_small_scan_stays_local_even_with_trino(con, monkeypatch):
    monkeypatch.setenv("CARINA_TRINO_DSN", "trino.example:8080/iceberg/carina")
    con.execute("CREATE TABLE small AS SELECT 1 AS a")
    router = lanes.LaneRouter(con)
    d = router.route(["small"])
    assert d.lane == "duckdb-local"
    assert "fits in-process" in d.reason


def test_unreachable_trino_falls_back(con, monkeypatch):
    monkeypatch.setenv("CARINA_TRINO_DSN", "trino.example:8080/iceberg/carina")
    monkeypatch.setenv("CARINA_LANE_ESCALATE_ROWS", "10")
    con.execute("CREATE TABLE big AS SELECT * FROM range(100)")
    router = lanes.LaneRouter(con)
    rows, decision = router.execute("SELECT count(*) FROM big", None, ["big"])
    assert rows[0][0] == 100
    assert decision.lane == "duckdb-local"
    assert "fell back" in decision.reason


def test_missing_table_estimates_zero(con):
    router = lanes.LaneRouter(con)
    assert router.estimate_rows(["does_not_exist"]) == 0
