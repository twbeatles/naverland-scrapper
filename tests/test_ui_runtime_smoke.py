import importlib.util
import os
import tempfile
import time
import unittest
from unittest.mock import patch


# Ensure headless-friendly Qt platform for CI runners.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@unittest.skipIf(importlib.util.find_spec("PyQt6") is None, "PyQt6 is not installed")
class TestUIRuntimeSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls._qt_app = QApplication.instance() or QApplication([])

    def test_real_estate_app_instantiation(self):
        from src.ui.app import RealEstateApp

        w = RealEstateApp()

        # Prevent background activity leaking into other tests.
        if hasattr(w, "schedule_timer") and w.schedule_timer:
            w.schedule_timer.stop()
        if hasattr(w, "tray_icon") and w.tray_icon:
            # Avoid calling close()/quit paths; they can block in headless test runs.
            w.tray_icon.hide()

        # Close DB connections explicitly (RealEstateApp.closeEvent calls this, but close can block).
        if hasattr(w, "db") and w.db:
            w.db.close()

        w.deleteLater()
        self._qt_app.processEvents()

    def test_app_guide_tab_contains_moved_help_content(self):
        from PyQt6.QtWidgets import QTextBrowser
        from src.ui.app import RealEstateApp

        w = RealEstateApp()

        browsers = w.findChildren(QTextBrowser)
        guide_html = "\n".join(browser.toHtml() for browser in browsers)
        self.assertIn("빠른 시작 가이드", guide_html)
        self.assertIn("탭별 안내", guide_html)
        self.assertIn("메뉴 안내", guide_html)
        self.assertIn("데이터 수집", guide_html)
        self.assertIn("DB 백업", guide_html)

        if hasattr(w, "schedule_timer") and w.schedule_timer:
            w.schedule_timer.stop()
        if hasattr(w, "tray_icon") and w.tray_icon:
            w.tray_icon.hide()
        if hasattr(w, "db") and w.db:
            w.db.close()

        w.deleteLater()
        self._qt_app.processEvents()

    def test_app_defers_dashboard_widget_until_first_open(self):
        from src.ui.app import RealEstateApp

        w = RealEstateApp()

        self.assertIsNotNone(getattr(w, "db_tab", None))
        self.assertIsNotNone(getattr(w, "favorites_tab", None))
        self.assertIsNone(getattr(w, "dashboard_widget", None))
        self.assertIs(w.tabs.widget(w.TAB_DB), w.db_tab)
        self.assertIs(w.tabs.widget(w.TAB_FAVORITES), w.favorites_tab)

        w.tabs.setCurrentWidget(w.dashboard_tab)
        w._refresh_tab()
        self.assertIsNotNone(getattr(w, "dashboard_widget", None))

        if hasattr(w, "schedule_timer") and w.schedule_timer:
            w.schedule_timer.stop()
        if hasattr(w, "tray_icon") and w.tray_icon:
            w.tray_icon.hide()
        if hasattr(w, "db") and w.db:
            w.db.close()

        w.deleteLater()
        self._qt_app.processEvents()

    def test_dashboard_first_open_receives_existing_collected_data(self):
        from src.ui.app import RealEstateApp

        w = RealEstateApp()
        sample_data = [
            {
                "단지명": "지연대시보드단지",
                "단지ID": "10101",
                "매물ID": "D1",
                "거래유형": "매매",
                "매매가": "1억 2,000만",
                "보증금": "",
                "월세": "",
                "면적(평)": 33.0,
                "층/방향": "10층",
                "타입/특징": "테스트",
                "수집시각": "2026-03-18 09:00:00",
                "is_new": True,
                "price_change": 0,
            }
        ]
        w._on_crawl_data_collected(sample_data)
        self.assertIsNone(getattr(w, "dashboard_widget", None))

        w.tabs.setCurrentWidget(w.dashboard_tab)
        w._refresh_tab()

        self.assertIsNotNone(getattr(w, "dashboard_widget", None))
        self.assertEqual(len(getattr(w.dashboard_widget, "_data", [])), 1)

        if hasattr(w, "schedule_timer") and w.schedule_timer:
            w.schedule_timer.stop()
        if hasattr(w, "tray_icon") and w.tray_icon:
            w.tray_icon.hide()
        if hasattr(w, "db") and w.db:
            w.db.close()

        w.deleteLater()
        self._qt_app.processEvents()

    def test_dialogs_instantiation(self):
        from src.ui.dialogs import URLBatchDialog, AdvancedFilterDialog

        d1 = URLBatchDialog()
        d2 = AdvancedFilterDialog()
        d1.deleteLater()
        d2.deleteLater()
        self._qt_app.processEvents()

    def test_url_batch_dialog_unverified_defaults_unchecked(self):
        from PyQt6.QtWidgets import QCheckBox
        from src.ui.dialogs.batch import URLBatchDialog

        with (
            patch("src.ui.dialogs.batch.NaverURLParser.extract_from_text", return_value=[("URL", "11111"), ("ID", "22222")]),
            patch("src.ui.dialogs.batch.NaverURLParser.fetch_complex_name", side_effect=["단지_11111", "검증단지"]),
        ):
            dlg = URLBatchDialog()
            dlg.input_text.setPlainText("dummy")
            dlg._parse_urls()
            for _ in range(60):
                self._qt_app.processEvents()
                if not dlg._parsing:
                    break
                time.sleep(0.01)

            chk_unknown = dlg.result_table.cellWidget(0, 0)
            chk_verified = dlg.result_table.cellWidget(1, 0)
            assert isinstance(chk_unknown, QCheckBox)
            assert isinstance(chk_verified, QCheckBox)
            self.assertFalse(chk_unknown.isChecked())
            self.assertTrue(chk_verified.isChecked())

            dlg.deleteLater()
            self._qt_app.processEvents()

    def test_url_batch_dialog_cancel_restores_button_state(self):
        from src.ui.dialogs.batch import URLBatchDialog

        def _slow_fetch(cid, cancel_checker=None):
            # give event loop time to click cancel
            for _ in range(20):
                if callable(cancel_checker) and cancel_checker():
                    raise Exception("cancelled")
                time.sleep(0.01)
            return f"단지_{cid}"

        with (
            patch("src.ui.dialogs.batch.NaverURLParser.extract_from_text", return_value=[("URL", "11111"), ("ID", "22222")]),
            patch("src.ui.dialogs.batch.NaverURLParser.fetch_complex_name", side_effect=_slow_fetch),
        ):
            dlg = URLBatchDialog()
            dlg.input_text.setPlainText("dummy")
            dlg._parse_urls()
            self.assertTrue(dlg._parsing)
            dlg._cancel_lookup()

            for _ in range(120):
                self._qt_app.processEvents()
                if not dlg._parsing:
                    break
                time.sleep(0.01)

            self.assertFalse(dlg._parsing)
            self.assertTrue(dlg.btn_parse.isEnabled())
            self.assertFalse(dlg.btn_cancel.isEnabled())

            dlg.deleteLater()
            self._qt_app.processEvents()

    def test_crawler_tab_batch_render_smoke(self):
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab
        from PyQt6.QtWidgets import QLabel

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "test_ui_batch.db"))
            tab = CrawlerTab(db)
            sample = [
                {
                    "단지명": "A단지",
                    "단지ID": "11111",
                    "거래유형": "매매",
                    "매매가": "10억",
                    "보증금": "",
                    "월세": "",
                    "면적(평)": 34.0,
                    "평당가_표시": "2,941만/평",
                    "층/방향": "10/20층 남향",
                    "타입/특징": "올수리",
                    "매물ID": "A1",
                    "수집시각": "2026-02-16 10:00:00",
                },
                {
                    "단지명": "B단지",
                    "단지ID": "22222",
                    "거래유형": "전세",
                    "매매가": "",
                    "보증금": "5억",
                    "월세": "",
                    "면적(평)": 25.0,
                    "평당가_표시": "2,000만/평",
                    "층/방향": "5/15층 동향",
                    "타입/특징": "역세권",
                    "매물ID": "B1",
                    "수집시각": "2026-02-16 10:00:01",
                },
            ]

            tab._on_items_batch(sample)
            self.assertEqual(tab.result_table.rowCount(), 2)
            self.assertEqual(len(tab.collected_data), 2)

            tab._update_stats_ui({
                "total_found": 2,
                "filtered_out": 0,
                "cache_hits": 0,
                "by_trade_type": {"매매": 1, "전세": 1, "월세": 0},
            })
            total_value = tab.summary_card.total_widget.findChild(QLabel, "value")
            self.assertIsNotNone(total_value)
            self.assertEqual(total_value.text(), "2건")

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_database_migration_creates_alert_log_table(self):
        from src.core.database import ComplexDatabase

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "migration_check.db"))
            conn = db._pool.get_connection()
            try:
                row = conn.cursor().execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='article_alert_log'"
                ).fetchone()
            finally:
                db._pool.return_connection(conn)

            self.assertIsNotNone(row)
            db.close()
