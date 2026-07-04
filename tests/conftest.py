"""Shared fixtures: an in-memory lakehouse and a temp product tree."""

from __future__ import annotations

import duckdb
import pytest

from carina import config
from carina.contracts import Contract, Product

CONTRACT_RAW = {
    "apiVersion": "odcs/v3.1-carina",
    "id": "test-source",
    "name": "Test source",
    "owner": "team-test@carina.local",
    "classification": "public",
    "source": {
        "type": "cbs-odata",
        "table": "00000TEST",
        "url": "https://example.invalid/odata/00000TEST",
        "license": "CC BY 4.0",
    },
    "silver": {
        "table": "silver_test",
        "columns": [
            {"name": "value", "from": "Value_1", "type": "DOUBLE",
             "description": "A measured value", "unit": "x1000"},
        ],
    },
    "quality": {
        "key": ["date"],
        "checks": [
            {"type": "not_null", "columns": ["date"]},
            {"type": "unique", "columns": ["date"]},
            {"type": "min_rows", "value": 2},
            {"type": "range", "column": "value", "min": 0, "max": 100},
        ],
    },
}


@pytest.fixture
def con():
    return duckdb.connect()


@pytest.fixture
def tmp_root(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "BRONZE_DIR", tmp_path / "data" / "bronze")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "data" / "lakehouse.duckdb")
    monkeypatch.setattr(config, "PRODUCTS_DIR", tmp_path / "products")
    (tmp_path / "products").mkdir()
    return tmp_path


def make_product(pdir, raw=None, contracts=None) -> Product:
    product = Product(id="test-product", path=pdir, raw=raw or {"id": "test-product"})
    for craw in contracts or []:
        product.contracts.append(
            Contract(id=craw["id"], path=pdir / "contracts" / f"{craw['id']}.yaml",
                     raw=craw, product_id=product.id)
        )
    return product


@pytest.fixture
def contract() -> Contract:
    return Contract(id=CONTRACT_RAW["id"], path=None, raw=CONTRACT_RAW,
                    product_id="test-product")
