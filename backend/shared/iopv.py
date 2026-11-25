"""Collect post-close IOPV quotes with Tencent-first provider failover."""

from dataclasses import dataclass
from datetime import datetime, time as daytime, timedelta, timezone
import json
import logging
import math
import re
import time
from urllib.request import Request, urlopen

from .config import TRACKED_ETFS
from .storage import upsert_iopv_history

CHINA = timezone(timedelta(hours=8))
MAX_ATTEMPTS = 6
RETRY_DELAY_SECONDS = 10
HTTP_TIMEOUT_SECONDS = 10
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Quote:
    code: str
    close: float
    iopv: float
    quote_at_bj: datetime
    fetched_at_bj: datetime
    source: str

    def record(self) -> dict:
        return {"code": self.code, "date": self.quote_at_bj.date().isoformat(),
                "close": self.close, "iopv": self.iopv, "source": self.source,
                "quote_at_bj": self.quote_at_bj.isoformat(),
                "fetched_at_bj": self.fetched_at_bj.isoformat()}


def _positive(value) -> float:
    if isinstance(value, bool):
        raise ValueError("Boolean quote value")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Quote value must be positive and finite")
    return value


def parse_tencent(raw: bytes, fetched_at: datetime) -> dict[str, Quote]:
    quotes = {}
    for symbol, body in re.findall(r'v_(\w+)="([^"]*)"', raw.decode("gb18030")):
        try:
            fields = body.split("~")
            code = fields[2]
            config = TRACKED_ETFS.get(code)
            if config is None or symbol != config.market + code:
                continue
            quote_at = datetime.strptime(fields[30], "%Y%m%d%H%M%S").replace(tzinfo=CHINA)
            quotes[code] = Quote(code, _positive(fields[3]), _positive(fields[78]),
                                 quote_at, fetched_at, "tencent")
        except (ValueError, TypeError, IndexError):
            continue
    return quotes


def parse_eastmoney(raw: bytes, fetched_at: datetime) -> dict[str, Quote]:
    payload = json.loads(raw)
    quotes = {}
    for row in (payload.get("data") or {}).get("diff") or []:
        try:
            code = row["f12"]
            config = TRACKED_ETFS.get(code)
            if config is None or str(row["f13"]) != config.eastmoney_secid[0]:
                continue
            quote_at = datetime.fromtimestamp(float(row["f124"]), CHINA)
            if str(row["f297"]) != quote_at.strftime("%Y%m%d"):
                continue
            quotes[code] = Quote(code, _positive(row["f2"]), _positive(row["f441"]),
                                 quote_at, fetched_at, "eastmoney")
        except (KeyError, ValueError, TypeError, OverflowError, OSError):
            continue
    return quotes


def fetch_quotes(source: str, codes: list[str]) -> dict[str, Quote]:
    if source == "tencent":
        symbols = ",".join(TRACKED_ETFS[code].market + code for code in codes)
        url = "https://qt.gtimg.cn/q=" + symbols
        parser = parse_tencent
    elif source == "eastmoney":
        secids = ",".join(TRACKED_ETFS[code].eastmoney_secid for code in codes)
        url = ("https://push2.eastmoney.com/api/qt/ulist.np/get?secids=" + secids
               + "&fields=f12,f13,f14,f2,f124,f297,f441&fltt=2")
        parser = parse_eastmoney
    else:
        raise ValueError(f"Unknown provider: {source}")
    request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"})
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        raw = response.read()
    return parser(raw, datetime.now(CHINA))


def collect_quotes(now: datetime | None = None, *, codes: list[str] | None = None) -> dict:
    """Retry only unresolved funds, then fall back to Eastmoney in one batch."""
    now = now or datetime.now(CHINA)
    now = now.astimezone(CHINA)
    target_date = now.date()
    result = {"date": target_date.isoformat(), "quotes": [], "failed": [], "errors": [], "attempts": {}}
    if now.weekday() >= 5 or now.time() < daytime(15, 30):
        result["skipped"] = "Weekend or before the first post-close collection time"
        return result
    pending = list(TRACKED_ETFS) if codes is None else list(dict.fromkeys(codes))
    if any(code not in TRACKED_ETFS for code in pending):
        raise ValueError("Unknown fund code in IOPV collection")
    accepted = {}
    for source in ("tencent", "eastmoney"):
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if not pending:
                break
            if attempt > 1:
                time.sleep(RETRY_DELAY_SECONDS)
            result["attempts"][source] = attempt
            try:
                quotes = fetch_quotes(source, pending)
                for code in pending:
                    quote = quotes.get(code)
                    if (quote and quote.quote_at_bj.date() == target_date
                            and quote.fetched_at_bj.date() == target_date
                            and quote.quote_at_bj.time() >= daytime(15)
                            and quote.quote_at_bj <= quote.fetched_at_bj
                            and math.isfinite(quote.close) and quote.close > 0
                            and math.isfinite(quote.iopv) and quote.iopv > 0):
                        accepted[code] = quote.record()
                pending = [code for code in pending if code not in accepted]
                if pending:
                    logger.warning("%s attempt %d: missing valid current-day quotes for %s", source, attempt, pending)
            except Exception as exc:
                message = f"{source} attempt {attempt}: {type(exc).__name__}: {exc}"
                logger.warning(message)
                result["errors"].append(message)
    result["quotes"] = list(accepted.values())
    result["failed"] = pending
    return result


def refresh_iopv(*, dry_run: bool = False, codes: list[str] | None = None) -> dict:
    result = collect_quotes(codes=codes)
    if not dry_run:
        result["written"] = upsert_iopv_history(result["quotes"])
        if result["written"]:
            from .dashboard import build_dashboard_snapshot
            from .storage import upsert_dashboard_snapshot
            upsert_dashboard_snapshot(build_dashboard_snapshot())
    return result
