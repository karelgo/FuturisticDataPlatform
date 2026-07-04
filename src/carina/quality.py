"""Quality checks — compiled from contracts, never handwritten.

Each contract's `quality.checks` list compiles to SQL executed against the
silver table. Results land in the quality_runs table and the evidence chain.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import duckdb

from . import evidence
from .contracts import Contract

DDL = """
CREATE TABLE IF NOT EXISTS quality_runs (
    run_ts     TIMESTAMP,
    contract   VARCHAR,
    check_name VARCHAR,
    check_type VARCHAR,
    passed     BOOLEAN,
    detail     JSON
)
"""


def _compile(check: dict, table: str) -> tuple[str, str]:
    """Compile one contract check into (name, sql). SQL returns failure count."""
    t = check["type"]
    if t == "not_null":
        cols = check["columns"]
        cond = " OR ".join(f"{c} IS NULL" for c in cols)
        return f"not_null({','.join(cols)})", f"SELECT count(*) FROM {table} WHERE {cond}"
    if t == "unique":
        cols = ", ".join(check["columns"])
        return (
            f"unique({cols})",
            f"SELECT count(*) FROM (SELECT {cols} FROM {table} GROUP BY {cols} HAVING count(*) > 1)",
        )
    if t == "range":
        c, lo, hi = check["column"], check.get("min"), check.get("max")
        conds = []
        if lo is not None:
            conds.append(f"{c} < {lo}")
        if hi is not None:
            conds.append(f"{c} > {hi}")
        return (
            f"range({c})",
            f"SELECT count(*) FROM {table} WHERE {c} IS NOT NULL AND ({' OR '.join(conds)})",
        )
    if t == "min_rows":
        n = check["value"]
        return f"min_rows({n})", f"SELECT CASE WHEN count(*) >= {n} THEN 0 ELSE 1 END FROM {table}"
    if t == "freshness":
        c, days = check.get("column", "date"), check["max_lag_days"]
        return (
            f"freshness({c}<={days}d)",
            f"SELECT CASE WHEN date_diff('day', max({c}), current_date) <= {days} THEN 0 ELSE 1 END FROM {table}",
        )
    if t == "allowed_values":
        c = check["column"]
        vals = ", ".join(f"'{v}'" for v in check["values"])
        return (
            f"allowed_values({c})",
            f"SELECT count(*) FROM {table} WHERE {c} IS NOT NULL AND {c} NOT IN ({vals})",
        )
    raise ValueError(f"Unknown check type: {t}")


def run_contract_checks(con: duckdb.DuckDBPyConnection, contract: Contract) -> dict:
    con.execute(DDL)
    ts = datetime.now(timezone.utc)
    table = contract.silver_table
    results = []
    for check in contract.checks:
        name, sql = _compile(check, table)
        failures = con.execute(sql).fetchone()[0]
        passed = failures == 0
        detail = {"failures": failures, "sql": sql}
        con.execute(
            "INSERT INTO quality_runs VALUES (?, ?, ?, ?, ?, ?)",
            [ts, contract.id, name, check["type"], passed, json.dumps(detail)],
        )
        results.append({"name": name, "type": check["type"], "passed": passed, "failures": failures})
    summary = {
        "contract": contract.id,
        "table": table,
        "total": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failed": sum(1 for r in results if not r["passed"]),
        "checks": results,
    }
    evidence.record(con, "quality.run", contract.id, summary)
    return summary


def latest_results(con: duckdb.DuckDBPyConnection, contract_id: str) -> list[dict]:
    con.execute(DDL)
    rows = con.execute(
        """
        SELECT check_name, check_type, passed, detail, run_ts FROM quality_runs
        WHERE contract = ? AND run_ts = (SELECT max(run_ts) FROM quality_runs WHERE contract = ?)
        ORDER BY check_name
        """,
        [contract_id, contract_id],
    ).fetchall()
    return [
        {"name": r[0], "type": r[1], "passed": r[2], "detail": json.loads(r[3]), "run_ts": str(r[4])}
        for r in rows
    ]
