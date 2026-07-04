"""Row-level parity checks (Phase 1 — KEEL, migration doctrine).

The ODAP→CARINA migration mechanic: dual-run the old and new path for the
same table and diff them row-by-row. A migration step is reversible until
its parity gate passes — the roadmap's gate is 30 consecutive green days.

Every run is evidence-logged, and the current green streak (runs and days)
is computed from the evidence chain itself, so the gate's state is auditable
rather than remembered.
"""

from __future__ import annotations

import json

import duckdb

from . import evidence

GREEN_TARGET_DAYS = 30


def _columns(con: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    return [r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()]


def check_parity(
    con: duckdb.DuckDBPyConnection,
    table_a: str,
    table_b: str,
    key: list[str],
) -> dict:
    """Row-level parity between two tables. Green = identical row sets."""
    subject = f"{table_a}<->{table_b}"
    cols_a, cols_b = _columns(con, table_a), _columns(con, table_b)
    if set(cols_a) != set(cols_b):
        result = {
            "green": False, "reason": "schema mismatch",
            "only_in_a": sorted(set(cols_a) - set(cols_b)),
            "only_in_b": sorted(set(cols_b) - set(cols_a)),
        }
    else:
        cols = ", ".join(cols_a)
        keys = ", ".join(key)
        rows_a = con.execute(f"SELECT count(*) FROM {table_a}").fetchone()[0]
        rows_b = con.execute(f"SELECT count(*) FROM {table_b}").fetchone()[0]
        keys_only_a = con.execute(
            f"SELECT count(*) FROM (SELECT {keys} FROM {table_a} EXCEPT SELECT {keys} FROM {table_b})"
        ).fetchone()[0]
        keys_only_b = con.execute(
            f"SELECT count(*) FROM (SELECT {keys} FROM {table_b} EXCEPT SELECT {keys} FROM {table_a})"
        ).fetchone()[0]
        cells_only_a = con.execute(
            f"SELECT count(*) FROM (SELECT {cols} FROM {table_a} EXCEPT SELECT {cols} FROM {table_b})"
        ).fetchone()[0]
        cells_only_b = con.execute(
            f"SELECT count(*) FROM (SELECT {cols} FROM {table_b} EXCEPT SELECT {cols} FROM {table_a})"
        ).fetchone()[0]
        green = (rows_a == rows_b and keys_only_a == 0 and keys_only_b == 0
                 and cells_only_a == 0 and cells_only_b == 0)
        result = {
            "green": green,
            "rows_a": rows_a, "rows_b": rows_b,
            "keys_only_in_a": keys_only_a, "keys_only_in_b": keys_only_b,
            "rows_differing_from_b": cells_only_a, "rows_differing_from_a": cells_only_b,
        }
        if not green:
            result["reason"] = "row-level differences"

    evidence.record(con, "parity.check", subject, {**result, "key": key})
    result["subject"] = subject
    result["streak"] = green_streak(con, subject)
    return result


def green_streak(con: duckdb.DuckDBPyConnection, subject: str) -> dict:
    """Consecutive trailing green parity runs for a table pair, from evidence."""
    rows = con.execute(
        "SELECT ts, payload FROM evidence WHERE action = 'parity.check' AND subject = ?"
        " ORDER BY seq DESC",
        [subject],
    ).fetchall()
    runs, first_ts, last_ts = 0, None, None
    for ts, payload in rows:
        if not json.loads(payload).get("green"):
            break
        runs += 1
        first_ts = ts
        last_ts = last_ts or ts
    days = (last_ts - first_ts).days if runs else 0
    return {
        "green_runs": runs,
        "green_days": days,
        "target_days": GREEN_TARGET_DAYS,
        "gate_passed": days >= GREEN_TARGET_DAYS,
        "since": str(first_ts) if first_ts else None,
    }
