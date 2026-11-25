"""Precomputed dashboard snapshot generation."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from math import isfinite
from typing import Any

from .config import DASHBOARD_GROUP_ORDER, TRACKED_ETFS
from .storage import get_premium_history

RANGES = {
    "3m": 3,
    "6m": 6,
    "1y": 12,
}

STATUS_LOW = 1
STATUS_BELOW_NORMAL = 2
STATUS_NORMAL = 3
STATUS_ABOVE_NORMAL = 4
STATUS_EXTREME = 5


def _beijing_now() -> str:
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).isoformat()


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and isfinite(value)


def _premium_record(record: dict) -> dict | None:
    if not record.get("date"):
        return None

    close = record.get("close")
    nav = record.get("nav")
    iopv = record.get("iopv")
    premium_rate = record.get("premium_rate")
    if not (
        _finite_number(close)
        and _finite_number(iopv if iopv is not None else nav)
        and _finite_number(premium_rate)
    ):
        return None

    return {
        "date": record["date"],
        "close": float(close),
        "nav": float(nav) if nav is not None else None,
        "iopv": float(iopv) if iopv is not None else None,
        "nav_date": record["nav_date"],
        "premium_basis": record["premium_basis"],
        "premium_rate": float(premium_rate),
    }


def normalize_records(records: list[dict]) -> list[dict]:
    """Return valid premium records sorted by date."""
    valid = [
        normalized
        for record in records
        if (normalized := _premium_record(record)) is not None
    ]
    valid.sort(key=lambda record: record["date"])
    return valid


def _shift_month(date_str: str, months: int) -> str:
    source = date.fromisoformat(date_str)
    month_index = source.year * 12 + source.month - 1 + months
    target_year = month_index // 12
    target_month = month_index % 12 + 1
    target_day = min(source.day, monthrange(target_year, target_month)[1])
    return date(target_year, target_month, target_day).isoformat()


def filter_by_range(records: list[dict], range_key: str) -> list[dict]:
    """Filter records to the requested trailing month range."""
    sorted_records = normalize_records(records)
    if not sorted_records:
        return sorted_records

    latest_date = sorted_records[-1]["date"]
    cutoff = _shift_month(latest_date, -RANGES[range_key])
    return [
        record
        for record in sorted_records
        if record["date"] >= cutoff
    ]


def percentile_rank(current: float, values: list[float]) -> float:
    """Return the share of values below or equal to the current value."""
    clean = [value for value in values if _finite_number(value)]
    if not clean:
        return 0.5

    count_below_or_equal = sum(1 for value in clean if value <= current)
    return max(0, min(1, count_below_or_equal / len(clean)))


def determine_premium_status(percentile: float) -> int:
    """Map percentile to the frontend premium status enum value."""
    if percentile >= 0.9:
        return STATUS_EXTREME
    if percentile >= 0.7:
        return STATUS_ABOVE_NORMAL
    if percentile >= 0.3:
        return STATUS_NORMAL
    if percentile >= 0.1:
        return STATUS_BELOW_NORMAL
    return STATUS_LOW


def _dashboard_latest(record: dict | None) -> dict | None:
    if not record:
        return None
    return {
        "date": record["date"],
        "premium_rate": record["premium_rate"],
    }


def summarize_premium(records: list[dict], range_key: str) -> dict:
    """Summarize one ETF premium history for one dashboard range."""
    filtered = filter_by_range(records, range_key)
    values = [record["premium_rate"] for record in filtered]
    latest = filtered[-1] if filtered else None

    if not latest or not values:
        return {
            "latest": None,
            "percentile": 0.5,
            "status": STATUS_NORMAL,
        }

    percentile = percentile_rank(latest["premium_rate"], values)
    return {
        "latest": _dashboard_latest(latest),
        "percentile": percentile,
        "status": determine_premium_status(percentile),
    }


def _group_ranges(items: list[dict]) -> dict[str, dict]:
    ranges: dict[str, dict] = {}
    for range_key in RANGES:
        latest_rates = [
            item["stats"][range_key]["latest"]["premium_rate"]
            for item in items
            if item["stats"][range_key]["latest"]
        ]
        ranges[range_key] = {
            "min_premium": min(latest_rates) if latest_rates else None,
            "max_premium": max(latest_rates) if latest_rates else None,
        }
    return ranges


def _ordered_group_keys(group_order: list[str]) -> list[str]:
    configured = [
        key
        for key in DASHBOARD_GROUP_ORDER
        if key in group_order
    ]
    configured_set = set(configured)
    return configured + [
        key
        for key in group_order
        if key not in configured_set
    ]


def build_dashboard_snapshot() -> dict:
    """Build the full dashboard payload from stored premium history."""
    items = []
    groups_by_key: dict[str, dict] = {}
    group_order: list[str] = []

    for config in TRACKED_ETFS.values():
        records = normalize_records(get_premium_history(config.code))
        stats = {
            range_key: summarize_premium(records, range_key)
            for range_key in RANGES
        }
        item = {
            "code": config.code,
            "name": config.name,
            "short_name": config.short_name,
            "fund_type": config.fund_type,
            "stats": stats,
        }
        items.append(item)

        group = groups_by_key.get(config.tracking_index)
        if not group:
            group = {
                "tracking_index": config.tracking_index,
                "tracking_index_name": config.tracking_index_name,
                "members": [],
                "ranges": {},
            }
            groups_by_key[config.tracking_index] = group
            group_order.append(config.tracking_index)
        group["members"].append(config.code)

    items_by_code = {
        item["code"]: item
        for item in items
    }
    for group in groups_by_key.values():
        group_items = [
            items_by_code[code]
            for code in group["members"]
            if code in items_by_code
        ]
        group["ranges"] = _group_ranges(group_items)

    return {
        "generated_at_bj": _beijing_now(),
        "items": items,
        "groups": [
            groups_by_key[key]
            for key in _ordered_group_keys(group_order)
        ],
    }
