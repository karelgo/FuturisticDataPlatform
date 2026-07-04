"""Paths and product discovery."""

from __future__ import annotations

import os
from pathlib import Path

# Repo root = three levels up from this file (src/carina/config.py)
ROOT = Path(os.environ.get("CARINA_ROOT", Path(__file__).resolve().parents[2]))

DATA_DIR = ROOT / "data"
BRONZE_DIR = DATA_DIR / "bronze"
DB_PATH = DATA_DIR / "lakehouse.duckdb"
PRODUCTS_DIR = ROOT / "products"
UI_DIR = Path(__file__).resolve().parent / "ui"


def ensure_dirs() -> None:
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)


def product_dirs() -> list[Path]:
    if not PRODUCTS_DIR.exists():
        return []
    return sorted(p for p in PRODUCTS_DIR.iterdir() if (p / "product.yaml").exists())
