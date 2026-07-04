"""The data-plane seam: publish lakehouse tables in open formats (Phase 1 — KEEL).

`carina publish` exports a product's silver + gold tables out of the embedded
DuckDB file into the warehouse:

  - **Apache Iceberg** tables when pyiceberg is installed
    (`pip install 'carina-platform[iceberg]'`) — a local SQL catalog under
    CARINA_WAREHOUSE by default, or the Iceberg REST catalog (Lakekeeper)
    when CARINA_CATALOG_URI is set. This is the KEEL table format: what the
    Trino lane and every external engine attach to.
  - plain **Parquet** files otherwise — still an open format, no lock-in.

Every published table is round-trip verified with the parity checker (the
same dual-run gate the ODAP migration uses: convert, then prove row-level
parity), and the publish lands in the evidence chain.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import duckdb

from . import config, evidence, parity
from .compiler import compile_catalog_entry
from .contracts import Product


def warehouse_root() -> Path:
    return Path(os.environ.get("CARINA_WAREHOUSE", str(config.DATA_DIR / "warehouse")))


def catalog_uri() -> str | None:
    return os.environ.get("CARINA_CATALOG_URI") or None


def iceberg_available() -> bool:
    return importlib.util.find_spec("pyiceberg") is not None


def load_iceberg_catalog():
    """The catalog behind the seam: Lakekeeper (REST) if configured, else a
    local SQL catalog in the warehouse directory."""
    from pyiceberg.catalog import load_catalog

    root = warehouse_root()
    root.mkdir(parents=True, exist_ok=True)
    uri = catalog_uri()
    if uri:
        props = {"uri": uri}
        if os.environ.get("CARINA_CATALOG_TOKEN"):
            props["token"] = os.environ["CARINA_CATALOG_TOKEN"]
        if os.environ.get("CARINA_CATALOG_WAREHOUSE"):
            props["warehouse"] = os.environ["CARINA_CATALOG_WAREHOUSE"]
        return load_catalog("carina", **props)
    return load_catalog(
        "carina",
        type="sql",
        uri=f"sqlite:///{root / 'catalog.db'}",
        warehouse=f"file://{root}",
    )


def product_tables(con: duckdb.DuckDBPyConnection, product: Product) -> list[dict]:
    """The tables a product publishes: contracted silver + declared gold."""
    out = []
    for ct in product.contracts:
        out.append({"table": ct.silver_table, "layer": "silver", "contract": ct})
    for gold in (product.raw.get("lineage") or {}):
        out.append({"table": gold, "layer": "gold", "contract": None})
    existing = {
        r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
    }
    return [t for t in out if t["table"] in existing]


def _key_columns(con: duckdb.DuckDBPyConnection, table: str, meta: dict) -> list[str]:
    ct = meta.get("contract")
    if ct is not None and ct.raw.get("quality", {}).get("key"):
        return ct.raw["quality"]["key"]
    # Gold tables declare no key — use full-row identity.
    return [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {table}").fetchall()]


def _publish_iceberg(con, catalog, product: Product, meta: dict) -> dict:
    from pyiceberg.exceptions import CommitFailedException, NoSuchTableError

    table = meta["table"]
    ns = ("carina", product.id.replace("-", "_"), meta["layer"])
    ident = (*ns, table)
    res = con.execute(f"SELECT * FROM {table}")
    arrow = res.to_arrow_table() if hasattr(res, "to_arrow_table") else res.fetch_arrow_table()
    if meta["contract"] is not None:
        props = {k: str(v) for k, v in compile_catalog_entry(meta["contract"])["properties"].items()}
    else:
        props = {"carina.product": product.id, "carina.layer": meta["layer"]}

    catalog.create_namespace_if_not_exists(ns)
    try:
        ice = catalog.load_table(ident)
    except NoSuchTableError:
        ice = catalog.create_table(ident, schema=arrow.schema, properties=props)
    try:
        ice.overwrite(arrow)
    except (ValueError, CommitFailedException):
        # Schema evolved since the last publish: replace the table.
        catalog.drop_table(ident)
        ice = catalog.create_table(ident, schema=arrow.schema, properties=props)
        ice.overwrite(arrow)

    # Round-trip: scan the Iceberg table back and register it for the parity diff.
    back = ice.scan().to_arrow()
    relation = f"__published_{table}"
    con.register(relation, back)
    snapshot = ice.current_snapshot()
    return {
        "table": table, "layer": meta["layer"], "format": "iceberg",
        "identifier": ".".join(ident), "location": ice.location(),
        "snapshot_id": snapshot.snapshot_id if snapshot else None,
        "rows": arrow.num_rows, "relation": relation,
    }


def _publish_parquet(con, product: Product, meta: dict) -> dict:
    table = meta["table"]
    out = warehouse_root() / "carina" / product.id.replace("-", "_") / meta["layer"] / table
    out.mkdir(parents=True, exist_ok=True)
    path = out / "data.parquet"
    con.execute(f"COPY (SELECT * FROM {table}) TO '{path.as_posix()}' (FORMAT PARQUET)")
    rows = con.execute(f"SELECT count(*) FROM read_parquet('{path.as_posix()}')").fetchone()[0]
    return {
        "table": table, "layer": meta["layer"], "format": "parquet",
        "location": str(path), "rows": rows,
        "relation": f"read_parquet('{path.as_posix()}')",
    }


def publish_product(con: duckdb.DuckDBPyConnection, product: Product) -> dict:
    """Publish all of a product's tables to the warehouse; verify each one."""
    mode = "iceberg" if iceberg_available() else "parquet"
    catalog = load_iceberg_catalog() if mode == "iceberg" else None
    results = []
    for meta in product_tables(con, product):
        if mode == "iceberg":
            r = _publish_iceberg(con, catalog, product, meta)
        else:
            r = _publish_parquet(con, product, meta)
        p = parity.check_parity(con, r["table"], r["relation"],
                                key=_key_columns(con, r["table"], meta))
        r["verified"] = p["green"]
        results.append(r)

    if mode == "iceberg":
        catalog_ref = catalog_uri() or f"sql:{warehouse_root() / 'catalog.db'}"
    else:
        catalog_ref = str(warehouse_root())
    summary = {
        "mode": mode,
        "catalog": catalog_ref,
        "tables": {
            r["table"]: {
                k: r[k]
                for k in ["layer", "format", "rows", "verified"]
                + (["snapshot_id"] if "snapshot_id" in r else [])
            }
            for r in results
        },
        "all_verified": all(r["verified"] for r in results),
    }
    evidence.record(con, "warehouse.publish", product.id, summary)
    summary["results"] = results
    return summary
