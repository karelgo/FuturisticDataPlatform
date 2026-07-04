"""Lane Router v1 (Phase 1 — KEEL, ADR-0004).

Nobody chooses an engine. Every semantic-layer query passes through the
router, which picks a lane from the registered set:

  duckdb-local  — always attached; the embedded, scale-to-zero default
  trino         — the scale-out seam; attaches when CARINA_TRINO_DSN is set
                  (host:port/catalog/schema) and the `trino` client is installed

The v1 policy is deliberately simple and inspectable: estimate the scan size
from the row counts of the tables a query touches; escalate past the
threshold when a scale-out lane is attached; otherwise stay in-process. The
full decision — lane, reason, estimate, candidates considered — travels with
every answer into provenance, so each answer names the engine that produced
it and why.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import duckdb

DEFAULT_ESCALATE_ROWS = 5_000_000


@dataclass
class Lane:
    id: str
    engine: str
    attached: bool
    description: str
    detail: str = ""


@dataclass
class Decision:
    lane: str
    reason: str
    estimated_rows: int
    candidates: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "lane": self.lane,
            "reason": self.reason,
            "estimated_rows": self.estimated_rows,
            "candidates": self.candidates,
        }


def _trino_dsn() -> str | None:
    return os.environ.get("CARINA_TRINO_DSN") or None


def escalate_threshold() -> int:
    return int(os.environ.get("CARINA_LANE_ESCALATE_ROWS", DEFAULT_ESCALATE_ROWS))


class LaneRouter:
    def __init__(self, con: duckdb.DuckDBPyConnection):
        self.con = con

    def lanes(self) -> list[Lane]:
        dsn = _trino_dsn()
        return [
            Lane(
                id="duckdb-local", engine="duckdb", attached=True,
                description="Embedded DuckDB — the scale-to-zero default lane.",
            ),
            Lane(
                id="trino", engine="trino", attached=dsn is not None,
                description="Distributed Trino — attaches via CARINA_TRINO_DSN.",
                detail=dsn or "not configured",
            ),
        ]

    def estimate_rows(self, tables: list[str]) -> int:
        total = 0
        for t in tables:
            try:
                total += self.con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            except duckdb.Error:
                pass  # table not built yet — contributes 0 to the estimate
        return total

    def route(self, tables: list[str]) -> Decision:
        estimate = self.estimate_rows(tables)
        threshold = escalate_threshold()
        attached = [lane for lane in self.lanes() if lane.attached]
        candidates = [lane.id for lane in attached]
        if len(attached) == 1:
            return Decision("duckdb-local", "only attached lane", estimate, candidates)
        if estimate > threshold:
            return Decision(
                "trino",
                f"estimated scan {estimate:,} rows exceeds escalation threshold {threshold:,}",
                estimate, candidates,
            )
        return Decision(
            "duckdb-local",
            f"estimated scan {estimate:,} rows fits in-process (threshold {threshold:,})",
            estimate, candidates,
        )

    def execute(self, sql: str, params: list | None, tables: list[str]) -> tuple[list, Decision]:
        """Route and run one query. Returns (rows, decision)."""
        decision = self.route(tables)
        if decision.lane == "trino":
            try:
                rows = self._execute_trino(sql, params)
                return rows, decision
            except Exception as e:  # client missing or cluster unreachable
                decision = Decision(
                    "duckdb-local",
                    f"trino selected but unavailable ({type(e).__name__}); fell back in-process",
                    decision.estimated_rows, decision.candidates,
                )
        rows = self.con.execute(sql, params or []).fetchall()
        return rows, decision

    def _execute_trino(self, sql: str, params: list | None) -> list:
        import trino  # optional dependency: pip install trino

        host_port, _, rest = _trino_dsn().partition("/")
        host, _, port = host_port.partition(":")
        catalog, _, schema = rest.partition("/")
        conn = trino.dbapi.connect(
            host=host, port=int(port or 8080),
            catalog=catalog or "iceberg", schema=schema or "carina",
            user=os.environ.get("CARINA_TRINO_USER", "carina"),
        )
        cur = conn.cursor()
        cur.execute(sql, params or None)
        return cur.fetchall()
