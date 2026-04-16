import os
import sys
import time
import unittest
from email.message import Message
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.parser import NaverURLParser


def _entry_cid(entry):
    if isinstance(entry, dict):
        return str(entry.get("complex_id", entry.get("cid", "")) or "")
    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
        return str(entry[1] or "")
    return ""


def _entry_asset(entry):
    if isinstance(entry, dict):
        return str(entry.get("asset_type", "APT") or "APT").strip().upper() or "APT"
    if isinstance(entry, (list, tuple)) and len(entry) >= 3:
        return str(entry[2] or "APT").strip().upper() or "APT"
    return "APT"


class TestNaverURLParser(unittest.TestCase):
    def setUp(self):
        NaverURLParser._reset_runtime_state_for_tests()

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
        ids = [_entry_cid(entry) for entry in results]
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
        keys = [(_entry_asset(entry), _entry_cid(entry)) for entry in results]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(keys), 100)

    def test_extract_from_text_ignores_contextless_numbers(self):
        text = "\n".join(
            [
                "기사 번호 987654321",
                "articleId=1234567890",
                "매물 54321",
            ]
        )
        results = NaverURLParser.extract_from_text(text)
        ids = [_entry_cid(entry) for entry in results]
        self.assertNotIn("987654321", ids)
        self.assertNotIn("1234567890", ids)
        self.assertNotIn("54321", ids)

    def test_extract_from_text_accepts_standalone_id_lines(self):
        text = "12345\n67890"
        results = NaverURLParser.extract_from_text(text)
        ids = [_entry_cid(entry) for entry in results]
        self.assertIn("12345", ids)
        self.assertIn("67890", ids)

    def test_extract_from_text_accepts_short_standalone_id_lines(self):
        text = "1\n22"
        results = NaverURLParser.extract_from_text(text)
        ids = [_entry_cid(entry) for entry in results]
        self.assertIn("1", ids)
        self.assertIn("22", ids)

    def test_extract_from_text_preserves_house_asset_scope_separately_from_complex_urls(self):
        text = "\n".join(
            [
                "https://new.land.naver.com/houses/54321?articleId=111",
                "https://new.land.naver.com/complexes/54321",
                "https://m.land.naver.com/houses/article/54321",
            ]
        )
        results = NaverURLParser.extract_from_text(text)
        scoped_ids = {(_entry_asset(entry), _entry_cid(entry)) for entry in results}
        self.assertEqual(scoped_ids, {("APT", "54321"), ("VL", "54321")})
        self.assertEqual(len(results), 2)
        vl_entry = next(entry for entry in results if _entry_asset(entry) == "VL")
        self.assertEqual(vl_entry.get("article_id", ""), "111")

    @patch(
        "src.core.parser.NaverURLParser._fetch_name_impl",
        side_effect=Exception("network fail"),
    )
    def test_fetch_complex_name_fallback_on_error(self, _mock_fetch):
        name = NaverURLParser.fetch_complex_name("99999")
        self.assertEqual(name, "단지_99999")

    def test_fetch_complex_name_activates_cooldown_on_429_and_skips_requery(self):
        class _RateLimitHTTPError(HTTPError):
            def __init__(self):
                super().__init__(
                    "https://new.land.naver.com/api/complexes/102378?sameAddressGroup=false",
                    429,
                    "Too Many Requests",
                    hdrs=Message(),
                    fp=None,
                )

            def read(self, n=None):
                return b'{"success":false,"code":"TOO_MANY_REQUESTS"}'

        with patch(
            "src.core.parser.NaverURLParser._fetch_name_impl",
            side_effect=[_RateLimitHTTPError(), AssertionError("should not requery during cooldown")],
        ) as mock_fetch:
            name1 = NaverURLParser.fetch_complex_name("102378")
            name2 = NaverURLParser.fetch_complex_name("102378")

        self.assertEqual(name1, "단지_102378")
        self.assertEqual(name2, "단지_102378")
        self.assertEqual(mock_fetch.call_count, 1)
        self.assertGreater(NaverURLParser._name_lookup_cooldown_until, time.monotonic())

    def test_fetch_complex_name_uses_process_cache_after_success(self):
        with patch(
            "src.core.parser.NaverURLParser._fetch_name_impl",
            side_effect=["테스트단지", AssertionError("should reuse cache")],
        ) as mock_fetch:
            first = NaverURLParser.fetch_complex_name("55555")
            second = NaverURLParser.fetch_complex_name("55555")

        self.assertEqual(first, "테스트단지")
        self.assertEqual(second, "테스트단지")
        self.assertEqual(mock_fetch.call_count, 1)

    def test_fetch_complex_name_separates_cache_by_asset_type(self):
        with patch(
            "src.core.parser.NaverURLParser._fetch_name_impl",
            side_effect=["아파트단지", "빌라단지"],
        ) as mock_fetch:
            apt_name = NaverURLParser.fetch_complex_name("77777", asset_type="APT")
            vl_name = NaverURLParser.fetch_complex_name("77777", asset_type="VL")

        self.assertEqual(apt_name, "아파트단지")
        self.assertEqual(vl_name, "빌라단지")
        self.assertEqual(mock_fetch.call_count, 2)


if __name__ == "__main__":
    unittest.main()
