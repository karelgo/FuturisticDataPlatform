"""The `carina` CLI — the golden path in one binary.

ingest → transform (WAP) → check → serve, plus the Phase-1 KEEL verbs:
compile (contract compiler v1), create data-product (golden path scaffold),
parity (dual-run migration gate), lanes (router state).
"""

from __future__ import annotations

import argparse
import sys

import duckdb

from . import authz, catalog, config, conformance, evidence, ingest, lanes, parity, quality, scaffold, transform, warehouse
from .compiler import (
    check_artifacts,
    check_policy_bundle as compiler_check_bundle,
    write_artifacts,
    write_policy_bundle,
)
from .contracts import all_contracts, load_products


def _connect() -> duckdb.DuckDBPyConnection:
    config.ensure_dirs()
    con = duckdb.connect(str(config.DB_PATH))
    evidence.init(con)
    return con


def _products(args) -> list:
    products = load_products()
    wanted = getattr(args, "product", None)
    if wanted:
        products = [p for p in products if p.id == wanted]
        if not products:
            raise SystemExit(f"error: unknown product '{wanted}'")
    return products


def cmd_ingest(args) -> int:
    con = _connect()
    for p in _products(args):
        print(f"→ product {p.id}: ingesting {len(p.contracts)} contracted sources")
        results = ingest.ingest_all(con, p.contracts)
        for r in results:
            print(f"   {r['contract']}: bronze={r['bronze_rows']} silver={r['silver_rows']} "
                  f"(source modified {r['source_modified']})")
    return 0


def cmd_transform(args) -> int:
    con = _connect()
    rc = 0
    for p in _products(args):
        r = transform.run_product_transforms(con, p)
        for f in r["files"]:
            tables = ", ".join(f"{t}={n}" for t, n in f["tables"].items())
            print(f"→ {p.id}/{f['file']}: staged {tables}")
        audits = r["audits"]
        failed = [a for a in audits if not a["passed"]]
        if r["published"]:
            print(f"→ {p.id}: WAP audits {len(audits)}/{len(audits)} green — published to main")
        elif audits:
            rc = 1
            print(f"→ {p.id}: WAP ABORT — {len(failed)} audit(s) failed; production untouched")
            for a in failed:
                print(f"   ✗ {a['table']}: {a['name']} ({a['failures']} failures)")
    return rc


def cmd_check(args) -> int:
    con = _connect()
    rc = 0
    for p in _products(args):
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


def cmd_compile(args) -> int:
    products = _products(args)
    if args.check:
        stale = {p.id: check_artifacts(p) for p in products}
        stale = {pid: paths for pid, paths in stale.items() if paths}
        bundle_stale = compiler_check_bundle(load_products())
        if stale or bundle_stale:
            print("✗ compiled artifacts are stale — run `carina compile` and commit:")
            for pid, paths in stale.items():
                for path in paths:
                    print(f"   {pid}: compiled/{path}")
            for path in bundle_stale:
                print(f"   policies/{path}")
            return 1
        print("→ compiled artifacts up to date for "
              f"{len(products)} product(s) (+ policy bundle)")
        return 0
    con = _connect()
    for p in products:
        r = write_artifacts(p)
        evidence.record(con, "compile.run", p.id, {
            "artifacts": len(r["artifacts"]), "changed": r["changed"],
            "removed": r["removed"], "digest": r["digest"],
        })
        print(f"→ {p.id}: {len(r['artifacts'])} artifacts compiled "
              f"({len(r['changed'])} changed, {len(r['removed'])} removed) → "
              f"{p.path.relative_to(config.ROOT) / 'compiled'}")
    # The OPA bundle spans all products, regardless of any --product filter.
    b = write_policy_bundle(load_products())
    if b["changed"] or b["removed"]:
        print(f"→ policy bundle: {len(b['artifacts'])} files "
              f"({len(b['changed'])} changed, {len(b['removed'])} removed) → policies/")
    return 0


def cmd_run(args) -> int:
    rc = cmd_compile(argparse.Namespace(product=getattr(args, "product", None), check=False))
    rc = cmd_ingest(args) or rc
    rc = cmd_transform(args) or rc
    rc = cmd_check(args) or rc
    con = _connect()
    if rc == 0:
        _record_golden_path_ship(con, args)
    v = evidence.verify(con)
    print(f"→ evidence chain: {v['records']} records, verified={'OK' if v['ok'] else 'BROKEN'}")
    return rc


def _record_golden_path_ship(con, args) -> None:
    """First fully green run of a scaffolded product = it shipped. Measured."""
    for p in _products(args):
        minutes = scaffold.minutes_since_created(p.raw)
        if minutes is None or evidence.latest(con, "golden_path.ship", p.id):
            continue
        evidence.record(con, "golden_path.ship", p.id, {
            "minutes_from_scaffold_to_live": round(minutes, 1),
            "target_minutes": 60,
            "within_target": minutes < 60,
        })
        flag = "within" if minutes < 60 else "OVER"
        print(f"⚓ {p.id}: shipped end-to-end in {minutes:.1f} min — {flag} the 60-min KEEL target")


def cmd_create(args) -> int:
    if args.kind != "data-product":
        raise SystemExit("error: only 'data-product' can be created")
    pdir = scaffold.create_data_product(
        args.id, name=args.name, source_table=args.source_table, owner=args.owner)
    con = _connect()
    evidence.record(con, "golden_path.scaffold", args.id, {
        "path": str(pdir.relative_to(config.ROOT)), "source_table": args.source_table,
    })
    print(f"→ scaffolded {pdir.relative_to(config.ROOT)}")
    print("   1. Fill in the contract (source table, filter, silver columns, checks)")
    print("   2. Shape the gold transform and the semantic metrics")
    print(f"   3. carina run --product {args.id}")
    print("   The clock is running: first green run records the measured scaffold→live time.")
    return 0


def cmd_parity(args) -> int:
    con = _connect()
    r = parity.check_parity(con, args.table_a, args.table_b, key=args.key.split(","))
    if r.get("reason") == "schema mismatch":
        print(f"✗ {r['subject']}: schema mismatch")
        print(f"   only in {args.table_a}: {r['only_in_a']}")
        print(f"   only in {args.table_b}: {r['only_in_b']}")
        return 1
    status = "GREEN" if r["green"] else "RED"
    print(f"→ parity {r['subject']}: [{status}] "
          f"rows {r['rows_a']}/{r['rows_b']}, "
          f"key diff {r['keys_only_in_a']}+{r['keys_only_in_b']}, "
          f"row diff {r['rows_differing_from_b']}+{r['rows_differing_from_a']}")
    s = r["streak"]
    print(f"   green streak: {s['green_runs']} run(s) over {s['green_days']} day(s) "
          f"— gate at {s['target_days']} days: {'PASSED' if s['gate_passed'] else 'open'}")
    return 0 if r["green"] else 1


def cmd_authz(args) -> int:
    if args.action != "simulate":
        raise SystemExit("error: only 'simulate' is supported")
    contracts = [ct for ct in all_contracts()
                 if ct.silver_table == args.table or ct.id == args.table]
    if not contracts:
        raise SystemExit(f"error: no contract governs '{args.table}'")
    actor = authz.Actor(
        subject=args.subject,
        groups=[g for g in (args.groups or "").split(",") if g],
        authenticated=not args.anonymous,
    )
    rc = 0
    for ct in contracts:
        d = authz.decide(ct, actor, args.action_verb)
        mark = "ALLOW" if d.allow else "DENY"
        print(f"→ {ct.id} / {ct.silver_table} [{args.action_verb}]: {mark} — {d.reason}")
        masks = authz.masks_for(ct, actor)
        if masks:
            print(f"   masked columns: {', '.join(m['column'] + ':' + m['treatment'] for m in masks)}")
        if not d.allow:
            rc = 1
    return rc


def cmd_publish(args) -> int:
    con = _connect()
    rc = 0
    mode = "iceberg" if warehouse.iceberg_available() else "parquet"
    if mode == "parquet":
        print("→ pyiceberg not installed — publishing plain Parquet "
              "(pip install 'carina-platform[iceberg]' for Iceberg tables)")
    for p in _products(args):
        s = warehouse.publish_product(con, p)
        print(f"→ {p.id}: published {len(s['results'])} tables as {s['mode']} "
              f"→ {s['catalog']}")
        for r in s["results"]:
            mark = "✓" if r["verified"] else "✗"
            print(f"   {mark} {r['layer']}/{r['table']}: {r['rows']} rows "
                  f"[round-trip parity {'GREEN' if r['verified'] else 'RED'}]")
        if not s["all_verified"]:
            rc = 1
    return rc


def cmd_catalog(args) -> int:
    if args.action != "status":
        raise SystemExit("error: only 'status' is supported")
    s = catalog.status()
    kind = s.get("kind")
    if kind == "iceberg-rest":
        state = "reachable" if s.get("reachable") else f"UNREACHABLE ({s.get('error')})"
        print(f"→ catalog: Iceberg REST (Lakekeeper seam) at {s['uri']} [{state}]")
    elif kind == "local-sql":
        print(f"→ catalog: local SQL catalog at {s['uri']} "
              "(set CARINA_CATALOG_URI to attach Lakekeeper)")
    else:
        print(f"→ catalog: none yet — {s.get('hint')}")
        return 0
    for ns, tables in (s.get("tables") or {}).items():
        print(f"   {ns}: {', '.join(tables) if tables else '(no tables)'}")
    return 0 if s.get("reachable") else 1


def cmd_lanes(_args) -> int:
    con = _connect()
    router = lanes.LaneRouter(con)
    print(f"→ lane router v1 (escalation threshold: {lanes.escalate_threshold():,} rows)")
    for lane in router.lanes():
        state = "attached" if lane.attached else "seam (not attached)"
        print(f"   {lane.id:14s} [{state:20s}] {lane.description}"
              + (f" ({lane.detail})" if lane.detail and lane.attached else ""))
    return 0


def cmd_conformance(_args) -> int:
    con = _connect()
    s = conformance.run_suite(con)
    lane_note = " vs ".join(s["lanes"]) if s["comparing"] else \
        f"{s['lanes'][0]} only — corpus validated; attach a second lane to compare"
    print(f"→ cross-lane conformance: {s['queries']} queries on {lane_note}")
    for q in s["detail"]:
        mark = "✓" if q["green"] else "✗"
        rows = ", ".join(f"{l}={v['rows']}" for l, v in q["lanes"].items())
        print(f"   {mark} {q['id']}: {rows}")
        for d in q["drift"]:
            print(f"      DRIFT vs {d['lane']}: {d['rows_only_in_baseline']} rows "
                  f"only in baseline, {d['rows_only_in_lane']} only in lane")
        for e in q["errors"]:
            print(f"      ERROR on {e['lane']}: {e['error']}")
    print(f"→ suite: {'GREEN' if s['green'] else 'RED'}")
    return 0 if s["green"] else 1


def cmd_serve(args) -> int:
    import uvicorn
    uvicorn.run("carina.api:app", host=args.host, port=args.port, log_level="info")
    return 0


def cmd_flight(args) -> int:
    from . import flight
    config.ensure_dirs()
    flight.serve(str(config.DB_PATH), host=args.host, port=args.port)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="carina", description="CARINA laptop profile")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def with_product(p):
        p.add_argument("--product", help="Limit to one product id")
        return p

    with_product(sub.add_parser("ingest", help="Fetch contracted sources into bronze + silver"))
    with_product(sub.add_parser("transform", help="Run gold transforms (write-audit-publish)"))
    with_product(sub.add_parser("check", help="Run contract-compiled quality checks"))
    with_product(sub.add_parser("run", help="compile + ingest + transform + check"))

    comp = with_product(sub.add_parser(
        "compile", help="Compile contracts → DDL, checks, policy, tuples, catalog"))
    comp.add_argument("--check", action="store_true",
                      help="CI gate: fail if compiled artifacts are stale")

    create = sub.add_parser("create", help="Scaffold from the golden path")
    create.add_argument("kind", choices=["data-product"])
    create.add_argument("id", help="Product id (kebab-case)")
    create.add_argument("--name", help="Human-readable name")
    create.add_argument("--source-table", default="TODO", help="CBS StatLine table id")
    create.add_argument("--owner", default="platform-team@carina.local")

    par = sub.add_parser("parity", help="Row-level parity between two tables (migration gate)")
    par.add_argument("table_a")
    par.add_argument("table_b")
    par.add_argument("--key", required=True, help="Comma-separated key columns")

    with_product(sub.add_parser(
        "publish", help="Publish tables to the warehouse (Iceberg/Parquet), parity-verified"))

    cat = sub.add_parser("catalog", help="Catalog seam state (Lakekeeper or local)")
    cat.add_argument("action", choices=["status"])

    az = sub.add_parser("authz", help="Evaluate contract policy for an actor")
    az.add_argument("action", choices=["simulate"])
    az.add_argument("table", help="Silver table or contract id")
    az.add_argument("--subject", default="someone@example.org")
    az.add_argument("--groups", help="Comma-separated group memberships")
    az.add_argument("--anonymous", action="store_true", help="Unauthenticated caller")
    az.add_argument("--action-verb", default="read", choices=["read", "write"])

    sub.add_parser("lanes", help="Show compute lanes and router state")

    sub.add_parser("conformance",
                   help="Run the cross-lane conformance corpus on all attached lanes")

    serve = sub.add_parser("serve", help="Serve the portal UI + API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8899)

    flt = sub.add_parser("flight", help="Serve the Arrow Flight front door")
    flt.add_argument("--host", default="127.0.0.1")
    flt.add_argument("--port", type=int, default=8815)

    args = parser.parse_args()
    rc = {
        "ingest": cmd_ingest, "transform": cmd_transform, "check": cmd_check,
        "run": cmd_run, "serve": cmd_serve, "compile": cmd_compile,
        "create": cmd_create, "parity": cmd_parity, "lanes": cmd_lanes,
        "publish": cmd_publish, "catalog": cmd_catalog, "authz": cmd_authz,
        "flight": cmd_flight, "conformance": cmd_conformance,
    }[args.cmd](args)
    sys.exit(rc)


if __name__ == "__main__":
    main()
