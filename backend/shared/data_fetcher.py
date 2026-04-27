"""Data fetching and premium calculation for QDII ETFs."""

import json
import logging
import time
from datetime import date
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from .config import EtfConfig

logger = logging.getLogger(__name__)

PRICE_SOURCE = "eastmoney_etf_daily_k"
PRICE_FALLBACK_SOURCE = "tencent_etf_daily_k_bfq"
NAV_SOURCE = "eastmoney_fund_nav"
_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _akshare():
    import akshare as ak

    return ak


def _pandas():
    import pandas as pd

    return pd


def _format_akshare_date(value: str | date | None, default: str) -> str:
    """Convert optional ISO/AKShare date values to YYYYMMDD."""
    if not value:
        return default
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    return str(value).replace("-", "")


def _format_iso_date(value: str | date | None, default: str = "") -> str:
    """Convert optional YYYYMMDD/ISO date values to YYYY-MM-DD."""
    if not value:
        return default
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    if "-" in text:
        return text
    return f"{text[:4]}-{text[4:6]}-{text[6:8]}"


def _to_date_str(value: Any) -> str:
    """Normalize pandas/AKShare date values to YYYY-MM-DD."""
    return _pandas().to_datetime(value).strftime("%Y-%m-%d")


def _float_or_none(value: Any) -> float | None:
    if _pandas().isna(value):
        return None
    return float(value)


def _get_json(url: str, referer: str, retries: int = 3) -> dict:
    headers = {**_HTTP_HEADERS, "Referer": referer}
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=30) as response:
                text = response.read().decode("utf-8", errors="replace")
            return json.loads(text)
        except Exception as exc:
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch JSON from {url}") from last_error


def _records_from_akshare_price_df(df: Any) -> list[dict]:
    records = []
    for _, row in df.iterrows():
        close = _float_or_none(row.get("收盘"))
        if close is None:
            continue
        records.append({
            "date": _to_date_str(row["日期"]),
            "open": _float_or_none(row.get("开盘")),
            "close": close,
            "high": _float_or_none(row.get("最高")),
            "low": _float_or_none(row.get("最低")),
            "volume": (
                int(row["成交量"])
                if _pandas().notna(row.get("成交量"))
                else None
            ),
            "amount": _float_or_none(row.get("成交额")),
            "adjust": "none",
            "source": PRICE_SOURCE,
        })

    records.sort(key=lambda r: r["date"])
    return records


def _fetch_tencent_price_history(
    config: EtfConfig,
    start_date: str = "",
    end_date: str = "",
) -> list[dict]:
    """Fetch unadjusted daily K lines from Tencent as a fallback source."""
    market_code = f"{config.market}{config.code}"
    param = quote(f"{market_code},day,,,2000,bfq", safe=",")
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={param}"
    referer = f"https://gu.qq.com/{market_code}/gp"
    payload = _get_json(url, referer=referer)

    if payload.get("code") != 0:
        logger.warning(
            "Tencent fallback returned code=%s msg=%s for %s",
            payload.get("code"),
            payload.get("msg"),
            config.code,
        )
        return []

    rows = ((payload.get("data") or {}).get(market_code) or {}).get("day") or []
    start_iso = _format_iso_date(start_date)
    end_iso = _format_iso_date(end_date)

    records = []
    for row in rows:
        if len(row) < 6:
            continue
        row_date = row[0]
        if start_iso and row_date < start_iso:
            continue
        if end_iso and row_date > end_iso:
            continue

        records.append({
            "date": row_date,
            "open": float(row[1]),
            "close": float(row[2]),
            "high": float(row[3]),
            "low": float(row[4]),
            "volume": int(float(row[5])),
            "amount": None,
            "adjust": "none",
            "source": PRICE_FALLBACK_SOURCE,
        })

    records.sort(key=lambda r: r["date"])
    return records


def fetch_etf_price_history(
    config: EtfConfig,
    start_date: str = "",
    end_date: str = "",
) -> list[dict]:
    """Fetch unadjusted daily exchange-traded ETF price history.

    Args:
        config: ETF configuration.
        start_date: Optional inclusive date, YYYY-MM-DD or YYYYMMDD.
        end_date: Optional inclusive date, YYYY-MM-DD or YYYYMMDD.

    Returns:
        Records sorted by date ascending. Each record contains date, open,
        close, high, low, volume, amount, adjust, and source.
    """
    start = _format_akshare_date(start_date, "19700101")
    end = _format_akshare_date(end_date, date.today().strftime("%Y%m%d"))

    try:
        df = _akshare().fund_etf_hist_em(
            symbol=config.code,
            period="daily",
            start_date=start,
            end_date=end,
            adjust="",
        )
    except Exception:
        logger.warning(
            "AKShare price fetch failed for %s; falling back to Tencent bfq",
            config.code,
        )
    else:
        if not df.empty:
            records = _records_from_akshare_price_df(df)
            if records:
                return records

        logger.warning(
            "AKShare price fetch returned no records for %s; falling back to Tencent bfq",
            config.code,
        )

    try:
        return _fetch_tencent_price_history(config, start_date, end_date)
    except Exception:
        logger.exception("Failed to fetch fallback ETF price history for %s", config.code)
        return []


def fetch_etf_nav_history(config: EtfConfig) -> list[dict]:
    """Fetch ETF unit NAV history from Eastmoney/Tiantian Fund via AKShare."""
    try:
        df = _akshare().fund_open_fund_info_em(
            symbol=config.code,
            indicator="单位净值走势",
        )
    except Exception:
        logger.exception("Failed to fetch ETF NAV history for %s", config.code)
        return []

    if df.empty:
        return []

    records = []
    for _, row in df.iterrows():
        nav = _float_or_none(row.get("单位净值"))
        if nav is None:
            continue
        records.append({
            "date": _to_date_str(row["净值日期"]),
            "nav": nav,
            "daily_return_pct": _float_or_none(row.get("日增长率")),
            "source": NAV_SOURCE,
        })

    records.sort(key=lambda r: r["date"])
    return records


def merge_premium_records(
    price_records: list[dict],
    nav_records: list[dict],
) -> list[dict]:
    """Join price and NAV records by date and calculate close premium."""
    nav_by_date = {record["date"]: record for record in nav_records}
    premium_records = []

    for price in price_records:
        nav = nav_by_date.get(price["date"])
        if not nav:
            continue
        nav_value = nav["nav"]
        close = price["close"]
        premium_records.append({
            "date": price["date"],
            "close": close,
            "nav": nav_value,
            "premium_rate": close / nav_value - 1,
        })

    premium_records.sort(key=lambda r: r["date"])
    return premium_records
