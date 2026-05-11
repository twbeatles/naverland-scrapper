import unittest

from src.core.analysis import ComplexComparator


class _ComparatorDb:
    def __init__(self):
        self.calls = []

    def get_complex_price_history(self, complex_id, trade_type="매매", asset_type=None):
        self.calls.append((complex_id, trade_type, asset_type))
        return [
            ("2026-05-10", "매매", 30.0, 10000, 12000, 11000, 2, asset_type or "APT"),
            ("2026-05-11", "매매", 30.0, 12000, 14000, 13000, 2, asset_type or "APT"),
        ]


class TestComplexComparator(unittest.TestCase):
    def test_compare_keeps_legacy_string_key_without_asset_scope(self):
        db = _ComparatorDb()
        result = ComplexComparator(db).compare(["12345"], trade_type="매매")

        self.assertEqual(db.calls, [("12345", "매매", None)])
        self.assertIn("12345", result)
        self.assertNotIn("APT:12345", result)
        self.assertEqual(result["12345"]["avg_price"], 12000)

    def test_compare_applies_default_asset_type_scope(self):
        db = _ComparatorDb()
        result = ComplexComparator(db).compare(["12345"], trade_type="전세", asset_type="APT")

        self.assertEqual(db.calls, [("12345", "전세", "APT")])
        self.assertIn("APT:12345", result)

    def test_compare_accepts_tuple_and_dict_asset_targets(self):
        db = _ComparatorDb()
        result = ComplexComparator(db).compare(
            [
                ("APT", "12345"),
                {"asset_type": "VL", "complex_id": "12345"},
            ],
            trade_type="매매",
        )

        self.assertEqual(
            db.calls,
            [
                ("12345", "매매", "APT"),
                ("12345", "매매", "VL"),
            ],
        )
        self.assertIn("APT:12345", result)
        self.assertIn("VL:12345", result)


if __name__ == "__main__":
    unittest.main()
