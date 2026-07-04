"""The catalog seam (ADR-0002): where Lakekeeper attaches.

`carina catalog status` reports the control point's state: the Iceberg REST
catalog (Lakekeeper) when CARINA_CATALOG_URI is set — reachability, prefix,
namespaces, tables — or the local SQL catalog in the warehouse directory
otherwise. Either way, the answer comes from the catalog itself, not from
what the platform remembers publishing.
"""

from __future__ import annotations

import urllib.parse

import httpx

from . import warehouse

NS_SEPARATOR = "\x1f"  # multipart namespaces are 0x1F-joined per the Iceberg REST spec


class RestCatalogClient:
    """Minimal Iceberg REST Catalog client — enough for status reporting.

    Data-path operations (create/load/commit tables) go through pyiceberg's
    RestCatalog; this client exists so status checks need no optional deps.
    """

    def __init__(self, uri: str, token: str | None = None, transport=None):
        self.base = uri.rstrip("/")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._client = httpx.Client(headers=headers, timeout=10.0, transport=transport)

    def config(self) -> dict:
        r = self._client.get(f"{self.base}/v1/config")
        r.raise_for_status()
        return r.json()

    def prefix(self) -> str:
        cfg = self.config()
        merged = {**cfg.get("defaults", {}), **cfg.get("overrides", {})}
        return merged.get("prefix", "")

    def _path(self, prefix: str, rest: str) -> str:
        p = f"/{urllib.parse.quote(prefix, safe='')}" if prefix else ""
        return f"{self.base}/v1{p}/{rest}"

    def namespaces(self, prefix: str = "") -> list[list[str]]:
        r = self._client.get(self._path(prefix, "namespaces"))
        r.raise_for_status()
        return r.json().get("namespaces", [])

    def tables(self, namespace: list[str], prefix: str = "") -> list[str]:
        ns = urllib.parse.quote(NS_SEPARATOR.join(namespace), safe="")
        r = self._client.get(self._path(prefix, f"namespaces/{ns}/tables"))
        r.raise_for_status()
        return [i["name"] for i in r.json().get("identifiers", [])]


def status() -> dict:
    """Catalog state, asked of the catalog itself."""
    uri = warehouse.catalog_uri()
    if uri:
        client = RestCatalogClient(uri)
        try:
            prefix = client.prefix()
            namespaces = client.namespaces(prefix)
            tables = {
                ".".join(ns): client.tables(ns, prefix) for ns in namespaces[:20]
            }
            return {"configured": True, "kind": "iceberg-rest", "uri": uri,
                    "reachable": True, "prefix": prefix,
                    "namespaces": namespaces, "tables": tables}
        except Exception as e:
            return {"configured": True, "kind": "iceberg-rest", "uri": uri,
                    "reachable": False, "error": f"{type(e).__name__}: {e}"}

    local_db = warehouse.warehouse_root() / "catalog.db"
    if warehouse.iceberg_available() and local_db.exists():
        cat = warehouse.load_iceberg_catalog()
        tables: dict[str, list[str]] = {}

        def walk(ns: tuple):
            found = [t[-1] for t in cat.list_tables(ns)]
            if found:
                tables[".".join(ns)] = sorted(found)
            for child in cat.list_namespaces(ns):
                walk(tuple(child))

        for top in cat.list_namespaces():
            walk(tuple(top))
        return {"configured": False, "kind": "local-sql", "uri": f"sqlite:///{local_db}",
                "reachable": True, "namespaces": sorted(tables), "tables": tables}

    return {"configured": False, "kind": "none", "reachable": False,
            "hint": "publish with `carina publish`, or set CARINA_CATALOG_URI "
                    "to attach Lakekeeper"}
