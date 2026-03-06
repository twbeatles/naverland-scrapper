import importlib.util
import os
import tempfile
import unittest
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


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

            self.assertIsNotNone(tab.crawler_thread)
            self.assertEqual(tab.crawler_thread.crawl_mode, "geo_sweep")
            self.assertEqual(tab.crawler_thread.engine_name, "playwright")
            self.assertFalse(tab.crawler_thread.fallback_engine_enabled)
            self.assertIsNotNone(tab.crawler_thread.geo_config)
            self.assertAlmostEqual(tab.crawler_thread.geo_config.lat, 37.55)
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
            self.assertEqual(tab.discovered_table.item(0, 0).text(), "기존")
            self.assertEqual(tab.discovered_table.item(0, 4).text(), "9")

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_discovered_complex_db_registration_runs_once_per_asset_and_complex(self):
        from src.core.crawler import CrawlerThread

        class _DBStub:
            def __init__(self):
                self.calls = 0

            def add_complex(self, name, cid, return_status=False):
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

        self.assertEqual(db_stub.calls, 1)
        self.assertEqual(len(emitted), 2)
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
