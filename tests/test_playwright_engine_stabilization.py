import asyncio
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.core.engines.playwright_engine import PlaywrightCrawlerEngine
from src.core.services.response_capture import TRADE_CODE_MAP


LEGACY_ARTICLE_ID_KEY = "\uf9cd\u317b\u042aID"


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
        self.cache = None
        self.negative_cache_ttl_minutes = 5
        self.trade_types = [TRADE_CODE_MAP.get("A1", "매매"), TRADE_CODE_MAP.get("B1", "전세")]
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
            "geo_discovered_count": 0,
            "geo_dedup_count": 0,
        }
        self.logged = []
        self.registered = []
        self.progress_signal = _SignalStub()
        self.complex_finished_signal = _SignalStub()
        self.stop_flag = False
        self.finalized_pairs = None
        self.stats_emitted = 0

    def _should_stop(self):
        return bool(self.stop_flag)

    def log(self, msg, level=20):
        self.logged.append((str(msg), int(level)))

    def register_discovered_complex(self, payload):
        self.registered.append(dict(payload))

    def _estimate_remaining_seconds(self, current, total):
        return 0

    def _process_raw_items(self, raw_items, trade_type):
        return len(raw_items or [])

    def _flush_history_updates(self, force=False):
        return 0

    def record_crawl_history(self, *args, **kwargs):
        return None

    def _finalize_disappeared_articles(self, processed_pairs):
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

    def on(self, event, handler):
        self._handlers.setdefault(event, []).append(handler)

    def remove_listener(self, event, handler):
        listeners = self._handlers.get(event, [])
        self._handlers[event] = [h for h in listeners if h is not handler]

    async def goto(self, url, wait_until="domcontentloaded"):
        self.url = url
        for response in list(self._responses):
            for handler in list(self._handlers.get("response", [])):
                handler(response)

    async def wait_for_load_state(self, state="networkidle", timeout=0):
        return None

    async def wait_for_timeout(self, timeout_ms):
        return None

    async def wait_for_selector(self, selector, timeout=0):
        return None

    def locator(self, query):
        return _FakeLocator()


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
                    return_value={"매물ID": "A1"},
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
        article_id = raw_items[0].get("매물ID")
        self.assertEqual(article_id, "A1")
        self.assertTrue(any("article_capture:complexes/12345" in msg for msg, _ in thread.logged))

    async def test_collect_target_raw_items_accepts_legacy_article_id_key(self):
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
                    return_value={LEGACY_ARTICLE_ID_KEY: "A1"},
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
        self.assertEqual(len(raw_items), 1)
        self.assertEqual(raw_items[0].get(LEGACY_ARTICLE_ID_KEY), "A1")

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
                [{"매물ID": "1"}, {"매물ID": "2"}]
            )
        elapsed = time.monotonic() - start

        try:
            self.assertEqual(len(result), 1)
            self.assertTrue(cancelled["value"])
            self.assertLess(elapsed, 0.5)
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
