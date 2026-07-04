"""The semantic layer — the only consumption path.

Metrics are declared in each product's semantic/metrics.yaml. The UI (and any
agent) queries metrics by id; this module compiles the metric definition into
SQL over the gold tables and returns rows *with provenance*: the SQL, the
tables touched, the contracts behind them, source freshness, and the evidence
head at query time. Raw SQL from consumers is not accepted (ADR-0008).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import yaml

from . import evidence
from .contracts import Product
from .lanes import LaneRouter


@dataclass
class SemanticModel:
    id: str
    table: str
    time_column: str
    grain: str
    dimensions: dict  # name -> column
    contracts: list[str]


@dataclass
class Metric:
    id: str
    model: str
    expr: str
    title: str
    description: str
    unit: str
    good_direction: str  # 'down' | 'up' | 'balance' | 'none'
    product_id: str


def load_semantic(products: list[Product]) -> tuple[dict[str, SemanticModel], dict[str, Metric]]:
    models: dict[str, SemanticModel] = {}
    metrics: dict[str, Metric] = {}
    for product in products:
        spath = product.path / "semantic" / "metrics.yaml"
        if not spath.exists():
            continue
        spec = yaml.safe_load(spath.read_text())
        for mid, m in (spec.get("models") or {}).items():
            models[mid] = SemanticModel(
                id=mid,
                table=m["table"],
                time_column=m.get("time", "date"),
                grain=m.get("grain", "unknown"),
                dimensions=m.get("dimensions") or {},
                contracts=m.get("contracts") or [],
            )
        for mid, m in (spec.get("metrics") or {}).items():
            metrics[mid] = Metric(
                id=mid,
                model=m["model"],
                expr=m["expr"],
                title=m.get("title", mid),
                description=m.get("description", ""),
                unit=m.get("unit", ""),
                good_direction=m.get("good_direction", "none"),
                product_id=product.id,
            )
    return models, metrics


def query_metric(
    con: duckdb.DuckDBPyConnection,
    models: dict[str, SemanticModel],
    metrics: dict[str, Metric],
    metric_id: str,
    dimension: str | None = None,
    since: str | None = None,
    actor: str = "portal.ui",
    router: LaneRouter | None = None,
) -> dict:
    if metric_id not in metrics:
        raise KeyError(f"Unknown metric: {metric_id}")
    metric = metrics[metric_id]
    model = models[metric.model]

    cols = [f"{model.time_column} AS t", f"{metric.expr} AS value"]
    dim_col = None
    if dimension:
        if dimension not in model.dimensions:
            raise KeyError(f"Metric {metric_id} has no dimension '{dimension}'")
        dim_col = model.dimensions[dimension]
        cols.insert(1, f"{dim_col} AS dim")

    sql = f"SELECT {', '.join(cols)} FROM {model.table}"
    params: list = []
    if since:
        sql += f" WHERE {model.time_column} >= ?"
        params.append(since)
    sql += f" ORDER BY {model.time_column}" + (", dim" if dim_col else "")

    router = router or LaneRouter(con)
    rows, decision = router.execute(sql, params, tables=[model.table])

    if dim_col:
        series: dict[str, list] = {}
        for t, dim, value in rows:
            series.setdefault(str(dim), []).append([str(t), value])
        data = {"kind": "multi", "series": series}
    else:
        data = {"kind": "single", "points": [[str(t), v] for t, v in rows]}

    evidence.record(con, "semantic.query", metric_id, {
        "dimension": dimension, "since": since, "rows": len(rows), "actor": actor,
        "routing": decision.as_dict(),
    }, actor=actor)

    freshness = evidence.latest(con, "ingest.fetch_info")
    return {
        "metric": {
            "id": metric.id, "title": metric.title, "unit": metric.unit,
            "description": metric.description, "good_direction": metric.good_direction,
        },
        "grain": model.grain,
        "data": data,
        "provenance": {
            "model": model.id,
            "table": model.table,
            "sql": sql,
            "contracts": model.contracts,
            "lane": decision.lane,
            "routing": decision.as_dict(),
            "evidence_head": evidence.head(con),
            "source_refreshed": (freshness or {}).get("ts"),
        },
    }
