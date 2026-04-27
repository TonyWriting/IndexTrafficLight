"""End-to-end ETF premium refresh pipeline."""

from dataclasses import dataclass

from .config import EtfConfig
from .data_fetcher import (
    fetch_etf_nav_history,
    fetch_etf_price_history,
    merge_premium_records,
)
from .storage import (
    upsert_nav_history,
    upsert_premium_history,
    upsert_price_history,
)


@dataclass(frozen=True)
class RefreshResult:
    """Summary of one ETF refresh run."""

    price_fetched: int
    nav_fetched: int
    premium_computed: int
    price_written: int
    nav_written: int
    premium_written: int
    premium_records: list[dict]


def _within_range(record: dict, start_date: str = "", end_date: str = "") -> bool:
    record_date = record["date"]
    if start_date and record_date < start_date:
        return False
    if end_date and record_date > end_date:
        return False
    return True


def _date_range(records: list[dict]) -> str:
    if not records:
        return "-"
    return f"{records[0]['date']} ~ {records[-1]['date']}"


def refresh_etf_premium(
    config: EtfConfig,
    start_date: str = "",
    end_date: str = "",
) -> RefreshResult:
    """Fetch raw data, calculate premiums, and write all three tables."""
    print(f"Fetching price history for {config.code}...", flush=True)
    price_records = fetch_etf_price_history(config, start_date, end_date)
    print(
        f"  price fetched: {len(price_records)} ({_date_range(price_records)})",
        flush=True,
    )

    print(f"Fetching NAV history for {config.code}...", flush=True)
    nav_records_all = fetch_etf_nav_history(config)
    nav_records_to_write = [
        record
        for record in nav_records_all
        if _within_range(record, start_date, end_date)
    ]
    print(
        "  nav fetched: "
        f"{len(nav_records_to_write)} ({_date_range(nav_records_to_write)})",
        flush=True,
    )

    premium_records = merge_premium_records(price_records, nav_records_all)
    print(
        "  premium computed: "
        f"{len(premium_records)} ({_date_range(premium_records)})",
        flush=True,
    )

    price_written = upsert_price_history(config.code, price_records)
    nav_written = upsert_nav_history(config.code, nav_records_to_write)
    premium_written = upsert_premium_history(config.code, premium_records)

    return RefreshResult(
        price_fetched=len(price_records),
        nav_fetched=len(nav_records_to_write),
        premium_computed=len(premium_records),
        price_written=price_written,
        nav_written=nav_written,
        premium_written=premium_written,
        premium_records=premium_records,
    )
