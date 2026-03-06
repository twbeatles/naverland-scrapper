import unittest

from src.core.services.gap_analysis import enrich_gap_fields, sale_price_text_to_won


class TestGapAnalysis(unittest.TestCase):
    def test_sale_price_text_to_won(self):
        self.assertEqual(sale_price_text_to_won("3억"), 300_000_000)
        self.assertEqual(sale_price_text_to_won("9,000만"), 90_000_000)

    def test_enrich_gap_fields_for_sale(self):
        item = {
            "거래유형": "매매",
            "매매가": "3억",
            "기전세금(원)": 290_000_000,
        }
        out = enrich_gap_fields(item)
        self.assertEqual(out["갭금액(원)"], 10_000_000)
        self.assertAlmostEqual(out["갭비율"], 10_000_000 / 300_000_000)


if __name__ == "__main__":
    unittest.main()
