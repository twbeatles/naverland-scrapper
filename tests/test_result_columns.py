import unittest

from src.utils.result_columns import (
    RESULT_EXTRA_COLUMN_DEFS,
    normalize_result_extra_columns,
)


class TestResultColumns(unittest.TestCase):
    def test_normalize_filters_unknown_and_dupes(self):
        self.assertEqual(
            normalize_result_extra_columns(["building", "nope", "building", "cp"]),
            ["building", "cp"],
        )

    def test_catalog_ids_unique(self):
        ids = [d["id"] for d in RESULT_EXTRA_COLUMN_DEFS]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 5)


if __name__ == "__main__":
    unittest.main()
