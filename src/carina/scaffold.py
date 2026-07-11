"""The golden path: `carina create data-product` (Phase 1 — KEEL).

One command scaffolds a complete, contract-first data product: the ODPS
descriptor, an ODCS contract template, a gold transform, and a semantic-model
stub. The scaffold stamps its creation time into product.yaml; the first
fully green `carina run --product <id>` records a `golden_path.ship` evidence
record with the measured scaffold→live duration. That number is the KEEL
definition of done: a new data product ships end-to-end in under 60 minutes,
measured — not claimed.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from . import config

PRODUCT_TEMPLATE = """\
# ODPS-flavored data product descriptor — the marketplace entry compiles from this.
id: {product_id}
name: "{name}"
description: >
  TODO: one paragraph — what question does this product answer, for whom?
owner: {owner}
tier: bronze
status: draft
created: "{created}"
tags: []

# Gold audits — run against staging before publish (Write-Audit-Publish).
audits:
  - {{table: gold_{slug}, type: min_rows, value: 1}}

# Gold-table lineage (upstream tables per gold table) — drives the lineage graph.
lineage:
  gold_{slug}: [silver_{slug}]
"""

CONTRACT_TEMPLATE = """\
apiVersion: odcs/v3.1-carina
id: {contract_id}
name: "TODO: human-readable name of this source"
owner: {owner}
classification: public   # public | internal | confidential

source:
  type: cbs-odata
  table: "{source_table}"
  url: https://opendata.cbs.nl/ODataApi/odata/{source_table}
  landing_page: https://opendata.cbs.nl/statline/#/CBS/en/dataset/{source_table}
  attribution: "TODO: source attribution"
  license: CC BY 4.0
  # filter: "Sex eq 'T001038'"       # optional server-side OData filter
  # dimensions: [Sex, Age]           # code lists to land alongside the data

silver:
  table: silver_{slug}
  # where: "substr(Periods, 5, 2) = 'MM'"   # optional row filter
  columns:
    # Declare the typed silver schema; everything else compiles from it.
    - {{name: value, from: TODO_SourceColumn_1, type: DOUBLE, description: "TODO", unit: ""}}

quality:
  key: [date]
  checks:
    - {{type: not_null, columns: [date]}}
    - {{type: unique, columns: [date]}}
    - {{type: min_rows, value: 1}}

refresh:
  cadence: monthly
  sla: "TODO"
"""

TRANSFORM_TEMPLATE = """\
-- Gold marts for the {product_id} product.
-- Every table here reads only silver tables built from contracted sources.
-- Transforms run Write-Audit-Publish: staged, audited, then published.

CREATE OR REPLACE TABLE gold_{slug} AS
SELECT *
FROM silver_{slug}
ORDER BY date;
"""

SEMANTIC_TEMPLATE = """\
# Semantic layer — the only consumption path. Metrics compile to SQL with provenance.
models:
  {slug}:
    table: gold_{slug}
    time: date
    grain: monthly
    contracts: [{contract_id}]
    dimensions: {{}}

metrics:
  {slug}_value:
    model: {slug}
    expr: value
    title: "TODO: metric title"
    description: "TODO: what this measures"
    unit: ""
    good_direction: none
"""


def create_data_product(
    product_id: str,
    name: str | None = None,
    source_table: str = "TODO",
    owner: str = "platform-team@carina.local",
) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", product_id):
        raise ValueError("product id must be lowercase kebab-case (a-z, 0-9, -)")
    pdir = config.PRODUCTS_DIR / product_id
    if pdir.exists():
        raise FileExistsError(f"product already exists: {pdir}")

    slug = product_id.replace("-", "_")
    contract_id = f"{product_id}-source"
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    values = {
        "product_id": product_id, "name": name or product_id, "slug": slug,
        "contract_id": contract_id, "owner": owner,
        "source_table": source_table, "created": created,
    }

    (pdir / "contracts").mkdir(parents=True)
    (pdir / "transforms").mkdir()
    (pdir / "semantic").mkdir()
    (pdir / "product.yaml").write_text(PRODUCT_TEMPLATE.format(**values))
    (pdir / "contracts" / f"{contract_id}.yaml").write_text(CONTRACT_TEMPLATE.format(**values))
    (pdir / "transforms" / "10_gold.sql").write_text(TRANSFORM_TEMPLATE.format(**values))
    (pdir / "semantic" / "metrics.yaml").write_text(SEMANTIC_TEMPLATE.format(**values))
    return pdir


def minutes_since_created(product_raw: dict) -> float | None:
    created = product_raw.get("created")
    if not created:
        return None
    t0 = datetime.fromisoformat(str(created))
    if t0.tzinfo is None:
        t0 = t0.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t0).total_seconds() / 60
