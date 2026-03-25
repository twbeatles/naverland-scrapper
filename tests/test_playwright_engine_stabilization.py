import asyncio
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

if os.environ.get("NAVERLAND_SKIP_PLAYWRIGHT_TESTS", "").strip().lower() in {"1", "true", "yes", "on"}:
    raise unittest.SkipTest("Playwright engine tests are skipped in this CI environment")

from src.core.engines.playwright_engine import PlaywrightCrawlerEngine
from src.core.services.response_capture import TRADE_CODE_MAP, normalize_marker_payload

_LEGACY_ARTICLE_ID_KEY = "\uf9cd\u317b\u042aID"


class _SignalStub:
    def __init__(self):
        self.calls = []

    def emit(self, *args):
        self.calls.append(args)


class _CacheStub:
    def __init__(self):
        self._store = {}
        self.get_calls = []
        self.set_calls = []

    @staticmethod
    def _normalize_ctx(ctx):
        return {
            "mode": str(ctx.get("mode", "") or ""),
            "asset_type": str(ctx.get("asset_type", "") or ""),
            "source_lat": "" if ctx.get("source_lat", None) is None else str(ctx.get("source_lat")),
            "source_lon": "" if ctx.get("source_lon", None) is None else str(ctx.get("source_lon")),
            "source_zoom": "" if ctx.get("source_zoom", None) is None else str(ctx.get("source_zoom")),
            "marker_id": str(ctx.get("marker_id", "") or ""),
        }

    @classmethod
    def _key(cls, complex_id, trade_type, ctx):
        normalized = cls._normalize_ctx(ctx)
        frozen = tuple(sorted((str(k), str(v)) for k, v in normalized.items()))
        return str(complex_id), str(trade_type), frozen

    def get(self, complex_id, trade_type, **ctx):
        self.get_calls.append((str(complex_id), str(trade_type), dict(ctx)))
        return self._store.get(self._key(complex_id, trade_type, ctx))

    def set(self, complex_id, trade_type, raw_items, ttl_seconds=None, reason="", **ctx):
        payload_ctx = dict(ctx)
        if reason:
            payload_ctx["reason"] = str(reason)
        if ttl_seconds is not None:
            payload_ctx["ttl_seconds"] = ttl_seconds
        self.set_calls.append((str(complex_id), str(trade_type), list(raw_items), payload_ctx))
        self._store[self._key(complex_id, trade_type, ctx)] = list(raw_items)


class _ThreadStub:
    def __init__(self):
        self.playwright_headless = True
        self.playwright_detail_workers = 1
        self.playwright_response_drain_timeout_ms = 3000
        self.block_heavy_resources = False
        self.engine_name = "playwright"
        self.crawl_mode = "complex"
        self.fallback_engine_enabled = False
        self.geo_incomplete_safety_mode = True
        self.geo_incomplete = False
        self.geo_incomplete_reasons = []
        self.geo_incomplete_count = 0
        self.cache: Any | None = None
        self.negative_cache_ttl_minutes = 5
        self.trade_types = [TRADE_CODE_MAP.get("A1", "매매"), TRADE_CODE_MAP.get("B1", "전세")]
        self.targets = [("테스트단지", "12345")]
        self.geo_config = SimpleNamespace(
            lat=37.55,
            lon=126.99,
            zoom=15,
            rings=0,
            step_px=320,
            dwell_ms=100,
            asset_types=["APT", "VL"],
        )
        self.stats = {
            "by_trade_type": {self.trade_types[0]: 0, self.trade_types[1]: 0, TRADE_CODE_MAP.get("B2", "월세"): 0},
            "response_drain_wait_count": 0,
            "response_drain_timeout_count": 0,
            "response_seen_count": 0,
            "parse_success_count": 0,
            "parse_fail_count": 0,
            "detail_success_count": 0,
            "detail_fail_count": 0,
            "detail_fetch_skipped_count": 0,
            "blocked_page_count": 0,
            "geo_discovered_count": 0,
            "geo_dedup_count": 0,
            "geo_incomplete": False,
            "geo_incomplete_count": 0,
            "geo_incomplete_reasons": [],
        }
        self.logged = []
        self.registered = []
        self.filtered_ids = set()
        self.pushed_items = []
        self.enriched_items = []
        self.progress_signal = _SignalStub()
        self.complex_finished_signal = _SignalStub()
        self.stop_flag = False
        self.finalized_pairs = None
        self.stats_emitted = 0
        self.history_calls = []
        self._pair_sequence = []
        self._processed_pairs = set()
        self._current_pair = None
        self._fallback_prefill_processed_target_pairs = set()
        self._pending_discovered_complexes = {}
        self._discovered_complex_status = {}
        self._registered_discovered_complex_keys = set()
        self._block_cooldown_seconds = 60

    def _should_stop(self):
        return bool(self.stop_flag)

    def _pair_key(self, name, cid, trade_type):
        return (str(name or ""), str(cid or ""), str(trade_type or ""))

    def _mark_pair_processed(self, name, cid, trade_type):
        self._processed_pairs.add(self._pair_key(name, cid, trade_type))

    def _sleep_interruptible(self, seconds, chunk_seconds=0.2):
        return True

    def _get_speed_delay(self):
        return 0.0

    def _reset_block_detection_streak(self):
        return None

    def _is_block_like_error(self, exc):
        return False

    def _register_block_detection(self, reason=""):
        return False

    def log(self, msg, level=20):
        self.logged.append((str(msg), int(level)))

    def register_discovered_complex(self, payload):
        self.registered.append(dict(payload))

    def _flush_discovered_complex_registrations(self):
        if self.geo_incomplete and self.geo_incomplete_safety_mode:
            return 0
        return len(self.registered)

    def _determine_run_status(
        self,
        requested_trade_types,
        successful_trade_types,
        attempted_trade_types,
        *,
        force_incomplete=False,
    ):
        if force_incomplete:
            return "incomplete"
        attempted = [str(x) for x in attempted_trade_types if str(x)]
        successful = [str(x) for x in successful_trade_types if str(x)]
        requested = [str(x) for x in requested_trade_types if str(x)]
        if attempted and not successful:
            return "failed"
        if requested and all(token in successful for token in requested):
            return "success"
        return "partial"

    def _mark_geo_incomplete(self, reason, detail=""):
        token = str(reason or "")
        self.geo_incomplete = True
        self.geo_incomplete_count += 1
        if token and token not in self.geo_incomplete_reasons:
            self.geo_incomplete_reasons.append(token)
        self.stats["geo_incomplete"] = True
        self.stats["geo_incomplete_count"] = self.geo_incomplete_count
        self.stats["geo_incomplete_reasons"] = list(self.geo_incomplete_reasons)

    def _geo_incomplete_reason_summary(self):
        return ", ".join(self.geo_incomplete_reasons)

    def _should_persist_geo_results(self):
        return not (self.geo_incomplete and self.geo_incomplete_safety_mode)

    def _estimate_remaining_seconds(self, current, total):
        return 0

    def _process_raw_items(self, raw_items, trade_type):
        return len(raw_items or [])

    def _flush_history_updates(self, force=False):
        return 0

    def _flush_pending_items_if_needed(self, force=False):
        return None

    def _check_filters(self, data, trade_type):
        article_id = str(data.get("매물ID", "") or data.get(_LEGACY_ARTICLE_ID_KEY, "") or "")
        return article_id not in self.filtered_ids

    def _enrich_item_with_history_and_alerts(self, data):
        row = dict(data or {})
        self.enriched_items.append(row)
        return row

    def _push_item(self, item):
        self.pushed_items.append(dict(item or {}))
        return True

    def record_crawl_history(self, *args, **kwargs):
        self.history_calls.append((args, kwargs))
        return None

    def _finalize_disappeared_articles(self, processed_pairs):
        if self.crawl_mode == "geo_sweep" and not self._should_persist_geo_results():
            return
        self.finalized_pairs = set(processed_pairs)

    def emit_stats(self):
        self.stats_emitted += 1


class _FakeLocatorFirst:
    async def click(self, timeout=0):
        return None


class _FakeLocator:
    def __init__(self):
        self.first = _FakeLocatorFirst()


class _FakeMouse:
    async def wheel(self, x, y):
        return None

    async def move(self, x, y, steps=None):
        return None

    async def down(self):
        return None

    async def up(self):
        return None


class _FakePage:
    def __init__(self, responses=None):
        self._handlers = {"response": []}
        self._responses = list(responses or [])
        self.url = "https://new.land.naver.com/"
        self.mouse = _FakeMouse()
        self.visited = []

    def on(self, event, handler):
        self._handlers.setdefault(event, []).append(handler)

    def remove_listener(self, event, handler):
        listeners = self._handlers.get(event, [])
        self._handlers[event] = [h for h in listeners if h is not handler]

    async def goto(self, url, wait_until="domcontentloaded"):
        self.url = url
        self.visited.append(url)
        for response in list(self._responses):
            for handler in list(self._handlers.get("response", [])):
                handler(response)

    async def wait_for_load_state(self, state="networkidle", timeout=0):
        return None

    async def wait_for_timeout(self, timeout_ms):
        return None

    async def wait_for_selector(self, selector, timeout=0):
        return None

    async def title(self):
        return "네이버 부동산"

    async def add_init_script(self, script):
        return None

    async def close(self):
        return None

    def locator(self, query):
        return _FakeLocator()


class _FakeContext:
    def __init__(self):
        self.pages = []
        self.storage_state_calls = []

    async def new_page(self):
        page = _FakePage(responses=[])
        self.pages.append(page)
        return page

    async def close(self):
        return None

    async def route(self, pattern, handler):
        return None

    async def storage_state(self, path=None):
        self.storage_state_calls.append(path)
        return {"cookies": []}


class _FakeBrowser:
    def __init__(self):
        self.contexts = []

    async def new_context(self, **kwargs):
        ctx = _FakeContext()
        self.contexts.append((kwargs, ctx))
        return ctx

    async def close(self):
        return None


class _FakeBrowserType:
    def __init__(self, fail_on_executable_path=False):
        self.executable_path = "C:/ms-playwright/chromium/chrome.exe"
        self.fail_on_executable_path = fail_on_executable_path
        self.launch_calls = []

    async def launch(self, **kwargs):
        self.launch_calls.append(dict(kwargs))
        if self.fail_on_executable_path and kwargs.get("executable_path"):
            raise RuntimeError("chrome launch failed")
        return _FakeBrowser()


class _FakePlaywrightController:
    def __init__(self, browser_type):
        self.chromium = browser_type
        self.devices = {"iPhone 14 Pro Max": {}}

    async def stop(self):
        return None


class _FakeAsyncPlaywright:
    def __init__(self, controller):
        self._controller = controller

    async def start(self):
        return self._controller


class _FakeResponse:
    def __init__(self, url, payload, delay_sec=0.0):
        self.url = url
        self._payload = payload
        self._delay_sec = float(delay_sec)

    async def json(self):
        if self._delay_sec > 0:
            await asyncio.sleep(self._delay_sec)
        return self._payload


class TestPlaywrightEngineStabilization(unittest.IsolatedAsyncioTestCase):
    async def test_collect_target_raw_items_drains_pending_response_tasks(self):
        thread = _ThreadStub()
        trade_type = thread.trade_types[0]
        engine = PlaywrightCrawlerEngine(thread)
        page = _FakePage(
            responses=[
                _FakeResponse(
                    url="https://new.land.naver.com/api/articles/complex/12345?tradeTypes=A1",
                    payload={
                        "articleList": [
                            {
                                "articleNo": "A1",
                                "tradeTypeCode": "A1",
                                "dealOrWarrantPrc": "10000",
                                "area1": 84.0,
                            }
                        ]
                    },
                    delay_sec=0.05,
                )
            ]
        )
        engine._desktop_page = page

        async def _noop_started():
            return None

        async def _passthrough(items):
            return items

        engine._ensure_started = _noop_started
        engine._enrich_items_with_mobile_details = _passthrough

        try:
            with (
                patch("src.core.engines.playwright_engine.detect_trade_type", return_value=trade_type),
                patch(
                    "src.core.engines.playwright_engine.normalize_article_payload",
                    return_value={"매물ID": "A1", _LEGACY_ARTICLE_ID_KEY: "A1"},
                ),
            ):
                collect_result = await engine._collect_target_raw_items(
                    "테스트단지",
                    "12345",
                    trade_type,
                    asset_type="APT",
                    mode="complex",
                )
        finally:
            engine._loop.close()

        raw_items = list(collect_result.get("raw_items", []) or [])
        self.assertTrue(collect_result.get("response_seen"))
        self.assertFalse(collect_result.get("drain_timed_out"))
        self.assertEqual(len(raw_items), 1)
        article_id = raw_items[0].get("매물ID") or raw_items[0].get(_LEGACY_ARTICLE_ID_KEY)
        self.assertEqual(article_id, "A1")
        self.assertTrue(any("article_capture:complexes/12345" in msg for msg, _ in thread.logged))

    async def test_marker_handler_drains_and_applies_dedupe_rules(self):
        thread = _ThreadStub()
        engine = PlaywrightCrawlerEngine(thread)
        discovered = {}
        handler, pending_tasks, stats = engine._build_marker_handler(discovered)

        try:
            handler(
                _FakeResponse(
                    url="https://new.land.naver.com/api/complexes/single-markers",
                    payload=[{"complexNo": "1001", "complexName": "단지A", "articleCount": 3}],
                    delay_sec=0.05,
                )
            )
            wait_count, timed_out = await engine._drain_pending_response_tasks(pending_tasks, label="test_marker_1")
            self.assertEqual(wait_count, 1)
            self.assertFalse(timed_out)
            self.assertIn("APT:1001", discovered)
            self.assertEqual(len(thread.registered), 1)

            handler(
                _FakeResponse(
                    url="https://new.land.naver.com/api/complexes/single-markers",
                    payload=[{"complexNo": "1001", "complexName": "단지A", "articleCount": 3}],
                    delay_sec=0.01,
                )
            )
            _wait_count2, _timed_out2 = await engine._drain_pending_response_tasks(pending_tasks, label="test_marker_2")
            self.assertEqual(int(stats.get("dedup_skipped", 0)), 1)
            self.assertEqual(len(thread.registered), 1)

            handler(
                _FakeResponse(
                    url="https://new.land.naver.com/api/complexes/single-markers",
                    payload=[{"complexNo": "1001", "complexName": "단지A", "articleCount": 5}],
                    delay_sec=0.01,
                )
            )
            _wait_count3, _timed_out3 = await engine._drain_pending_response_tasks(pending_tasks, label="test_marker_3")
            self.assertEqual(int(discovered["APT:1001"]["count"]), 5)
            self.assertEqual(len(thread.registered), 2)
        finally:
            engine._loop.close()

    async def test_geo_sweep_scans_each_trade_type_per_asset_type(self):
        thread = _ThreadStub()
        engine = PlaywrightCrawlerEngine(thread)
        engine._desktop_page = _FakePage(responses=[])
        called = []

        async def _noop_started():
            return None

        async def _scan(asset_type, trade_type, lat, lon, zoom, geo):
            called.append((asset_type, trade_type))
            return True

        engine._ensure_started = _noop_started
        engine._scan_geo_asset_type = _scan

        try:
            await engine._run_geo()
        finally:
            engine._loop.close()

        self.assertEqual(
            called,
            [("APT", thread.trade_types[0]), ("APT", thread.trade_types[1]), ("VL", thread.trade_types[0]), ("VL", thread.trade_types[1])],
        )

    async def test_detail_enrich_cancels_pending_tasks_on_stop(self):
        thread = _ThreadStub()
        engine = PlaywrightCrawlerEngine(thread)
        engine._page_pool = asyncio.Queue()
        await engine._page_pool.put(object())
        await engine._page_pool.put(object())

        cancelled = {"value": False}
        call_count = {"value": 0}

        async def _fake_fetch(_page, _article_id):
            call_count["value"] += 1
            if call_count["value"] == 1:
                await asyncio.sleep(0.01)
                thread.stop_flag = True
                return {}
            try:
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                cancelled["value"] = True
                raise
            return {}

        start = time.monotonic()
        with patch("src.core.engines.playwright_engine.fetch_mobile_article_detail", side_effect=_fake_fetch):
            result = await engine._enrich_items_with_mobile_details(
                [
                    {"매물ID": "1", _LEGACY_ARTICLE_ID_KEY: "1"},
                    {"매물ID": "2", _LEGACY_ARTICLE_ID_KEY: "2"},
                ]
            )
        elapsed = time.monotonic() - start

        try:
            self.assertEqual(len(result), 1)
            self.assertTrue(cancelled["value"])
            self.assertLess(elapsed, 1.2)
            self.assertGreaterEqual(call_count["value"], 1)
        finally:
            engine._loop.close()

    async def test_drain_timeout_increments_timeout_counter(self):
        thread = _ThreadStub()
        engine = PlaywrightCrawlerEngine(thread)
        task = asyncio.create_task(asyncio.sleep(1.0))
        pending = {task}
        try:
            wait_count, timed_out = await engine._drain_pending_response_tasks(
                pending,
                label="timeout_case",
                timeout_ms=1,
            )
        finally:
            engine._loop.close()

        self.assertEqual(wait_count, 1)
        self.assertTrue(timed_out)
        self.assertEqual(int(thread.stats.get("response_drain_wait_count", 0)), 1)
        self.assertEqual(int(thread.stats.get("response_drain_timeout_count", 0)), 1)
        self.assertGreaterEqual(thread.stats_emitted, 1)

    async def test_complex_cache_context_normalization_and_legacy_fallback(self):
        thread = _ThreadStub()
        trade_type = thread.trade_types[0]
        cache = _CacheStub()
        thread.cache = cache
        engine = PlaywrightCrawlerEngine(thread)

        legacy_items = [{"id": "legacy"}]
        cache.set(
            "12345",
            trade_type,
            legacy_items,
            mode="complex",
            asset_type="",
            marker_id="12345",
        )

        async def _must_not_collect(*args, **kwargs):
            raise AssertionError("network collection should not run on legacy cache fallback")

        engine._collect_target_raw_items = _must_not_collect
        try:
            result = await engine._crawl_target_with_cache("테스트", "12345", trade_type, mode="complex")
        finally:
            engine._loop.close()

        self.assertTrue(result["cache_hit"])
        self.assertEqual(result["raw_count"], 1)
        self.assertTrue(
            any(
                call[3].get("mode") == "complex"
                and call[3].get("asset_type") == "APT"
                and call[3].get("marker_id") == ""
                for call in cache.set_calls
            )
        )

    async def test_complex_cache_reuses_selenium_normalized_context(self):
        thread = _ThreadStub()
        trade_type = thread.trade_types[0]
        cache = _CacheStub()
        thread.cache = cache
        engine = PlaywrightCrawlerEngine(thread)

        shared_items = [{"id": "shared"}]
        cache.set("99999", trade_type, shared_items, mode="complex", asset_type="APT")

        async def _must_not_collect(*args, **kwargs):
            raise AssertionError("network collection should not run on normalized cache hit")

        engine._collect_target_raw_items = _must_not_collect
        try:
            result = await engine._crawl_target_with_cache("테스트", "99999", trade_type, mode="complex")
        finally:
            engine._loop.close()

        self.assertTrue(result["cache_hit"])
        self.assertEqual(result["raw_count"], 1)

    async def test_negative_cache_written_only_on_confirmed_empty(self):
        thread = _ThreadStub()
        trade_type = thread.trade_types[0]
        cache = _CacheStub()
        thread.cache = cache
        thread.negative_cache_ttl_minutes = 7
        engine = PlaywrightCrawlerEngine(thread)

        async def _collect_confirmed_empty(*_args, **_kwargs):
            return {"raw_items": [], "response_seen": True, "drain_timed_out": False}

        engine._collect_target_raw_items = _collect_confirmed_empty
        try:
            result = await engine._crawl_target_with_cache("테스트", "55555", trade_type, mode="complex")
        finally:
            engine._loop.close()

        self.assertEqual(result["count"], 0)
        self.assertFalse(result["cache_hit"])
        self.assertTrue(any(call[3].get("reason") == "confirmed_empty" for call in cache.set_calls))

    async def test_negative_cache_skipped_on_drain_timeout(self):
        thread = _ThreadStub()
        trade_type = thread.trade_types[0]
        cache = _CacheStub()
        thread.cache = cache
        thread.negative_cache_ttl_minutes = 7
        engine = PlaywrightCrawlerEngine(thread)

        async def _collect_timeout_empty(*_args, **_kwargs):
            return {"raw_items": [], "response_seen": True, "drain_timed_out": True}

        engine._collect_target_raw_items = _collect_timeout_empty
        try:
            result = await engine._crawl_target_with_cache("테스트", "66666", trade_type, mode="complex")
        finally:
            engine._loop.close()

        self.assertEqual(result["count"], 0)
        self.assertFalse(result["cache_hit"])
        self.assertFalse(cache.set_calls)

    async def test_response_and_parse_metrics_increment_for_failed_parse(self):
        thread = _ThreadStub()
        trade_type = thread.trade_types[0]
        engine = PlaywrightCrawlerEngine(thread)

        async def _collect_failed_parse(*_args, **_kwargs):
            return {"raw_items": [], "response_seen": True, "parse_success": False, "drain_timed_out": False}

        engine._collect_target_raw_items = _collect_failed_parse
        try:
            result = await engine._crawl_target_with_cache("테스트", "77777", trade_type, mode="complex")
        finally:
            engine._loop.close()

        self.assertEqual(result["count"], 0)
        self.assertEqual(int(thread.stats.get("response_seen_count", 0)), 1)
        self.assertEqual(int(thread.stats.get("parse_success_count", 0)), 0)
        self.assertEqual(int(thread.stats.get("parse_fail_count", 0)), 1)

    async def test_capture_failure_flags_block_like_redirect_and_skips_negative_cache(self):
        thread = _ThreadStub()
        trade_type = thread.trade_types[0]
        cache = _CacheStub()
        thread.cache = cache
        engine = PlaywrightCrawlerEngine(thread)

        async def _collect_capture_failed(*_args, **_kwargs):
            return {
                "raw_items": [],
                "response_seen": False,
                "parse_success": False,
                "drain_timed_out": False,
                "response_match_count": 0,
                "final_url": "https://new.land.naver.com/404",
                "block_like_redirect": True,
                "block_reason": "redirect_404",
                "capture_failed": True,
                "failure_reason": "block-like redirect: redirect_404",
            }

        engine._collect_target_raw_items = _collect_capture_failed
        try:
            result = await engine._crawl_target_with_cache("테스트", "81818", trade_type, mode="complex")
        finally:
            engine._loop.close()

        self.assertTrue(result["capture_failed"])
        self.assertTrue(result["block_like_redirect"])
        self.assertEqual(int(thread.stats.get("capture_failed_count", 0)), 1)
        self.assertEqual(int(thread.stats.get("block_like_redirect_count", 0)), 1)
        self.assertEqual(thread.stats.get("playwright_last_final_url"), "https://new.land.naver.com/404")
        self.assertFalse(cache.set_calls)

    async def test_runtime_prefers_local_chrome_when_available(self):
        thread = _ThreadStub()
        browser_type = _FakeBrowserType()
        controller = _FakePlaywrightController(browser_type)
        engine = PlaywrightCrawlerEngine(thread)

        with (
            patch("src.core.engines.playwright_engine.async_playwright", return_value=_FakeAsyncPlaywright(controller)),
            patch("src.core.engines.playwright_engine.ChromeParamHelper.get_chrome_executable_path", return_value="C:\\Chrome\\chrome.exe"),
        ):
            await engine._ensure_started()

        try:
            self.assertEqual(thread.stats.get("playwright_browser_source"), "local_chrome")
            self.assertEqual(browser_type.launch_calls[0].get("executable_path"), "C:\\Chrome\\chrome.exe")
        finally:
            await engine._shutdown_async()
            engine._loop.close()

    async def test_runtime_falls_back_to_playwright_chromium_when_local_chrome_launch_fails(self):
        thread = _ThreadStub()
        browser_type = _FakeBrowserType(fail_on_executable_path=True)
        controller = _FakePlaywrightController(browser_type)
        engine = PlaywrightCrawlerEngine(thread)

        with (
            patch("src.core.engines.playwright_engine.async_playwright", return_value=_FakeAsyncPlaywright(controller)),
            patch("src.core.engines.playwright_engine.ChromeParamHelper.get_chrome_executable_path", return_value="C:\\Chrome\\chrome.exe"),
        ):
            await engine._ensure_started()

        try:
            self.assertEqual(thread.stats.get("playwright_browser_source"), "playwright_chromium")
            self.assertEqual(len(browser_type.launch_calls), 2)
            self.assertIn("executable_path", browser_type.launch_calls[0])
            self.assertNotIn("executable_path", browser_type.launch_calls[1])
        finally:
            await engine._shutdown_async()
            engine._loop.close()

    async def test_runtime_reuses_storage_state_and_runs_warmups(self):
        thread = _ThreadStub()
        browser_type = _FakeBrowserType()
        controller = _FakePlaywrightController(browser_type)
        engine = PlaywrightCrawlerEngine(thread)

        with tempfile.TemporaryDirectory() as tmp:
            desktop_state = Path(tmp) / "desktop_storage_state.json"
            mobile_state = Path(tmp) / "mobile_storage_state.json"
            desktop_state.write_text("{}", encoding="utf-8")
            mobile_state.write_text("{}", encoding="utf-8")

            with (
                patch("src.core.engines.playwright_engine.async_playwright", return_value=_FakeAsyncPlaywright(controller)),
                patch.object(engine, "_profile_root", return_value=tmp),
            ):
                await engine._ensure_started()

            try:
                self.assertEqual(int(thread.stats.get("playwright_session_reused", 0)), 2)
                self.assertGreaterEqual(int(thread.stats.get("playwright_warmup_count", 0)), 3)
                self.assertEqual(thread.stats.get("playwright_profile_dir"), tmp)
            finally:
                await engine._shutdown_async()
                engine._loop.close()

    async def test_collect_target_raw_items_tries_next_entry_plan_when_direct_capture_missing(self):
        thread = _ThreadStub()
        trade_type = thread.trade_types[0]
        engine = PlaywrightCrawlerEngine(thread)
        page = _FakePage(responses=[])
        engine._desktop_page = page
        attempted_plans = []

        async def _noop_started():
            return None

        async def _run_entry_plan(_page, plan, *, label):
            attempted_plans.append(str(plan.get("name", "")))
            _page.url = str(plan.get("target", ""))
            if plan.get("name") == "fin_then_new_target":
                for handler in list(_page._handlers.get("response", [])):
                    handler(
                        _FakeResponse(
                            url="https://new.land.naver.com/api/articles/complex/12345?tradeTypes=A1",
                            payload={"articleList": [{"articleNo": "A2", "tradeTypeCode": "A1"}]},
                        )
                    )

        engine._ensure_started = _noop_started
        typed_engine = cast(Any, engine)
        typed_engine._run_entry_plan = _run_entry_plan
        typed_engine._build_entry_plans = lambda _url: [
            {"name": "direct", "warmups": [], "target": "https://new.land.naver.com/complexes/12345"},
            {"name": "fin_then_new_target", "warmups": [], "target": "https://new.land.naver.com/complexes/12345"},
        ]

        try:
            with (
                patch("src.core.engines.playwright_engine.detect_trade_type", return_value=trade_type),
                patch(
                    "src.core.engines.playwright_engine.normalize_article_payload",
                    return_value={"매물ID": "A2", _LEGACY_ARTICLE_ID_KEY: "A2"},
                ),
            ):
                collect_result = await engine._collect_target_raw_items(
                    "테스트단지",
                    "12345",
                    trade_type,
                    asset_type="APT",
                    mode="complex",
                )
        finally:
            engine._loop.close()

        self.assertEqual(attempted_plans, ["direct", "fin_then_new_target"])
        self.assertEqual(len(list(collect_result.get("raw_items", []) or [])), 1)
        self.assertEqual(int(collect_result.get("response_match_count", 0) or 0), 1)

    async def test_crawl_target_with_cache_retries_after_headed_fallback_recovery(self):
        thread = _ThreadStub()
        trade_type = thread.trade_types[0]
        engine = PlaywrightCrawlerEngine(thread)
        collect_calls = []

        async def _collect(*_args, **_kwargs):
            collect_calls.append(len(collect_calls))
            if len(collect_calls) == 1:
                return {
                    "raw_items": [],
                    "response_seen": False,
                    "parse_success": False,
                    "drain_timed_out": False,
                    "response_match_count": 0,
                    "capture_failed": True,
                    "block_like_redirect": True,
                    "block_reason": "redirect_404",
                    "failure_reason": "block-like redirect: redirect_404",
                    "final_url": "https://new.land.naver.com/404",
                }
            return {
                "raw_items": [{"매물ID": "RECOVER-1", "거래유형": trade_type, "매매가": "10000", "면적(㎡)": 84.0}],
                "response_seen": True,
                "parse_success": True,
                "drain_timed_out": False,
                "response_match_count": 1,
                "capture_failed": False,
                "block_like_redirect": False,
                "block_reason": "",
                "failure_reason": "",
                "final_url": "https://new.land.naver.com/complexes/12345",
            }

        engine._collect_target_raw_items = _collect
        engine._enrich_items_with_mobile_details = AsyncMock(
            return_value=[{"매물ID": "RECOVER-1", "거래유형": trade_type, "매매가": "10000", "면적(㎡)": 84.0}]
        )
        engine._maybe_enable_headed_fallback = AsyncMock(return_value=True)

        try:
            result = await engine._crawl_target_with_cache("테스트", "12345", trade_type, mode="complex")
        finally:
            engine._loop.close()

        self.assertEqual(result["count"], 1)
        self.assertEqual(len(collect_calls), 2)
        engine._maybe_enable_headed_fallback.assert_awaited_once()

    async def test_detail_metrics_increment_on_success_and_failure(self):
        thread = _ThreadStub()
        engine = PlaywrightCrawlerEngine(thread)
        engine._page_pool = asyncio.Queue()
        await engine._page_pool.put(object())
        await engine._page_pool.put(object())

        async def _no_retry(label: str, func, *, attempts=3):
            return await func()

        engine._async_retry = _no_retry
        with patch(
            "src.core.engines.playwright_engine.fetch_mobile_article_detail",
            side_effect=[{"brokerName": "ok"}, RuntimeError("detail failed")],
        ):
            result = await engine._enrich_items_with_mobile_details(
                [{"매물ID": "A-1"}, {"매물ID": "A-2"}]
            )
        try:
            self.assertEqual(len(result), 2)
            self.assertEqual(int(thread.stats.get("detail_success_count", 0)), 1)
            self.assertEqual(int(thread.stats.get("detail_fail_count", 0)), 1)
        finally:
            engine._loop.close()

    async def test_filter_miss_skips_detail_fetch_but_preserves_history_tracking(self):
        thread = _ThreadStub()
        thread.filtered_ids = {"MISS-1"}
        trade_type = thread.trade_types[0]
        engine = PlaywrightCrawlerEngine(thread)

        async def _collect(*_args, **_kwargs):
            return {
                "raw_items": [{"매물ID": "MISS-1", "거래유형": trade_type, "매매가": "10000", "면적(㎡)": 84.0}],
                "response_seen": True,
                "parse_success": True,
                "drain_timed_out": False,
            }

        engine._collect_target_raw_items = _collect
        engine._enrich_items_with_mobile_details = AsyncMock(return_value=[])
        try:
            result = await engine._crawl_target_with_cache("테스트", "80808", trade_type, mode="complex")
        finally:
            engine._loop.close()

        self.assertEqual(result["count"], 0)
        engine._enrich_items_with_mobile_details.assert_not_awaited()
        self.assertEqual(int(thread.stats.get("filtered_out", 0)), 1)
        self.assertEqual(int(thread.stats.get("detail_fetch_skipped_count", 0)), 1)
        self.assertEqual(len(thread.enriched_items), 1)
        self.assertEqual(len(thread.pushed_items), 0)

    async def test_filter_hit_fetches_detail_and_pushes_detailed_item(self):
        thread = _ThreadStub()
        trade_type = thread.trade_types[0]
        engine = PlaywrightCrawlerEngine(thread)

        raw_item = {"매물ID": "HIT-1", "거래유형": trade_type, "매매가": "10000", "면적(㎡)": 84.0}

        async def _collect(*_args, **_kwargs):
            return {
                "raw_items": [dict(raw_item)],
                "response_seen": True,
                "parse_success": True,
                "drain_timed_out": False,
            }

        async def _detail(items):
            self.assertEqual(len(items), 1)
            enriched = dict(items[0])
            enriched["기전세금(원)"] = 350_000_000
            enriched["부동산상호"] = "테스트부동산"
            return [enriched]

        engine._collect_target_raw_items = _collect
        engine._enrich_items_with_mobile_details = AsyncMock(side_effect=_detail)
        try:
            result = await engine._crawl_target_with_cache("테스트", "90909", trade_type, mode="complex")
        finally:
            engine._loop.close()

        self.assertEqual(result["count"], 1)
        engine._enrich_items_with_mobile_details.assert_awaited_once()
        self.assertEqual(int(thread.stats.get("detail_fetch_skipped_count", 0)), 0)
        self.assertEqual(len(thread.pushed_items), 1)
        self.assertEqual(int(thread.pushed_items[0].get("기전세금(원)", 0)), 350_000_000)
        self.assertEqual(str(thread.pushed_items[0].get("부동산상호", "")), "테스트부동산")

    async def test_cache_hit_fetches_details_only_for_filter_hits(self):
        thread = _ThreadStub()
        thread.filtered_ids = {"MISS-2"}
        trade_type = thread.trade_types[0]
        cache = _CacheStub()
        thread.cache = cache
        engine = PlaywrightCrawlerEngine(thread)

        cache.set(
            "91919",
            trade_type,
            [
                {"매물ID": "MISS-2", "거래유형": trade_type, "매매가": "10000", "면적(㎡)": 84.0},
                {"매물ID": "HIT-2", "거래유형": trade_type, "매매가": "12000", "면적(㎡)": 84.0},
            ],
            mode="complex",
            asset_type="APT",
        )

        async def _detail(items):
            self.assertEqual([str(item.get("매물ID", "")) for item in items], ["HIT-2"])
            enriched = dict(items[0])
            enriched["부동산상호"] = "캐시상세"
            return [enriched]

        engine._enrich_items_with_mobile_details = AsyncMock(side_effect=_detail)
        try:
            result = await engine._crawl_target_with_cache("테스트", "91919", trade_type, mode="complex")
        finally:
            engine._loop.close()

        self.assertTrue(result["cache_hit"])
        self.assertEqual(result["count"], 1)
        engine._enrich_items_with_mobile_details.assert_awaited_once()
        self.assertEqual(int(thread.stats.get("detail_fetch_skipped_count", 0)), 1)
        self.assertEqual(len(thread.enriched_items), 2)
        self.assertEqual(len(thread.pushed_items), 1)
        self.assertEqual(str(thread.pushed_items[0].get("부동산상호", "")), "캐시상세")

    async def test_geo_mode_skips_history_when_no_trade_types_succeeded(self):
        thread = _ThreadStub()
        engine = PlaywrightCrawlerEngine(thread)
        engine._desktop_page = _FakePage(responses=[])

        async def _noop_started():
            return None

        def _fake_marker_handler(discovered):
            discovered["APT:1001"] = {
                "asset_type": "APT",
                "complex_id": "1001",
                "complex_name": "단지A",
                "count": 2,
                "marker_id": "m1",
            }
            pending_tasks: set[asyncio.Task[object]] = set()

            def _handle_response(response) -> None:
                return None

            return (_handle_response, pending_tasks, {"dedup_skipped": 0})

        async def _noop_scan(*_args, **_kwargs):
            return True

        async def _always_fail(*_args, **_kwargs):
            raise RuntimeError("target crawl failed")

        async def _fake_drain(*_args, **_kwargs):
            return (0, False)

        engine._ensure_started = _noop_started
        engine._build_marker_handler = _fake_marker_handler
        engine._scan_geo_asset_type = _noop_scan
        engine._crawl_target_with_cache = _always_fail
        engine._drain_pending_response_tasks = _fake_drain

        try:
            await engine._run_geo()
        finally:
            engine._loop.close()

        self.assertEqual(len(thread.history_calls), 0)

    def test_normalize_marker_payload_separates_marker_id_and_complex_id(self):
        payload = normalize_marker_payload(
            {
                "markerId": "marker-101",
                "complexNo": "complex-202",
                "complexName": "테스트단지",
                "articleCount": 4,
            },
            asset_type="APT",
        )

        self.assertEqual(payload["complex_id"], "complex-202")
        self.assertEqual(payload["marker_id"], "marker-101")

    async def test_complex_mode_records_partial_run_status_when_some_trade_types_fail(self):
        thread = _ThreadStub()
        engine = PlaywrightCrawlerEngine(thread)

        async def _noop_started():
            return None

        async def _noop_memory(reason):
            return None

        async def _crawl(name, cid, trade_type, *args, **kwargs):
            if trade_type == thread.trade_types[0]:
                return {"count": 2}
            raise RuntimeError("second trade failed")

        engine._ensure_started = _noop_started
        engine._check_memory_and_recycle_if_needed = _noop_memory
        engine._crawl_target_with_cache = _crawl

        try:
            await engine._run_complex_mode()
        finally:
            engine._loop.close()

        self.assertEqual(len(thread.history_calls), 1)
        args, kwargs = thread.history_calls[0]
        self.assertEqual(kwargs["run_status"], "partial")
        self.assertEqual(args[2], thread.trade_types[0])

    async def test_complex_mode_records_failed_run_status_when_all_trade_types_fail(self):
        thread = _ThreadStub()
        engine = PlaywrightCrawlerEngine(thread)

        async def _noop_started():
            return None

        async def _noop_memory(reason):
            return None

        async def _crawl(*args, **kwargs):
            raise RuntimeError("all failed")

        engine._ensure_started = _noop_started
        engine._check_memory_and_recycle_if_needed = _noop_memory
        engine._crawl_target_with_cache = _crawl

        try:
            await engine._run_complex_mode()
        finally:
            engine._loop.close()

        self.assertEqual(len(thread.history_calls), 1)
        args, kwargs = thread.history_calls[0]
        self.assertEqual(kwargs["run_status"], "failed")
        self.assertEqual(int(args[3]), 0)
        self.assertEqual(set(str(args[2]).split(",")), set(thread.trade_types))

    async def test_geo_scan_failure_isolated_per_asset_and_trade_type(self):
        thread = _ThreadStub()
        thread.crawl_mode = "geo_sweep"
        engine = PlaywrightCrawlerEngine(thread)
        engine._desktop_page = _FakePage(responses=[])
        called = []

        async def _noop_started():
            return None

        def _fake_marker_handler(discovered):
            pending_tasks: set[asyncio.Task] = set()

            def _handle_response(response) -> None:
                return None

            return (_handle_response, pending_tasks, {"dedup_skipped": 0})

        async def _scan(asset_type, trade_type, lat, lon, zoom, geo):
            called.append((asset_type, trade_type))
            if asset_type == "APT" and trade_type == thread.trade_types[0]:
                raise RuntimeError("scan failed")
            return True

        async def _fake_drain(*_args, **_kwargs):
            return (0, False)

        engine._ensure_started = _noop_started
        engine._build_marker_handler = _fake_marker_handler
        engine._scan_geo_asset_type = _scan
        engine._drain_pending_response_tasks = _fake_drain

        try:
            await engine._run_geo()
        finally:
            engine._loop.close()

        self.assertEqual(
            called,
            [
                ("APT", thread.trade_types[0]),
                ("APT", thread.trade_types[1]),
                ("VL", thread.trade_types[0]),
                ("VL", thread.trade_types[1]),
            ],
        )
        self.assertTrue(thread.geo_incomplete)
        self.assertIn("geo_scan_failure", thread.geo_incomplete_reasons)

    async def test_geo_scan_marks_incomplete_when_marker_switch_fails(self):
        thread = _ThreadStub()
        thread.crawl_mode = "geo_sweep"
        engine = PlaywrightCrawlerEngine(thread)
        engine._desktop_page = _FakePage(responses=[])

        async def _call(label, func, *, attempts=3):
            return await func()

        async def _noop_recenter(lat, lon, zoom):
            return None

        async def _switch_fail():
            return False

        engine._async_retry = _call
        engine._human_like_recenter = _noop_recenter
        engine._switch_to_listing_markers = _switch_fail

        try:
            result = await engine._scan_geo_asset_type("APT", thread.trade_types[0], 37.55, 126.99, 15, thread.geo_config)
        finally:
            engine._loop.close()

        self.assertFalse(result)
        self.assertTrue(thread.geo_incomplete)
        self.assertIn("marker_switch_fail", thread.geo_incomplete_reasons)

    async def test_geo_incomplete_safety_mode_skips_history_and_disappeared_finalize(self):
        thread = _ThreadStub()
        thread.crawl_mode = "geo_sweep"
        thread.geo_incomplete_safety_mode = True
        engine = PlaywrightCrawlerEngine(thread)
        engine._desktop_page = _FakePage(responses=[])

        async def _noop_started():
            return None

        def _fake_marker_handler(discovered):
            discovered["APT:1001"] = {
                "asset_type": "APT",
                "complex_id": "1001",
                "complex_name": "단지A",
                "count": 2,
                "marker_id": "marker-1",
            }
            pending_tasks: set[asyncio.Task] = set()

            def _handle_response(response) -> None:
                return None

            return (_handle_response, pending_tasks, {"dedup_skipped": 0})

        async def _noop_scan(*_args, **_kwargs):
            return True

        async def _crawl(*_args, **_kwargs):
            return {"count": 1}

        async def _fake_drain(*_args, **_kwargs):
            return (1, True)

        engine._ensure_started = _noop_started
        engine._build_marker_handler = _fake_marker_handler
        engine._scan_geo_asset_type = _noop_scan
        engine._crawl_target_with_cache = _crawl
        engine._drain_pending_response_tasks = _fake_drain

        try:
            await engine._run_geo()
        finally:
            engine._loop.close()

        self.assertTrue(thread.geo_incomplete)
        self.assertEqual(len(thread.history_calls), 0)
        self.assertIsNone(thread.finalized_pairs)

    async def test_geo_incomplete_without_safety_mode_records_incomplete_history(self):
        thread = _ThreadStub()
        thread.crawl_mode = "geo_sweep"
        thread.geo_incomplete_safety_mode = False
        engine = PlaywrightCrawlerEngine(thread)
        engine._desktop_page = _FakePage(responses=[])

        async def _noop_started():
            return None

        def _fake_marker_handler(discovered):
            discovered["APT:1001"] = {
                "asset_type": "APT",
                "complex_id": "1001",
                "complex_name": "단지A",
                "count": 2,
                "marker_id": "marker-1",
            }
            pending_tasks: set[asyncio.Task] = set()

            def _handle_response(response) -> None:
                return None

            return (_handle_response, pending_tasks, {"dedup_skipped": 0})

        async def _noop_scan(*_args, **_kwargs):
            return True

        async def _crawl(*_args, **_kwargs):
            return {"count": 1}

        async def _fake_drain(*_args, **_kwargs):
            return (1, True)

        engine._ensure_started = _noop_started
        engine._build_marker_handler = _fake_marker_handler
        engine._scan_geo_asset_type = _noop_scan
        engine._crawl_target_with_cache = _crawl
        engine._drain_pending_response_tasks = _fake_drain

        try:
            await engine._run_geo()
        finally:
            engine._loop.close()

        self.assertTrue(thread.geo_incomplete)
        self.assertEqual(len(thread.history_calls), 1)
        _args, kwargs = thread.history_calls[0]
        self.assertEqual(kwargs["run_status"], "incomplete")

    async def test_memory_watchdog_recycles_context_and_emits_stats(self):
        thread = _ThreadStub()
        thread.stats["playwright_recycle_count"] = 0
        thread.stats["playwright_last_recycle_reason"] = ""
        engine = PlaywrightCrawlerEngine(thread)
        engine._shutdown_async = AsyncMock(return_value=None)
        engine._ensure_started = AsyncMock(return_value=None)

        class _MemInfo:
            rss = int(700 * 1024 * 1024)

        class _Proc:
            @staticmethod
            def memory_info():
                return _MemInfo()

        with (
            patch("src.core.engines.playwright_engine.PSUTIL_AVAILABLE", True),
            patch("src.core.engines.playwright_engine.psutil.Process", return_value=_Proc()),
        ):
            await engine._check_memory_and_recycle_if_needed("unit_test")

        try:
            engine._shutdown_async.assert_awaited_once()
            engine._ensure_started.assert_awaited_once()
            self.assertEqual(int(thread.stats.get("playwright_recycle_count", 0)), 1)
            self.assertIn("unit_test", str(thread.stats.get("playwright_last_recycle_reason", "")))
            self.assertGreaterEqual(thread.stats_emitted, 1)
        finally:
            engine._loop.close()


if __name__ == "__main__":
    unittest.main()
