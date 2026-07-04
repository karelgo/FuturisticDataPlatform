"""The `carina` CLI — ingest, transform, check, serve."""

from __future__ import annotations

import argparse
import sys

import duckdb

from . import config, evidence, ingest, quality, transform
from .contracts import load_products


def _connect() -> duckdb.DuckDBPyConnection:
    config.ensure_dirs()
    con = duckdb.connect(str(config.DB_PATH))
    evidence.init(con)
    return con


def cmd_ingest(_args) -> int:
    con = _connect()
    products = load_products()
    for p in products:
        print(f"→ product {p.id}: ingesting {len(p.contracts)} contracted sources")
        results = ingest.ingest_all(con, p.contracts)
        for r in results:
            print(f"   {r['contract']}: bronze={r['bronze_rows']} silver={r['silver_rows']} "
                  f"(source modified {r['source_modified']})")
    return 0


def cmd_transform(_args) -> int:
    con = _connect()
    for p in load_products():
        for r in transform.run_product_transforms(con, p):
            tables = ", ".join(f"{t}={n}" for t, n in r["tables"].items())
            print(f"→ {p.id}/{r['file']}: {tables}")
    return 0


def cmd_check(_args) -> int:
    con = _connect()
    rc = 0
    for p in load_products():
        for ct in p.contracts:
            s = quality.run_contract_checks(con, ct)
            status = "PASS" if s["failed"] == 0 else "FAIL"
            print(f"→ {ct.id}: {s['passed']}/{s['total']} checks passed [{status}]")
            if s["failed"]:
                rc = 1
                for c in s["checks"]:
                    if not c["passed"]:
                        print(f"   ✗ {c['name']}: {c['failures']} failures")
    return rc


def cmd_run(args) -> int:
    rc = cmd_ingest(args)
    rc = cmd_transform(args) or rc
    rc = cmd_check(args) or rc
    con = _connect()
    v = evidence.verify(con)
    print(f"→ evidence chain: {v['records']} records, verified={'OK' if v['ok'] else 'BROKEN'}")
    return rc


def cmd_serve(args) -> int:
    import uvicorn
    uvicorn.run("carina.api:app", host=args.host, port=args.port, log_level="info")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="carina", description="CARINA laptop profile")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ingest", help="Fetch contracted sources into bronze + silver")
    sub.add_parser("transform", help="Run product gold transforms")
    sub.add_parser("check", help="Run contract-compiled quality checks")
    sub.add_parser("run", help="ingest + transform + check")
    serve = sub.add_parser("serve", help="Serve the portal UI + API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8899)

    args = parser.parse_args()
    rc = {
        "ingest": cmd_ingest, "transform": cmd_transform, "check": cmd_check,
        "run": cmd_run, "serve": cmd_serve,
    }[args.cmd](args)
    sys.exit(rc)


if __name__ == "__main__":
    main()
