"""Write-Audit-Publish: green audits publish; red audits leave prod untouched."""

from carina import transform

from .conftest import make_product


def _product_with_transform(tmp_path, sql, audits=None):
    pdir = tmp_path / "products" / "test-product"
    (pdir / "transforms").mkdir(parents=True)
    (pdir / "transforms" / "10_gold.sql").write_text(sql)
    raw = {"id": "test-product"}
    if audits:
        raw["audits"] = audits
    return make_product(pdir, raw=raw)


def test_green_audit_publishes(con, tmp_path):
    con.execute("CREATE TABLE silver_test AS SELECT 1 AS a UNION ALL SELECT 2")
    product = _product_with_transform(
        tmp_path,
        "CREATE OR REPLACE TABLE gold_t AS SELECT a * 10 AS v FROM silver_test;",
        audits=[{"table": "gold_t", "type": "min_rows", "value": 2}],
    )
    r = transform.run_product_transforms(con, product)
    assert r["published"] is True
    assert con.execute("SELECT count(*) FROM main.gold_t").fetchone()[0] == 2
    # staging is cleaned up after publish
    assert transform._staging_tables(con) == []


def test_gold_on_gold_resolves_staging(con, tmp_path):
    con.execute("CREATE TABLE silver_test AS SELECT 5 AS a")
    product = _product_with_transform(
        tmp_path,
        "CREATE OR REPLACE TABLE gold_a AS SELECT a FROM silver_test;\n"
        "CREATE OR REPLACE TABLE gold_b AS SELECT a + 1 AS b FROM gold_a;",
    )
    r = transform.run_product_transforms(con, product)
    assert r["published"] is True
    assert con.execute("SELECT b FROM main.gold_b").fetchone()[0] == 6


def test_red_audit_aborts_and_keeps_production(con, tmp_path):
    con.execute("CREATE TABLE silver_test AS SELECT 1 AS a")
    con.execute("CREATE TABLE gold_t AS SELECT 'last-good' AS v")
    product = _product_with_transform(
        tmp_path,
        "CREATE OR REPLACE TABLE gold_t AS SELECT a FROM silver_test;",
        audits=[{"table": "gold_t", "type": "min_rows", "value": 999}],
    )
    r = transform.run_product_transforms(con, product)
    assert r["published"] is False
    assert r["reason"] == "audit failed"
    # production still has the last good table
    assert con.execute("SELECT v FROM main.gold_t").fetchone()[0] == "last-good"
    # staging kept for inspection, and swept on the next run
    assert "gold_t" in transform._staging_tables(con)


def test_builtin_nonempty_audit_catches_empty_gold(con, tmp_path):
    con.execute("CREATE TABLE silver_test AS SELECT 1 AS a WHERE 1 = 0")
    product = _product_with_transform(
        tmp_path, "CREATE OR REPLACE TABLE gold_t AS SELECT a FROM silver_test;")
    r = transform.run_product_transforms(con, product)
    assert r["published"] is False
    failed = [a for a in r["audits"] if not a["passed"]]
    assert failed and failed[0]["name"].startswith("nonempty")
