"""Cross-Lane Conformance Suite v1 (Phase 1 — KEEL, ADR-0004).

The same answer from every engine, or the build goes red. The canonical
corpus (conformance/corpus.yaml) runs on every *attached* lane; results are
normalized (dates to ISO, floats to 9 significant digits, row multisets) and
diffed cell-by-cell against the duckdb-local baseline. Any difference is
dialect drift — the exact failure mode that silently corrupts answers when
engines or SQLGlot are upgraded, which is why this suite gates those
upgrades and runs nightly.

With a single attached lane the suite still validates that every corpus
query executes green on the baseline — so the corpus itself can't rot while
waiting for the second lane.
"""

from __future__ import annotations

import datetime
from collections import Counter
from decimal import Decimal

import duckdb
import yaml

from . import config, evidence
from .lanes import LaneRouter

BASELINE = "duckdb-local"


def load_corpus() -> list[dict]:
    spec = yaml.safe_load((config.ROOT / "conformance" / "corpus.yaml").read_text())
    return spec.get("queries", [])


def _normalize_cell(v) -> str:
    if v is None:
        return "∅"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (float, Decimal)):
        return f"{float(v):.9g}"
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()[:19]
    return str(v)


def normalize_rows(rows: list) -> Counter:
    """Rows as an order-insensitive multiset of normalized tuples."""
    return Counter(tuple(_normalize_cell(c) for c in row) for row in rows)


def run_suite(
    con: duckdb.DuckDBPyConnection,
    corpus: list[dict] | None = None,
    router: LaneRouter | None = None,
) -> dict:
    corpus = corpus if corpus is not None else load_corpus()
    router = router or LaneRouter(con)
    lanes = [lane.id for lane in router.lanes() if lane.attached]

    queries = []
    for q in corpus:
        entry = {"id": q["id"], "lanes": {}, "drift": [], "errors": []}
        results: dict[str, Counter] = {}
        for lane in lanes:
            try:
                rows = router.run_on_lane(lane, q["sql"])
                results[lane] = normalize_rows(rows)
                entry["lanes"][lane] = {"rows": sum(results[lane].values())}
            except Exception as e:
                entry["errors"].append({"lane": lane,
                                        "error": f"{type(e).__name__}: {e}"})
        base = results.get(BASELINE)
        for lane, rows in results.items():
            if lane == BASELINE or base is None:
                continue
            only_base = base - rows
            only_lane = rows - base
            if only_base or only_lane:
                entry["drift"].append({
                    "lane": lane,
                    "rows_only_in_baseline": sum(only_base.values()),
                    "rows_only_in_lane": sum(only_lane.values()),
                    "sample_baseline": [list(r) for r in list(only_base)[:3]],
                    "sample_lane": [list(r) for r in list(only_lane)[:3]],
                })
        entry["green"] = not entry["drift"] and not entry["errors"]
        queries.append(entry)

    summary = {
        "lanes": lanes,
        "comparing": len(lanes) > 1,
        "queries": len(queries),
        "green": all(q["green"] for q in queries),
        "drifted": [q["id"] for q in queries if q["drift"]],
        "errored": [q["id"] for q in queries if q["errors"]],
    }
    evidence.record(con, "conformance.run", "cross-lane", {
        **summary,
        "detail": [{k: q[k] for k in ("id", "green", "drift", "errors")}
                   for q in queries],
    })
    summary["detail"] = queries
    return summary
