"""Gold transforms: run a product's SQL files against the lakehouse."""

from __future__ import annotations

import re

import duckdb

from . import evidence
from .contracts import Product


def run_product_transforms(con: duckdb.DuckDBPyConnection, product: Product) -> list[dict]:
    tdir = product.path / "transforms"
    results = []
    if not tdir.exists():
        return results
    for sql_file in sorted(tdir.glob("*.sql")):
        # Strip comment lines first (they may contain semicolons), then split
        # into statements so a failure names its statement.
        sql = "\n".join(
            line for line in sql_file.read_text().splitlines()
            if not line.lstrip().startswith("--")
        )
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        created: list[str] = []
        for stmt in statements:
            con.execute(stmt)
            m = re.search(r"CREATE\s+OR\s+REPLACE\s+(?:TABLE|VIEW)\s+(\w+)", stmt, re.IGNORECASE)
            if m:
                created.append(m.group(1))
        counts = {}
        for t in created:
            counts[t] = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        evidence.record(con, "transform.run", product.id, {
            "file": sql_file.name, "statements": len(statements), "tables": counts,
        })
        results.append({"file": sql_file.name, "tables": counts})
    return results
