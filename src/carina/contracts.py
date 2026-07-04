"""Contract loading — the hub artifact.

Contracts are ODCS-flavored YAML files. Everything downstream compiles from
them: the ingest filter, the silver schema, the quality checks, the catalog
entry, and the trust panel shown in the UI (ADR-0011).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import config


@dataclass
class Contract:
    id: str
    path: Path
    raw: dict
    product_id: str

    @property
    def name(self) -> str:
        return self.raw.get("name", self.id)

    @property
    def source(self) -> dict:
        return self.raw.get("source", {})

    @property
    def silver(self) -> dict:
        return self.raw.get("silver", {})

    @property
    def silver_table(self) -> str:
        return self.silver["table"]

    @property
    def checks(self) -> list[dict]:
        return self.raw.get("quality", {}).get("checks", [])

    @property
    def owner(self) -> str:
        return self.raw.get("owner", "unknown")

    @property
    def classification(self) -> str:
        return self.raw.get("classification", "internal")


@dataclass
class Product:
    id: str
    path: Path
    raw: dict
    contracts: list[Contract] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.raw.get("name", self.id)


def load_products() -> list[Product]:
    products = []
    for pdir in config.product_dirs():
        praw = yaml.safe_load((pdir / "product.yaml").read_text())
        product = Product(id=praw.get("id", pdir.name), path=pdir, raw=praw)
        cdir = pdir / "contracts"
        if cdir.exists():
            for cpath in sorted(cdir.glob("*.yaml")):
                craw = yaml.safe_load(cpath.read_text())
                product.contracts.append(
                    Contract(id=craw["id"], path=cpath, raw=craw, product_id=product.id)
                )
        products.append(product)
    return products


def all_contracts() -> list[Contract]:
    return [c for p in load_products() for c in p.contracts]
