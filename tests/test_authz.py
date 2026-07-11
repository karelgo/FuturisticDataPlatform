"""Policy decisions must match what the generated Rego encodes."""

import json

from carina import authz
from carina.contracts import Contract

from .conftest import CONTRACT_RAW


def _contract(classification="public", consumers=(), masks=()):
    raw = dict(CONTRACT_RAW)
    raw["classification"] = classification
    if consumers or masks:
        raw["access"] = {"consumers": list(consumers),
                         "masks": [dict(m) for m in masks]}
    return Contract(id="t", path=None, raw=raw, product_id="p")


OWNER = CONTRACT_RAW["owner"]  # team-test@carina.local


def test_owner_reads_and_writes():
    ct = _contract(classification="internal")
    actor = authz.Actor("eng", groups=[OWNER], authenticated=True)
    assert authz.decide(ct, actor, "read").allow
    assert authz.decide(ct, actor, "write").allow


def test_public_needs_authentication():
    ct = _contract(classification="public")
    assert authz.decide(ct, authz.Actor("a", authenticated=True), "read").allow
    assert not authz.decide(ct, authz.Actor.anonymous(), "read").allow


def test_public_does_not_grant_write():
    ct = _contract(classification="public")
    assert not authz.decide(ct, authz.Actor("a", authenticated=True), "write").allow


def test_internal_denies_non_owner_allows_consumer():
    ct = _contract(classification="internal", consumers=["analysts@carina.local"])
    outsider = authz.Actor("bob", groups=["other@x"], authenticated=True)
    analyst = authz.Actor("ana", groups=["analysts@carina.local"], authenticated=True)
    assert not authz.decide(ct, outsider, "read").allow
    assert authz.decide(ct, analyst, "read").allow
    assert not authz.decide(ct, analyst, "write").allow  # consumers read only


def test_masks_apply_to_everyone_but_owner():
    ct = _contract(masks=[{"column": "value", "treatment": "hash"}])
    owner = authz.Actor("eng", groups=[OWNER], authenticated=True)
    other = authz.Actor("ana", authenticated=True)
    assert authz.masks_for(ct, owner) == []
    assert authz.masks_for(ct, other) == [{"column": "value", "treatment": "hash"}]


def test_deny_is_evidence_logged(con):
    ct = _contract(classification="internal")
    allowed, decisions = authz.decide_all([ct], authz.Actor.anonymous(), con=con)
    assert allowed is False
    row = con.execute(
        "SELECT subject, payload FROM main.evidence WHERE action = 'authz.deny'"
    ).fetchone()
    assert row[0] == "t"
    payload = json.loads(row[1])
    assert payload["decisions"][0]["allow"] is False


def test_allow_is_not_logged_as_deny(con):
    from carina import evidence
    evidence.init(con)
    ct = _contract(classification="public")
    allowed, _ = authz.decide_all([ct], authz.Actor("a", authenticated=True), con=con)
    assert allowed is True
    n = con.execute(
        "SELECT count(*) FROM main.evidence WHERE action = 'authz.deny'").fetchone()[0]
    assert n == 0
