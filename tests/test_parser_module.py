import os
import sys
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.parser import NaverURLParser


class TestNaverURLParser(unittest.TestCase):
    def test_extract_complex_id(self):
        url = "https://land.naver.com/complex/123456"
        self.assertEqual(NaverURLParser.extract_complex_id(url), "123456")

        url = "https://new.land.naver.com/complexes/123456"
        self.assertEqual(NaverURLParser.extract_complex_id(url), "123456")

    def test_extract_from_text(self):
        text = "https://land.naver.com/complex/11111\n단지ID: 22222"
        results = NaverURLParser.extract_from_text(text)
        ids = [cid for _, cid in results]
        self.assertIn("11111", ids)
        self.assertIn("22222", ids)

    def test_extract_from_text_large_deduplicate(self):
        parts = []
        for i in range(1000, 1100):
            parts.append(f"https://new.land.naver.com/complexes/{i}")
            parts.append(str(i))
            parts.append(f"https://new.land.naver.com/complexes/{i}")  # duplicated URL
        text = "\n".join(parts)
        results = NaverURLParser.extract_from_text(text)
        ids = [cid for _, cid in results]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 100)

    @patch(
        "src.core.parser.NaverURLParser._fetch_name_impl",
        side_effect=Exception("network fail"),
    )
    def test_fetch_complex_name_fallback_on_error(self, _mock_fetch):
        name = NaverURLParser.fetch_complex_name("99999")
        self.assertEqual(name, "단지_99999")


if __name__ == "__main__":
    unittest.main()
