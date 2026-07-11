from carina import parity


def _twin_tables(con):
    con.execute("CREATE TABLE a AS SELECT range AS k, range * 2 AS v FROM range(10)")
    con.execute("CREATE TABLE b AS SELECT * FROM a")


def test_identical_tables_are_green(con):
    _twin_tables(con)
    r = parity.check_parity(con, "a", "b", key=["k"])
    assert r["green"] is True
    assert r["streak"]["green_runs"] == 1
    assert r["streak"]["gate_passed"] is False  # 30-day gate stays open


def test_cell_difference_is_red(con):
    _twin_tables(con)
    con.execute("UPDATE b SET v = -1 WHERE k = 3")
    r = parity.check_parity(con, "a", "b", key=["k"])
    assert r["green"] is False
    assert r["rows_differing_from_b"] == 1
    assert r["keys_only_in_a"] == 0  # same keys, different cells


def test_missing_row_is_red(con):
    _twin_tables(con)
    con.execute("DELETE FROM b WHERE k = 7")
    r = parity.check_parity(con, "a", "b", key=["k"])
    assert r["green"] is False
    assert r["keys_only_in_a"] == 1


def test_schema_mismatch_reported(con):
    con.execute("CREATE TABLE a AS SELECT 1 AS k, 2 AS v")
    con.execute("CREATE TABLE b AS SELECT 1 AS k, 2 AS w")
    r = parity.check_parity(con, "a", "b", key=["k"])
    assert r["green"] is False
    assert r["reason"] == "schema mismatch"
    assert r["only_in_a"] == ["v"]


def test_streak_resets_after_red(con):
    _twin_tables(con)
    parity.check_parity(con, "a", "b", key=["k"])          # green
    con.execute("UPDATE b SET v = -1 WHERE k = 1")
    parity.check_parity(con, "a", "b", key=["k"])          # red
    con.execute("UPDATE b SET v = 2 WHERE k = 1")
    r = parity.check_parity(con, "a", "b", key=["k"])      # green again
    assert r["streak"]["green_runs"] == 1  # streak restarted after the red run
