"""The operations console backend (ops plane, laptop profile).

One place to see every component of the platform and interrogate it:

  components() — the control-plane inventory: each component's status asked
                 of the component itself (evidence verify, anchor coverage,
                 lane attachment, catalog reachability, auth mode, …)
  run_query()  — the operator SQL lane: read-only by construction (sqlglot
                 whitelist, single statement, row-capped), executed through
                 the lane router, and evidence-logged with the operator's
                 identity. Consumers still never get SQL (ADR-0008); this
                 lane exists for the people who run the platform, and it is
                 audited like everything else.
  logs         — an in-process structured-log ring buffer per component
  traces       — an in-process request tracer (root span per API request,
                 child spans around compile/authz/lane work)

The logs and traces stores are the laptop stand-in for OTel → ClickStack:
same panes in the console, a different backend behind them in the cluster
profile.
"""

from __future__ import annotations

import contextlib
import contextvars
import logging
import os
import time
import uuid
from collections import deque
from datetime import datetime, timezone

import duckdb

from . import anchoring, auth, catalog, evidence, lanes, warehouse
from .contracts import load_products

OPS_GROUPS_ENV = "CARINA_OPS_GROUPS"
DEFAULT_OPS_GROUPS = "platform-team@carina.local"
QUERY_ROW_CAP = 500


def ops_groups() -> list[str]:
    return [g for g in os.environ.get(OPS_GROUPS_ENV, DEFAULT_OPS_GROUPS).split(",") if g]


# ---- structured logs (ring buffer) -----------------------------------------

_LOGS: deque = deque(maxlen=500)


class _RingHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        _LOGS.append({
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc)
                  .isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
        })


def install_log_capture() -> None:
    handler = _RingHandler()
    # uvicorn's loggers don't propagate to root — attach to them directly.
    for name in (None, "uvicorn", "uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(name)
        if not any(isinstance(h, _RingHandler) for h in logger.handlers):
            logger.addHandler(handler)
    root = logging.getLogger()
    if root.level > logging.INFO or root.level == logging.NOTSET:
        root.setLevel(logging.INFO)


def recent_logs(component: str | None = None, limit: int = 200) -> list[dict]:
    rows = [r for r in _LOGS if not component or r["component"].startswith(component)]
    return rows[-limit:][::-1]


def log_components() -> list[str]:
    return sorted({r["component"] for r in _LOGS})


# ---- traces (in-process, OTel-shaped) ---------------------------------------

_TRACES: deque = deque(maxlen=200)
_current_trace: contextvars.ContextVar = contextvars.ContextVar("carina_trace", default=None)
_current_span: contextvars.ContextVar = contextvars.ContextVar("carina_span", default=None)


@contextlib.contextmanager
def trace(name: str, **attributes):
    """Root span; everything inside lands in one trace."""
    t = {"trace_id": uuid.uuid4().hex[:16], "name": name,
         "start": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
         "spans": []}
    token = _current_trace.set(t)
    try:
        with span(name, **attributes):
            yield t
    finally:
        t["duration_ms"] = round(sum(
            s["duration_ms"] for s in t["spans"] if s["parent_id"] is None), 2)
        _TRACES.append(t)
        _current_trace.reset(token)


@contextlib.contextmanager
def span(name: str, **attributes):
    """Child span; no-op when there is no active trace."""
    t = _current_trace.get()
    if t is None:
        yield None
        return
    s = {"span_id": uuid.uuid4().hex[:8], "parent_id": _current_span.get(),
         "name": name, "offset_ms": None, "duration_ms": None,
         "attributes": dict(attributes), "status": "ok"}
    trace_start = time.monotonic() if not t["spans"] else None
    if "_t0" not in t:
        t["_t0"] = trace_start or time.monotonic()
    start = time.monotonic()
    s["offset_ms"] = round((start - t["_t0"]) * 1000, 2)
    token = _current_span.set(s["span_id"])
    t["spans"].append(s)
    try:
        yield s
    except Exception:
        s["status"] = "error"
        raise
    finally:
        s["duration_ms"] = round((time.monotonic() - start) * 1000, 2)
        _current_span.reset(token)


def recent_traces(limit: int = 50) -> list[dict]:
    out = []
    for t in list(_TRACES)[-limit:][::-1]:
        out.append({k: v for k, v in t.items() if k != "_t0"})
    return out


# ---- the operator SQL lane ---------------------------------------------------

def validate_readonly(sql: str) -> None:
    """Reject anything that is not a single read statement."""
    import sqlglot
    from sqlglot import expressions as exp

    statements = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    if len(statements) != 1:
        raise ValueError("exactly one statement per query")
    stmt = statements[0]
    if not isinstance(stmt, (exp.Select, exp.Union, exp.Describe, exp.Show)):
        raise ValueError(
            f"read-only lane: {stmt.key.upper()} is not allowed (SELECT/DESCRIBE/SHOW only)")


_log = logging.getLogger("carina.ops")


def run_query(con: duckdb.DuckDBPyConnection, sql: str, actor_subject: str) -> dict:
    validate_readonly(sql)
    _log.info("sql-workbench query by %s: %s", actor_subject,
              sql if len(sql) < 120 else sql[:117] + "...")
    router = lanes.LaneRouter(con)
    decision = router.route([])
    with span("lane.execute", lane=decision.lane):
        res = con.execute(sql)
        columns = [d[0] for d in res.description] if res.description else []
        rows = res.fetchmany(QUERY_ROW_CAP + 1)
    truncated = len(rows) > QUERY_ROW_CAP
    rows = [[None if v is None else str(v) for v in row] for row in rows[:QUERY_ROW_CAP]]
    evidence.record(con, "ops.query", "sql-workbench", {
        "sql": sql, "rows": len(rows), "truncated": truncated,
        "lane": decision.lane, "actor": actor_subject,
    }, actor=actor_subject)
    return {"columns": columns, "rows": rows, "row_count": len(rows),
            "truncated": truncated, "row_cap": QUERY_ROW_CAP,
            "lane": decision.lane}


# ---- component inventory ------------------------------------------------------

def _safe(fn, fallback=None):
    try:
        return fn()
    except Exception as e:
        return fallback if fallback is not None else {"error": f"{type(e).__name__}: {e}"}


def components(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Every platform component, its plane, and its live status — asked of
    the component itself, not of a config file."""
    out = []

    tables = con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
    ).fetchall()
    names = [t[0] for t in tables]
    layers = {
        "bronze": sum(n.startswith("bronze") for n in names),
        "silver": sum(n.startswith("silver") for n in names),
        "gold": sum(n.startswith("gold") for n in names),
    }
    out.append({"id": "lakehouse", "name": "Lakehouse (DuckDB)", "plane": "data",
                "status": "ok" if layers["gold"] else "warn",
                "detail": {**layers, "hint": None if layers["gold"] else "run `carina run`"}})

    ch = evidence.verify(con)
    an = _safe(lambda: anchoring.verify_anchors(con), {"ok": False, "anchors": 0})
    out.append({"id": "evidence", "name": "Evidence chain", "plane": "trust",
                "status": "ok" if ch.get("ok") and an.get("ok") else "error",
                "detail": {"records": ch.get("records", 0), "chain_ok": ch.get("ok"),
                           "anchors": an.get("anchors", 0),
                           "anchored_through": an.get("anchored_through", 0),
                           "unanchored": an.get("unanchored", 0)}})

    router = lanes.LaneRouter(con)
    for lane in router.lanes():
        out.append({"id": f"lane-{lane.id}", "name": f"Lane: {lane.id}", "plane": "compute",
                    "status": "ok" if lane.attached else "off",
                    "detail": {"engine": lane.engine,
                               "attached": lane.attached,
                               "note": lane.description}})

    cat = _safe(catalog.status, {"kind": "unknown", "reachable": False})
    cat_tables = sum(len(v) for v in (cat.get("tables") or {}).values())
    out.append({"id": "catalog", "name": "Catalog (Lakekeeper seam)", "plane": "data",
                "status": "ok" if cat.get("reachable") else
                          ("off" if cat.get("kind") in ("none", "unknown") else "error"),
                "detail": {"kind": cat.get("kind"), "uri": cat.get("uri"),
                           "tables": cat_tables, "error": cat.get("error")}})

    out.append({"id": "warehouse", "name": "Warehouse (Iceberg/Parquet)", "plane": "data",
                "status": "ok" if warehouse.iceberg_available() else "warn",
                "detail": {"format": "iceberg" if warehouse.iceberg_available() else "parquet",
                           "root": str(warehouse.warehouse_root())}})

    out.append({"id": "identity", "name": "Identity (Keycloak seam)", "plane": "trust",
                "status": "ok" if auth.mode() == "oidc" else "warn",
                "detail": {"auth_mode": auth.mode(), "issuer": auth.issuer(),
                           "note": None if auth.mode() == "oidc" else "dev identity — not for shared environments"}})

    denies = con.execute(
        "SELECT count(*) FROM main.evidence WHERE action = 'authz.deny'").fetchone()[0]
    products = load_products()
    n_contracts = sum(len(p.contracts) for p in products)
    out.append({"id": "policy", "name": "Policy (compiled OPA/FGA)", "plane": "trust",
                "status": "ok",
                "detail": {"contracts": n_contracts, "products": len(products),
                           "authz_denies_logged": denies}})

    for p in products:
        pub = evidence.latest(con, "wap.publish", p.id)
        abort = evidence.latest(con, "wap.abort", p.id)
        aborted_last = bool(abort and (not pub or abort["seq"] > pub["seq"]))
        try:
            q = con.execute(
                """SELECT count(*) FILTER (passed), count(*) FROM quality_runs
                   WHERE run_ts = (SELECT max(run_ts) FROM quality_runs q2
                                   WHERE q2.contract = quality_runs.contract)
                     AND contract IN (SELECT unnest(?::VARCHAR[]))""",
                [[ct.id for ct in p.contracts]],
            ).fetchone()
        except duckdb.Error:
            q = (0, 0)  # quality_runs not built yet
        out.append({"id": f"product-{p.id}", "name": f"Product: {p.id}", "plane": "product",
                    "status": "error" if aborted_last else
                              ("ok" if pub and q[0] == q[1] else "warn"),
                    "detail": {"contracts": len(p.contracts),
                               "checks": f"{q[0]}/{q[1]}",
                               "last_publish": (pub or {}).get("ts"),
                               "wap": "ABORTED" if aborted_last else ("published" if pub else "never run")}})

    conf = evidence.latest(con, "conformance.run")
    out.append({"id": "conformance", "name": "Cross-lane conformance", "plane": "compute",
                "status": ("ok" if conf["payload"].get("green") else "error") if conf else "off",
                "detail": {"last_run": (conf or {}).get("ts"),
                           "lanes": (conf or {}).get("payload", {}).get("lanes"),
                           "green": (conf or {}).get("payload", {}).get("green")}})

    return out
