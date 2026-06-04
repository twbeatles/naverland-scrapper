import os
import sys
import time
import unittest
from typing import Any
from unittest.mock import patch


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.crawler import CrawlerThread


class _DBStub:
    def get_article_history_state_bulk(self, _complex_id, trade_type=None, asset_type=None):
        return {}

    def get_enabled_alert_rules(self, _complex_id, _trade_type, asset_type=None):
        return []

    def upsert_article_history_bulk(self, rows):
        return len(rows)

    def update_article_history(self, **_kwargs):
        return True

    def record_alert_notification(self, **_kwargs):
        return True


class _CacheStub:
    def __init__(self, items=None):
        self._items = None if items is None else list(items)
        self.set_calls = []

    def get(self, _cid, _ttype, **_kwargs):
        if self._items is None:
            return None
        return list(self._items)

    def set(self, _cid, _ttype, _items, ttl_seconds=None, **_kwargs):
        payload_ctx = dict(_kwargs)
        if ttl_seconds is not None:
            payload_ctx["ttl_seconds"] = ttl_seconds
        self.set_calls.append((_cid, _ttype, list(_items), payload_ctx))
        self._items = list(_items)
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

    def test_monthly_history_and_price_change_use_rent_metric(self):
        thread = CrawlerThread(
            targets=[],
            trade_types=["월세"],
            area_filter={"enabled": False},
            price_filter={"enabled": False},
            db=_DBStub(),
            cache=None,
            max_retry_count=0,
        )
        first_item = {
            "단지명": "월세단지",
            "단지ID": "91001",
            "매물ID": "M1",
            "거래유형": "월세",
            "매매가": "",
            "보증금": "20000",
            "월세": "100",
            "면적(평)": 24.0,
            "층/방향": "5층",
            "타입/특징": "테스트",
        }
        first_out = thread._enrich_item_with_history_and_alerts(dict(first_item))
        self.assertTrue(first_out["is_new"])

        second_item = dict(first_item)
        second_item["보증금"] = "25000"
        second_item["월세"] = "80"
        second_out = thread._enrich_item_with_history_and_alerts(second_item)

        self.assertEqual(second_out["price_change"], -20)

    def test_history_state_cache_is_scoped_by_trade_type(self):
        class _TradeScopedDB(_DBStub):
            def __init__(self):
                self.calls = []

            def get_article_history_state_bulk(self, _complex_id, trade_type=None, asset_type=None):
                self.calls.append((trade_type, asset_type))
                if trade_type == "매매":
                    return {"A1": {"price": 10000, "price_text": "10000", "status": "active"}}
                if trade_type == "전세":
                    return {"A1": {"price": 5000, "price_text": "5000", "status": "active"}}
                return {"A1": {"price": 10000, "price_text": "10000", "status": "active"}}

        db = _TradeScopedDB()
        thread = CrawlerThread(
            targets=[],
            trade_types=["매매", "전세"],
            area_filter={"enabled": False},
            price_filter={"enabled": False},
            db=db,
            cache=None,
            max_retry_count=0,
        )
        sale = {
            "단지명": "테스트",
            "단지ID": "91001",
            "매물ID": "A1",
            "거래유형": "매매",
            "매매가": "11000",
            "면적(평)": 24.0,
        }
        jeonse = {
            "단지명": "테스트",
            "단지ID": "91001",
            "매물ID": "A1",
            "거래유형": "전세",
            "보증금": "6000",
            "면적(평)": 24.0,
        }

        sale_out = thread._enrich_item_with_history_and_alerts(dict(sale))
        jeonse_out = thread._enrich_item_with_history_and_alerts(dict(jeonse))

        self.assertEqual(sale_out["price_change"], 1000)
        self.assertEqual(jeonse_out["price_change"], 1000)
        self.assertIn(("매매", "APT"), db.calls)
        self.assertIn(("전세", "APT"), db.calls)

    def test_stats_payload_includes_geo_marker_switch_counts(self):
        thread = CrawlerThread(
            targets=[],
            trade_types=["매매"],
            area_filter={"enabled": False},
            price_filter={"enabled": False},
            db=_DBStub(),
            cache=None,
            max_retry_count=0,
        )
        thread.stats["geo_marker_switch_attempt_count"] = 3
        thread.stats["geo_marker_switch_success_count"] = 2
        thread.stats["geo_marker_switch_fail_count"] = 1
        thread.stats["geo_marker_switch_last_method"] = "text:매물"

        payload = thread._build_stats_payload()

        self.assertEqual(payload["geo_marker_switch_attempt_count"], 3)
        self.assertEqual(payload["geo_marker_switch_success_count"], 2)
        self.assertEqual(payload["geo_marker_switch_fail_count"], 1)
        self.assertEqual(payload["geo_marker_switch_last_method"], "text:매물")

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

    def test_negative_cache_written_only_on_confirmed_empty_in_selenium(self):
        cache = _CacheStub(None)
        thread = CrawlerThread(
            targets=[],
            trade_types=["매매"],
            area_filter={"enabled": False},
            price_filter={"enabled": False},
            db=_DBStub(),
            cache=cache,
            max_retry_count=0,
        )
        thread.negative_cache_ttl_minutes = 7
        thread._crawl_once = lambda *_args, **_kwargs: {
            "count": 0,
            "raw_items": [],
            "raw_count": 0,
            "response_seen": True,
            "parse_success": True,
            "empty_confirmed": True,
            "blocked_detected": False,
        }

        result = thread._crawl(None, "테스트단지", "12345", "매매")
        self.assertEqual(result["count"], 0)
        self.assertFalse(result["cache_hit"])
        self.assertTrue(any(call[3].get("reason") == "confirmed_empty" for call in cache.set_calls))

    def test_negative_cache_skipped_when_empty_not_confirmed_in_selenium(self):
        cache = _CacheStub(None)
        thread = CrawlerThread(
            targets=[],
            trade_types=["매매"],
            area_filter={"enabled": False},
            price_filter={"enabled": False},
            db=_DBStub(),
            cache=cache,
            max_retry_count=0,
        )
        thread.negative_cache_ttl_minutes = 7
        thread._crawl_once = lambda *_args, **_kwargs: {
            "count": 0,
            "raw_items": [],
            "raw_count": 0,
            "response_seen": True,
            "parse_success": False,
            "empty_confirmed": False,
            "blocked_detected": False,
        }

        result = thread._crawl(None, "테스트단지", "12345", "매매")
        self.assertEqual(result["count"], 0)
        self.assertFalse(result["cache_hit"])
        self.assertFalse(cache.set_calls)

    def test_selenium_metrics_increment_when_parse_fails(self):
        thread = CrawlerThread(
            targets=[],
            trade_types=["매매"],
            area_filter={"enabled": False},
            price_filter={"enabled": False},
            db=_DBStub(),
            cache=None,
            max_retry_count=0,
        )
        thread._crawl_once = lambda *_args, **_kwargs: {
            "count": 0,
            "raw_items": [],
            "raw_count": 0,
            "response_seen": True,
            "parse_success": False,
            "empty_confirmed": False,
            "blocked_detected": False,
        }

        result = thread._crawl(None, "테스트단지", "12345", "매매")
        self.assertEqual(result["count"], 0)
        self.assertEqual(int(thread.stats.get("response_seen_count", 0)), 1)
        self.assertEqual(int(thread.stats.get("parse_success_count", 0)), 0)
        self.assertEqual(int(thread.stats.get("parse_fail_count", 0)), 1)

    def test_blocked_circuit_breaker_pair_cooldown_and_global_abort(self):
        thread = self._build_thread(price_filter={"enabled": False})
        s1 = thread._record_blocked_event("단지A", "10001", "매매")
        self.assertFalse(bool(s1.get("pair_cooldown_started")))
        self.assertFalse(bool(s1.get("global_abort")))
        self.assertEqual(int(thread.stats.get("blocked_page_count", 0)), 1)

        s2 = thread._record_blocked_event("단지A", "10001", "매매")
        self.assertTrue(bool(s2.get("pair_cooldown_started")))
        self.assertEqual(int(s2.get("pair_cooldown_seconds", 0)), 90)
        self.assertGreater(thread._get_pair_blocked_cooldown_remaining("단지A", "10001", "매매"), 0.0)

        thread._record_blocked_event("단지B", "20002", "매매")
        thread._record_blocked_event("단지C", "30003", "매매")
        s5 = thread._record_blocked_event("단지D", "40004", "매매")
        self.assertTrue(bool(s5.get("global_abort")))

    def test_selenium_loop_skips_cooldown_pair_and_excludes_disappeared_scope(self):
        thread = CrawlerThread(
            targets=[("단지A", "10001")],
            trade_types=["매매"],
            area_filter={"enabled": False},
            price_filter={"enabled": False},
            db=_DBStub(),
            cache=None,
            max_retry_count=0,
        )
        pair = thread._pair_key("단지A", "10001", "매매")
        thread._blocked_pair_cooldown_until[pair] = time.monotonic() + 60.0
        finalized = {}

        class _Driver:
            def quit(self):
                return None

        def _fake_init_driver() -> Any:
            return _Driver()

        def _fake_finalize_disappeared_articles(processed_target_pairs) -> None:
            finalized.setdefault("pairs", set(processed_target_pairs))

        thread._init_driver = _fake_init_driver
        thread._crawl = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("_crawl must not run while cooldown is active")
        )
        thread._finalize_disappeared_articles = _fake_finalize_disappeared_articles

        with (
            patch("src.core.crawler.UC_AVAILABLE", True),
            patch("src.core.crawler.BS4_AVAILABLE", True),
            patch("src.core.crawler.PSUTIL_AVAILABLE", False),
        ):
            thread._run_selenium_loop()

        self.assertEqual(finalized.get("pairs"), set())

    def test_finalize_disappeared_articles_skips_when_no_successful_pairs(self):
        class _DisappearDB:
            def __init__(self):
                self.scoped_calls = 0
                self.global_calls = 0

            def get_article_history_state_bulk(self, _complex_id, trade_type=None, asset_type=None):
                return {}

            def get_enabled_alert_rules(self, _complex_id, _trade_type, asset_type=None):
                return []

            def upsert_article_history_bulk(self, rows):
                return len(rows)

            def update_article_history(self, **_kwargs):
                return True

            def record_alert_notification(self, **_kwargs):
                return True

            def mark_disappeared_articles_for_targets(self, rows):
                self.scoped_calls += 1
                return 0

            def mark_disappeared_articles(self):
                self.global_calls += 1
                return 0

        db = _DisappearDB()
        thread = CrawlerThread(
            targets=[],
            trade_types=["매매"],
            area_filter={"enabled": False},
            price_filter={"enabled": False},
            db=db,
            cache=None,
            max_retry_count=0,
        )

        thread._finalize_disappeared_articles(set())
        self.assertEqual(db.scoped_calls, 0)
        self.assertEqual(db.global_calls, 0)

        thread._finalize_disappeared_articles({("APT", "10001", "매매")})
        self.assertEqual(db.scoped_calls, 1)
        self.assertEqual(db.global_calls, 0)

    def test_blocked_page_detection_signal(self):
        thread = self._build_thread(price_filter={"enabled": False})
        signal = thread._detect_block_signal("Access Denied", "<html>captcha required</html>")
        self.assertIsNotNone(signal)

    def test_scroll_container_fallback_smoke(self):
        thread = self._build_thread(price_filter={"enabled": False})
        states = [(5, {"A1"}), (5, {"A1"}), (5, {"A1"})]
        calls = []

        def _fake_detect_scroll_container(driver) -> bool:
            return True

        def _fake_get_item_state(driver, selectors) -> tuple[int, set[str]]:
            return states.pop(0)

        def _fake_scroll_once(driver, use_container) -> bool:
            calls.append(use_container)
            return False if len(calls) == 1 else True

        thread._detect_scroll_container = _fake_detect_scroll_container
        thread._get_item_state = _fake_get_item_state
        thread._scroll_once = _fake_scroll_once
        with patch("src.core.crawler.time.sleep", return_value=None):
            thread._scroll(object())

        self.assertGreaterEqual(len(calls), 2)
        self.assertTrue(calls[0])
        self.assertFalse(calls[1])

    def test_scroll_window_fallback_smoke(self):
        thread = self._build_thread(price_filter={"enabled": False})
        states = [(3, {"X"}), (3, {"X"}), (3, {"X"})]
        calls = []

        def _fake_detect_scroll_container(driver) -> bool:
            return False

        def _fake_get_item_state(driver, selectors) -> tuple[int, set[str]]:
            return states.pop(0)

        def _fake_scroll_once(driver, use_container) -> bool:
            calls.append(use_container)
            return False

        thread._detect_scroll_container = _fake_detect_scroll_container
        thread._get_item_state = _fake_get_item_state
        thread._scroll_once = _fake_scroll_once

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

    def test_selenium_fallback_finalizes_prefilled_playwright_success(self):
        thread = CrawlerThread(
            targets=[("단지A", "10001")],
            trade_types=["매매", "전세"],
            area_filter={"enabled": False},
            price_filter={"enabled": False},
            db=_DBStub(),
            cache=None,
            max_retry_count=0,
        )
        setattr(thread, "_fallback_allowed_pairs", {thread._pair_key("단지A", "10001", "전세")})
        thread._fallback_prefill_processed_target_pairs = {("APT", "10001", "매매")}
        thread._fallback_prefill_complexes = {
            ("단지A", "10001"): {
                "name": "단지A",
                "cid": "10001",
                "count": 2,
                "trade_types": {"매매"},
            }
        }

        class _Driver:
            def quit(self):
                return None

        history_calls = []
        finalized = {}
        finished = []

        def _record_history(*args, **kwargs):
            history_calls.append((args, kwargs))

        def _finalize(processed_target_pairs):
            finalized["pairs"] = set(processed_target_pairs)

        def _crawl(driver, name, cid, ttype, asset_type="APT"):
            self.assertIsNotNone(driver)
            self.assertEqual((name, cid, ttype, asset_type), ("단지A", "10001", "전세", "APT"))
            return {"count": 3}

        thread.record_crawl_history = _record_history
        setattr(thread, "_finalize_disappeared_articles", _finalize)
        setattr(thread, "_init_driver", lambda: _Driver())
        setattr(thread, "_crawl", _crawl)
        thread.complex_finished_signal.connect(lambda *args: finished.append(args))

        with (
            patch("src.core.crawler.UC_AVAILABLE", True),
            patch("src.core.crawler.BS4_AVAILABLE", True),
            patch("src.core.crawler.PSUTIL_AVAILABLE", False),
        ):
            thread._run_selenium_loop()

        self.assertEqual(len(history_calls), 1)
        args, kwargs = history_calls[0]
        self.assertEqual(args[:4], ("단지A", "10001", "매매,전세", 5))
        self.assertEqual(kwargs["engine"], "selenium")
        self.assertEqual(kwargs["run_status"], "success")
        self.assertEqual(finalized["pairs"], {("APT", "10001", "매매"), ("APT", "10001", "전세")})
        self.assertEqual(finished, [("단지A", "10001", "매매,전세", 5)])

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

    def test_push_item_keeps_asset_scoped_duplicates_separate(self):
        thread = self._build_thread(price_filter={"enabled": False})

        apt_item = {"단지ID": "12345", "매물ID": "A-1", "거래유형": "매매", "자산유형": "APT"}
        vl_item = {"단지ID": "12345", "매물ID": "A-1", "거래유형": "매매", "자산유형": "VL"}

        thread._push_item(dict(apt_item))
        thread._push_item(dict(vl_item))

        self.assertEqual(len(thread.collected_data), 2)
        self.assertEqual(
            {(row.get("자산유형"), row.get("단지ID"), row.get("매물ID")) for row in thread.collected_data},
            {("APT", "12345", "A-1"), ("VL", "12345", "A-1")},
        )

    def test_push_item_treats_blank_asset_type_as_apt_for_legacy_dedupe(self):
        thread = self._build_thread(price_filter={"enabled": False})

        legacy_item = {"단지ID": "12345", "매물ID": "A-1", "거래유형": "매매"}
        apt_item = {"단지ID": "12345", "매물ID": "A-1", "거래유형": "매매", "자산유형": "APT"}

        thread._push_item(dict(legacy_item))
        thread._push_item(dict(apt_item))

        self.assertEqual(len(thread.collected_data), 1)

    def test_process_raw_items_counts_only_new_pushes(self):
        thread = self._build_thread(price_filter={"enabled": False})
        raw_items = [
            {
                "단지명": "테스트단지",
                "단지ID": "12345",
                "매물ID": "A-1",
                "거래유형": "매매",
                "매매가": "10000",
                "보증금": "",
                "월세": "",
                "면적(평)": 34.0,
                "층/방향": "10층",
                "특징태그": "",
                "자산유형": "APT",
            },
            {
                "단지명": "테스트단지",
                "단지ID": "12345",
                "매물ID": "A-1",
                "거래유형": "매매",
                "매매가": "10000",
                "보증금": "",
                "월세": "",
                "면적(평)": 34.0,
                "층/방향": "10층",
                "특징태그": "",
                "자산유형": "APT",
            },
        ]

        matched = thread._process_raw_items(raw_items, "매매")

        self.assertEqual(matched, 1)
        self.assertEqual(int(thread.stats.get("total_found", 0)), 1)
        self.assertEqual(len(thread.collected_data), 1)


if __name__ == "__main__":
    unittest.main()
