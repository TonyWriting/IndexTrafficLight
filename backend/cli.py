"""CLI tool for QDII ETF premium data management."""

import argparse
import json
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from shared.config import TRACKED_ETFS, EtfConfig
from shared.dashboard import build_dashboard_snapshot
from shared.pipeline import RefreshResult, refresh_etf_premium
from shared.storage import get_premium_history, upsert_dashboard_snapshot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)
logger = logging.getLogger(__name__)

DEFAULT_QUERY_LIMIT = 10
LOCAL_SETTINGS_PATH = Path(__file__).with_name("local.settings.json")


def _load_local_settings() -> None:
    """Load Azure Functions local settings for CLI runs."""
    if not LOCAL_SETTINGS_PATH.exists():
        return

    settings = json.loads(LOCAL_SETTINGS_PATH.read_text(encoding="utf-8-sig"))
    values = settings.get("Values", {})
    if not isinstance(values, dict):
        return

    for key, value in values.items():
        if isinstance(value, str) and key not in os.environ:
            os.environ[key] = value


def _safe_print(message: str) -> None:
    """Print progress without failing on legacy Windows encodings."""
    try:
        print(message, flush=True)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        safe_message = message.encode(
            encoding,
            errors="replace",
        ).decode(
            encoding,
            errors="replace",
        )
        print(safe_message, flush=True)


def _selected_configs(code: str = "") -> list[EtfConfig]:
    if code:
        config = TRACKED_ETFS.get(code)
        if not config:
            raise ValueError(
                f"Unknown fund code: {code}. Valid: {', '.join(TRACKED_ETFS)}"
            )
        return [config]
    return list(TRACKED_ETFS.values())


def _print_refresh_result(config: EtfConfig, result: RefreshResult) -> None:
    print(f"\n[{config.name}] refresh complete")
    print(f"  price:   fetched={result.price_fetched}, written={result.price_written}")
    print(f"  nav:     fetched={result.nav_fetched}, written={result.nav_written}")
    print(
        "  premium: "
        f"computed={result.premium_computed}, written={result.premium_written}"
    )

    if not result.premium_records:
        print("  no same-date close+NAV records were available")
        return

    print("  latest premium records:")
    for record in result.premium_records[-DEFAULT_QUERY_LIMIT:]:
        premium_pct = record["premium_rate"] * 100
        print(
            "   "
            f" {record['date']} close={record['close']:.3f} "
            f"nav={record['nav']:.4f} premium={premium_pct:.2f}%"
        )


def cmd_backfill(args: argparse.Namespace) -> None:
    """Fetch and store all available history."""
    for config in _selected_configs(args.code):
        logger.info("Backfilling all available history for %s", config.name)
        result = refresh_etf_premium(
            config,
            start_date=args.start,
            end_date=args.end,
        )
        _print_refresh_result(config, result)


def cmd_refresh(args: argparse.Namespace) -> None:
    """Refresh recent records to handle delayed QDII NAV disclosure."""
    end = date.fromisoformat(args.end)
    start = end - timedelta(days=args.days)

    for config in _selected_configs(args.code):
        logger.info(
            "Refreshing %s for %s ~ %s",
            config.name,
            start.isoformat(),
            end.isoformat(),
        )
        result = refresh_etf_premium(
            config,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )
        _print_refresh_result(config, result)


def cmd_query(args: argparse.Namespace) -> None:
    """Read calculated premium records from Azure Table Storage."""
    config = TRACKED_ETFS.get(args.code)
    if not config:
        raise ValueError(
            f"Unknown fund code: {args.code}. Valid: {', '.join(TRACKED_ETFS)}"
        )

    end = date.fromisoformat(args.end)
    start = end - timedelta(days=args.days)
    records = get_premium_history(
        args.code,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
    )

    if args.limit > 0:
        records = records[-args.limit:]

    print(f"\n[{config.name}] {len(records)} premium records")
    print(f"{'date':<12} {'close':>10} {'nav':>10} {'premium':>10}")
    print("-" * 46)

    for record in records:
        premium_pct = record["premium_rate"] * 100
        print(
            f"{record['date']:<12} "
            f"{record['close']:>10.3f} "
            f"{record['nav']:>10.4f} "
            f"{premium_pct:>9.2f}%"
        )


def cmd_dashboard(args: argparse.Namespace) -> None:
    """Build and store the latest dashboard snapshot."""
    def print_progress(code: str, name: str) -> None:
        _safe_print(f"  processing {code} {name}")

    print("\n[dashboard] building snapshot")
    snapshot = upsert_dashboard_snapshot(
        build_dashboard_snapshot(on_etf_start=print_progress)
    )
    print("\n[dashboard] snapshot complete")
    print(f"  generated_at_bj={snapshot['generated_at_bj']}")
    print(f"  items={len(snapshot['items'])}")
    print(f"  groups={len(snapshot['groups'])}")


def main() -> None:
    _load_local_settings()

    parser = argparse.ArgumentParser(
        description="Index Traffic Light backend ETF premium CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_backfill = subparsers.add_parser(
        "backfill",
        help="Fetch and store all available ETF price, NAV, and premium history",
    )
    p_backfill.add_argument("--code", default="", help="Fund code, default: all")
    p_backfill.add_argument(
        "--start",
        default="",
        help="Optional start date YYYY-MM-DD; default: source earliest",
    )
    p_backfill.add_argument(
        "--end",
        default="",
        help="Optional end date YYYY-MM-DD; default: today",
    )
    p_backfill.set_defaults(func=cmd_backfill)

    p_refresh = subparsers.add_parser(
        "refresh",
        help="Refresh recent ETF data to fill delayed QDII NAV",
    )
    p_refresh.add_argument("--code", default="", help="Fund code, default: all")
    p_refresh.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of natural days to refresh, default: 7",
    )
    p_refresh.add_argument(
        "--end",
        default=date.today().isoformat(),
        help="End date YYYY-MM-DD, default: today",
    )
    p_refresh.set_defaults(func=cmd_refresh)

    p_query = subparsers.add_parser(
        "query",
        help="Read calculated ETF premium history",
    )
    p_query.add_argument("code", help="Fund code, e.g. 159509")
    p_query.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of natural days to query, default: 30",
    )
    p_query.add_argument(
        "--end",
        default=date.today().isoformat(),
        help="End date YYYY-MM-DD, default: today",
    )
    p_query.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_QUERY_LIMIT,
        help="Maximum rows to print, default: 10; use 0 for all",
    )
    p_query.set_defaults(func=cmd_query)

    p_dashboard = subparsers.add_parser(
        "dashboard",
        help="Build and store the latest precomputed dashboard snapshot",
    )
    p_dashboard.set_defaults(func=cmd_dashboard)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
