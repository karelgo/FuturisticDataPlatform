"""Catalog seam: REST client against a mocked Lakekeeper, and local status."""

import json

import httpx

from carina import catalog, warehouse


def _mock_catalog_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/catalog")
        if path == "/v1/config":
            return httpx.Response(200, json={
                "defaults": {"prefix": "carina"}, "overrides": {}})
        if path == "/v1/carina/namespaces":
            return httpx.Response(200, json={
                "namespaces": [["carina", "wages_nl", "gold"]]})
        if path.endswith("/tables"):
            return httpx.Response(200, json={
                "identifiers": [{"namespace": ["carina", "wages_nl", "gold"],
                                 "name": "gold_wages_monthly"}]})
        return httpx.Response(404, json={"error": "not found"})
    return httpx.MockTransport(handler)


def test_rest_client_config_prefix_and_tables():
    client = catalog.RestCatalogClient(
        "http://lakekeeper.test/catalog", transport=_mock_catalog_transport())
    assert client.prefix() == "carina"
    ns = client.namespaces("carina")
    assert ns == [["carina", "wages_nl", "gold"]]
    assert client.tables(ns[0], "carina") == ["gold_wages_monthly"]


def test_status_unconfigured_no_warehouse(tmp_path, monkeypatch):
    monkeypatch.setenv("CARINA_WAREHOUSE", str(tmp_path / "empty"))
    monkeypatch.delenv("CARINA_CATALOG_URI", raising=False)
    s = catalog.status()
    assert s["configured"] is False
    assert s["kind"] == "none"


def test_status_unreachable_rest(monkeypatch):
    monkeypatch.setenv("CARINA_CATALOG_URI", "http://127.0.0.1:1/catalog")
    s = catalog.status()
    assert s["configured"] is True
    assert s["reachable"] is False
    assert "error" in s


def test_status_local_after_publish(con, tmp_path, monkeypatch):
    if not warehouse.iceberg_available():
        import pytest
        pytest.skip("pyiceberg not installed")
    monkeypatch.setenv("CARINA_WAREHOUSE", str(tmp_path / "wh"))
    monkeypatch.delenv("CARINA_CATALOG_URI", raising=False)
    from .conftest import CONTRACT_RAW, make_product
    con.execute("""CREATE TABLE silver_test AS
        SELECT make_date(2024, 1, 1) AS date, 1.0 AS value""")
    pdir = tmp_path / "products" / "test-product"
    pdir.mkdir(parents=True)
    product = make_product(pdir, raw={"id": "test-product"}, contracts=[CONTRACT_RAW])
    warehouse.publish_product(con, product)

    s = catalog.status()
    assert s["kind"] == "local-sql"
    assert s["tables"]["carina.test_product.silver"] == ["silver_test"]
