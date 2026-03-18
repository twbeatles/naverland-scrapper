import importlib.util
import os
import tempfile
import unittest
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _table_text(table, row: int, column: int) -> str:
    item = table.item(row, column)
    assert item is not None
    return item.text()


@unittest.skipIf(importlib.util.find_spec("PyQt6") is None, "PyQt6 is not installed")
class TestGeoTabWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls._qt_app = QApplication.instance() or QApplication([])

    def test_geo_tab_builds_geo_sweep_thread(self):
        from src.core.database import ComplexDatabase

        try:
            from src.ui.widgets.geo_crawler_tab import GeoCrawlerTab
        except ImportError as exc:
            if "_imaging" in str(exc):
                self.skipTest("Pillow DLL blocked in this environment")
            raise

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "geo_tab.db"))
            tab = GeoCrawlerTab(db)
            tab.spin_lat.setValue(37.55)
            tab.spin_lon.setValue(126.99)
            tab.check_trade.setChecked(True)

            def _settings_get(key, default=None):
                if key == "fallback_engine_enabled":
                    return True
                return default

            with (
                patch("src.ui.widgets.geo_crawler_tab.settings.get", side_effect=_settings_get),
                patch("src.core.crawler.CrawlerThread.start", return_value=None),
            ):
                tab.start_crawling()

            thread = tab.crawler_thread
            assert thread is not None
            self.assertEqual(thread.crawl_mode, "geo_sweep")
            self.assertEqual(thread.engine_name, "playwright")
            self.assertFalse(thread.fallback_engine_enabled)
            self.assertTrue(thread.geo_incomplete_safety_mode)
            geo_config = thread.geo_config
            assert geo_config is not None
            self.assertAlmostEqual(geo_config.lat, 37.55)
            self.assertIn(
                "Geo 모드는 Playwright 전용이며 Selenium fallback은 지원하지 않습니다.",
                tab.log_browser.toPlainText(),
            )

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_geo_discovered_table_upserts_by_asset_and_complex(self):
        from src.core.database import ComplexDatabase

        try:
            from src.ui.widgets.geo_crawler_tab import GeoCrawlerTab
        except ImportError as exc:
            if "_imaging" in str(exc):
                self.skipTest("Pillow DLL blocked in this environment")
            raise

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "geo_table_upsert.db"))
            tab = GeoCrawlerTab(db)
            tab._discovered_row_map = {}

            tab._on_discovered_complex(
                {
                    "db_status": "inserted",
                    "asset_type": "APT",
                    "complex_name": "테스트단지",
                    "complex_id": "12345",
                    "count": 7,
                }
            )
            tab._on_discovered_complex(
                {
                    "db_status": "existing",
                    "asset_type": "APT",
                    "complex_name": "테스트단지",
                    "complex_id": "12345",
                    "count": 9,
                }
            )

            self.assertEqual(tab.discovered_table.rowCount(), 1)
            self.assertEqual(_table_text(tab.discovered_table, 0, 0), "기존")
            self.assertEqual(_table_text(tab.discovered_table, 0, 4), "9")

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_geo_tab_disables_retry_when_retry_setting_off(self):
        from src.core.database import ComplexDatabase

        try:
            from src.ui.widgets.geo_crawler_tab import GeoCrawlerTab
        except ImportError as exc:
            if "_imaging" in str(exc):
                self.skipTest("Pillow DLL blocked in this environment")
            raise

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "geo_retry_off.db"))
            tab = GeoCrawlerTab(db)
            tab.check_trade.setChecked(True)

            def _settings_get(key, default=None):
                overrides = {
                    "retry_on_error": False,
                    "max_retry_count": 7,
                    "cache_enabled": False,
                }
                return overrides.get(key, default)

            with (
                patch("src.ui.widgets.geo_crawler_tab.settings.get", side_effect=_settings_get),
                patch("src.ui.widgets.geo_crawler_tab.CrawlerThread") as mock_thread_cls,
            ):
                tab.start_crawling()

            kwargs = mock_thread_cls.call_args.kwargs
            self.assertEqual(kwargs["max_retry_count"], 0)
            mock_thread_cls.return_value.start.assert_called_once()

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_discovered_complex_db_registration_runs_once_per_asset_and_complex(self):
        from src.core.crawler import CrawlerThread

        class _DBStub:
            def __init__(self):
                self.calls = 0

            def add_complex(self, name, cid, *, asset_type="APT", return_status=False):
                self.calls += 1
                return "inserted"

        db_stub = _DBStub()
        thread = CrawlerThread(
            targets=[],
            trade_types=["매매"],
            area_filter={"enabled": False},
            price_filter={"enabled": False},
            db=db_stub,
        )
        emitted = []
        thread.discovered_complex_signal.connect(lambda payload: emitted.append(payload))

        thread.register_discovered_complex(
            {"asset_type": "APT", "complex_id": "12345", "complex_name": "테스트단지", "count": 5}
        )
        thread.register_discovered_complex(
            {"asset_type": "APT", "complex_id": "12345", "complex_name": "테스트단지", "count": 8}
        )
        self.assertEqual(db_stub.calls, 0)
        self.assertEqual(emitted[-1]["db_status"], "pending")
        thread._flush_discovered_complex_registrations()

        self.assertEqual(db_stub.calls, 1)
        self.assertEqual(len(emitted), 3)
        self.assertEqual(emitted[-1]["db_status"], "inserted")

    def test_geo_status_message_updates_from_stats(self):
        from src.core.database import ComplexDatabase

        try:
            from src.ui.widgets.geo_crawler_tab import GeoCrawlerTab
        except ImportError as exc:
            if "_imaging" in str(exc):
                self.skipTest("Pillow DLL blocked in this environment")
            raise

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "geo_status.db"))
            tab = GeoCrawlerTab(db)
            messages = []
            tab.status_message.connect(lambda msg: messages.append(msg))

            tab._update_stats_ui(
                {
                    "total_found": 0,
                    "filtered_out": 0,
                    "cache_hits": 0,
                    "new_count": 0,
                    "price_up": 0,
                    "price_down": 0,
                    "by_trade_type": {"매매": 0, "전세": 0, "월세": 0},
                    "geo_discovered_count": 4,
                    "geo_dedup_count": 2,
                    "response_drain_wait_count": 7,
                    "response_drain_timeout_count": 1,
                }
            )

            self.assertTrue(any("Geo 발견 4 / 중복제거 2 / drain대기 7 / drain타임아웃 1" in m for m in messages))
            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_geo_tab_preserves_zero_settings_and_disables_retry_when_configured(self):
        from src.core.database import ComplexDatabase

        try:
            from src.ui.widgets.geo_crawler_tab import GeoCrawlerTab
        except ImportError as exc:
            if "_imaging" in str(exc):
                self.skipTest("Pillow DLL blocked in this environment")
            raise

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "geo_zero_settings.db"))

            def _settings_get(key, default=None):
                overrides = {
                    "geo_grid_rings": 0,
                    "retry_on_error": False,
                    "max_retry_count": 9,
                    "cache_enabled": False,
                    "fallback_engine_enabled": False,
                }
                return overrides.get(key, default)

            with patch("src.ui.widgets.geo_crawler_tab.settings.get", side_effect=_settings_get):
                tab = GeoCrawlerTab(db)
                self.assertEqual(tab.spin_rings.value(), 0)
                tab.check_trade.setChecked(True)

                with patch("src.core.crawler.CrawlerThread.start", return_value=None):
                    tab.start_crawling()

                thread = tab.crawler_thread
                assert thread is not None
                retry_handler = thread.retry_handler
                assert retry_handler is not None
                self.assertEqual(retry_handler.max_retries, 0)

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_geo_tab_restores_last_coordinates_and_saves_manual_location_on_start(self):
        from src.core.database import ComplexDatabase

        try:
            from src.ui.widgets.geo_crawler_tab import GeoCrawlerTab
        except ImportError as exc:
            if "_imaging" in str(exc):
                self.skipTest("Pillow DLL blocked in this environment")
            raise

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "geo_last_coords.db"))

            def _settings_get(key, default=None):
                overrides = {
                    "geo_last_lat": 37.1111,
                    "geo_last_lon": 127.2222,
                    "cache_enabled": False,
                    "fallback_engine_enabled": False,
                }
                return overrides.get(key, default)

            with patch("src.ui.widgets.geo_crawler_tab.settings.get", side_effect=_settings_get):
                tab = GeoCrawlerTab(db)

            self.assertAlmostEqual(tab.spin_lat.value(), 37.1111, places=4)
            self.assertAlmostEqual(tab.spin_lon.value(), 127.2222, places=4)

            tab.check_trade.setChecked(True)
            tab.spin_lat.setValue(37.3333)
            tab.spin_lon.setValue(127.4444)

            with (
                patch("src.ui.widgets.geo_crawler_tab.settings.update") as mock_update,
                patch("src.core.crawler.CrawlerThread.start", return_value=None),
            ):
                tab.start_crawling()

            self.assertTrue(
                any(
                    call.args
                    and isinstance(call.args[0], dict)
                    and call.args[0].get("geo_last_lat") == 37.3333
                    and call.args[0].get("geo_last_lon") == 127.4444
                    for call in mock_update.call_args_list
                )
            )

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_geo_tab_can_apply_scheduled_profile_without_overwriting_last_manual_coords(self):
        from src.core.database import ComplexDatabase

        try:
            from src.ui.widgets.geo_crawler_tab import GeoCrawlerTab
        except ImportError as exc:
            if "_imaging" in str(exc):
                self.skipTest("Pillow DLL blocked in this environment")
            raise

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "geo_scheduled_profile.db"))

            def _settings_get(key, default=None):
                overrides = {
                    "cache_enabled": False,
                    "fallback_engine_enabled": False,
                }
                return overrides.get(key, default)

            with patch("src.ui.widgets.geo_crawler_tab.settings.get", side_effect=_settings_get):
                tab = GeoCrawlerTab(db)

            tab.check_trade.setChecked(True)
            tab.apply_geo_profile(
                lat=37.7777,
                lon=127.8888,
                zoom=14,
                rings=2,
                step_px=360,
                dwell_ms=900,
                asset_types=["VL"],
                persist_last=False,
            )

            with (
                patch("src.ui.widgets.geo_crawler_tab.settings.update") as mock_update,
                patch("src.core.crawler.CrawlerThread.start", return_value=None),
            ):
                tab.start_crawling()

            self.assertFalse(mock_update.called)
            thread = tab.crawler_thread
            assert thread is not None
            geo_config = thread.geo_config
            assert geo_config is not None
            self.assertAlmostEqual(geo_config.lat, 37.7777, places=4)
            self.assertAlmostEqual(geo_config.lon, 127.8888, places=4)
            self.assertEqual(geo_config.zoom, 14)
            self.assertEqual(geo_config.rings, 2)

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_geo_final_summary_log_on_finish(self):
        from src.core.database import ComplexDatabase

        try:
            from src.ui.widgets.geo_crawler_tab import GeoCrawlerTab
        except ImportError as exc:
            if "_imaging" in str(exc):
                self.skipTest("Pillow DLL blocked in this environment")
            raise

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "geo_finish_summary.db"))
            tab = GeoCrawlerTab(db)

            class _ThreadStub:
                def __init__(self):
                    self.stats = {
                        "geo_discovered_count": 11,
                        "geo_dedup_count": 3,
                        "response_drain_wait_count": 19,
                        "response_drain_timeout_count": 2,
                    }

            tab.crawler_thread = _ThreadStub()
            messages = []
            tab.status_message.connect(lambda msg: messages.append(msg))

            tab._on_crawl_finished([])

            text = tab.log_browser.toPlainText()
            self.assertIn("Geo 요약: 발견 11, 중복제거 3, drain대기 19, drain timeout 2", text)
            self.assertTrue(any("Geo 완료: 발견 11, 중복제거 3, drain대기 19, drain타임아웃 2" in m for m in messages))

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()


if __name__ == "__main__":
    unittest.main()
