from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from mumzcare import data_loader
from mumzcare.rag import retrieve_policy
from mumzcare.schemas import Citation


ORDER_RE = re.compile(r"\bMW-\d{4}\b", re.IGNORECASE)
NOW = datetime(2026, 4, 27, 21, 15, tzinfo=ZoneInfo("Asia/Dubai"))


def parse_order_id(message: str) -> str | None:
    match = ORDER_RE.search(message)
    return match.group(0).upper() if match else None


def get_order(order_id: str) -> dict[str, Any] | None:
    return data_loader.orders().get(order_id)


def get_tracking(order_id: str) -> dict[str, Any] | None:
    return data_loader.tracking().get(order_id)


def get_return(order_id: str) -> dict[str, Any] | None:
    return data_loader.returns().get(order_id)


def get_product(sku: str) -> dict[str, Any] | None:
    return data_loader.products().get(sku)


def search_policy(query: str) -> list[Citation]:
    return retrieve_policy(query)


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)
