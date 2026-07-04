from carina import evidence


def test_chain_appends_and_verifies(con):
    evidence.record(con, "test.a", "s1", {"n": 1})
    evidence.record(con, "test.b", "s2", {"n": 2})
    v = evidence.verify(con)
    assert v["ok"] is True
    assert v["records"] == 2
    assert v["head"] == evidence.head(con)


def test_tampering_is_detected(con):
    evidence.record(con, "test.a", "s1", {"n": 1})
    evidence.record(con, "test.b", "s2", {"n": 2})
    con.execute("UPDATE evidence SET payload = '{\"n\": 999}' WHERE seq = 1")
    v = evidence.verify(con)
    assert v["ok"] is False
    assert v["broken_at"] == 1
    assert v["reason"] == "payload tampered"


def test_latest_filters_by_action_and_subject(con):
    evidence.record(con, "ingest.fetch_info", "c1", {"k": "old"})
    evidence.record(con, "ingest.fetch_info", "c1", {"k": "new"})
    evidence.record(con, "ingest.fetch_info", "c2", {"k": "other"})
    r = evidence.latest(con, "ingest.fetch_info", "c1")
    assert r["payload"]["k"] == "new"
