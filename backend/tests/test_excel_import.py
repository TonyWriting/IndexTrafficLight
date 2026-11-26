"""Workbook validation, replacement, and restart behavior tests."""

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import openpyxl
from openpyxl.comments import Comment

from shared.excel_import import HEADERS, import_fund, read_workbook, source_records, verify_workbook
from shared import storage


class MemoryTable:
    def __init__(self):
        self.rows = {}
        self.batches = []

    def submit_transaction(self, operations):
        operations = list(operations)
        assert 0 < len(operations) <= 100
        assert len({operation[1]["PartitionKey"] for operation in operations}) == 1
        self.batches.append(operations)
        for operation in operations:
            action, entity = operation[:2]
            key = (entity["PartitionKey"], entity["RowKey"])
            if action == "delete":
                del self.rows[key]
            else:
                self.rows[key] = dict(entity)

    def list_entities(self, **kwargs):
        return iter(self.rows.values())

    def query_entities(self, query, parameters):
        return [row for row in self.rows.values() if row["PartitionKey"] == parameters["code"]]


class WorkbookImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "fixture.xlsx"
        self.config = patch("shared.excel_import.TRACKED_ETFS", {"159509": object()})
        self.config.start()
        self.addCleanup(self.config.stop)
        self.tables = {name: MemoryTable() for name in storage.BUSINESS_TABLES}
        self.client = patch("shared.storage._get_table_client", side_effect=self.tables.__getitem__)
        self.mock_client = self.client.start()
        self.addCleanup(self.client.stop)
        self.write_fixture()

    def write_fixture(self):
        workbook = openpyxl.Workbook()
        overview = workbook.active
        overview.title = "总览"
        overview.append(["code", "name", "count", "skipped", "start", "end", "premium"])
        overview.append(["159509", "Test", 3, 0, datetime(2025, 11, 27), datetime(2025, 12, 1), 0.2])
        sheet = workbook.create_sheet("Test159509")
        sheet.append(HEADERS)
        for day, nav_day in [("2025-11-27", "2025-11-26"), ("2025-11-28", "2025-11-26"), ("2025-12-01", "2025-11-28")]:
            sheet.append([datetime.fromisoformat(day), 2.4, 2.0, 0.2])
            sheet.cell(sheet.max_row, 3).comment = Comment(f"所用正式净值日期：{nav_day}", "test")
        workbook.create_sheet("跳过日期").append(["code", "name", "day", "nav_day", "reason"])
        workbook.save(self.path)
        workbook.close()

    def edit(self, change):
        workbook = openpyxl.load_workbook(self.path)
        change(workbook["Test159509"])
        workbook.save(self.path)
        workbook.close()

    def test_validation_is_offline_and_preserves_holiday_pairing(self):
        data = read_workbook(self.path)
        self.mock_client.assert_not_called()
        rows = data.funds["159509"]
        self.assertEqual("2025-11-26", rows[1]["nav_date"])
        self.assertEqual(2, len(source_records(rows)[1]))

    def test_invalid_rows_rejected_before_storage(self):
        cases = {
            "NAV date comment": lambda sheet: setattr(sheet["C2"], "comment", None),
            "premium mismatch": lambda sheet: setattr(sheet["D2"], "value", 0.3),
            "duplicate date": lambda sheet: setattr(sheet["A3"], "value", sheet["A2"].value),
            # Rows 2 and 3 share one NAV date, so they must use the same NAV.
            "Conflicting NAV": lambda sheet: (setattr(sheet["C3"], "value", 2.1),
                                              setattr(sheet["D3"], "value", 2.4 / 2.1 - 1)),
        }
        for message, change in cases.items():
            with self.subTest(message):
                self.write_fixture()
                self.edit(change)
                with self.assertRaisesRegex(ValueError, message):
                    read_workbook(self.path)
        self.mock_client.assert_not_called()

    def test_interrupted_import_can_be_rerun_without_duplicates(self):
        data = read_workbook(self.path)
        with patch("shared.excel_import.upsert_premium_history", side_effect=RuntimeError("interrupted")):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                import_fund(data, "159509")
        self.assertEqual(0, len(self.tables[storage.TABLE_PREMIUM_HISTORY].rows))
        import_fund(data, "159509")
        import_fund(data, "159509")
        self.assertEqual({storage.TABLE_PRICE_HISTORY: 3, storage.TABLE_NAV_HISTORY: 2,
                          storage.TABLE_PREMIUM_HISTORY: 3}, verify_workbook(data))

    def test_extra_or_corrupt_records_rejected(self):
        data = read_workbook(self.path)
        import_fund(data, "159509")
        table = self.tables[storage.TABLE_PREMIUM_HISTORY]
        table.rows[("159509", "20251127")]["nav_date"] = "2025-11-25"
        with self.assertRaisesRegex(ValueError, "nav_date"):
            verify_workbook(data)
        import_fund(data, "159509")
        table.rows[("159509", "20200101")] = {"PartitionKey": "159509", "RowKey": "20200101"}
        with self.assertRaisesRegex(ValueError, "keys differ"):
            verify_workbook(data)

    def test_subset_workbook_preserves_other_fund_partitions(self):
        with patch("shared.excel_import.TRACKED_ETFS", {"159509": object(), "513500": object()}):
            data = read_workbook(self.path)
        for table in self.tables.values():
            table.rows[("513500", "20251127")] = {"PartitionKey": "513500", "RowKey": "20251127"}
        import_fund(data, "159509")
        self.assertEqual(3, verify_workbook(data)[storage.TABLE_PREMIUM_HISTORY])
        for table in self.tables.values():
            self.assertEqual({"PartitionKey": "513500", "RowKey": "20251127"}, table.rows[("513500", "20251127")])

    def test_unknown_workbook_fund_rejected(self):
        with patch("shared.excel_import.TRACKED_ETFS", {"513500": object()}):
            with self.assertRaisesRegex(ValueError, "unique tracked fund codes"):
                read_workbook(self.path)
        self.mock_client.assert_not_called()

    def test_reset_deletes_every_partition_in_only_four_business_tables(self):
        for table in self.tables.values():
            for code in ("159509", "999999"):
                for index in range(205):
                    table.rows[(code, str(index))] = {"PartitionKey": code, "RowKey": str(index)}
        deleted = storage.reset_history()
        self.assertEqual({name: 410 for name in storage.BUSINESS_TABLES}, deleted)
        self.assertTrue(all(not table.rows for table in self.tables.values()))
        self.assertEqual(set(storage.BUSINESS_TABLES), {call.args[0] for call in self.mock_client.call_args_list})


if __name__ == "__main__":
    unittest.main()
