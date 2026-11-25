"""CLI for importing and inspecting NAV-proxy premium history."""

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import sys

from shared.config import TRACKED_ETFS
from shared.dashboard import build_dashboard_snapshot
from shared.excel_import import read_workbook, import_fund, verify_workbook
from shared.iopv import refresh_iopv
from shared.storage import get_premium_history, reset_history, upsert_dashboard_snapshot

ROOT = Path(__file__).resolve().parent
logging.getLogger("azure").setLevel(logging.WARNING)


def _load_local_settings() -> None:
    path = ROOT / "local.settings.json"
    if path.exists():
        values = json.loads(path.read_text(encoding="utf-8-sig")).get("Values", {})
        for key, value in values.items():
            if isinstance(value, str):
                os.environ.setdefault(key, value)


def _report(command: str, result: dict) -> None:
    now = datetime.now(timezone(timedelta(hours=8)))
    report = {"command": command, "completed_at_bj": now.isoformat(), **result}
    directory = ROOT / "reports"
    directory.mkdir(exist_ok=True)
    path = directory / f"{now:%Y%m%d-%H%M%S-%f}-{command}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Report: {path}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    _load_local_settings()
    parser = argparse.ArgumentParser(description="NAV-proxy premium history management")
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser("import-excel", help="Import a validated workbook, one fund at a time")
    importer.add_argument("--file", required=True)
    selection = importer.add_mutually_exclusive_group(required=True)
    selection.add_argument("--code", choices=list(TRACKED_ETFS))
    selection.add_argument("--all", action="store_true")
    importer.add_argument("--dry-run", action="store_true")
    verifier = commands.add_parser("verify-excel", help="Compare all three history tables with Excel")
    verifier.add_argument("--file", required=True)
    commands.add_parser("reset-history", help="Delete all entities in the four business tables WITHOUT backup")
    commands.add_parser("dashboard", help="Rebuild the homepage snapshot from stored history")
    collector = commands.add_parser("collect-iopv", help="Collect today's post-close IOPV quotes")
    collector.add_argument("--dry-run", action="store_true")
    collector.add_argument("--code", nargs="+", choices=list(TRACKED_ETFS), help="Collect only these funds")
    query = commands.add_parser("query", help="Print stored premium records")
    query.add_argument("code", choices=list(TRACKED_ETFS))
    query.add_argument("--days", type=int, default=30)
    query.add_argument("--end", default=date.today().isoformat())
    query.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if args.command in {"import-excel", "verify-excel"}:
        data = read_workbook(args.file)
        if args.command == "import-excel" and args.code and args.code not in data.funds:
            parser.error(f"Fund {args.code} is not included in the workbook")
        result = data.summary()
        if args.command == "verify-excel":
            result["verified"] = verify_workbook(data)
        elif args.dry_run:
            result["dry_run"] = True
        else:
            codes = [args.code] if args.code else list(data.funds)
            result["imported"] = [import_fund(data, code) for code in codes]
        _report(args.command, result)
    elif args.command == "reset-history":
        _report(args.command, {"deleted": reset_history()})
    elif args.command == "collect-iopv":
        result = refresh_iopv(dry_run=args.dry_run, codes=args.code)
        _report(args.command, result)
        if result["failed"]:
            raise SystemExit(1)
    elif args.command == "dashboard":
        snapshot = upsert_dashboard_snapshot(build_dashboard_snapshot())
        _report(args.command, {"items": len(snapshot["items"]), "groups": len(snapshot["groups"]),
                              "generated_at_bj": snapshot["generated_at_bj"]})
    elif args.command == "query":
        start = (date.fromisoformat(args.end) - timedelta(days=args.days)).isoformat()
        records = get_premium_history(args.code, start, args.end)
        print(json.dumps(records[-args.limit:] if args.limit > 0 else records, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
