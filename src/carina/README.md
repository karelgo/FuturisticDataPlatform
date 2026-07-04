# carina — the laptop-profile platform package

| Module | Role (design counterpart) |
|---|---|
| `contracts.py` | Loads products + ODCS-flavored contracts — the hub artifacts (ADR-0011) |
| `ingest.py` | Contract-driven fetch → bronze (raw) → silver (compiled DDL); CBS StatLine client in `cbs.py` |
| `quality.py` | Compiles `quality.checks` from contracts into SQL, runs them, records results + evidence |
| `transform.py` | Runs product gold-mart SQL (`products/*/transforms/`) |
| `semantic.py` | The only consumption path: metric YAML → compiled SQL with full provenance (ADR-0008) |
| `insights.py` | Deterministic prepared analysis — the laptop stand-in for the Analyst agent |
| `evidence.py` | Append-only SHA-256 hash chain over every platform action (ADR-0010) |
| `api.py` | FastAPI: overview, product detail, lineage, metric queries, insights, evidence + verification; serves the UI |
| `cli.py` | `carina ingest | transform | check | run | serve` |
| `ui/` | The portal SPA: no build step, ECharts vendored (`ui/assets/vendor/echarts.min.js`, Apache-2.0) |

State lives in `data/` (gitignored): `lakehouse.duckdb` plus raw bronze JSON. Rebuild everything from live sources with `carina run`.
