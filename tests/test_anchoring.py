"""Evidence anchoring: history survives the database; tampering with any of
the three sides (segments, anchor log, database) is detected."""

import json

import pytest

from carina import anchoring, evidence


@pytest.fixture
def anchored(con, tmp_path, monkeypatch):
    monkeypatch.setenv("CARINA_WAREHOUSE", str(tmp_path / "wh"))
    for i in range(3):
        evidence.record(con, "test.event", f"s{i}", {"n": i})
    r = anchoring.anchor(con)
    return con, r


def test_anchor_exports_segment_and_verifies(anchored):
    con, r = anchored
    assert r["anchored"] == 3
    seg = anchoring.anchors_dir() / r["anchor"]["segment"]
    lines = [json.loads(x) for x in seg.read_text().splitlines()]
    assert [x["seq"] for x in lines] == [1, 2, 3]
    v = anchoring.verify_anchors(con)
    assert v["ok"] is True
    assert v["anchored_through"] == 3
    assert v["unanchored"] == 1  # the anchor's own evidence record


def test_anchor_is_incremental_and_idempotent(anchored):
    con, _ = anchored
    r2 = anchoring.anchor(con)  # covers only the anchor record itself
    assert r2["anchored"] == 1
    assert r2["anchor"]["seq_from"] == 4
    evidence.record(con, "test.more", "s", {})
    r3 = anchoring.anchor(con)
    assert (r3["anchor"]["seq_from"], r3["anchor"]["seq_to"]) == (5, 6)
    assert anchoring.verify_anchors(con)["ok"] is True


def test_tampered_segment_is_detected(anchored):
    con, r = anchored
    seg = anchoring.anchors_dir() / r["anchor"]["segment"]
    seg.write_text(seg.read_text().replace("test.event", "evil.event"))
    v = anchoring.verify_anchors(con)
    assert v["ok"] is False
    assert any("segment tampered" in p for p in v["problems"])


def test_edited_anchor_log_is_detected(anchored):
    con, _ = anchored
    path = anchoring.anchor_log_path()
    rec = json.loads(path.read_text())
    rec["seq_to"] = 999
    path.write_text(json.dumps(rec, sort_keys=True) + "\n")
    v = anchoring.verify_anchors(con)
    assert v["ok"] is False
    assert any("anchor_hash mismatch" in p for p in v["problems"])


def test_rewritten_database_diverges_from_anchor(anchored):
    con, _ = anchored
    con.execute("UPDATE main.evidence SET chain_hash = repeat('f', 64) WHERE seq = 3")
    v = anchoring.verify_anchors(con)
    assert v["ok"] is False
    assert any("diverges" in p for p in v["problems"])


def test_nothing_new_is_a_noop(con, tmp_path, monkeypatch):
    monkeypatch.setenv("CARINA_WAREHOUSE", str(tmp_path / "wh"))
    evidence.init(con)
    assert anchoring.anchor(con)["anchored"] == 0
    assert anchoring.verify_anchors(con)["ok"] is True
