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

        url = "https://new.land.naver.com/houses/654321?articleId=999999999"
        self.assertEqual(NaverURLParser.extract_complex_id(url), "654321")

        url = "https://fin.land.naver.com/articles/2513105556"
        self.assertIsNone(NaverURLParser.extract_complex_id(url))

    def test_extract_article_id(self):
        url = "https://new.land.naver.com/houses/654321?articleId=999999999"
        self.assertEqual(NaverURLParser.extract_article_id(url), "999999999")

        url = "https://m.land.naver.com/article/info/2513105556"
        self.assertEqual(NaverURLParser.extract_article_id(url), "2513105556")

        url = "https://fin.land.naver.com/articles/2513105556"
        self.assertEqual(NaverURLParser.extract_article_id(url), "2513105556")

    def test_parse_url_info_returns_structured_metadata(self):
        parsed = NaverURLParser.parse_url_info(
            "https://new.land.naver.com/houses/654321?articleId=999999999"
        )
        self.assertEqual(parsed["family"], "new")
        self.assertEqual(parsed["entity_type"], "article")
        self.assertEqual(parsed["asset_type"], "VL")
        self.assertEqual(parsed["complex_id"], "654321")
        self.assertEqual(parsed["article_id"], "999999999")

        parsed_fin = NaverURLParser.parse_url_info(
            "https://fin.land.naver.com/articles/2513105556"
        )
        self.assertEqual(parsed_fin["family"], "fin")
        self.assertEqual(parsed_fin["entity_type"], "article")
        self.assertEqual(parsed_fin["article_id"], "2513105556")
        self.assertEqual(parsed_fin["complex_id"], "")

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

    def test_extract_from_text_ignores_contextless_numbers(self):
        text = "\n".join(
            [
                "기사 번호 987654321",
                "articleId=1234567890",
                "매물 54321",
            ]
        )
        results = NaverURLParser.extract_from_text(text)
        ids = [cid for _, cid in results]
        self.assertNotIn("987654321", ids)
        self.assertNotIn("1234567890", ids)
        self.assertNotIn("54321", ids)

    def test_extract_from_text_accepts_standalone_id_lines(self):
        text = "12345\n67890"
        results = NaverURLParser.extract_from_text(text)
        ids = [cid for _, cid in results]
        self.assertIn("12345", ids)
        self.assertIn("67890", ids)

    def test_extract_from_text_accepts_short_standalone_id_lines(self):
        text = "1\n22"
        results = NaverURLParser.extract_from_text(text)
        ids = [cid for _, cid in results]
        self.assertIn("1", ids)
        self.assertIn("22", ids)

    def test_extract_from_text_accepts_house_urls_and_deduplicates_with_complex_urls(self):
        text = "\n".join(
            [
                "https://new.land.naver.com/houses/54321?articleId=111",
                "https://new.land.naver.com/complexes/54321",
                "https://m.land.naver.com/houses/article/54321",
            ]
        )
        results = NaverURLParser.extract_from_text(text)
        ids = [cid for _, cid in results]
        self.assertEqual(ids, ["54321"])

    @patch(
        "src.core.parser.NaverURLParser._fetch_name_impl",
        side_effect=Exception("network fail"),
    )
    def test_fetch_complex_name_fallback_on_error(self, _mock_fetch):
        name = NaverURLParser.fetch_complex_name("99999")
        self.assertEqual(name, "단지_99999")


if __name__ == "__main__":
    unittest.main()
