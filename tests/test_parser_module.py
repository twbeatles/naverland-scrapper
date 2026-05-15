import os
import sys
import time
import unittest
from email.message import Message
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.parser import ArticleLookupBrowserFallbackSession, NaverURLParser


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

    def test_extract_from_text_returns_article_only_url_for_later_resolution(self):
        text = "\n".join(
            [
                "https://fin.land.naver.com/articles/2513105556",
                "https://m.land.naver.com/article/info/2513105557",
            ]
        )
        results = NaverURLParser.extract_from_text(text)

        self.assertEqual([entry.get("article_id") for entry in results], ["2513105556", "2513105557"])
        self.assertTrue(all(entry.get("needs_article_lookup") for entry in results))
        self.assertTrue(all(entry.get("complex_id") == "" for entry in results))

    def test_resolve_article_complex_from_article_payload(self):
        payload = '{"articleNo":"2513105556","complexNo":"102378","realEstateTypeCode":"APT"}'

        with patch("src.core.parser.NaverURLParser._fetch_article_lookup_impl", return_value=payload):
            resolved = NaverURLParser.resolve_article_complex("2513105556")

        self.assertEqual(resolved["complex_id"], "102378")
        self.assertEqual(resolved["asset_type"], "APT")
        self.assertEqual(resolved["article_id"], "2513105556")

    def test_resolve_article_complex_from_fin_complex_number_payload(self):
        payload = (
            '<a href="https://loan.pay.naver.com/n/mortgage?complexNumber=3833&amp;'
            'pyeongTypeNumber=4">대출</a>'
        )

        with patch("src.core.parser.NaverURLParser._fetch_article_lookup_impl", return_value=payload):
            resolved = NaverURLParser.resolve_article_complex("2625154515")

        self.assertEqual(resolved["complex_id"], "3833")
        self.assertEqual(resolved["asset_type"], "APT")
        self.assertEqual(resolved["article_id"], "2625154515")

    def test_resolve_article_complex_from_escaped_complex_number_state(self):
        payload = r'{\"params\":{\"articleNumber\":\"2625154515\",\"complexNumber\":\"3833\"}}'

        with patch("src.core.parser.NaverURLParser._fetch_article_lookup_impl", return_value=payload):
            resolved = NaverURLParser.resolve_article_complex("2625154515")

        self.assertEqual(resolved["complex_id"], "3833")
        self.assertEqual(resolved["asset_type"], "APT")

    def test_extract_article_complex_info_from_browser_response_url(self):
        corpus = "https://fin.land.naver.com/front-api/v1/complex/photo?complexNumber=3833"

        cid, asset_type = NaverURLParser._extract_article_complex_info(corpus)

        self.assertEqual(cid, "3833")
        self.assertEqual(asset_type, "APT")

    def test_resolve_article_complex_detects_vl_building_payload(self):
        payload = '{"articleNo":"2513105556","bildNo":"654321","realEstateTypeName":"빌라"}'

        with patch("src.core.parser.NaverURLParser._fetch_article_lookup_impl", return_value=payload):
            resolved = NaverURLParser.resolve_article_complex("2513105556")

        self.assertEqual(resolved["complex_id"], "654321")
        self.assertEqual(resolved["asset_type"], "VL")

    def test_resolve_article_complex_returns_empty_on_lookup_failure(self):
        with (
            patch("src.core.parser.NaverURLParser._fetch_article_lookup_impl", side_effect=OSError("down")),
            patch("src.core.parser.NaverURLParser._resolve_article_complex_browser_fallback", return_value={}),
        ):
            self.assertEqual(NaverURLParser.resolve_article_complex("2513105556"), {})

    def test_resolve_article_complex_uses_browser_fallback_after_urllib_failure(self):
        with (
            patch("src.core.parser.NaverURLParser._fetch_article_lookup_impl", side_effect=OSError("down")),
            patch(
                "src.core.parser.NaverURLParser._resolve_article_complex_browser_fallback",
                return_value={
                    "source": "fin_article:browser_fallback",
                    "complex_id": "654321",
                    "asset_type": "VL",
                    "article_id": "2513105556",
                    "url": "https://fin.land.naver.com/articles/2513105556",
                },
            ) as mock_fallback,
        ):
            resolved = NaverURLParser.resolve_article_complex("2513105556")

        self.assertEqual(resolved["complex_id"], "654321")
        self.assertEqual(resolved["asset_type"], "VL")
        self.assertIn("browser_fallback", resolved["source"])
        mock_fallback.assert_called_once()

    def test_resolve_article_complex_uses_injected_browser_fallback(self):
        class _Fallback:
            def __init__(self):
                self.calls = []

            def resolve(self, article_id, *, cancel_checker=None, fallback_asset_type="APT"):
                self.calls.append((article_id, fallback_asset_type))
                return {
                    "source": "injected:browser_fallback",
                    "complex_id": "654321",
                    "asset_type": "VL",
                    "article_id": article_id,
                    "url": "https://fin.land.naver.com/articles/2513105556",
                }

        fallback = _Fallback()
        with (
            patch("src.core.parser.NaverURLParser._fetch_article_lookup_impl", side_effect=OSError("down")),
            patch("src.core.parser.NaverURLParser._resolve_article_complex_browser_fallback") as mock_default_fallback,
        ):
            resolved = NaverURLParser.resolve_article_complex(
                "2513105556",
                fallback_asset_type="APT",
                browser_fallback=fallback,
            )

        self.assertEqual(resolved["complex_id"], "654321")
        self.assertEqual(resolved["asset_type"], "VL")
        self.assertEqual(fallback.calls, [("2513105556", "APT")])
        mock_default_fallback.assert_not_called()

    def test_article_browser_fallback_prefers_local_chrome(self):
        class _FakePage:
            def add_init_script(self, *_args, **_kwargs):
                return None

        class _FakeBrowser:
            def new_page(self, **_kwargs):
                return _FakePage()

        class _FakeChromium:
            def __init__(self):
                self.launches = []

            def launch(self, **kwargs):
                self.launches.append(kwargs)
                return _FakeBrowser()

        class _FakeController:
            def __init__(self):
                self.chromium = _FakeChromium()

            def stop(self):
                return None

        class _FakeStarter:
            def __init__(self, controller):
                self.controller = controller

            def start(self):
                return self.controller

        controller = _FakeController()
        with (
            patch("playwright.sync_api.sync_playwright", return_value=_FakeStarter(controller)),
            patch(
                "src.utils.helpers.ChromeParamHelper.get_chrome_executable_path",
                return_value="C:/Program Files/Google/Chrome/Application/chrome.exe",
            ),
        ):
            session = ArticleLookupBrowserFallbackSession()
            self.assertIsNotNone(session._ensure_page())

        self.assertEqual(
            controller.chromium.launches[0].get("executable_path"),
            "C:/Program Files/Google/Chrome/Application/chrome.exe",
        )
        self.assertTrue(controller.chromium.launches[0].get("headless"))

    @patch(
        "src.core.parser.NaverURLParser._fetch_name_impl",
        side_effect=Exception("network fail"),
    )
    def test_fetch_complex_name_fallback_on_error(self, _mock_fetch):
        name = NaverURLParser.fetch_complex_name("99999")
        self.assertEqual(name, "단지_99999")

    def test_fetch_complex_name_uses_browser_fallback_during_direct_lookup_cooldown(self):
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

        with (
            patch(
                "src.core.parser.NaverURLParser._fetch_name_impl",
                side_effect=[_RateLimitHTTPError(), AssertionError("should not requery during cooldown")],
            ) as mock_fetch,
            patch(
                "src.core.parser.NaverURLParser._fetch_name_browser_fallback",
                side_effect=["", "쿨다운단지"],
            ) as mock_browser,
        ):
            name1 = NaverURLParser.fetch_complex_name("102378")
            name2 = NaverURLParser.fetch_complex_name("102378")

        self.assertEqual(name1, "단지_102378")
        self.assertEqual(name2, "쿨다운단지")
        self.assertEqual(mock_fetch.call_count, 1)
        self.assertEqual(mock_browser.call_count, 2)
        self.assertEqual(NaverURLParser._name_cache.get("APT:102378"), "쿨다운단지")
        self.assertGreater(NaverURLParser._name_lookup_cooldown_until, time.monotonic())

    def test_fetch_complex_name_uses_browser_fallback_on_429(self):
        class _RateLimitHTTPError(HTTPError):
            def __init__(self):
                super().__init__(
                    "https://new.land.naver.com/api/complexes/3833?sameAddressGroup=false",
                    429,
                    "Too Many Requests",
                    hdrs=Message(),
                    fp=None,
                )

            def read(self, n=None):
                return b'{"success":false,"code":"TOO_MANY_REQUESTS"}'

        with (
            patch("src.core.parser.NaverURLParser._fetch_name_impl", side_effect=_RateLimitHTTPError()),
            patch("src.core.parser.NaverURLParser._fetch_name_browser_fallback", return_value="남산타운") as mock_browser,
        ):
            name = NaverURLParser.fetch_complex_name("3833")

        self.assertEqual(name, "남산타운")
        mock_browser.assert_called_once()
        self.assertEqual(NaverURLParser._name_cache.get("APT:3833"), "남산타운")

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
