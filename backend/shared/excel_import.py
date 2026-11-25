"""Validate and import NAV-proxy workbooks without fetching market data."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import hashlib
import re

import openpyxl

from .config import TRACKED_ETFS
from .storage import (
    HISTORY_TABLES, TABLE_PRICE_HISTORY, TABLE_NAV_HISTORY, TABLE_PREMIUM_HISTORY,
    read_entities, upsert_price_history, upsert_nav_history, upsert_premium_history,
)

HEADERS = ["日期", "当天收盘价", "净值模拟的IOPV", "溢价率"]
PREMIUM_BASIS = "nav_proxy_iopv"
SOURCE = "excel_nav_proxy_import"
TOLERANCE = Decimal("1e-12")


@dataclass
class WorkbookData:
    file: str
    sha256: str
    funds: dict[str, list[dict]]
    skipped: dict[str, list[str]]

    def summary(self) -> dict:
        return {
            "file": self.file, "sha256": self.sha256,
            "funds": [{"code": code, "count": len(rows), "skipped": len(self.skipped[code]),
                       "start": rows[0]["date"], "end": rows[-1]["date"]}
                      for code, rows in self.funds.items()],
            "total": sum(len(rows) for rows in self.funds.values()),
        }


def _date(value) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raise ValueError(f"Expected an Excel date, got {value!r}")


def _number(value) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Expected a number, got {value!r}")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError(f"Non-finite number: {value!r}")
    return result


def read_workbook(path: str | Path) -> WorkbookData:
    """Validate the entire workbook before any database operation."""
    path = Path(path).resolve()
    content = path.read_bytes()
    values = openpyxl.load_workbook(BytesIO(content), data_only=True)
    formulas = openpyxl.load_workbook(BytesIO(content), data_only=False)
    try:
        overview = list(values["总览"].iter_rows(min_row=2, values_only=True))
        codes = [str(row[0]) for row in overview]
        if not codes or len(set(codes)) != len(codes) or not set(codes) <= set(TRACKED_ETFS):
            raise ValueError("Workbook must contain unique tracked fund codes")
        sheets = {}
        for name in values.sheetnames:
            match = re.search(r"(\d{6})$", name)
            if match:
                code = match[1]
                if code in sheets or code not in codes:
                    raise ValueError(f"Unexpected or duplicate fund sheet: {name}")
                sheets[code] = name
        if set(sheets) != set(codes):
            raise ValueError("Missing fund worksheet")
        funds, skipped = {}, {code: [] for code in codes}
        for record in values["跳过日期"].iter_rows(min_row=2, values_only=True):
            code, _, trade_date, nav_date, _ = record
            code = str(code)
            if code not in skipped or _date(nav_date) >= _date(trade_date):
                raise ValueError(f"Invalid skipped record: {record!r}")
            skipped[code].append(_date(trade_date))
        for overview_row in overview:
            code = str(overview_row[0])
            sheet = values[sheets[code]]
            if sheet.max_column != 4 or [cell.value for cell in sheet[1]] != HEADERS:
                raise ValueError(f"Invalid headers: {sheet.title}")
            rows, nav_by_date = [], {}
            for index in range(2, sheet.max_row + 1):
                day = _date(sheet.cell(index, 1).value)
                close = _number(sheet.cell(index, 2).value)
                nav = _number(sheet.cell(index, 3).value)
                premium = _number(sheet.cell(index, 4).value)
                comment = sheet.cell(index, 3).comment
                match = re.search(r"所用正式净值日期：(\d{4}-\d{2}-\d{2})", comment.text if comment else "")
                if not match:
                    raise ValueError(f"Missing NAV date comment: {code} row {index}")
                nav_date = date.fromisoformat(match[1]).isoformat()
                if nav_date >= day or (rows and rows[-1]["date"] >= day):
                    raise ValueError(f"Invalid or duplicate date: {code} row {index}")
                if close <= 0 or nav <= 0 or abs(close / nav - 1 - premium) > TOLERANCE:
                    raise ValueError(f"Price/NAV/premium mismatch: {code} row {index}")
                formula = formulas[sheet.title].cell(index, 4)
                if formula.data_type == "f" and formula.value != f"=B{index}/C{index}-1":
                    raise ValueError(f"Unexpected premium formula: {code} row {index}")
                if nav_date in nav_by_date and nav_by_date[nav_date] != nav:
                    raise ValueError(f"Conflicting NAV for {code} on {nav_date}")
                nav_by_date[nav_date] = nav
                rows.append({"date": day, "close": float(close), "nav": float(nav),
                             "nav_date": nav_date, "premium_rate": float(premium),
                             "premium_basis": PREMIUM_BASIS})
            if not rows or len(rows) != overview_row[2] or len(skipped[code]) != overview_row[3]:
                raise ValueError(f"Overview counts differ: {code}")
            if rows[0]["date"] != _date(overview_row[4]) or rows[-1]["date"] != _date(overview_row[5]):
                raise ValueError(f"Overview date range differs: {code}")
            if len(set(skipped[code])) != len(skipped[code]) or set(skipped[code]) & {row["date"] for row in rows}:
                raise ValueError(f"Invalid skipped dates: {code}")
            if abs(_number(overview_row[6]) - Decimal(str(rows[-1]["premium_rate"]))) > TOLERANCE:
                raise ValueError(f"Overview premium differs: {code}")
            funds[code] = rows
        return WorkbookData(str(path), hashlib.sha256(content).hexdigest(), funds, skipped)
    finally:
        values.close()
        formulas.close()


def source_records(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    prices = [{"date": row["date"], "close": row["close"], "source": SOURCE, "adjust": "none"} for row in rows]
    navs = {row["nav_date"]: {"date": row["nav_date"], "nav": row["nav"], "source": SOURCE} for row in rows}
    return prices, [navs[day] for day in sorted(navs)]


def import_fund(data: WorkbookData, code: str) -> dict:
    rows = data.funds[code]
    prices, navs = source_records(rows)
    counts = {"code": code, "prices": upsert_price_history(code, prices),
              "navs": upsert_nav_history(code, navs),
              "premiums": upsert_premium_history(code, rows)}
    verify_workbook(data, code)
    return counts


def verify_workbook(data: WorkbookData, code: str = "") -> dict:
    """Verify only the selected workbook funds, including extra or missing dates."""
    selected = {code: data.funds[code]} if code else data.funds
    expected = {name: {} for name in HISTORY_TABLES}
    for fund_code, rows in selected.items():
        prices, navs = source_records(rows)
        for name, records in ((TABLE_PRICE_HISTORY, prices), (TABLE_NAV_HISTORY, navs), (TABLE_PREMIUM_HISTORY, rows)):
            for row in records:
                key = (fund_code, row["date"].replace("-", ""))
                expected[name][key] = row
    counts = {}
    for name in HISTORY_TABLES:
        entities = [entity for fund_code in selected for entity in read_entities(name, fund_code)]
        actual = {(entity["PartitionKey"], entity["RowKey"]): entity for entity in entities}
        if actual.keys() != expected[name].keys():
            raise ValueError(f"Stored keys differ from workbook: {name}")
        for key, row in expected[name].items():
            entity = actual[key]
            for field, value in row.items():
                stored = entity.get("date_str" if field == "date" else field)
                if isinstance(value, float):
                    if stored is None or abs(_number(stored) - Decimal(str(value))) > TOLERANCE:
                        raise ValueError(f"Stored value differs: {name} {key} {field}")
                elif stored != value:
                    raise ValueError(f"Stored value differs: {name} {key} {field}")
        counts[name] = len(actual)
    return counts
