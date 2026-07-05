"""Conformance suite: identical lanes green, drifted lanes caught loudly."""

import duckdb
import pytest

from carina import conformance
from carina.lanes import LaneRouter

CORPUS = [
    {"id": "sum-by-k", "sql": "SELECT k, sum(v) AS s FROM t GROUP BY k ORDER BY k"},
    {"id": "count-all", "sql": "SELECT count(*) FROM t"},
]


@pytest.fixture
def twin_lanes(con, monkeypatch):
    """A fake trino lane backed by a second DuckDB — perturbable per test."""
    con.execute(
        "CREATE TABLE t AS SELECT range % 3 AS k, CAST(range AS DOUBLE) AS v FROM range(9)")
    other = duckdb.connect()
    other.execute(
        "CREATE TABLE t AS SELECT range % 3 AS k, CAST(range AS DOUBLE) AS v FROM range(9)")
    monkeypatch.setenv("CARINA_TRINO_DSN", "trino.test:8080/iceberg/gold")
    monkeypatch.setattr(
        LaneRouter, "_execute_trino",
        lambda self, sql, params: other.execute(sql, params or []).fetchall())
    return con, other


def test_identical_lanes_are_green(twin_lanes):
    con, _ = twin_lanes
    s = conformance.run_suite(con, corpus=CORPUS)
    assert s["comparing"] is True
    assert s["lanes"] == ["duckdb-local", "trino"]
    assert s["green"] is True
    assert s["drifted"] == []


def test_value_drift_is_caught(twin_lanes):
    con, other = twin_lanes
    other.execute("UPDATE t SET v = v + 0.25 WHERE k = 1")
    s = conformance.run_suite(con, corpus=CORPUS)
    assert s["green"] is False
    assert "sum-by-k" in s["drifted"]
    assert "count-all" not in s["drifted"]  # counts unaffected by the perturbation
    drift = next(q for q in s["detail"] if q["id"] == "sum-by-k")["drift"][0]
    assert drift["lane"] == "trino"
    assert drift["rows_only_in_baseline"] == 1


def test_lane_error_is_red_not_silent(twin_lanes):
    con, other = twin_lanes
    other.execute("DROP TABLE t")
    s = conformance.run_suite(con, corpus=CORPUS)
    assert s["green"] is False
    assert set(s["errored"]) == {"sum-by-k", "count-all"}


def test_single_lane_validates_corpus(con):
    con.execute("CREATE TABLE t AS SELECT 1 AS k, 1.0 AS v")
    s = conformance.run_suite(con, corpus=CORPUS)
    assert s["comparing"] is False
    assert s["green"] is True


def test_run_is_evidence_logged(twin_lanes):
    con, _ = twin_lanes
    conformance.run_suite(con, corpus=CORPUS)
    row = con.execute(
        "SELECT count(*) FROM main.evidence WHERE action = 'conformance.run'"
    ).fetchone()
    assert row[0] == 1


def test_normalization_evens_out_representations():
    from datetime import date
    from decimal import Decimal
    a = conformance.normalize_rows([(date(2024, 1, 1), Decimal("1.5"), None)])
    b = conformance.normalize_rows([("2024-01-01", 1.5, None)])
    assert a == b


def test_repo_corpus_is_well_formed():
    corpus = conformance.load_corpus()
    ids = [q["id"] for q in corpus]
    assert len(ids) == len(set(ids)) and len(ids) >= 8
    assert all(q["sql"].strip() for q in corpus)
