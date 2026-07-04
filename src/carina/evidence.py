"""The evidence plane (laptop profile).

Append-only, hash-chained log of every platform action: ingests, transforms,
quality runs, semantic queries. Each record's chain_hash commits to the full
history before it, so tampering with any past record is detectable by
re-walking the chain. This is the single-node stand-in for CARINA's
Merkle-anchored Iceberg audit tables (ADR-0010).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import duckdb

GENESIS = "0" * 64

DDL = """
CREATE TABLE IF NOT EXISTS evidence (
    seq          BIGINT PRIMARY KEY,
    ts           TIMESTAMP NOT NULL,
    actor        VARCHAR NOT NULL,
    action       VARCHAR NOT NULL,
    subject      VARCHAR NOT NULL,
    payload      JSON NOT NULL,
    payload_hash VARCHAR NOT NULL,
    prev_hash    VARCHAR NOT NULL,
    chain_hash   VARCHAR NOT NULL
)
"""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def init(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(DDL)


def record(
    con: duckdb.DuckDBPyConnection,
    action: str,
    subject: str,
    payload: dict,
    actor: str = "carina.pipeline",
) -> str:
    """Append one evidence record; returns its chain hash."""
    init(con)
    row = con.execute(
        "SELECT seq, chain_hash FROM evidence ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    seq = (row[0] + 1) if row else 1
    prev_hash = row[1] if row else GENESIS
    ts = datetime.now(timezone.utc)
    payload_json = json.dumps(payload, sort_keys=True, default=str)
    payload_hash = _sha256(payload_json)
    chain_hash = _sha256(
        f"{seq}|{ts.isoformat()}|{actor}|{action}|{subject}|{payload_hash}|{prev_hash}"
    )
    con.execute(
        "INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [seq, ts, actor, action, subject, payload_json, payload_hash, prev_hash, chain_hash],
    )
    return chain_hash


def verify(con: duckdb.DuckDBPyConnection) -> dict:
    """Re-walk the chain and confirm every link. Returns a verification report."""
    init(con)
    rows = con.execute(
        "SELECT seq, ts, actor, action, subject, payload, payload_hash, prev_hash, chain_hash"
        " FROM evidence ORDER BY seq"
    ).fetchall()
    prev = GENESIS
    for seq, ts, actor, action, subject, payload, payload_hash, prev_hash, chain_hash in rows:
        if prev_hash != prev:
            return {"ok": False, "broken_at": seq, "reason": "prev_hash mismatch", "records": len(rows)}
        if _sha256(payload) != payload_hash:
            return {"ok": False, "broken_at": seq, "reason": "payload tampered", "records": len(rows)}
        ts_iso = ts.replace(tzinfo=timezone.utc).isoformat() if ts.tzinfo is None else ts.isoformat()
        expect = _sha256(f"{seq}|{ts_iso}|{actor}|{action}|{subject}|{payload_hash}|{prev_hash}")
        if expect != chain_hash:
            return {"ok": False, "broken_at": seq, "reason": "chain_hash mismatch", "records": len(rows)}
        prev = chain_hash
    return {"ok": True, "records": len(rows), "head": prev if rows else None}


def head(con: duckdb.DuckDBPyConnection) -> str | None:
    init(con)
    row = con.execute("SELECT chain_hash FROM evidence ORDER BY seq DESC LIMIT 1").fetchone()
    return row[0] if row else None


def latest(con: duckdb.DuckDBPyConnection, action_prefix: str, subject: str | None = None) -> dict | None:
    """Most recent evidence record for an action prefix (and optional subject)."""
    init(con)
    q = "SELECT seq, ts, actor, action, subject, payload, chain_hash FROM evidence WHERE action LIKE ?"
    args: list = [action_prefix + "%"]
    if subject:
        q += " AND subject = ?"
        args.append(subject)
    q += " ORDER BY seq DESC LIMIT 1"
    row = con.execute(q, args).fetchone()
    if not row:
        return None
    return {
        "seq": row[0], "ts": str(row[1]), "actor": row[2], "action": row[3],
        "subject": row[4], "payload": json.loads(row[5]), "chain_hash": row[6],
    }
