import json

import pytest
import yaml

from carina import compiler
from carina.contracts import load_products

from .conftest import CONTRACT_RAW, make_product


def test_silver_sql_compiles_from_contract(contract):
    sql = compiler.compile_silver_sql(contract)
    assert sql.startswith("CREATE OR REPLACE TABLE silver_test AS")
    assert 'CAST("Value_1" AS DOUBLE) AS value' in sql
    assert "FROM bronze_00000test" in sql
    assert "AS period_code" in sql  # built-in period parsing always present


def test_silver_sql_executes(con, contract):
    con.execute("""CREATE TABLE bronze_00000test AS
        SELECT '2024MM01' AS Periods, 10.0 AS Value_1
        UNION ALL SELECT '2024MM02', 20.0""")
    con.execute(compiler.compile_silver_sql(contract))
    rows = con.execute("SELECT date, value FROM silver_test ORDER BY date").fetchall()
    assert len(rows) == 2
    assert str(rows[0][0]) == "2024-01-01"


@pytest.mark.parametrize("check,expect_fragment", [
    ({"type": "not_null", "columns": ["a"]}, "a IS NULL"),
    ({"type": "unique", "columns": ["a", "b"]}, "GROUP BY a, b"),
    ({"type": "range", "column": "v", "min": 0, "max": 5}, "v < 0 OR v > 5"),
    ({"type": "min_rows", "value": 3}, "count(*) >= 3"),
    ({"type": "freshness", "column": "d", "max_lag_days": 30}, "date_diff"),
    ({"type": "allowed_values", "column": "c", "values": ["x"]}, "NOT IN ('x')"),
    ({"type": "nonempty"}, "count(*) > 0"),
])
def test_check_compilation(check, expect_fragment):
    _, sql = compiler.compile_check(check, "t")
    assert expect_fragment in sql


def test_unknown_check_type_raises():
    with pytest.raises(ValueError):
        compiler.compile_check({"type": "nope"}, "t")


def test_policy_rego_public_contract(contract):
    rego = compiler.compile_policy_rego(contract)
    assert "package carina.contracts.test_source" in rego
    assert "default allow := false" in rego
    assert "input.subject.authenticated == true" in rego  # public read
    assert 'input.subject.groups[_] == "team-test@carina.local"' in rego


def test_policy_rego_consumers_and_masks():
    raw = dict(CONTRACT_RAW)
    raw["classification"] = "internal"
    raw["access"] = {
        "consumers": ["analysts@carina.local"],
        "masks": [{"column": "value", "treatment": "hash"}],
    }
    from carina.contracts import Contract
    ct = Contract(id="masked", path=None, raw=raw, product_id="p")
    rego = compiler.compile_policy_rego(ct)
    assert "input.subject.authenticated" not in rego  # not public
    assert 'input.subject.groups[_] == "analysts@carina.local"' in rego
    assert '"treatment": "hash"' in rego


def test_catalog_entry_shape(contract):
    entry = compiler.compile_catalog_entry(contract)
    assert entry["name"] == "silver_test"
    assert entry["namespace"] == ["carina", "test_product", "silver"]
    names = [f["name"] for f in entry["schema"]["fields"]]
    assert names[:5] == ["period_code", "period_type", "year", "period_num", "date"]
    value_field = next(f for f in entry["schema"]["fields"] if f["name"] == "value")
    assert value_field["type"] == "double"
    assert entry["properties"]["carina.classification"] == "public"


def test_fga_tuples(tmp_root):
    pdir = tmp_root / "products" / "test-product"
    pdir.mkdir()
    product = make_product(pdir, raw={"id": "test-product", "owner": "team-test@carina.local"},
                           contracts=[CONTRACT_RAW])
    fga = compiler.compile_fga_tuples(product)
    tuples = fga["tuples"]
    assert {"user": "group:team-test@carina.local", "relation": "owner",
            "object": "product:test-product"} in tuples
    assert {"user": "user:*", "relation": "reader",
            "object": "contract:test-source"} in tuples  # public → world-readable


def test_write_then_check_roundtrip(tmp_root):
    pdir = tmp_root / "products" / "test-product"
    (pdir / "contracts").mkdir(parents=True)
    (pdir / "product.yaml").write_text(yaml.safe_dump({"id": "test-product"}))
    (pdir / "contracts" / "test-source.yaml").write_text(yaml.safe_dump(CONTRACT_RAW))
    product = load_products()[0]

    r = compiler.write_artifacts(product)
    assert len(r["changed"]) == 5  # 4 per-contract artifacts + fga-tuples.json
    assert compiler.check_artifacts(product) == []

    # Drift: contract changes → check fails until recompiled
    stale_artifact = pdir / "compiled" / "test-source" / "policy.rego"
    stale_artifact.write_text("tampered")
    assert "test-source/policy.rego" in compiler.check_artifacts(product)

    r2 = compiler.write_artifacts(product)
    assert r2["changed"] == ["test-source/policy.rego"]
    assert compiler.check_artifacts(product) == []
    assert json.loads((pdir / "compiled" / "fga-tuples.json").read_text())["tuples"]
