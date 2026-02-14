import os
import sys
import tempfile
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.database import ComplexDatabase


class TestComplexDatabase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "test_complexes.db")
        self.db = ComplexDatabase(self.db_path)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_add_and_get_complex(self):
        ok = self.db.add_complex("테스트단지", "12345", "메모")
        self.assertTrue(ok)

        rows = self.db.get_all_complexes()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "테스트단지")
        self.assertEqual(rows[0]["complex_id"], "12345")

    def test_group_lifecycle(self):
        self.db.add_complex("단지A", "11111")
        all_complexes = self.db.get_all_complexes()
        complex_db_id = all_complexes[0]["id"]

        self.assertTrue(self.db.create_group("관심단지", "설명"))
        groups = self.db.get_all_groups()
        self.assertEqual(len(groups), 1)
        group_id = groups[0]["id"]

        added = self.db.add_complexes_to_group(group_id, [complex_db_id])
        self.assertEqual(added, 1)

        in_group = self.db.get_complexes_in_group(group_id)
        self.assertEqual(len(in_group), 1)
        self.assertEqual(in_group[0]["name"], "단지A")


if __name__ == "__main__":
    unittest.main()
