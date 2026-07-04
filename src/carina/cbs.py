"""CBS StatLine OData v3 client (opendata.cbs.nl)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

TIMEOUT = httpx.Timeout(60.0, connect=20.0)


def _get_json(client: httpx.Client, url: str) -> dict:
    resp = client.get(url)
    resp.raise_for_status()
    return resp.json()


def fetch_table_info(client: httpx.Client, base_url: str) -> dict:
    data = _get_json(client, f"{base_url}/TableInfos?$format=json")
    return data["value"][0] if data.get("value") else {}


def fetch_codelist(client: httpx.Client, base_url: str, dimension: str) -> list[dict]:
    data = _get_json(client, f"{base_url}/{dimension}?$format=json")
    return data["value"]


def fetch_typed_dataset(client: httpx.Client, base_url: str, odata_filter: str | None) -> tuple[list[dict], list[str]]:
    """Fetch all rows of TypedDataSet, following pagination. Returns (rows, urls)."""
    url = f"{base_url}/TypedDataSet?$format=json"
    if odata_filter:
        url += "&$filter=" + httpx.QueryParams({"f": odata_filter})["f"].replace("+", "%20")
    rows: list[dict] = []
    urls: list[str] = []
    while url:
        urls.append(url)
        data = _get_json(client, url)
        rows.extend(data.get("value", []))
        url = data.get("odata.nextLink")
        if url and "$format" not in url:
            url += "&$format=json"
    return rows, urls


def write_json(path: Path, obj) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False)
    path.write_text(text)
    return len(text.encode("utf-8"))


def make_client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, headers={"User-Agent": "carina-reference/0.1"}, follow_redirects=True)
