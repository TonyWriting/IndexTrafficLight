"""IOPV provider failover, scheduling, and valuation precedence tests."""

from datetime import datetime, timedelta
import json
import unittest
from unittest.mock import MagicMock, patch

from shared import iopv, storage
from shared.dashboard import summarize_premium

NOW = datetime(2026, 10, 19, 15, 30, tzinfo=iopv.CHINA)


def quote(code="159696", source="tencent", day=NOW, value=2.0):
    return iopv.Quote(code, 2.4, value, day.replace(hour=15, minute=0), day, source)


class ProviderTests(unittest.TestCase):
    def test_targeted_collection_only_requests_selected_funds(self):
        with patch("shared.iopv.fetch_quotes", return_value={"513500": quote("513500")}) as fetch:
            result = iopv.collect_quotes(NOW, codes=["513500", "513500"])
        fetch.assert_called_once_with("tencent", ["513500"])
        self.assertEqual(["513500"], [row["code"] for row in result["quotes"]])
        self.assertEqual([], result["failed"])

    def test_tencent_parser_reads_iopv_field_on_both_exchanges(self):
        def line(symbol):
            fields = [""] * 88
            fields[2], fields[3], fields[30] = symbol[2:], "2.400", "20261019150000"
            fields[78], fields[81] = "2.0000", "1.8000"  # 78 is IOPV, 81 is NAV
            return f'v_{symbol}="' + "~".join(fields) + '";'
        quotes = iopv.parse_tencent((line("sh513500") + line("sz159696")).encode("gb18030"), NOW)
        self.assertEqual({"513500", "159696"}, set(quotes))
        self.assertEqual((2.4, 2.0), (quotes["159696"].close, quotes["159696"].iopv))
        self.assertEqual("2026-10-19", quotes["159696"].record()["date"])

    def test_eastmoney_parser_reads_iopv_and_rejects_missing_values(self):
        def row(code, market, iopv_value=2.0):
            return {"f12": code, "f13": market, "f2": 2.4, "f441": iopv_value,
                    "f124": int(NOW.replace(hour=15, minute=0).timestamp()), "f297": 20261019}
        def parse(*rows):
            return iopv.parse_eastmoney(json.dumps({"data": {"diff": list(rows)}}).encode(), NOW)
        quotes = parse(row("513500", 1), row("159696", 0))
        self.assertEqual({"513500", "159696"}, set(quotes))
        self.assertEqual(("eastmoney", 2.0), (quotes["159696"].source, quotes["159696"].iopv))
        self.assertEqual({}, parse(row("159696", 0, "-")))

    @patch("shared.iopv.time.sleep")
    @patch("shared.iopv.TRACKED_ETFS", {"159696": object()})
    def test_six_attempts_per_source_and_ten_second_intervals(self, sleep):
        with patch("shared.iopv.fetch_quotes", side_effect=OSError("network")) as fetch:
            result = iopv.collect_quotes(NOW)
        self.assertEqual(["tencent"] * 6 + ["eastmoney"] * 6, [call.args[0] for call in fetch.call_args_list])
        self.assertEqual([10] * 10, [call.args[0] for call in sleep.call_args_list])
        self.assertEqual(["159696"], result["failed"])
        self.assertEqual([], result["quotes"])

    @patch("shared.iopv.time.sleep")
    @patch("shared.iopv.TRACKED_ETFS", {"159696": object()})
    def test_success_stops_retries_before_eastmoney(self, sleep):
        with patch("shared.iopv.fetch_quotes", side_effect=[OSError("network"), {"159696": quote()}]) as fetch:
            result = iopv.collect_quotes(NOW)
        self.assertEqual(2, fetch.call_count)
        sleep.assert_called_once_with(10)
        self.assertEqual("tencent", result["quotes"][0]["source"])
        self.assertEqual([], result["failed"])

    @patch("shared.iopv.time.sleep")
    @patch("shared.iopv.TRACKED_ETFS", {"159696": object(), "159509": object()})
    def test_partial_response_retries_only_unresolved_funds(self, sleep):
        def fetch(source, codes):
            if source == "tencent":
                return {"159696": quote()}
            return {"159509": quote("159509", "eastmoney")}
        with patch("shared.iopv.fetch_quotes", side_effect=fetch) as mock:
            result = iopv.collect_quotes(NOW)
        self.assertEqual(["159696", "159509"], mock.call_args_list[0].args[1])
        self.assertTrue(all(call.args[1] == ["159509"] for call in mock.call_args_list[1:]))
        self.assertEqual(2, len(result["quotes"]))
        self.assertEqual([], result["failed"])

    @patch("shared.iopv.time.sleep")
    @patch("shared.iopv.TRACKED_ETFS", {"159696": object()})
    def test_old_or_preclose_quotes_cannot_become_today(self, sleep):
        for invalid in (quote(day=NOW - timedelta(days=3)),
                        iopv.Quote("159696", 2.4, 2.0, NOW.replace(hour=14), NOW, "tencent")):
            with self.subTest(quote=invalid), patch("shared.iopv.fetch_quotes", return_value={"159696": invalid}):
                result = iopv.collect_quotes(NOW)
                self.assertEqual([], result["quotes"])

    def test_weekend_and_before_first_run_skip_fetch(self):
        for now in (NOW - timedelta(days=1), NOW.replace(minute=29)):
            with self.subTest(now=now), patch("shared.iopv.fetch_quotes") as fetch:
                self.assertIn("skipped", iopv.collect_quotes(now))
                fetch.assert_not_called()

    def test_refresh_writes_only_outside_dry_run_and_rebuilds_snapshot_after_writes(self):
        collected = {"date": "2026-10-19", "quotes": [quote().record()], "failed": [], "errors": [], "attempts": {}}
        for dry_run, written, rebuilt in ((True, None, False), (False, 0, False), (False, 1, True)):
            with (self.subTest(dry_run=dry_run, written=written),
                  patch("shared.iopv.collect_quotes", return_value=dict(collected)),
                  patch("shared.iopv.upsert_iopv_history", return_value=written) as upsert,
                  patch("shared.dashboard.build_dashboard_snapshot", return_value={}),
                  patch("shared.storage.upsert_dashboard_snapshot") as save):
                iopv.refresh_iopv(dry_run=dry_run)
                self.assertEqual(not dry_run, upsert.called)
                self.assertEqual(rebuilt, save.called)

    def test_daily_overwrite_keeps_one_key(self):
        table = MagicMock()
        stored = {}
        def write(operations):
            for _, entity, _ in operations:
                stored[(entity["PartitionKey"], entity["RowKey"])] = entity
        table.submit_transaction.side_effect = write
        with patch("shared.storage._get_table_client", return_value=table):
            storage.upsert_iopv_history([quote(value=2.0).record()])
            storage.upsert_iopv_history([quote(day=NOW.replace(hour=18, minute=30), value=2.1).record()])
        self.assertEqual(1, len(stored))
        self.assertEqual(2.1, stored[("159696", "20261019")]["iopv"])


class ValuationTests(unittest.TestCase):
    def test_iopv_overrides_same_day_proxy_and_fills_new_dates(self):
        base = {"PartitionKey": "159696", "RowKey": "20261016", "date_str": "2026-10-16",
                "close": 2.2, "nav": 1.8, "nav_date": "2026-10-15",
                "premium_rate": 2.2 / 1.8 - 1, "premium_basis": "nav_proxy_iopv"}
        raw = [{"date_str": "2026-10-16", "close": 2.4, "iopv": 2.0},
               {"date_str": "2026-10-19", "close": 2.6, "iopv": 2.0}]
        proxy_table, iopv_table = MagicMock(), MagicMock()
        proxy_table.query_entities.return_value = [base]
        iopv_table.query_entities.return_value = raw
        with patch("shared.storage._get_table_client", side_effect=[proxy_table, iopv_table]):
            rows = storage.get_premium_history("159696")
        self.assertEqual(2, len(rows))
        self.assertAlmostEqual(0.2, rows[0]["premium_rate"])
        self.assertIsNone(rows[0]["nav"])
        self.assertEqual("iopv", rows[0]["premium_basis"])
        self.assertEqual("2026-10-19", summarize_premium(rows, "1y")["latest"]["date"])

    def test_invalid_iopv_falls_back_to_that_days_saved_proxy(self):
        base = {"RowKey": "20261016", "date_str": "2026-10-16", "close": 2.2, "nav": 1.8,
                "nav_date": "2026-10-15", "premium_rate": 2.2 / 1.8 - 1, "premium_basis": "nav_proxy_iopv"}
        proxy_table, iopv_table = MagicMock(), MagicMock()
        proxy_table.query_entities.return_value = [base]
        iopv_table.query_entities.return_value = [
            {"date_str": "2026-10-16", "close": 2.4, "iopv": 0},
            {"date_str": "2026-10-19", "close": 2.4, "iopv": float("nan")},
        ]
        with patch("shared.storage._get_table_client", side_effect=[proxy_table, iopv_table]):
            rows = storage.get_premium_history("159696")
        self.assertEqual(1, len(rows))
        self.assertEqual("nav_proxy_iopv", rows[0]["premium_basis"])
        self.assertEqual("2026-10-15", rows[0]["nav_date"])
        self.assertIsNone(rows[0]["iopv"])


if __name__ == "__main__":
    unittest.main()
