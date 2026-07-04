"""Ingestion: contract-driven fetch from CBS StatLine into bronze + silver.

Bronze = raw API payloads landed as-is (JSON files + DuckDB tables).
Silver = typed, renamed, period-parsed tables whose schema is declared in the
contract. The silver DDL is *compiled* from the contract — never handwritten.
"""

from __future__ import annotations

import duckdb

from . import cbs, config, evidence
from .contracts import Contract

# Built-in period parsing: CBS period codes look like 2003JJ00 (year),
# 1997KW01 (quarter), 2026MM05 (month).
PERIOD_SQL = """
    {periods_col} AS period_code,
    substr({periods_col}, 5, 2) AS period_type,
    CAST(substr({periods_col}, 1, 4) AS INTEGER) AS year,
    CAST(substr({periods_col}, 7, 2) AS INTEGER) AS period_num,
    CASE substr({periods_col}, 5, 2)
        WHEN 'JJ' THEN make_date(CAST(substr({periods_col},1,4) AS INTEGER), 1, 1)
        WHEN 'KW' THEN make_date(CAST(substr({periods_col},1,4) AS INTEGER), (CAST(substr({periods_col},7,2) AS INTEGER)-1)*3+1, 1)
        WHEN 'MM' THEN make_date(CAST(substr({periods_col},1,4) AS INTEGER), CAST(substr({periods_col},7,2) AS INTEGER), 1)
    END AS date
"""


def bronze_table(contract: Contract) -> str:
    return f"bronze_{contract.source['table'].lower()}"


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

    # 4. Compile silver from the contract's declared columns
    silver = contract.silver
    cols_sql = [PERIOD_SQL.format(periods_col=silver.get("periods_column", "Periods"))]
    for col in silver.get("columns", []):
        if "from" in col:
            expr = f'"{col["from"]}"'
        else:
            expr = col["expr"]
        cols_sql.append(f'CAST({expr} AS {col.get("type", "VARCHAR")}) AS {col["name"]}')

    joins = ""
    for j in silver.get("dim_joins", []):
        dim_table = f"bronze_{table_id.lower()}__{j['dimension'].lower()}"
        joins += (
            f' LEFT JOIN {dim_table} AS {j["alias"]} '
            f'ON trim(b."{j["dimension"]}") = trim({j["alias"]}.Key)'
        )

    where = silver.get("where", "1=1")
    stable = contract.silver_table
    con.execute(
        f"CREATE OR REPLACE TABLE {stable} AS "
        f"SELECT {', '.join(cols_sql)} FROM {btable} b{joins} WHERE {where}"
    )
    srows = con.execute(f"SELECT count(*) FROM {stable}").fetchone()[0]
    evidence.record(con, "ingest.build_silver", contract.id, {
        "silver_table": stable, "rows": srows,
        "columns": [c["name"] for c in silver.get("columns", [])],
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
