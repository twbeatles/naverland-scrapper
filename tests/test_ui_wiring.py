import importlib.util
import os
import tempfile
import unittest
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@unittest.skipIf(importlib.util.find_spec("PyQt6") is None, "PyQt6 is not installed")
class TestUIWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls._qt_app = QApplication.instance() or QApplication([])

    def test_crawler_tab_saves_search_history_and_crawl_history(self):
        from src.core.crawler import CrawlerThread
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab

        class _HistoryStub:
            def __init__(self):
                self.calls = []

            def add(self, payload):
                self.calls.append(payload)

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "ui_wiring.db"))
            history = _HistoryStub()
            tab = CrawlerTab(db, history_manager=history)
            tab.add_task("테스트단지", "12345")

            with patch.object(CrawlerThread, "start", return_value=None):
                tab.start_crawling()

            self.assertEqual(len(history.calls), 1)
            self.assertEqual(history.calls[0]["complexes"][0]["cid"], "12345")
            self.assertIn("매매", history.calls[0]["trade_types"])

            tab._on_complex_finished("테스트단지", "12345", "매매,전세", 4)
            rows = db.get_crawl_history(limit=1)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["complex_id"], "12345")
            self.assertEqual(rows[0]["item_count"], 4)

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_crawler_thread_enriches_item_and_emits_alert(self):
        from src.core.crawler import CrawlerThread
        from src.core.database import ComplexDatabase

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "thread_wiring.db"))
            self.assertTrue(
                db.add_alert_setting("12345", "테스트단지", "매매", 10.0, 50.0, 5000, 20000)
            )

            thread = CrawlerThread(
                targets=[],
                trade_types=[],
                area_filter={"enabled": False},
                price_filter={"enabled": False},
                db=db,
                show_new_badge=True,
                show_price_change=True,
                price_change_threshold=0,
                track_disappeared=True,
            )
            alerts = []
            thread.alert_triggered_signal.connect(lambda *args: alerts.append(args))

            item_v1 = {
                "단지명": "테스트단지",
                "단지ID": "12345",
                "매물ID": "A1",
                "거래유형": "매매",
                "매매가": "1억",
                "보증금": "",
                "월세": "",
                "면적(평)": 30.0,
                "층/방향": "10층",
                "타입/특징": "올수리",
            }
            out1 = thread._enrich_item_with_history_and_alerts(dict(item_v1))
            self.assertTrue(out1["is_new"])

            item_v2 = dict(item_v1)
            item_v2["매매가"] = "9,000만"
            out2 = thread._enrich_item_with_history_and_alerts(item_v2)
            self.assertLess(out2["price_change"], 0)
            self.assertGreaterEqual(len(alerts), 1)

            db.close()

    def test_crawler_tab_respects_badge_and_price_change_settings(self):
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "ui_setting_flags.db"))
            tab = CrawlerTab(db)
            sample = {
                "단지명": "A단지",
                "단지ID": "11111",
                "거래유형": "매매",
                "매매가": "1억",
                "보증금": "",
                "월세": "",
                "면적(평)": 34.0,
                "평당가_표시": "2,941만/평",
                "층/방향": "10층 남향",
                "타입/특징": "올수리",
                "매물ID": "A1",
                "수집시각": "2026-02-20 10:00:00",
                "is_new": True,
                "price_change": 500,
            }

            def _get_setting(key, default=None):
                overrides = {
                    "show_new_badge": False,
                    "show_price_change": False,
                    "price_change_threshold": 0,
                }
                return overrides.get(key, default)

            with patch("src.ui.widgets.crawler_tab.settings.get", side_effect=_get_setting):
                tab._append_rows_batch([sample])

            self.assertEqual(tab.result_table.item(0, 7).text(), "1건")
            self.assertEqual(tab.result_table.item(0, 8).text(), "")
            self.assertEqual(tab.result_table.item(0, 9).text(), "")

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_crawler_tab_compacts_same_listing_rows(self):
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "ui_compact_rows.db"))
            tab = CrawlerTab(db)
            tab._compact_duplicates = True

            batch = [
                {
                    "단지명": "A단지",
                    "단지ID": "11111",
                    "거래유형": "매매",
                    "매매가": "10000",
                    "보증금": "",
                    "월세": "",
                    "면적(평)": 34.0,
                    "평당가_표시": "294만/평",
                    "층/방향": "10층 남향",
                    "타입/특징": "올수리",
                    "매물ID": "A1",
                    "수집시각": "2026-02-20 10:00:00",
                    "is_new": False,
                    "price_change": 0,
                },
                {
                    "단지명": "A단지",
                    "단지ID": "11111",
                    "거래유형": "매매",
                    "매매가": "10000",
                    "보증금": "",
                    "월세": "",
                    "면적(평)": 34.0,
                    "평당가_표시": "294만/평",
                    "층/방향": "10층 남향",
                    "타입/특징": "올수리",
                    "매물ID": "A2",
                    "수집시각": "2026-02-20 10:00:01",
                    "is_new": False,
                    "price_change": 0,
                },
            ]
            tab._on_items_batch(batch)
            self.assertEqual(len(tab.collected_data), 2)
            self.assertEqual(tab.result_table.rowCount(), 1)
            self.assertEqual(tab.result_table.item(0, 7).text(), "2건")

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_crawler_tab_chunk_append_and_filter_cache(self):
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "ui_chunk_filter.db"))
            tab = CrawlerTab(db)

            items = []
            for i in range(450):
                feature = "alpha 역세권" if i < 300 else "beta 공원뷰"
                items.append(
                    {
                        "단지명": f"A단지{i}",
                        "단지ID": "11111",
                        "거래유형": "매매",
                        "매매가": "10000",
                        "보증금": "",
                        "월세": "",
                        "면적(평)": 34.0,
                        "평당가_표시": "294만/평",
                        "층/방향": "10층 남향",
                        "타입/특징": feature,
                        "매물ID": f"A{i}",
                        "수집시각": "2026-02-20 10:00:00",
                        "is_new": False,
                        "price_change": 0,
                    }
                )

            tab._pending_search_text = "alpha"
            tab._append_rows_batch(items)
            self.assertEqual(tab.result_table.rowCount(), 450)
            self.assertEqual(len(tab._row_search_cache), 450)

            hidden_alpha = sum(1 for r in range(450) if tab.result_table.isRowHidden(r))
            self.assertEqual(hidden_alpha, 150)

            tab._filter_results("beta")
            hidden_beta = sum(1 for r in range(450) if tab.result_table.isRowHidden(r))
            self.assertEqual(hidden_beta, 300)
            # 반복 필터링에도 상태 일관성 유지
            tab._filter_results("beta")
            hidden_beta_again = sum(1 for r in range(450) if tab.result_table.isRowHidden(r))
            self.assertEqual(hidden_beta_again, 300)

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_crawler_tab_rejects_start_when_thread_running(self):
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab

        class _RunningThread:
            def isRunning(self):
                return True

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "ui_running_guard.db"))
            tab = CrawlerTab(db)
            running_thread = _RunningThread()
            tab.crawler_thread = running_thread

            tab.start_crawling()

            self.assertIs(tab.crawler_thread, running_thread)
            self.assertIn("이미 크롤링이 실행 중", tab.log_browser.toPlainText())

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_crawler_tab_applies_runtime_settings_and_completion_sound(self):
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab

        def _settings_get(key, default=None):
            overrides = {
                "result_filter_debounce_ms": 350,
                "crawl_speed": "느림",
                "default_sort_column": "면적",
                "default_sort_order": "desc",
                "compact_duplicate_listings": True,
                "play_sound_on_complete": True,
            }
            return overrides.get(key, default)

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "ui_runtime_settings.db"))
            tab = CrawlerTab(db)

            with patch("src.ui.widgets.crawler_tab.settings.get", side_effect=_settings_get):
                tab.update_runtime_settings()

            self.assertEqual(tab._search_timer.interval(), 350)
            self.assertEqual(tab.speed_slider.current_speed(), "느림")
            self.assertEqual(tab.combo_sort.currentText(), "면적 ↓")

            tab.crawler_thread = object()
            with (
                patch("src.ui.widgets.crawler_tab.settings.get", side_effect=_settings_get),
                patch("src.ui.widgets.crawler_tab.QApplication.beep") as mock_beep,
                patch.object(tab, "_save_price_snapshots", return_value=None),
            ):
                tab._on_crawl_finished([])

            mock_beep.assert_called_once()
            self.assertIsNone(tab.crawler_thread)

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_app_shortcuts_group_sync_and_safe_minimize(self):
        from src.ui.app import RealEstateApp
        from src.utils.constants import SHORTCUTS

        with patch("src.ui.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            app = RealEstateApp()

        self.assertIn(SHORTCUTS["settings"], app._shortcuts)

        # 트레이 미지원 환경에서도 예외 없이 반환되어야 함
        app._minimize_to_tray()

        app.schedule_group_combo.clear()
        with patch.object(app.db, "get_all_groups", return_value=[(1, "테스트그룹", "")]):
            app.group_tab.groups_updated.emit()
        self.assertEqual(app.schedule_group_combo.count(), 1)

        if hasattr(app, "schedule_timer") and app.schedule_timer:
            app.schedule_timer.stop()
        if hasattr(app, "db") and app.db:
            app.db.close()
        app.deleteLater()
        self._qt_app.processEvents()

    def test_app_shutdown_waits_crawler_before_db_close(self):
        from src.ui.app import RealEstateApp

        with patch("src.ui.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            app = RealEstateApp()

        call_order = []
        with (
            patch.object(
                app.crawler_tab,
                "shutdown_crawl",
                side_effect=lambda timeout_ms=8000: call_order.append("crawler_shutdown") or True,
            ),
            patch.object(app.db, "close", side_effect=lambda: call_order.append("db_close")),
        ):
            app._shutdown()

        self.assertEqual(call_order, ["crawler_shutdown", "db_close"])

        if hasattr(app, "db") and app.db:
            app.db.close()
        app.deleteLater()
        self._qt_app.processEvents()

    def test_close_event_confirmation_and_quit_path(self):
        from PyQt6.QtWidgets import QMessageBox
        from src.ui.app import RealEstateApp

        class _EventStub:
            def __init__(self):
                self.accepted = False
                self.ignored = False

            def accept(self):
                self.accepted = True

            def ignore(self):
                self.ignored = True

        with patch("src.ui.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            app = RealEstateApp()

        def _settings_get(key, default=None):
            overrides = {
                "minimize_to_tray": False,
                "confirm_before_close": True,
            }
            return overrides.get(key, default)

        evt = _EventStub()
        with (
            patch("src.ui.app.settings.get", side_effect=_settings_get),
            patch("src.ui.app.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes) as mock_question,
            patch.object(app, "_shutdown") as mock_shutdown,
        ):
            app.closeEvent(evt)

        self.assertTrue(evt.accepted)
        self.assertFalse(evt.ignored)
        self.assertEqual(mock_question.call_count, 1)
        mock_shutdown.assert_called_once()

        with (
            patch("src.ui.app.QMessageBox.question", side_effect=AssertionError("should not be called")),
            patch.object(app, "_shutdown") as mock_shutdown2,
            patch("src.ui.app.QApplication.quit") as mock_quit,
        ):
            app._quit_app(skip_confirm=True)

        mock_shutdown2.assert_called_once()
        mock_quit.assert_called_once()

        if hasattr(app, "schedule_timer") and app.schedule_timer:
            app.schedule_timer.stop()
        if hasattr(app, "db") and app.db:
            app.db.close()
        app.deleteLater()
        self._qt_app.processEvents()


if __name__ == "__main__":
    unittest.main()
