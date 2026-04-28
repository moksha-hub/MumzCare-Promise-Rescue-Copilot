from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def load_json(name: str) -> list[dict[str, Any]]:
    path = DATA_DIR / name
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


@lru_cache(maxsize=1)
def orders() -> dict[str, dict[str, Any]]:
    return {row["order_id"]: row for row in load_json("orders.json")}


@lru_cache(maxsize=1)
def tracking() -> dict[str, dict[str, Any]]:
    return {row["order_id"]: row for row in load_json("tracking_events.json")}


@lru_cache(maxsize=1)
def returns() -> dict[str, dict[str, Any]]:
    return {row["order_id"]: row for row in load_json("returns.json")}


@lru_cache(maxsize=1)
def products() -> dict[str, dict[str, Any]]:
    return {row["sku"]: row for row in load_json("products.json")}


def policy_text() -> str:
    return (DATA_DIR / "policy_docs.md").read_text(encoding="utf-8")
