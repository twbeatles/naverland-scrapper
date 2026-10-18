"""Data-integrity regressions using real engine/DB code and isolated fixtures."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from typing import Any

from src.core.cache import CrawlCache
from src.core.database import ComplexDatabase
from src.core.engines.playwright_engine import PlaywrightCrawlerEngine
from src.core.services.collection_result import (
    article_list_from_payload, collection_fingerprint, result_is_complete, snapshot_block_reason,
    observation_date,
)
from src.core.services.detail_fetcher_parts.hydration import _decode_rsc_frames
from src.core.services.price_snapshots import build_price_snapshot_rows
from src.core.services.response_capture import normalize_article_payload


def article(aid="a", price="9억"):
    return {"articleNo": aid, "tradeTypeCode": "A1", "dealOrWarrantPrc": price, "area1": 99}


class Response:
    def __init__(self, payload=None, status=200):
        self.payload, self.status = payload, status

    async def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class Request:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    async def get(self, *args, **kwargs):
        self.calls += 1
        value = next(self.responses)
        if isinstance(value, Exception):
            raise value
        return value


class TestCollectionContract(unittest.TestCase):
    def test_error_envelopes_are_not_empty_listings(self):
        for payload in ({}, {"success": False}, {"code": "TOO_MANY_REQUESTS"},
                        {"articleList": None}, {"articleList": ""}, []):
            with self.subTest(payload=payload):
                self.assertIsNone(article_list_from_payload(payload))
        self.assertEqual(article_list_from_payload({"articleList": []}), [])
        self.assertEqual(article_list_from_payload({"articles": []}), [])

    def test_snapshot_safety_gate(self):
        cases: list[dict[str, Any]] = [{"stopped": True}, {"price_filter": {"enabled": True}},
                       {"area_filter": {"enabled": True}}, {"stats": {"geo_incomplete": True}},
                       {"stats": {"collection_incomplete_count": 1}},
                       {"stats": {"collection_results": [{"cache_hit": True}]}},
                       {"stats": {"history_save_failed": True}}]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                self.assertTrue(snapshot_block_reason(**kwargs))
        self.assertEqual(snapshot_block_reason(stats={}), "")

    def test_anonymized_live_contract_prices_and_area_provenance(self):
        payload = json.loads((Path(__file__).parent / "fixtures/naver_article_contract.json").read_text())
        sale, rent = [normalize_article_payload(a, "sample", "123") for a in payload["articleList"]]
        self.assertEqual(build_price_snapshot_rows([sale])[0][5], 195000)
        self.assertEqual(rent["보증금"], "2억")
        self.assertEqual(rent["월세"], "220")
        self.assertEqual(sale["공급면적(㎡)"], 139)
        self.assertEqual(sale["전용면적(㎡)"], 114)
        self.assertEqual(sale["면적소스"], "list_api")

    def test_invalid_numeric_values_do_not_enter_statistics(self):
        item = normalize_article_payload(dict(article(), area1="NaN", area2="inf", dealOrWarrantPrc=""), "sample", "123")
        self.assertEqual(item["면적(㎡)"], 0)
        self.assertIn("missing_price", item["데이터품질오류"])
        self.assertIn("missing_area", item["데이터품질오류"])

    def test_rsc_split_frames_are_json_decoded_without_eval(self):
        frames = [[0], [1, '1:{"agentName":"샘'], [1, '플","phone":"02-000-0000"}\n'],
                  [1, '2:I["module"]\n3:not-json\n']]
        records = _decode_rsc_frames(frames)
        self.assertEqual(records[0]["agentName"], "샘플")
        self.assertEqual(records[1], ["module"])
        self.assertEqual(_decode_rsc_frames("invalid"), [])

    def test_database_date_policy_at_korean_midnight_and_utc_boundary(self):
        kst = timezone(timedelta(hours=9))
        for hour, expected in ((0, "2026-10-17"), (8, "2026-10-17"), (9, "2026-10-18")):
            self.assertEqual(observation_date(datetime(2026, 10, 18, hour, tzinfo=kst)), expected)


class TestPaginationIntegrity(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.thread = SimpleNamespace(stats={}, log=lambda *a: None, article_api_page_delay_ms=0)
        self.engine = PlaywrightCrawlerEngine(self.thread)
        self.kwargs: dict[str, Any] = dict(name="sample", cid="123", trade_type="매매", base_kind="complexes",
                           path_asset="APT", target_url="https://new.land.naver.com/complexes/123",
                           mode="complex", source_lat=None, source_lon=None, source_zoom=None,
                           marker_id="", seen_ids=set())

    async def asyncTearDown(self):
        self.engine._loop.close()

    async def test_later_failures_preserve_data_but_never_complete(self):
        for responses in ([Response({}, 429)], [Response({}, 500), Response({}, 500)],
                          [Response(ValueError("bad json"))], [Response({})],
                          [TimeoutError(), TimeoutError()]):
            with self.subTest(responses=responses):
                request = Request([Response({"articleList": [article()], "isMoreData": True}), *responses])
                result = await self.engine._paginate_article_api_request_context(
                    request, **dict(self.kwargs, seen_ids=set()))
                self.assertIsNotNone(result)
                assert result is not None
                self.assertEqual(len(result["raw_items"]), 1)
                self.assertFalse(result_is_complete(result))
                self.assertEqual(result["last_successful_page"], 1)
                self.assertEqual(result["failed_page"], 2)

    async def test_full_and_confirmed_empty_are_complete(self):
        for items in ([], [article()]):
            result = await self.engine._paginate_article_api_request_context(
                Request([Response({"articleList": items, "isMoreData": False})]),
                **dict(self.kwargs, seen_ids=set()))
            assert result is not None
            self.assertTrue(result_is_complete(result))

    async def test_page_cap_is_partial(self):
        with patch("src.core.engines.playwright_engine.MAX_ARTICLE_API_PAGES", 1):
            result = await self.engine._paginate_article_api_request_context(
                Request([Response({"articleList": [article()], "isMoreData": True})]), **self.kwargs)
        assert result is not None
        self.assertFalse(result_is_complete(result))
        self.assertEqual(result["failure_reason"], "page_cap")

    async def test_invalid_rows_preserve_valid_rows_as_partial(self):
        result = await self.engine._paginate_article_api_request_context(
            Request([Response({"articleList": [article(), None], "isMoreData": False})]), **self.kwargs)
        assert result is not None
        self.assertEqual(len(result["raw_items"]), 1)
        self.assertFalse(result_is_complete(result))


class TestDatabaseIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = ComplexDatabase(Path(self.tmp.name) / "synthetic.db")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_observation_refresh_preserves_excluded_price_and_details(self):
        rows = [dict(article_id=aid, complex_id="123", complex_name="sample", trade_type="매매",
                     price=price, price_text=str(price), asset_type=asset, broker_office="sample")
                for aid, price, asset in (("a", 90000, "APT"), ("b", 150000, "APT"), ("b", 200000, "VL"))]
        self.db.upsert_article_history_bulk(rows)
        conn = self.db._pool.get_connection()
        conn.execute("UPDATE article_history SET last_seen=date(CURRENT_DATE,'-1 day')")
        conn.commit()
        self.db._pool.return_connection(conn)
        items = [normalize_article_payload(article("a"), "sample", "123"),
                 normalize_article_payload(article("b", "15억"), "sample", "123")]
        self.assertTrue(self.db.touch_observed_articles(items))
        self.assertEqual(self.db.mark_disappeared_articles_for_targets([("APT", "123", "매매")]), 0)
        state = self.db.get_article_history_state_bulk("123", asset_type="APT")
        self.assertEqual(state["b"]["status"], "active")
        self.assertEqual(state["b"]["price"], 150000)

    def test_complete_snapshot_replacement_removes_stale_groups(self):
        items = [normalize_article_payload(article("a"), "sample", "123")]
        rows = build_price_snapshot_rows(items)
        self.db.add_price_snapshots_bulk(rows)
        self.db.add_price_snapshots_bulk([], replace_targets=[("APT", "123", "매매")])
        conn = self.db._pool.get_connection()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM price_snapshots").fetchone()[0], 0)
        self.db._pool.return_connection(conn)

    def test_snapshot_delete_rolls_back_if_insert_fails(self):
        rows = build_price_snapshot_rows([normalize_article_payload(article(), "sample", "123")])
        self.db.add_price_snapshots_bulk(rows)
        with patch.object(self.db, "_price_snapshot_upsert_sql", return_value="INSERT INTO missing_table VALUES (?)"):
            self.assertEqual(self.db.add_price_snapshots_bulk(rows, replace_targets=[("APT", "123", "매매")]), 0)
        conn = self.db._pool.get_connection()
        self.assertEqual(conn.execute("SELECT avg_price FROM price_snapshots").fetchone()[0], 90000)
        self.db._pool.return_connection(conn)

    def test_run_diagnostics_are_persisted_without_changing_history_tuple(self):
        self.assertTrue(self.db.add_crawl_history("sample", "123", "매매", 1,
                                               diagnostics={"collection_status": "partial", "failed_page": 2}))
        conn = self.db._pool.get_connection()
        data = json.loads(conn.execute("SELECT diagnostics_json FROM crawl_history").fetchone()[0])
        self.assertEqual(data["failed_page"], 2)
        self.db._pool.return_connection(conn)
        self.assertEqual(len(self.db.get_crawl_history()[0]), 9)

    def test_pre_fingerprint_survives_cache_reload(self):
        with patch("src.core.cache.CACHE_PATH", Path(self.tmp.name) / "cache.json"):
            cache = CrawlCache()
            off = collection_fingerprint(include_pre=False)
            on = collection_fingerprint(include_pre=True)
            cache.set("123", "매매", [{"매물ID": "a"}], query_fingerprint=off)
            cache.flush()
            restored = CrawlCache()
            self.assertIsNone(restored.get("123", "매매", query_fingerprint=on))
            cached = restored.get("123", "매매", query_fingerprint=off)
            assert cached is not None
            self.assertEqual(len(cached), 1)


class TestUserFlowIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = ComplexDatabase(Path(self.tmp.name) / "flow.db")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_api_filter_history_and_disappearance_end_to_end(self):
        from src.core.crawler import CrawlerThread
        items = [normalize_article_payload(article("a"), "sample", "123"),
                 normalize_article_payload(article("b", "15억"), "sample", "123")]
        unfiltered = CrawlerThread([], ["매매"], {"enabled": False}, {"enabled": False}, self.db)
        self.assertEqual(unfiltered._process_raw_items(items, "매매"), 2)
        conn = self.db._pool.get_connection()
        conn.execute("UPDATE article_history SET last_seen=date(CURRENT_DATE,'-1 day')")
        conn.commit()
        self.db._pool.return_connection(conn)
        filtered = CrawlerThread([], ["매매"], {"enabled": False},
                                 {"enabled": True, "매매": {"min": 0, "max": 100000}}, self.db)
        self.assertEqual(filtered._process_raw_items(items, "매매"), 1)
        filtered._finalize_disappeared_articles({("APT", "123", "매매")})
        self.assertEqual(self.db.get_article_history_state_bulk("123", asset_type="APT")["b"]["status"], "active")

    def test_finish_handler_preserves_existing_stats_for_filtered_partial_and_stopped_runs(self):
        from src.ui.widgets.crawler_tab import CrawlerTab
        items = [normalize_article_payload(article("a"), "sample", "123"),
                 normalize_article_payload(article("b", "15억"), "sample", "123")]
        self.db.add_price_snapshots_bulk(build_price_snapshot_rows(items))
        for stats, price_filter, stopped in (
            ({}, {"enabled": True}, False),
            ({"collection_incomplete_count": 1}, {}, False),
            ({}, {}, True),
        ):
            tab = CrawlerTab(self.db)
            tab.collected_data = items[:1]
            tab.crawler_thread = SimpleNamespace(stats=stats, area_filter={}, price_filter=price_filter)
            tab._stop_requested = stopped
            try:
                with patch("src.ui.widgets.crawler_tab.settings.get", side_effect=lambda k, d=None: False if k == "play_sound_on_complete" else d):
                    tab._on_crawl_finished(items[:1])
                conn = self.db._pool.get_connection()
                self.assertEqual(conn.execute("SELECT avg_price,item_count FROM price_snapshots").fetchone()[:], (120000, 2))
                self.db._pool.return_connection(conn)
            finally:
                tab.deleteLater()
                self.app.processEvents()

    def test_borderline_list_area_gets_precise_detail_before_final_filter(self):
        from src.core.crawler import CrawlerThread
        from src.core.services.detail_fetcher_parts.apply import apply_mobile_detail
        thread = CrawlerThread([], ["매매"], {"enabled": True, "min": 139.5, "max": 140},
                               {"enabled": False}, self.db)
        engine = PlaywrightCrawlerEngine(thread)
        item = normalize_article_payload(dict(article(), area1=139), "sample", "123")
        async def detail(items):
            return [apply_mobile_detail(dict(items[0]), {"공급면적(㎡)": 139.94,
                    "면적소스": "detail_structured", "면적정밀도": "상세 표기값"})]
        engine._enrich_items_with_mobile_details = AsyncMock(side_effect=detail)
        try:
            count = asyncio.run(engine._process_raw_items_with_filtered_details([item], "매매"))
            self.assertEqual(count, 1)
            self.assertEqual(thread.collected_data[0]["면적(㎡)"], 139.94)
        finally:
            engine._loop.close()


if __name__ == "__main__":
    unittest.main()
