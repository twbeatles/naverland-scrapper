import os
import sys
import unittest
from unittest.mock import patch


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.crawler import CrawlerThread


class _DBStub:
    def get_article_history_state_bulk(self, _complex_id):
        return {}

    def get_enabled_alert_rules(self, _complex_id, _trade_type):
        return []

    def upsert_article_history_bulk(self, rows):
        return len(rows)

    def update_article_history(self, **_kwargs):
        return True

    def record_alert_notification(self, **_kwargs):
        return True


class _CacheStub:
    def __init__(self, items):
        self._items = list(items)

    def get(self, _cid, _ttype, **_kwargs):
        return list(self._items)

    def set(self, _cid, _ttype, _items, ttl_seconds=None, **_kwargs):
        return None


class TestCrawlerRegressions(unittest.TestCase):
    def _build_thread(self, *, price_filter):
        return CrawlerThread(
            targets=[],
            trade_types=["매매", "월세"],
            area_filter={"enabled": False},
            price_filter=price_filter,
            db=_DBStub(),
            cache=None,
            max_retry_count=0,
        )

    def test_monthly_filter_requires_deposit_and_rent(self):
        thread = self._build_thread(
            price_filter={
                "enabled": True,
                "월세": {
                    "deposit_min": 10000,
                    "deposit_max": 30000,
                    "rent_min": 60,
                    "rent_max": 100,
                },
            }
        )
        both_ok = {"보증금": "20000", "월세": "80", "면적(㎡)": 84.0}
        deposit_fail = {"보증금": "5000", "월세": "80", "면적(㎡)": 84.0}
        rent_fail = {"보증금": "20000", "월세": "40", "면적(㎡)": 84.0}

        self.assertTrue(thread._check_filters(both_ok, "월세"))
        self.assertFalse(thread._check_filters(deposit_fail, "월세"))
        self.assertFalse(thread._check_filters(rent_fail, "월세"))

    def test_cache_hit_reapplies_current_filters_using_raw_items(self):
        raw_items = [
            {
                "단지명": "테스트단지",
                "단지ID": "12345",
                "매물ID": "A1",
                "거래유형": "매매",
                "매매가": "10000",
                "보증금": "",
                "월세": "",
                "면적(㎡)": 84.0,
                "면적(평)": 25.4,
                "층/방향": "10층",
                "타입/특징": "",
            }
        ]
        cache = _CacheStub(raw_items)

        strict = CrawlerThread(
            targets=[],
            trade_types=["매매"],
            area_filter={"enabled": False},
            price_filter={"enabled": True, "매매": {"min": 20000, "max": 30000}},
            db=_DBStub(),
            cache=cache,
            max_retry_count=0,
        )
        loose = CrawlerThread(
            targets=[],
            trade_types=["매매"],
            area_filter={"enabled": False},
            price_filter={"enabled": True, "매매": {"min": 9000, "max": 11000}},
            db=_DBStub(),
            cache=cache,
            max_retry_count=0,
        )

        strict_result = strict._crawl(None, "테스트단지", "12345", "매매")
        loose_result = loose._crawl(None, "테스트단지", "12345", "매매")

        self.assertEqual(strict_result["count"], 0)
        self.assertEqual(loose_result["count"], 1)
        self.assertEqual(loose_result["raw_count"], 1)

    def test_negative_cache_hit_returns_zero_without_network_call(self):
        cache = _CacheStub([])
        thread = CrawlerThread(
            targets=[],
            trade_types=["매매"],
            area_filter={"enabled": False},
            price_filter={"enabled": False},
            db=_DBStub(),
            cache=cache,
            max_retry_count=0,
        )
        thread._crawl_once = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("_crawl_once must not be called on negative cache hit")
        )

        result = thread._crawl(None, "테스트단지", "12345", "매매")
        self.assertEqual(result["count"], 0)
        self.assertTrue(result["cache_hit"])
        self.assertEqual(result["raw_count"], 0)

    def test_blocked_page_detection_signal(self):
        thread = self._build_thread(price_filter={"enabled": False})
        signal = thread._detect_block_signal("Access Denied", "<html>captcha required</html>")
        self.assertIsNotNone(signal)

    def test_scroll_container_fallback_smoke(self):
        thread = self._build_thread(price_filter={"enabled": False})
        thread._detect_scroll_container = lambda _driver: True
        states = [(5, {"A1"}), (5, {"A1"}), (5, {"A1"})]
        thread._get_item_state = lambda _driver, _selectors: states.pop(0)
        calls = []

        def _fake_scroll_once(_driver, use_container):
            calls.append(use_container)
            return False if len(calls) == 1 else True

        thread._scroll_once = _fake_scroll_once
        with patch("src.core.crawler.time.sleep", return_value=None):
            thread._scroll(object())

        self.assertGreaterEqual(len(calls), 2)
        self.assertTrue(calls[0])
        self.assertFalse(calls[1])

    def test_scroll_window_fallback_smoke(self):
        thread = self._build_thread(price_filter={"enabled": False})
        thread._detect_scroll_container = lambda _driver: False
        states = [(3, {"X"}), (3, {"X"}), (3, {"X"})]
        thread._get_item_state = lambda _driver, _selectors: states.pop(0)
        calls = []
        thread._scroll_once = lambda _driver, use_container: calls.append(use_container) or False

        with patch("src.core.crawler.time.sleep", return_value=None):
            thread._scroll(object())

        self.assertTrue(calls)
        self.assertTrue(all(flag is False for flag in calls))

    def test_fallback_resumes_only_remaining_pairs(self):
        thread = CrawlerThread(
            targets=[("단지A", "10001"), ("단지B", "20002")],
            trade_types=["매매", "전세"],
            area_filter={"enabled": False},
            price_filter={"enabled": False},
            db=_DBStub(),
            cache=None,
            max_retry_count=0,
        )
        thread._mark_pair_processed("단지A", "10001", "매매")

        captured = {}

        def _fake_run(engine_self):
            captured["allowed_pairs"] = set(engine_self.thread._fallback_allowed_pairs or set())

        with patch("src.core.crawler.SeleniumCrawlerEngine.run", new=_fake_run):
            thread._run_fallback_selenium(start_name="단지A", start_cid="10001", start_trade="전세")

        expected = {
            thread._pair_key("단지A", "10001", "전세"),
            thread._pair_key("단지B", "20002", "매매"),
            thread._pair_key("단지B", "20002", "전세"),
        }
        self.assertEqual(captured.get("allowed_pairs"), expected)
        self.assertIsNone(thread._fallback_allowed_pairs)

    def test_push_item_dedupes_only_when_article_id_exists(self):
        thread = self._build_thread(price_filter={"enabled": False})

        item = {"단지ID": "12345", "매물ID": "A-1", "거래유형": "매매"}
        thread._push_item(dict(item))
        thread._push_item(dict(item))
        self.assertEqual(len(thread.collected_data), 1)

        no_article_id = {"단지ID": "12345", "거래유형": "매매"}
        thread._push_item(dict(no_article_id))
        thread._push_item(dict(no_article_id))
        self.assertEqual(len(thread.collected_data), 3)


if __name__ == "__main__":
    unittest.main()
