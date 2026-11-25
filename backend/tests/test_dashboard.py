"""Tests for dashboard group ordering."""

import unittest
from unittest.mock import patch

from shared.dashboard import build_dashboard_snapshot, filter_by_range, RANGES


class DashboardGroupOrderTests(unittest.TestCase):
    @patch("shared.dashboard.get_premium_history", return_value=[])
    def test_seventeen_funds_in_three_groups(self, _) -> None:
        snapshot = build_dashboard_snapshot()
        group_keys = [group["tracking_index"] for group in snapshot["groups"]]

        self.assertEqual(17, len(snapshot["items"]))
        self.assertEqual(
            [
                "NASDAQ_TECH",
                "NASDAQ100",
                "SP500",
            ],
            group_keys,
        )
        self.assertEqual(["513500", "513650", "159612", "159655"], snapshot["groups"][2]["members"])
        self.assertNotIn("161125", {item["code"] for item in snapshot["items"]})

    def test_six_month_boundary_uses_latest_record(self):
        def row(day):
            return {"date": day, "close": 2.1, "nav": 2.0, "premium_rate": 0.05,
                    "nav_date": "2026-04-15", "premium_basis": "nav_proxy_iopv"}
        records = [row(day) for day in ("2026-04-15", "2026-04-16", "2026-10-16")]
        self.assertEqual(["2026-04-16", "2026-10-16"], [record["date"] for record in filter_by_range(records, "6m")])
        self.assertEqual({"3m": 3, "6m": 6, "1y": 12}, RANGES)

    def test_six_month_boundary_clamps_month_end(self):
        from shared.dashboard import _shift_month
        self.assertEqual("2024-02-29", _shift_month("2024-08-31", -6))


if __name__ == "__main__":
    unittest.main()
