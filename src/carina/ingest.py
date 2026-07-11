"""Ingestion: contract-driven fetch from CBS StatLine into bronze + silver.

Bronze = raw API payloads landed as-is (JSON files + DuckDB tables).
Silver = typed, renamed, period-parsed tables whose schema is declared in the
contract. The silver DDL comes from the contract compiler — never handwritten,
and byte-identical to the compiled artifact in products/*/compiled/.
"""

from __future__ import annotations

import duckdb

from . import cbs, config, evidence
from .compiler import bronze_table, compile_silver_sql
from .contracts import Contract


def ingest_contract(con: duckdb.DuckDBPyConnection, contract: Contract, client) -> dict:
    """Fetch one contract's source and build bronze + silver. Returns summary."""
    src = contract.source
    base_url = src["url"].rstrip("/")
    table_id = src["table"]

    # 1. Freshness metadata from the source itself
    info = cbs.fetch_table_info(client, base_url)
    evidence.record(con, "ingest.fetch_info", contract.id, {
        "cbs_table": table_id,
        "source_modified": info.get("Modified"),
        "source_period": info.get("Period"),
        "title": (info.get("Title") or "").strip(),
    })

    # 2. Code lists for declared dimensions
    codelists = {}
    for dim in src.get("dimensions", []):
        values = cbs.fetch_codelist(client, base_url, dim)
        codelists[dim] = values
        path = config.BRONZE_DIR / f"{table_id}__{dim}.json"
        cbs.write_json(path, values)
        con.execute(
            f"CREATE OR REPLACE TABLE bronze_{table_id.lower()}__{dim.lower()} AS "
            f"SELECT * FROM read_json_auto('{path.as_posix()}')"
        )

    # 3. The data itself (filtered server-side by the contract's filter)
    rows, urls = cbs.fetch_typed_dataset(client, base_url, src.get("filter"))
    raw_path = config.BRONZE_DIR / f"{table_id}.json"
    nbytes = cbs.write_json(raw_path, rows)
    btable = bronze_table(contract)
    con.execute(
        f"CREATE OR REPLACE TABLE {btable} AS "
        f"SELECT * FROM read_json_auto('{raw_path.as_posix()}', maximum_object_size=134217728)"
    )
    nrows = con.execute(f"SELECT count(*) FROM {btable}").fetchone()[0]
    evidence.record(con, "ingest.load_bronze", contract.id, {
        "cbs_table": table_id, "bronze_table": btable, "rows": nrows,
        "bytes": nbytes, "requests": len(urls), "filter": src.get("filter"),
    })

    # 4. Build silver from the compiled contract DDL
    stable = contract.silver_table
    con.execute(compile_silver_sql(contract))
    srows = con.execute(f"SELECT count(*) FROM {stable}").fetchone()[0]
    evidence.record(con, "ingest.build_silver", contract.id, {
        "silver_table": stable, "rows": srows,
        "columns": [c["name"] for c in contract.silver.get("columns", [])],
    })

    return {
        "contract": contract.id, "bronze_rows": nrows, "silver_rows": srows,
        "source_modified": info.get("Modified"), "source_period": info.get("Period"),
    }


def ingest_all(con: duckdb.DuckDBPyConnection, contracts: list[Contract]) -> list[dict]:
    results = []
    with cbs.make_client() as client:
        for contract in contracts:
            results.append(ingest_contract(con, contract, client))
    return results
