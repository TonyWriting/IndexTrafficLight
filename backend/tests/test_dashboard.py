"""Dashboard snapshot, status threshold, and observation range tests."""

import unittest
from unittest.mock import patch

from shared.config import DASHBOARD_GROUP_ORDER, TRACKED_ETFS
from shared.dashboard import (
    STATUS_ABOVE_NORMAL, STATUS_BELOW_NORMAL, STATUS_EXTREME, STATUS_LOW, STATUS_NORMAL,
    build_dashboard_snapshot, filter_by_range, percentile_rank, summarize_premium,
)


def record(day, premium_rate=0.05):
    return {"date": day, "close": 2.1, "nav": 2.0, "premium_rate": premium_rate,
            "nav_date": day, "premium_basis": "nav_proxy_iopv"}


def series(n, k):
    """Return n daily records whose latest premium ranks k-th from the bottom."""
    rates = [value for value in range(1, n + 1) if value != k] + [k]
    return [record(f"2026-10-{index:02d}", rate / 100) for index, rate in enumerate(rates, 1)]


class DashboardTests(unittest.TestCase):
    @patch("shared.dashboard.get_premium_history", return_value=[])
    def test_snapshot_lists_every_fund_once_in_configured_group_order(self, _):
        snapshot = build_dashboard_snapshot()
        members = [code for group in snapshot["groups"] for code in group["members"]]
        self.assertEqual(list(DASHBOARD_GROUP_ORDER), [group["tracking_index"] for group in snapshot["groups"]])
        self.assertCountEqual(TRACKED_ETFS, [item["code"] for item in snapshot["items"]])
        self.assertCountEqual(TRACKED_ETFS, members)

    def test_snapshot_reports_latest_premium_percentile_and_group_extremes(self):
        histories = {"513500": series(10, 1)}
        with patch("shared.dashboard.get_premium_history",
                   side_effect=lambda code: histories.get(code, series(10, 10))):
            snapshot = build_dashboard_snapshot()
        items = {item["code"]: item for item in snapshot["items"]}
        self.assertEqual({"latest": {"date": "2026-10-10", "premium_rate": 0.10}, "percentile": 1.0,
                          "status": STATUS_EXTREME}, items["159696"]["stats"]["3m"])
        self.assertEqual(STATUS_BELOW_NORMAL, items["513500"]["stats"]["1y"]["status"])
        group = next(group for group in snapshot["groups"] if "513500" in group["members"])
        self.assertEqual({"min_premium": 0.01, "max_premium": 0.10}, group["ranges"]["6m"])

    def test_status_thresholds_use_inclusive_lower_bounds(self):
        # Keep this table identical to the frontend premium tests.
        cases = [(11, 1, STATUS_LOW), (10, 1, STATUS_BELOW_NORMAL), (10, 2, STATUS_BELOW_NORMAL),
                 (10, 3, STATUS_NORMAL), (10, 6, STATUS_NORMAL), (10, 7, STATUS_ABOVE_NORMAL),
                 (10, 8, STATUS_ABOVE_NORMAL), (10, 9, STATUS_EXTREME)]
        for n, k, status in cases:
            with self.subTest(percentile=f"{k}/{n}"):
                self.assertEqual(status, summarize_premium(series(n, k), "3m")["status"])
        self.assertEqual(0.75, percentile_rank(0.2, [0.1, 0.2, 0.2, 0.3]))

    def test_range_filter_drops_invalid_records_and_clamps_month_end(self):
        # The invalid latest record must not move the cutoff, which clamps to February 29.
        records = [record(day) for day in ("2024-02-28", "2024-02-29", "2024-08-31")]
        records.append(record("2024-09-30", float("nan")))
        self.assertEqual(["2024-02-29", "2024-08-31"], [row["date"] for row in filter_by_range(records, "6m")])


if __name__ == "__main__":
    unittest.main()
