"""Gold transforms with Write–Audit–Publish (Phase 1 — KEEL, ADR-0005).

Transforms never write to production directly. Each product's SQL builds its
gold tables in a staging schema (the laptop stand-in for an Iceberg branch),
compiled audits run against staging, and only a fully green audit publishes
the tables atomically into main. A red audit aborts: production keeps the
last good tables, and the abort is evidence-logged.

Audits are compiled, never handwritten: every created table gets a built-in
nonempty audit, plus whatever the product declares in its `audits:` block
(same check grammar as contract quality checks).
"""

from __future__ import annotations

import re

import duckdb

from . import evidence
from .compiler import compile_check
from .contracts import Product

STAGING = "wap"


def _staging_tables(con: duckdb.DuckDBPyConnection) -> list[str]:
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = ?",
        [STAGING],
    ).fetchall()
    return [r[0] for r in rows]


def _write(con: duckdb.DuckDBPyConnection, product: Product) -> tuple[list[str], list[dict]]:
    """Run the product's transform SQL into the staging schema."""
    created: list[str] = []
    files: list[dict] = []
    for sql_file in sorted((product.path / "transforms").glob("*.sql")):
        # Strip comment lines first (they may contain semicolons), then split
        # into statements so a failure names its statement.
        sql = "\n".join(
            line for line in sql_file.read_text().splitlines()
            if not line.lstrip().startswith("--")
        )
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        file_created: list[str] = []
        for stmt in statements:
            con.execute(stmt)
            m = re.search(r"CREATE\s+OR\s+REPLACE\s+(?:TABLE|VIEW)\s+(\w+)", stmt, re.IGNORECASE)
            if m:
                file_created.append(m.group(1))
        counts = {
            t: con.execute(f"SELECT count(*) FROM {STAGING}.{t}").fetchone()[0]
            for t in file_created
        }
        evidence.record(con, "wap.write", product.id, {
            "file": sql_file.name, "statements": len(statements),
            "staging_schema": STAGING, "tables": counts,
        })
        created += file_created
        files.append({"file": sql_file.name, "tables": counts})
    return created, files


def _audit(con: duckdb.DuckDBPyConnection, product: Product, created: list[str]) -> list[dict]:
    """Compiled audits against staging. Failure count 0 = pass."""
    audits = [{"table": t, "type": "nonempty"} for t in created]
    audits += product.raw.get("audits", [])
    results = []
    for a in audits:
        table = a["table"]
        name, sql = compile_check(a, f"{STAGING}.{table}")
        failures = con.execute(sql).fetchone()[0]
        results.append({"table": table, "name": name, "passed": failures == 0,
                        "failures": failures})
    return results


def run_product_transforms(con: duckdb.DuckDBPyConnection, product: Product) -> dict:
    """Write → audit → publish. Returns a summary incl. whether we published."""
    tdir = product.path / "transforms"
    if not tdir.exists() or not any(tdir.glob("*.sql")):
        return {"product": product.id, "files": [], "audits": [], "published": False,
                "reason": "no transforms"}

    con.execute(f"CREATE SCHEMA IF NOT EXISTS {STAGING}")
    for t in _staging_tables(con):  # leftovers from a previous aborted run
        con.execute(f"DROP TABLE IF EXISTS {STAGING}.{t}")

    # Unqualified CREATEs land in staging; unqualified reads resolve staging
    # first (so gold-on-gold references see this run), then main (silver).
    con.execute(f"SET search_path = '{STAGING},main'")
    try:
        created, files = _write(con, product)
        audits = _audit(con, product, created)
        failed = [a for a in audits if not a["passed"]]
        evidence.record(con, "wap.audit", product.id, {
            "audits": audits, "passed": len(audits) - len(failed), "failed": len(failed),
        })

        if failed:
            # Keep staging tables for inspection; production is untouched.
            evidence.record(con, "wap.abort", product.id, {
                "reason": "audit failed", "failed_audits": failed,
                "staging_kept": created,
            })
            return {"product": product.id, "files": files, "audits": audits,
                    "published": False, "reason": "audit failed"}

        con.execute("BEGIN")
        for t in created:
            con.execute(f"CREATE OR REPLACE TABLE main.{t} AS SELECT * FROM {STAGING}.{t}")
            con.execute(f"DROP TABLE {STAGING}.{t}")
        con.execute("COMMIT")
        evidence.record(con, "wap.publish", product.id, {
            "tables": {t: c for f in files for t, c in f["tables"].items()},
        })
        return {"product": product.id, "files": files, "audits": audits,
                "published": True, "reason": "audits green"}
    finally:
        con.execute("SET search_path = 'main'")
