import csv
import os
import tempfile
import unittest

from src.core.export import DataExporter, OPENPYXL_AVAILABLE
from src.utils.helpers import PriceConverter


class TestExportModule(unittest.TestCase):
    def test_price_converter_to_signed_string(self):
        self.assertEqual(PriceConverter.to_signed_string(1500), "+1,500만")
        self.assertEqual(PriceConverter.to_signed_string(-1500), "-1,500만")
        self.assertEqual(PriceConverter.to_signed_string(0), "")
        self.assertEqual(PriceConverter.to_signed_string(0, zero_text="-"), "-")

    def test_csv_exports_price_change_with_sign(self):
        data = [
            {"단지명": "A", "가격변동": 0, "price_change": 1500},
            {"단지명": "B", "가격변동": 0, "price_change": -2500},
            {"단지명": "C", "가격변동": 0, "price_change": 0},
        ]
        template = {
            "order": ["단지명", "가격변동"],
            "columns": {"단지명": True, "가격변동": True},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "export.csv")
            out = DataExporter(data).to_csv(path, template=template)
            self.assertEqual(out, path)
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]["가격변동"], "+1,500만")
        self.assertEqual(rows[1]["가격변동"], "-2,500만")
        self.assertEqual(rows[2]["가격변동"], "")

    @unittest.skipUnless(OPENPYXL_AVAILABLE, "openpyxl not installed")
    def test_excel_exports_price_change_with_sign(self):
        from openpyxl import load_workbook

        data = [{"단지명": "A", "price_change": -3500}]
        template = {
            "order": ["단지명", "가격변동"],
            "columns": {"단지명": True, "가격변동": True},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "export.xlsx")
            out = DataExporter(data).to_excel(path, template=template)
            self.assertEqual(out, path)
            wb = load_workbook(path, data_only=True)
            ws = wb.active
            value = ws.cell(row=2, column=2).value
            wb.close()

        self.assertEqual(value, "-3,500만")


if __name__ == "__main__":
    unittest.main()
