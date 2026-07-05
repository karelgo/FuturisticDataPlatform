"""Evidence anchoring (Phase 1 hardening, ADR-0010).

The evidence chain lives inside the lakehouse database; anchoring makes it
durable and independently verifiable. `carina evidence anchor` exports every
not-yet-anchored record as a canonical JSONL *segment* into the warehouse
(object storage in production — a different failure domain than the
database) and appends an entry to an *anchor log* that is itself
hash-chained: each anchor commits to its segment's SHA-256, the evidence
chain head it covers, and the previous anchor.

The three failure modes this closes:
  - lakehouse file lost         → history reconstructible from segments
  - segment/anchor file edited  → anchor hashes break
  - database records rewritten  → chain head no longer matches the anchor

`carina evidence verify` checks all three sides against each other.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from . import evidence
from .warehouse import warehouse_root

GENESIS = "0" * 64

_COLS = ("seq", "ts", "actor", "action", "subject", "payload",
         "payload_hash", "prev_hash", "chain_hash")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def anchors_dir() -> Path:
    return warehouse_root() / "evidence"


def anchor_log_path() -> Path:
    return anchors_dir() / "anchors.jsonl"


def read_anchors() -> list[dict]:
    path = anchor_log_path()
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _anchor_hash(rec: dict) -> str:
    body = {k: v for k, v in rec.items() if k != "anchor_hash"}
    return _sha256_bytes(json.dumps(body, sort_keys=True).encode())


def anchor(con: duckdb.DuckDBPyConnection) -> dict:
    """Export not-yet-anchored evidence and append one anchor. Idempotent:
    running with nothing new to anchor is a no-op."""
    evidence.init(con)
    anchors = read_anchors()
    last_seq = anchors[-1]["seq_to"] if anchors else 0
    prev_hash = anchors[-1]["anchor_hash"] if anchors else GENESIS

    rows = con.execute(
        f"SELECT {', '.join(_COLS)} FROM main.evidence WHERE seq > ? ORDER BY seq",
        [last_seq],
    ).fetchall()
    if not rows:
        return {"anchored": 0, "seq_through": last_seq, "anchor": None}

    records = [dict(zip(_COLS, r)) for r in rows]
    for r in records:
        r["ts"] = str(r["ts"])
    seq_from, seq_to = records[0]["seq"], records[-1]["seq"]

    segments = anchors_dir() / "segments"
    segments.mkdir(parents=True, exist_ok=True)
    segment_rel = f"segments/evidence-{seq_from:08d}-{seq_to:08d}.jsonl"
    segment_bytes = ("\n".join(json.dumps(r, sort_keys=True) for r in records) + "\n").encode()
    (anchors_dir() / segment_rel).write_bytes(segment_bytes)

    rec = {
        "seq_from": seq_from,
        "seq_to": seq_to,
        "records": len(records),
        "segment": segment_rel,
        "segment_sha256": _sha256_bytes(segment_bytes),
        "chain_head": records[-1]["chain_hash"],
        "prev_anchor": prev_hash,
        "anchored_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    rec["anchor_hash"] = _anchor_hash(rec)
    with anchor_log_path().open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")

    # The anchor itself becomes evidence — covered by the *next* anchor.
    evidence.record(con, "evidence.anchor", "evidence-chain", {
        "seq_from": seq_from, "seq_to": seq_to, "records": len(records),
        "segment": segment_rel, "anchor_hash": rec["anchor_hash"],
    })
    return {"anchored": len(records), "seq_through": seq_to, "anchor": rec}


def verify_anchors(con: duckdb.DuckDBPyConnection) -> dict:
    """Verify segments, the anchor chain, and their agreement with the DB."""
    evidence.init(con)
    problems = []
    anchors = read_anchors()
    prev = GENESIS
    for i, rec in enumerate(anchors, 1):
        if rec.get("prev_anchor") != prev:
            problems.append(f"anchor {i}: broken anchor chain (prev_anchor mismatch)")
        if _anchor_hash(rec) != rec.get("anchor_hash"):
            problems.append(f"anchor {i}: anchor_hash mismatch (log edited)")
        seg = anchors_dir() / rec["segment"]
        if not seg.exists():
            problems.append(f"anchor {i}: segment missing ({rec['segment']})")
        elif _sha256_bytes(seg.read_bytes()) != rec["segment_sha256"]:
            problems.append(f"anchor {i}: segment tampered ({rec['segment']})")
        row = con.execute(
            "SELECT chain_hash FROM main.evidence WHERE seq = ?", [rec["seq_to"]]
        ).fetchone()
        if row and row[0] != rec["chain_head"]:
            problems.append(
                f"anchor {i}: database chain diverges from anchored head at seq {rec['seq_to']}")
        prev = rec.get("anchor_hash", prev)

    head_seq = con.execute(
        "SELECT coalesce(max(seq), 0) FROM main.evidence").fetchone()[0]
    anchored_through = anchors[-1]["seq_to"] if anchors else 0
    return {
        "ok": not problems,
        "problems": problems,
        "anchors": len(anchors),
        "anchored_through": anchored_through,
        "head_seq": head_seq,
        "unanchored": max(0, head_seq - anchored_through),
    }
