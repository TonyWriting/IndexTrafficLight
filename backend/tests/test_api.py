"""Regression checks for the review switch and public API contracts."""

import json
import unittest
from unittest.mock import patch

import azure.functions as func
import function_app


class ApiTests(unittest.TestCase):
    def call(self, name, params=None):
        handler = getattr(function_app, name)
        response = handler(func.HttpRequest(method="GET", url="http://localhost/api/test",
                                            params=params or {}, body=b""))
        return response.status_code, json.loads(response.get_body())

    def test_review_mode_environment_still_controls_boolean_response(self):
        for value, enabled in (("true", True), (" TRUE ", True), ("1", True),
                               ("false", False), ("0", False), ("", False)):
            with self.subTest(value=value), patch.dict("os.environ", {"REVIEW_MODE_ENABLED": value}):
                status, body = self.call("api_review_mode")
                self.assertEqual(200, status)
                self.assertIs(body["review_mode"], enabled)

    def test_dashboard_reports_missing_snapshot(self):
        with patch("function_app.get_dashboard_snapshot", return_value=None):
            status, body = self.call("api_dashboard")
        self.assertEqual(503, status)
        self.assertIn("error", body)

    def test_history_keeps_both_valuation_sources(self):
        records = [
            {"date": "2026-10-16", "close": 2.4, "nav": 2.0, "nav_date": "2026-10-15",
             "iopv": None, "premium_rate": 0.2, "premium_basis": "nav_proxy_iopv"},
            {"date": "2026-10-19", "close": 2.4, "nav": None, "nav_date": None,
             "iopv": 2.0, "premium_rate": 0.2, "premium_basis": "iopv"},
        ]
        with patch("function_app.get_premium_history", return_value=records) as read:
            status, body = self.call("api_etf_history", {"code": "513500", "start": "2026-10-16"})
        self.assertEqual(200, status)
        self.assertEqual(2, body["count"])
        self.assertEqual(records, body["data"])
        read.assert_called_once_with("513500", start_date="2026-10-16", end_date="")

    def test_history_rejects_unknown_funds_and_invalid_dates_before_storage(self):
        for params in ({"code": "161125"}, {"code": "513500", "start": "invalid"}):
            with self.subTest(params=params), patch("function_app.get_premium_history") as read:
                status, _ = self.call("api_etf_history", params)
                self.assertEqual(400, status)
                read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
