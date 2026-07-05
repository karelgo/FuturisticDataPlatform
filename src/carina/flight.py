"""The Arrow Flight front door (Phase 1 — KEEL, ADR-0004).

`carina flight` serves the semantic layer over Arrow Flight: a client asks
for a *metric* (never SQL — ADR-0008), the ticket compiles through the same
semantic layer as the REST API, the lane router runs it, and the answer comes
back as an Arrow table whose schema metadata carries the full provenance
(SQL, contracts, lane, routing decision, evidence head).

Identity is the same front door as REST: with CARINA_AUTH_MODE=oidc, the
`authorization` gRPC header must carry a valid Bearer token, and the
contract-compiled policy decides access; denies are evidence-logged.

Ticket format (JSON): {"metric": "...", "dimension": null, "since": null}
Requires the iceberg extra (pyarrow): pip install 'carina-platform[iceberg]'.

This is deliberately Arrow-Flight-with-a-metric-protocol, not yet the full
Flight SQL command set — the seam where Flight SQL (and ADBC drivers)
attach is this server. Nobody gets raw SQL either way.
"""

from __future__ import annotations

import json
import threading

import duckdb

from . import auth, authz, evidence, semantic
from .contracts import load_products
from .lanes import LaneRouter


def make_server(db_path: str, host: str = "127.0.0.1", port: int = 8815):
    """Build (and bind) the Flight server; caller decides whether to block.
    Pass port=0 to bind an ephemeral port (tests)."""
    import pyarrow.flight as fl

    class AuthMiddleware(fl.ServerMiddleware):
        def __init__(self, actor: authz.Actor):
            self.actor = actor

    class AuthMiddlewareFactory(fl.ServerMiddlewareFactory):
        def start_call(self, info, headers):
            header = (headers.get("authorization") or [None])[0]
            try:
                actor = auth.actor_from_authorization(header)
            except auth.AuthError as e:
                raise fl.FlightUnauthenticatedError(str(e))
            return AuthMiddleware(actor)

    class CarinaFlightServer(fl.FlightServerBase):
        def __init__(self, location):
            super().__init__(location, middleware={"auth": AuthMiddlewareFactory()})
            self._lock = threading.Lock()
            self._con = duckdb.connect(db_path)
            evidence.init(self._con)

        def _state(self):
            products = load_products()
            models, metrics = semantic.load_semantic(products)
            return products, models, metrics

        def do_get(self, context, ticket):
            actor: authz.Actor = context.get_middleware("auth").actor
            try:
                req = json.loads(ticket.ticket.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise fl.FlightServerError("ticket must be JSON: {metric, dimension?, since?}")

            with self._lock:
                products, models, metrics = self._state()
                try:
                    sql, params, metric, model, dim_col = semantic.compile_metric_sql(
                        models, metrics, req["metric"],
                        req.get("dimension"), req.get("since"))
                except KeyError as e:
                    raise fl.FlightServerError(str(e))

                contracts = [ct for p in products for ct in p.contracts
                             if ct.id in model.contracts]
                allowed, decisions = authz.decide_all(contracts, actor, "read",
                                                      con=self._con)
                if not allowed:
                    raise fl.FlightUnauthorizedError(json.dumps(
                        [d.as_dict() for d in decisions if not d.allow]))

                router = LaneRouter(self._con)
                decision = router.route([model.table])
                res = self._con.execute(sql, params)
                table = (res.to_arrow_table() if hasattr(res, "to_arrow_table")
                         else res.fetch_arrow_table())

                evidence.record(self._con, "semantic.query", metric.id, {
                    "surface": "flight", "dimension": req.get("dimension"),
                    "since": req.get("since"), "rows": table.num_rows,
                    "actor": actor.subject, "routing": decision.as_dict(),
                }, actor=actor.subject)

                provenance = {
                    "metric": metric.id, "model": model.id, "table": model.table,
                    "sql": sql, "contracts": model.contracts,
                    "lane": decision.lane, "routing": decision.as_dict(),
                    "evidence_head": evidence.head(self._con),
                }
            table = table.replace_schema_metadata(
                {"carina.provenance": json.dumps(provenance)})
            return fl.RecordBatchStream(table)

        def list_flights(self, context, criteria):
            _, _, metrics = self._state()
            import pyarrow as pa
            for m in metrics.values():
                descriptor = fl.FlightDescriptor.for_command(
                    json.dumps({"metric": m.id}).encode())
                yield fl.FlightInfo(pa.schema([]), descriptor, [], -1, -1)

    return CarinaFlightServer(f"grpc://{host}:{port}")


def serve(db_path: str, host: str = "127.0.0.1", port: int = 8815) -> None:
    server = make_server(db_path, host, port)
    print(f"→ CARINA Flight front door on grpc://{host}:{server.port} "
          f"(auth mode: {auth.mode()})")
    print('   ticket: {"metric": "...", "dimension": null, "since": null}')
    server.serve()
