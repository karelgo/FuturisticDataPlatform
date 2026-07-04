"""Publish path: open formats out, parity-verified back."""

import pytest

from carina import warehouse

from .conftest import CONTRACT_RAW, make_product


def _built_product(con, tmp_path):
    """A product whose silver (contracted) and gold (lineage) tables exist."""
    con.execute("""CREATE TABLE silver_test AS
        SELECT make_date(2024, 1, 1) + INTERVAL (range) MONTH AS date,
               range * 1.5 AS value
        FROM range(6)""")
    con.execute("CREATE TABLE gold_test AS SELECT date, value * 2 AS doubled FROM silver_test")
    pdir = tmp_path / "products" / "test-product"
    pdir.mkdir(parents=True)
    return make_product(
        pdir,
        raw={"id": "test-product", "lineage": {"gold_test": ["silver_test"]}},
        contracts=[CONTRACT_RAW],
    )


def test_parquet_publish_roundtrip(con, tmp_path, monkeypatch):
    monkeypatch.setenv("CARINA_WAREHOUSE", str(tmp_path / "wh"))
    monkeypatch.setattr(warehouse, "iceberg_available", lambda: False)
    product = _built_product(con, tmp_path)
    s = warehouse.publish_product(con, product)
    assert s["mode"] == "parquet"
    assert s["all_verified"] is True
    assert (tmp_path / "wh" / "carina" / "test_product" / "silver"
            / "silver_test" / "data.parquet").exists()
    assert s["tables"]["gold_test"]["rows"] == 6


@pytest.mark.skipif(not warehouse.iceberg_available(), reason="pyiceberg not installed")
def test_iceberg_publish_roundtrip(con, tmp_path, monkeypatch):
    monkeypatch.setenv("CARINA_WAREHOUSE", str(tmp_path / "wh"))
    monkeypatch.delenv("CARINA_CATALOG_URI", raising=False)
    product = _built_product(con, tmp_path)
    s = warehouse.publish_product(con, product)
    assert s["mode"] == "iceberg"
    assert s["all_verified"] is True

    cat = warehouse.load_iceberg_catalog()
    t = cat.load_table(("carina", "test_product", "silver", "silver_test"))
    assert t.scan().to_arrow().num_rows == 6
    # contract metadata travels into catalog properties
    assert t.properties["carina.contract"] == "test-source"
    assert t.properties["carina.classification"] == "public"


@pytest.mark.skipif(not warehouse.iceberg_available(), reason="pyiceberg not installed")
def test_iceberg_republish_and_schema_change(con, tmp_path, monkeypatch):
    monkeypatch.setenv("CARINA_WAREHOUSE", str(tmp_path / "wh"))
    monkeypatch.delenv("CARINA_CATALOG_URI", raising=False)
    product = _built_product(con, tmp_path)
    warehouse.publish_product(con, product)

    # New rows: overwrite in place
    con.execute("INSERT INTO gold_test SELECT make_date(2025,1,1), 99.0")
    s = warehouse.publish_product(con, product)
    assert s["all_verified"] is True
    assert s["tables"]["gold_test"]["rows"] == 7

    # Schema change: table is replaced, still verified
    con.execute("ALTER TABLE gold_test ADD COLUMN extra INTEGER DEFAULT 1")
    s = warehouse.publish_product(con, product)
    assert s["all_verified"] is True


def test_product_tables_skips_unbuilt(con, tmp_path):
    product = _built_product(con, tmp_path)
    product.raw["lineage"]["gold_never_built"] = ["silver_test"]
    names = [t["table"] for t in warehouse.product_tables(con, product)]
    assert "gold_never_built" not in names
    assert "silver_test" in names and "gold_test" in names
