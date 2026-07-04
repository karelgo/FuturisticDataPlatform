"""The CARINA portal API — one front door for UI and agents alike."""

from __future__ import annotations

import json
import threading

import duckdb
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, evidence, insights, lanes, quality, semantic
from .contracts import load_products

app = FastAPI(title="CARINA — laptop profile", version="0.1.0")

_lock = threading.Lock()
_con: duckdb.DuckDBPyConnection | None = None


def con() -> duckdb.DuckDBPyConnection:
    global _con
    if _con is None:
        config.ensure_dirs()
        _con = duckdb.connect(str(config.DB_PATH))
        evidence.init(_con)
    return _con


def load_state():
    products = load_products()
    models, metrics = semantic.load_semantic(products)
    return products, models, metrics


@app.get("/api/overview")
def overview():
    with _lock:
        c = con()
        products, models, metrics = load_state()
        prods = []
        for p in products:
            contract_ids = [ct.id for ct in p.contracts]
            checks = {"passed": 0, "failed": 0}
            fresh = []
            for ct in p.contracts:
                for r in quality.latest_results(c, ct.id):
                    checks["passed" if r["passed"] else "failed"] += 1
                info = evidence.latest(c, "ingest.fetch_info", ct.id)
                if info:
                    fresh.append({
                        "contract": ct.id,
                        "source_modified": info["payload"].get("source_modified"),
                        "ingested_at": info["ts"],
                    })
            prods.append({
                "id": p.id,
                "name": p.name,
                "description": p.raw.get("description", ""),
                "owner": p.raw.get("owner", ""),
                "tier": p.raw.get("tier", ""),
                "status": p.raw.get("status", ""),
                "contracts": contract_ids,
                "checks": checks,
                "freshness": fresh,
                "tags": p.raw.get("tags", []),
            })
        ev = evidence.verify(c)
        return {
            "platform": {"name": "CARINA", "profile": "laptop", "version": "0.1.0"},
            "products": prods,
            "metrics_count": len(metrics),
            "evidence": {"records": ev.get("records", 0), "ok": ev.get("ok"), "head": ev.get("head")},
        }


@app.get("/api/product/{product_id}")
def product_detail(product_id: str):
    with _lock:
        c = con()
        products, models, metrics = load_state()
        product = next((p for p in products if p.id == product_id), None)
        if not product:
            raise HTTPException(404, f"Unknown product: {product_id}")
        contracts = []
        for ct in product.contracts:
            info = evidence.latest(c, "ingest.fetch_info", ct.id)
            ingest = evidence.latest(c, "ingest.build_silver", ct.id)
            contracts.append({
                "id": ct.id,
                "name": ct.name,
                "owner": ct.owner,
                "classification": ct.classification,
                "source": {
                    "table": ct.source.get("table"),
                    "url": ct.source.get("url"),
                    "attribution": ct.source.get("attribution"),
                    "license": ct.source.get("license"),
                    "filter": ct.source.get("filter"),
                },
                "silver_table": ct.silver_table,
                "columns": ct.silver.get("columns", []),
                "checks_declared": ct.checks,
                "checks_latest": quality.latest_results(c, ct.id),
                "freshness": {
                    "source_modified": (info or {}).get("payload", {}).get("source_modified"),
                    "source_period": (info or {}).get("payload", {}).get("source_period"),
                    "ingested_at": (info or {}).get("ts"),
                    "silver_rows": (ingest or {}).get("payload", {}).get("rows"),
                },
                "refresh": ct.raw.get("refresh", {}),
            })
        sem_models = [
            {
                "id": m.id, "table": m.table, "grain": m.grain,
                "dimensions": list(m.dimensions.keys()), "contracts": m.contracts,
            }
            for m in models.values()
        ]
        return {
            "id": product.id,
            "name": product.name,
            "description": product.raw.get("description", ""),
            "narrative": product.raw.get("narrative", ""),
            "owner": product.raw.get("owner", ""),
            "tier": product.raw.get("tier", ""),
            "status": product.raw.get("status", ""),
            "tags": product.raw.get("tags", []),
            "contracts": contracts,
            "semantic_models": sem_models,
            "metrics": [
                {"id": m.id, "title": m.title, "unit": m.unit, "model": m.model, "description": m.description}
                for m in metrics.values() if m.product_id == product.id
            ],
        }


@app.get("/api/lineage/{product_id}")
def lineage(product_id: str):
    products, models, metrics = load_state()
    product = next((p for p in products if p.id == product_id), None)
    if not product:
        raise HTTPException(404, f"Unknown product: {product_id}")
    nodes, edges = [], []
    for ct in product.contracts:
        src_id = f"cbs:{ct.source.get('table')}"
        nodes.append({"id": src_id, "kind": "source", "label": f"CBS {ct.source.get('table')}"})
        nodes.append({"id": ct.silver_table, "kind": "silver", "label": ct.silver_table, "contract": ct.id})
        edges.append({"from": src_id, "to": ct.silver_table, "via": ct.id})
    lineage_spec = product.raw.get("lineage", {})
    for gold, upstreams in lineage_spec.items():
        nodes.append({"id": gold, "kind": "gold", "label": gold})
        for u in upstreams:
            edges.append({"from": u, "to": gold, "via": "transform"})
    for m in models.values():
        mid = f"model:{m.id}"
        nodes.append({"id": mid, "kind": "semantic", "label": m.id})
        edges.append({"from": m.table, "to": mid, "via": "semantic"})
    # de-dupe nodes
    seen, uniq = set(), []
    for n in nodes:
        if n["id"] not in seen:
            seen.add(n["id"])
            uniq.append(n)
    return {"nodes": uniq, "edges": edges}


@app.get("/api/metrics")
def metric_catalog():
    _, models, metrics = load_state()
    return [
        {
            "id": m.id, "title": m.title, "unit": m.unit, "description": m.description,
            "model": m.model, "grain": models[m.model].grain,
            "dimensions": list(models[m.model].dimensions.keys()),
        }
        for m in metrics.values()
    ]


@app.get("/api/metrics/{metric_id}/query")
def metric_query(
    metric_id: str,
    dimension: str | None = Query(default=None),
    since: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    with _lock:
        c = con()
        _, models, metrics = load_state()
        try:
            return semantic.query_metric(c, models, metrics, metric_id, dimension, since)
        except KeyError as e:
            raise HTTPException(404, str(e))


@app.get("/api/insights")
def prepared_insights():
    with _lock:
        c = con()
        try:
            return {"insights": insights.compute_insights(c), "prepared_by": "carina.insights (deterministic)"}
        except duckdb.CatalogException:
            return {"insights": [], "prepared_by": "carina.insights",
                    "note": "gold tables missing — run `carina run` first"}


@app.get("/api/evidence")
def evidence_log(limit: int = Query(default=50, le=500), offset: int = 0, action: str | None = None):
    with _lock:
        c = con()
        evidence.init(c)
        where, args = "", []
        if action:
            where = "WHERE action LIKE ?"
            args.append(action + "%")
        rows = c.execute(
            f"SELECT seq, ts, actor, action, subject, payload, payload_hash, prev_hash, chain_hash "
            f"FROM evidence {where} ORDER BY seq DESC LIMIT ? OFFSET ?",
            args + [limit, offset],
        ).fetchall()
        total = c.execute(f"SELECT count(*) FROM evidence {where}", args).fetchone()[0]
        return {
            "total": total,
            "records": [
                {
                    "seq": r[0], "ts": str(r[1]), "actor": r[2], "action": r[3], "subject": r[4],
                    "payload": json.loads(r[5]), "payload_hash": r[6], "prev_hash": r[7], "chain_hash": r[8],
                }
                for r in rows
            ],
        }


@app.get("/api/evidence/verify")
def evidence_verify():
    with _lock:
        return evidence.verify(con())


@app.get("/api/lanes")
def lane_state():
    with _lock:
        router = lanes.LaneRouter(con())
        return {
            "escalate_threshold_rows": lanes.escalate_threshold(),
            "lanes": [
                {"id": lane.id, "engine": lane.engine, "attached": lane.attached,
                 "description": lane.description}
                for lane in router.lanes()
            ],
        }


# ---- static UI -------------------------------------------------------------

app.mount("/assets", StaticFiles(directory=str(config.UI_DIR / "assets")), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    # Single-page app: every non-API path serves the shell.
    if path.startswith("api/"):
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(str(config.UI_DIR / "index.html"))
