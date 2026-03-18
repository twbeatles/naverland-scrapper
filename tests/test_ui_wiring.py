import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _table_text(table, row: int, column: int) -> str:
    item = table.item(row, column)
    assert item is not None
    return item.text()


@unittest.skipIf(importlib.util.find_spec("PyQt6") is None, "PyQt6 is not installed")
class TestUIWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls._qt_app = QApplication.instance() or QApplication([])

    def test_crawler_tab_saves_search_history_and_complex_finished_slot_is_ui_only(self):
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
            self.assertEqual(len(rows), 0)

            self.assertTrue(db.add_crawl_history("테스트단지", "12345", "매매,전세", 4))
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

            self.assertEqual(_table_text(tab.result_table, 0, 7), "1건")
            self.assertEqual(_table_text(tab.result_table, 0, 8), "")
            self.assertEqual(_table_text(tab.result_table, 0, 9), "")

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
            self.assertEqual(_table_text(tab.result_table, 0, 7), "2건")

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

    def test_crawler_tab_db_load_excludes_vl_targets(self):
        from PyQt6.QtWidgets import QDialog
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab

        class _DialogStub:
            def __init__(self, _title, items, _parent):
                self._selected = [payload for _label, payload in items]

            def exec(self):
                return QDialog.DialogCode.Accepted

            def selected_items(self):
                return list(self._selected)

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "ui_db_load_filter.db"))
            db.add_complex("APT단지", "11001", asset_type="APT")
            db.add_complex("VL단지", "11002", asset_type="VL")
            tab = CrawlerTab(db)

            with patch("src.ui.widgets.crawler_tab.MultiSelectDialog", _DialogStub):
                tab._show_db_load_dialog()

            self.assertEqual(tab.table_list.rowCount(), 1)
            self.assertEqual(_table_text(tab.table_list, 0, 1), "11001")
            self.assertIn("APT만 지원", tab.log_browser.toPlainText())

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_crawler_tab_group_load_excludes_vl_targets(self):
        from PyQt6.QtWidgets import QDialog
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab

        class _DialogStub:
            def __init__(self, _title, items, _parent):
                self._selected = [payload for _label, payload in items]

            def exec(self):
                return QDialog.DialogCode.Accepted

            def selected_items(self):
                return list(self._selected)

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "ui_group_load_filter.db"))
            db.add_complex("APT단지", "12001", asset_type="APT")
            db.add_complex("VL단지", "12002", asset_type="VL")
            rows = db.get_all_complexes()
            apt_id = next(int(row["id"]) for row in rows if row["asset_type"] == "APT")
            vl_id = next(int(row["id"]) for row in rows if row["asset_type"] == "VL")
            db.create_group("관심단지", "")
            gid = int(db.get_all_groups()[0]["id"])
            db.add_complexes_to_group(gid, [apt_id, vl_id])

            tab = CrawlerTab(db)
            with patch("src.ui.widgets.crawler_tab.MultiSelectDialog", _DialogStub):
                tab._show_group_load_dialog()

            self.assertEqual(tab.table_list.rowCount(), 1)
            self.assertEqual(_table_text(tab.table_list, 0, 1), "12001")
            self.assertIn("APT만 지원", tab.log_browser.toPlainText())

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_crawler_tab_advanced_filter_applies_and_clears(self):
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "ui_advanced_filter_apply.db"))
            tab = CrawlerTab(db)

            items = [
                {
                    "단지명": "하락단지",
                    "단지ID": "11111",
                    "거래유형": "매매",
                    "매매가": "1억",
                    "보증금": "",
                    "월세": "",
                    "면적(평)": 34.0,
                    "평당가_표시": "294만/평",
                    "층/방향": "10층 남향",
                    "타입/특징": "alpha",
                    "매물ID": "A1",
                    "수집시각": "2026-02-25 10:00:00",
                    "is_new": False,
                    "price_change": -500,
                },
                {
                    "단지명": "상승단지",
                    "단지ID": "11111",
                    "거래유형": "매매",
                    "매매가": "1억 2,000만",
                    "보증금": "",
                    "월세": "",
                    "면적(평)": 35.0,
                    "평당가_표시": "340만/평",
                    "층/방향": "10층 남향",
                    "타입/특징": "beta",
                    "매물ID": "A2",
                    "수집시각": "2026-02-25 10:00:01",
                    "is_new": False,
                    "price_change": 500,
                },
                {
                    "단지명": "무변동단지",
                    "단지ID": "11111",
                    "거래유형": "매매",
                    "매매가": "9,000만",
                    "보증금": "",
                    "월세": "",
                    "면적(평)": 24.0,
                    "평당가_표시": "375만/평",
                    "층/방향": "2층",
                    "타입/특징": "gamma",
                    "매물ID": "A3",
                    "수집시각": "2026-02-25 10:00:02",
                    "is_new": False,
                    "price_change": 0,
                },
            ]

            tab._append_rows_batch(items)
            tab._advanced_filters = {"only_price_down": True}
            tab._filter_results("")

            hidden = sum(1 for r in range(tab.result_table.rowCount()) if tab.result_table.isRowHidden(r))
            self.assertEqual(hidden, 2)

            tab.clear_advanced_filters()
            hidden_after_clear = sum(
                1 for r in range(tab.result_table.rowCount()) if tab.result_table.isRowHidden(r)
            )
            self.assertEqual(hidden_after_clear, 0)

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_crawler_tab_blocks_start_during_maintenance_mode(self):
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "ui_maintenance_guard.db"))
            tab = CrawlerTab(db, maintenance_guard=lambda: True)
            tab.add_task("유지보수단지", "50001")

            with patch("src.ui.widgets.crawler_tab.QMessageBox.warning") as mock_warning:
                tab.start_crawling()

            self.assertIsNone(tab.crawler_thread)
            self.assertIn("유지보수 모드", tab.log_browser.toPlainText())
            mock_warning.assert_not_called()

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

    def test_scheduled_run_skips_when_crawler_already_running(self):
        from src.ui.app import RealEstateApp

        class _RunningThread:
            def isRunning(self):
                return True

        with patch("src.ui.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            app = RealEstateApp()

        app.schedule_group_combo.clear()
        app.schedule_group_combo.addItem("테스트그룹", 10)
        app.crawler_tab.clear_tasks()
        app.crawler_tab.add_task("기존단지", "99999")
        app.crawler_tab.crawler_thread = _RunningThread()

        with (
            patch.object(app.crawler_tab, "clear_tasks", wraps=app.crawler_tab.clear_tasks) as mock_clear,
            patch.object(app.db, "get_complexes_in_group", return_value=[(1, "새단지", "12345", "")]),
            patch.object(app.crawler_tab, "start_crawling") as mock_start,
        ):
            app._run_scheduled()

        self.assertEqual(mock_clear.call_count, 0)
        self.assertEqual(app.crawler_tab.table_list.rowCount(), 1)
        self.assertEqual(_table_text(app.crawler_tab.table_list, 0, 1), "99999")
        mock_start.assert_not_called()

        if hasattr(app, "schedule_timer") and app.schedule_timer:
            app.schedule_timer.stop()
        if hasattr(app, "db") and app.db:
            app.db.close()
        app.deleteLater()
        self._qt_app.processEvents()

    def test_scheduled_run_filters_vl_targets_in_complex_mode(self):
        from src.ui.app import RealEstateApp

        with patch("src.ui.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            app = RealEstateApp()

        app.schedule_group_combo.clear()
        app.schedule_group_combo.addItem("테스트그룹", 10)

        with (
            patch.object(
                app.db,
                "get_complexes_in_group",
                return_value=[
                    (1, "APT단지", "APT", "11111", ""),
                    (2, "VL단지", "VL", "22222", ""),
                ],
            ),
            patch.object(app.crawler_tab, "start_crawling") as mock_start,
        ):
            app._run_scheduled()

        self.assertEqual(app.crawler_tab.table_list.rowCount(), 1)
        self.assertEqual(_table_text(app.crawler_tab.table_list, 0, 1), "11111")
        self.assertIn("APT만 지원", app.crawler_tab.log_browser.toPlainText())
        mock_start.assert_called_once()

        if hasattr(app, "schedule_timer") and app.schedule_timer:
            app.schedule_timer.stop()
        if hasattr(app, "db") and app.db:
            app.db.close()
        app.deleteLater()
        self._qt_app.processEvents()

    def test_scheduled_run_skips_when_group_has_only_vl_targets(self):
        from src.ui.app import RealEstateApp

        with patch("src.ui.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            app = RealEstateApp()

        app.schedule_group_combo.clear()
        app.schedule_group_combo.addItem("테스트그룹", 11)

        with (
            patch.object(
                app.db,
                "get_complexes_in_group",
                return_value=[(1, "VL단지", "VL", "22222", "")],
            ),
            patch.object(app.crawler_tab, "start_crawling") as mock_start,
        ):
            app._run_scheduled()

        self.assertEqual(app.crawler_tab.table_list.rowCount(), 0)
        mock_start.assert_not_called()

        if hasattr(app, "schedule_timer") and app.schedule_timer:
            app.schedule_timer.stop()
        if hasattr(app, "db") and app.db:
            app.db.close()
        app.deleteLater()
        self._qt_app.processEvents()

    def test_app_advanced_filter_wiring_to_crawler_tab(self):
        from src.ui.app import RealEstateApp

        with patch("src.ui.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            app = RealEstateApp()

        with patch.object(app.crawler_tab, "open_advanced_filter_dialog") as mock_open:
            app._show_advanced_filter()

        self.assertIs(app.tabs.currentWidget(), app.crawler_tab)
        mock_open.assert_called_once()

        with patch.object(app.crawler_tab, "clear_advanced_filters") as mock_clear:
            app._clear_advanced_filter()
        mock_clear.assert_called_once()

        if hasattr(app, "schedule_timer") and app.schedule_timer:
            app.schedule_timer.stop()
        if hasattr(app, "db") and app.db:
            app.db.close()
        app.deleteLater()
        self._qt_app.processEvents()

    def test_restore_db_maintenance_and_timer_restart(self):
        from PyQt6.QtWidgets import QMessageBox
        from src.ui.app import RealEstateApp

        class _TimerStub:
            def __init__(self, active=True):
                self.active = active
                self.stop_called = 0
                self.start_calls = []

            def isActive(self):
                return self.active

            def stop(self):
                self.stop_called += 1
                self.active = False

            def start(self, ms):
                self.start_calls.append(ms)
                self.active = True

        with patch("src.ui.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            app = RealEstateApp()
        app.schedule_timer = _TimerStub(active=True)

        restore_path = "C:/tmp/mock_restore.db"
        with (
            patch("src.ui.app.QFileDialog.getOpenFileName", return_value=(restore_path, "Database (*.db)")),
            patch("src.ui.app.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes),
            patch.object(app.crawler_tab, "shutdown_crawl", return_value=True) as mock_shutdown_crawl,
            patch.object(app.geo_tab, "shutdown_crawl", return_value=True) as mock_geo_shutdown,
            patch.object(app.db, "restore_database", return_value=True) as mock_restore,
            patch.object(app, "_load_initial_data") as mock_reload,
            patch("src.ui.app.QMessageBox.information"),
            patch("src.ui.app.QApplication.processEvents", return_value=None),
        ):
            app._restore_db()

        mock_shutdown_crawl.assert_called_once()
        mock_geo_shutdown.assert_called_once()
        mock_restore.assert_called_once_with(Path(restore_path))
        mock_reload.assert_called_once()
        self.assertEqual(app.schedule_timer.stop_called, 1)
        self.assertEqual(app.schedule_timer.start_calls, [60000])
        self.assertFalse(app._maintenance_mode)

        if hasattr(app, "schedule_timer") and app.schedule_timer:
            app.schedule_timer.stop()
        if hasattr(app, "db") and app.db:
            app.db.close()
        app.deleteLater()
        self._qt_app.processEvents()

    def test_restore_db_aborts_when_crawler_shutdown_fails(self):
        from PyQt6.QtWidgets import QMessageBox
        from src.ui.app import RealEstateApp

        class _TimerStub:
            def __init__(self, active=True):
                self.active = active
                self.stop_called = 0
                self.start_calls = []

            def isActive(self):
                return self.active

            def stop(self):
                self.stop_called += 1
                self.active = False

            def start(self, ms):
                self.start_calls.append(ms)
                self.active = True

        with patch("src.ui.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            app = RealEstateApp()
        app.schedule_timer = _TimerStub(active=True)

        with (
            patch("src.ui.app.QFileDialog.getOpenFileName", return_value=("C:/tmp/mock_restore.db", "Database (*.db)")),
            patch("src.ui.app.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes),
            patch.object(app.crawler_tab, "shutdown_crawl", return_value=False),
            patch.object(app.geo_tab, "shutdown_crawl", return_value=True) as mock_geo_shutdown,
            patch.object(app.db, "restore_database") as mock_restore,
            patch("src.ui.app.QMessageBox.warning") as mock_warning,
            patch("src.ui.app.QApplication.processEvents", return_value=None),
        ):
            app._restore_db()

        mock_restore.assert_not_called()
        mock_geo_shutdown.assert_not_called()
        mock_warning.assert_called_once()
        self.assertEqual(app.schedule_timer.start_calls, [60000])
        self.assertFalse(app._maintenance_mode)

        if hasattr(app, "schedule_timer") and app.schedule_timer:
            app.schedule_timer.stop()
        if hasattr(app, "db") and app.db:
            app.db.close()
        app.deleteLater()
        self._qt_app.processEvents()

    def test_restore_db_aborts_when_geo_shutdown_fails(self):
        from PyQt6.QtWidgets import QMessageBox
        from src.ui.app import RealEstateApp

        class _TimerStub:
            def __init__(self, active=True):
                self.active = active
                self.stop_called = 0
                self.start_calls = []

            def isActive(self):
                return self.active

            def stop(self):
                self.stop_called += 1
                self.active = False

            def start(self, ms):
                self.start_calls.append(ms)
                self.active = True

        with patch("src.ui.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            app = RealEstateApp()
        app.schedule_timer = _TimerStub(active=True)

        with (
            patch("src.ui.app.QFileDialog.getOpenFileName", return_value=("C:/tmp/mock_restore.db", "Database (*.db)")),
            patch("src.ui.app.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes),
            patch.object(app.crawler_tab, "shutdown_crawl", return_value=True) as mock_shutdown_crawl,
            patch.object(app.geo_tab, "shutdown_crawl", return_value=False),
            patch.object(app.db, "restore_database") as mock_restore,
            patch("src.ui.app.QMessageBox.warning") as mock_warning,
            patch("src.ui.app.QApplication.processEvents", return_value=None),
        ):
            app._restore_db()

        mock_shutdown_crawl.assert_called_once()
        mock_restore.assert_not_called()
        mock_warning.assert_called_once()
        self.assertEqual(app.schedule_timer.start_calls, [60000])
        self.assertFalse(app._maintenance_mode)

        if hasattr(app, "schedule_timer") and app.schedule_timer:
            app.schedule_timer.stop()
        if hasattr(app, "db") and app.db:
            app.db.close()
        app.deleteLater()
        self._qt_app.processEvents()

    def test_stats_tab_handles_mixed_pyeong_types(self):
        from src.core.database import ComplexDatabase
        from src.ui.app import RealEstateApp

        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "ui_stats_mixed_types.db")

            def _db_factory():
                return ComplexDatabase(db_path)

            with (
                patch("src.ui.app.ComplexDatabase", side_effect=_db_factory),
                patch("src.ui.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False),
            ):
                app = RealEstateApp()

            conn = app.db._pool.get_connection()
            try:
                conn.cursor().execute(
                    "INSERT OR IGNORE INTO complexes (name, complex_id, memo) VALUES (?, ?, ?)",
                    ("테스트단지", "90001", ""),
                )
                conn.cursor().executemany(
                    """
                    INSERT INTO price_snapshots (
                        complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count, snapshot_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        ("90001", "매매", 34.0, 10000, 12000, 11000, 2, "2026-02-24"),
                        ("90001", "매매", "34평", "1억", "1억 2,000만", "1억 1,000만", "3건", "2026-02-25"),
                    ],
                )
                conn.commit()
            finally:
                app.db._pool.return_connection(conn)

            app._load_stats_complexes()
            idx = -1
            for i in range(app.stats_complex_combo.count()):
                data = app.stats_complex_combo.itemData(i)
                if isinstance(data, tuple) and len(data) >= 2 and str(data[1]) == "90001":
                    idx = i
                    break
                if isinstance(data, str):
                    if data == "90001" or data.endswith(":90001"):
                        idx = i
                        break
                if isinstance(data, (tuple, list)) and len(data) >= 1 and str(data[0]).endswith(":90001"):
                    idx = i
                    break
            self.assertGreaterEqual(idx, 0)

            app.stats_complex_combo.setCurrentIndex(idx)
            app._on_stats_complex_changed(idx)

            labels = [app.stats_pyeong_combo.itemText(i) for i in range(app.stats_pyeong_combo.count())]
            self.assertIn("34평", labels)

            app._load_stats()
            self.assertGreaterEqual(app.stats_table.rowCount(), 1)

            if hasattr(app, "schedule_timer") and app.schedule_timer:
                app.schedule_timer.stop()
            if hasattr(app, "db") and app.db:
                app.db.close()
            app.deleteLater()
            self._qt_app.processEvents()

    def test_stats_tab_monthly_metric_selector_defaults_to_rent_and_can_switch_to_deposit(self):
        from src.core.database import ComplexDatabase
        from src.ui.app import RealEstateApp

        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "ui_stats_monthly_metrics.db")

            def _db_factory():
                return ComplexDatabase(db_path)

            with (
                patch("src.ui.app.ComplexDatabase", side_effect=_db_factory),
                patch("src.ui.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False),
            ):
                app = RealEstateApp()
            try:
                self.assertTrue(app.db.add_complex("월세단지", "91001", asset_type="APT"))
                self.assertEqual(
                    app.db.add_price_snapshots_bulk(
                        [
                            ("91001", "월세", 24.0, 50000, 55000, 52500, 2, "APT", "deposit", 0),
                            ("91001", "월세", 24.0, 90, 110, 100, 2, "APT", "rent", 0),
                            ("91001", "월세", 24.0, 40000, 42000, 41000, 1, "APT", "deposit", 1),
                        ]
                    ),
                    3,
                )

                app._load_stats_complexes()
                for i in range(app.stats_complex_combo.count()):
                    data = app.stats_complex_combo.itemData(i)
                    if isinstance(data, tuple) and len(data) >= 2 and str(data[1]) == "91001":
                        app.stats_complex_combo.setCurrentIndex(i)
                        break
                app.stats_type_combo.setCurrentText("월세")
                app._on_stats_complex_changed(app.stats_complex_combo.currentIndex())
                app._load_stats()

                self.assertFalse(app.stats_metric_label.isHidden())
                self.assertFalse(app.stats_metric_combo.isHidden())
                self.assertEqual(app.stats_metric_combo.currentData(), "rent")
                self.assertIn("월세", app.stats_table.horizontalHeaderItem(3).text())
                self.assertEqual(_table_text(app.stats_table, 0, 5), "100")

                app.stats_metric_combo.setCurrentIndex(app.stats_metric_combo.findData("deposit"))
                app._load_stats()

                self.assertEqual(app.stats_metric_combo.currentData(), "deposit")
                self.assertIn("보증금", app.stats_table.horizontalHeaderItem(3).text())
                self.assertEqual(_table_text(app.stats_table, 0, 5), "52500")
            finally:
                if hasattr(app, "schedule_timer") and app.schedule_timer:
                    app.schedule_timer.stop()
                if hasattr(app, "db") and app.db:
                    app.db.close()
                app.deleteLater()
                self._qt_app.processEvents()

    def test_settings_dialog_preserves_zero_values(self):
        from src.ui.dialogs.settings import SettingsDialog

        def _settings_get(key, default=None):
            overrides = {
                "max_retry_count": 0,
                "geo_grid_rings": 0,
            }
            return overrides.get(key, default)

        with patch("src.ui.dialogs.settings.settings.get", side_effect=_settings_get):
            dialog = SettingsDialog()

        self.assertEqual(dialog.spin_max_retry_count.value(), 0)
        self.assertEqual(dialog.spin_geo_rings.value(), 0)

        dialog.deleteLater()
        self._qt_app.processEvents()

    def test_alert_setting_dialog_supports_asset_scope_and_common_rules(self):
        from src.core.database import ComplexDatabase
        from src.ui.dialogs.settings import AlertSettingDialog

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "ui_alert_scope.db"))
            db.add_complex("APT단지", "31001", asset_type="APT")
            db.add_complex("VL단지", "31001", asset_type="VL")

            dialog = AlertSettingDialog(db=db)

            combo_texts = [dialog.combo_complex.itemText(i) for i in range(dialog.combo_complex.count())]
            self.assertIn("APT단지 (APT:31001)", combo_texts)
            self.assertIn("VL단지 (VL:31001)", combo_texts)

            dialog.combo_complex.setCurrentIndex(combo_texts.index("APT단지 (APT:31001)"))
            dialog.check_common_scope.setChecked(True)
            dialog._add()

            rows = db.get_all_alert_settings()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["asset_type"], "ALL")
            self.assertEqual(_table_text(dialog.table, 0, 1), "공통")

            dialog.deleteLater()
            db.close()
            self._qt_app.processEvents()

    def test_crawler_tab_dedupes_same_cid_on_add_and_start(self):
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "ui_task_dedupe.db"))
            tab = CrawlerTab(db)

            self.assertTrue(tab.add_task("첫단지", "12345"))
            self.assertFalse(tab.add_task("둘단지", "12345"))
            self.assertEqual(tab.table_list.rowCount(), 1)
            self.assertEqual(_table_text(tab.table_list, 0, 0), "첫단지")
            self.assertIn("중복 스킵", tab.log_browser.toPlainText())

            tab._append_task_row("레거시중복", "12345")
            self.assertEqual(tab.table_list.rowCount(), 2)

            with patch("src.ui.widgets.crawler_tab.CrawlerThread") as mock_thread_cls:
                tab.start_crawling()

            self.assertEqual(tab.table_list.rowCount(), 1)
            self.assertEqual(mock_thread_cls.call_args.args[0], [("첫단지", "12345")])

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_history_tab_shows_asset_engine_and_mode_columns(self):
        from src.core.database import ComplexDatabase
        from src.ui.app import RealEstateApp

        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "ui_history_metadata.db")

            def _db_factory():
                return ComplexDatabase(db_path)

            with (
                patch("src.ui.app.ComplexDatabase", side_effect=_db_factory),
                patch("src.ui.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False),
            ):
                app = RealEstateApp()

            app.db.add_crawl_history(
                "메타단지",
                "41001",
                "매매",
                3,
                engine="playwright",
                mode="complex",
                asset_type="APT",
            )

            app._load_history()

            self.assertEqual(app.history_table.columnCount(), 9)
            self.assertEqual(_table_text(app.history_table, 0, 0), "메타단지")
            self.assertEqual(_table_text(app.history_table, 0, 2), "APT")
            self.assertEqual(_table_text(app.history_table, 0, 3), "playwright")
            self.assertEqual(_table_text(app.history_table, 0, 4), "complex")
            self.assertEqual(_table_text(app.history_table, 0, 5), "success")

            if hasattr(app, "schedule_timer") and app.schedule_timer:
                app.schedule_timer.stop()
            if hasattr(app, "db") and app.db:
                app.db.close()
            app.deleteLater()
            self._qt_app.processEvents()

    def test_stats_tab_clears_chart_for_multi_series(self):
        from src.core.database import ComplexDatabase
        from src.ui.app import RealEstateApp

        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "ui_stats_multi_series.db")

            def _db_factory():
                return ComplexDatabase(db_path)

            with (
                patch("src.ui.app.ComplexDatabase", side_effect=_db_factory),
                patch("src.ui.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False),
            ):
                app = RealEstateApp()

            conn = app.db._pool.get_connection()
            try:
                conn.cursor().execute(
                    "INSERT OR IGNORE INTO complexes (name, asset_type, complex_id, memo) VALUES (?, ?, ?, ?)",
                    ("복합차트단지", "APT", "92001", ""),
                )
                conn.cursor().executemany(
                    """
                    INSERT INTO price_snapshots (
                        complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count, asset_type, snapshot_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        ("92001", "매매", 34.0, 10000, 12000, 11000, 2, "APT", "2026-03-10"),
                        ("92001", "전세", 34.0, 5000, 7000, 6000, 2, "APT", "2026-03-11"),
                    ],
                )
                conn.commit()
            finally:
                app.db._pool.return_connection(conn)

            app._load_stats_complexes()
            for i in range(app.stats_complex_combo.count()):
                data = app.stats_complex_combo.itemData(i)
                if isinstance(data, tuple) and len(data) >= 2 and str(data[1]) == "92001":
                    app.stats_complex_combo.setCurrentIndex(i)
                    break
            app._load_stats()

            chart_widget = app.chart_widget
            assert chart_widget is not None
            self.assertEqual(
                chart_widget.message_label.text(),
                "차트를 보려면 거래유형과 평형을 하나로 좁혀주세요.",
            )

            if hasattr(app, "schedule_timer") and app.schedule_timer:
                app.schedule_timer.stop()
            if hasattr(app, "db") and app.db:
                app.db.close()
            app.deleteLater()
            self._qt_app.processEvents()

    def test_stats_tab_repeated_entry_after_data_collection(self):
        from src.core.database import ComplexDatabase
        from src.ui.app import RealEstateApp

        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "ui_stats_repeated_entry.db")

            def _db_factory():
                return ComplexDatabase(db_path)

            with (
                patch("src.ui.app.ComplexDatabase", side_effect=_db_factory),
                patch("src.ui.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False),
            ):
                app = RealEstateApp()

            sample_data = [
                {
                    "단지명": "반복진입단지",
                    "단지ID": "99001",
                    "매물ID": "R1",
                    "거래유형": "매매",
                    "매매가": "1억 1,000만",
                    "보증금": "",
                    "월세": "",
                    "면적(평)": 34.0,
                    "층/방향": "10층",
                    "타입/특징": "테스트",
                    "수집시각": "2026-02-25 11:00:00",
                    "is_new": True,
                    "price_change": 0,
                }
            ]
            app._on_crawl_data_collected(sample_data)

            for _ in range(10):
                app.tabs.setCurrentWidget(app.stats_tab)
                app._refresh_tab()
                app.tabs.setCurrentWidget(app.dashboard_tab)
                app._refresh_tab()

            self.assertTrue(True)  # 예외 없이 반복 진입 완료가 목적

            if hasattr(app, "schedule_timer") and app.schedule_timer:
                app.schedule_timer.stop()
            if hasattr(app, "db") and app.db:
                app.db.close()
            app.deleteLater()
            self._qt_app.processEvents()

    def test_stats_tab_accepts_compound_asset_complex_key(self):
        from src.core.database import ComplexDatabase
        from src.ui.app import RealEstateApp

        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "ui_stats_compound_key.db")

            def _db_factory():
                return ComplexDatabase(db_path)

            with (
                patch("src.ui.app.ComplexDatabase", side_effect=_db_factory),
                patch("src.ui.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False),
            ):
                app = RealEstateApp()

            conn = app.db._pool.get_connection()
            try:
                conn.cursor().execute(
                    "INSERT OR IGNORE INTO complexes (name, asset_type, complex_id, memo) VALUES (?, ?, ?, ?)",
                    ("복합키단지", "APT", "90123", ""),
                )
                conn.cursor().execute(
                    """
                    INSERT INTO price_snapshots (
                        complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count, snapshot_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("90123", "매매", 34.0, 10000, 12000, 11000, 2, "2026-02-24"),
                )
                conn.commit()
            finally:
                app.db._pool.return_connection(conn)

            app.stats_complex_combo.clear()
            app.stats_complex_combo.addItem("복합키단지 (APT)", "APT:90123")
            app.stats_complex_combo.setCurrentIndex(0)

            app._on_stats_complex_changed(0)
            app._load_stats()
            self.assertGreaterEqual(app.stats_table.rowCount(), 1)

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
            result = app._shutdown()

        self.assertTrue(result)
        self.assertEqual(call_order, ["crawler_shutdown", "db_close"])

        if hasattr(app, "db") and app.db:
            app.db.close()
        app.deleteLater()
        self._qt_app.processEvents()

    def test_app_shutdown_blocks_db_close_on_crawler_timeout(self):
        from src.ui.app import RealEstateApp

        with patch("src.ui.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            app = RealEstateApp()

        with (
            patch.object(app.crawler_tab, "shutdown_crawl", return_value=False),
            patch.object(app.db, "close") as mock_close,
        ):
            result = app._shutdown()

        self.assertFalse(result)
        self.assertFalse(app._is_shutting_down)
        mock_close.assert_not_called()

        if hasattr(app, "schedule_timer") and app.schedule_timer:
            app.schedule_timer.stop()
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
            patch.object(app, "_shutdown", return_value=True) as mock_shutdown,
        ):
            app.closeEvent(evt)

        self.assertTrue(evt.accepted)
        self.assertFalse(evt.ignored)
        self.assertEqual(mock_question.call_count, 1)
        mock_shutdown.assert_called_once()

        with (
            patch("src.ui.app.QMessageBox.question", side_effect=AssertionError("should not be called")),
            patch.object(app, "_shutdown", return_value=True) as mock_shutdown2,
            patch("src.ui.app.QApplication.quit") as mock_quit,
        ):
            app._quit_app(skip_confirm=True)

        mock_shutdown2.assert_called_once()
        mock_quit.assert_called_once()

        evt2 = _EventStub()
        with (
            patch("src.ui.app.settings.get", side_effect=_settings_get),
            patch("src.ui.app.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes),
            patch.object(app, "_shutdown", return_value=False),
        ):
            app.closeEvent(evt2)
        self.assertFalse(evt2.accepted)
        self.assertTrue(evt2.ignored)

        if hasattr(app, "schedule_timer") and app.schedule_timer:
            app.schedule_timer.stop()
        if hasattr(app, "db") and app.db:
            app.db.close()
        app.deleteLater()
        self._qt_app.processEvents()

    def test_app_shutdown_aborts_when_crawler_shutdown_fails(self):
        from src.ui.app import RealEstateApp

        with patch("src.ui.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            app = RealEstateApp()

        call_order = []
        with (
            patch.object(app.crawler_tab, "shutdown_crawl", return_value=False),
            patch.object(app.db, "close", side_effect=lambda: call_order.append("db_close")),
        ):
            ok = app._shutdown()

        self.assertFalse(ok)
        self.assertEqual(call_order, [])
        self.assertFalse(app._is_shutting_down)

        if hasattr(app, "schedule_timer") and app.schedule_timer:
            app.schedule_timer.stop()
        if hasattr(app, "db") and app.db:
            app.db.close()
        app.deleteLater()
        self._qt_app.processEvents()

    def test_close_event_cancels_when_shutdown_fails(self):
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
                "confirm_before_close": False,
            }
            return overrides.get(key, default)

        evt = _EventStub()
        with (
            patch("src.ui.app.settings.get", side_effect=_settings_get),
            patch.object(app, "_shutdown", return_value=False),
            patch("src.ui.app.QMessageBox.warning") as mock_warning,
        ):
            app.closeEvent(evt)

        self.assertFalse(evt.accepted)
        self.assertTrue(evt.ignored)
        mock_warning.assert_called_once()

        if hasattr(app, "schedule_timer") and app.schedule_timer:
            app.schedule_timer.stop()
        if hasattr(app, "db") and app.db:
            app.db.close()
        app.deleteLater()
        self._qt_app.processEvents()

    def test_crawler_tab_disables_retry_when_retry_setting_off(self):
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "retry_off.db"))
            tab = CrawlerTab(db)
            tab.add_task("테스트단지", "12345")

            def _settings_get(key, default=None):
                overrides = {
                    "retry_on_error": False,
                    "max_retry_count": 7,
                    "cache_enabled": False,
                }
                return overrides.get(key, default)

            with (
                patch("src.ui.widgets.crawler_tab.settings.get", side_effect=_settings_get),
                patch("src.ui.widgets.crawler_tab.CrawlerThread") as mock_thread_cls,
            ):
                tab.start_crawling()

            kwargs = mock_thread_cls.call_args.kwargs
            self.assertEqual(kwargs["max_retry_count"], 0)
            mock_thread_cls.return_value.start.assert_called_once()

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_crawler_tab_accepts_short_manual_complex_id(self):
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "short_manual_id.db"))
            tab = CrawlerTab(db)
            tab.input_name.setText("테스트단지")
            tab.input_id.setText("12")

            with patch("src.ui.widgets.crawler_tab.QMessageBox.warning") as mock_warning:
                tab._add_complex()

            self.assertEqual(tab.table_list.rowCount(), 1)
            self.assertEqual(_table_text(tab.table_list, 0, 0), "테스트단지")
            self.assertEqual(_table_text(tab.table_list, 0, 1), "12")
            mock_warning.assert_not_called()

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_crawler_tab_manual_complex_name_is_optional(self):
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "optional_manual_name.db"))
            tab = CrawlerTab(db)
            tab.input_name.setText("")
            tab.input_id.setText("7")

            with patch("src.ui.widgets.crawler_tab.QMessageBox.warning") as mock_warning:
                tab._add_complex()

            self.assertEqual(tab.table_list.rowCount(), 1)
            self.assertEqual(_table_text(tab.table_list, 0, 0), "단지_7")
            self.assertEqual(_table_text(tab.table_list, 0, 1), "7")
            mock_warning.assert_not_called()

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_crawler_tab_rejects_non_numeric_manual_complex_id(self):
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "invalid_manual_id.db"))
            tab = CrawlerTab(db)
            tab.input_name.setText("테스트단지")
            tab.input_id.setText("12A")

            with patch("src.ui.widgets.crawler_tab.QMessageBox.warning") as mock_warning:
                tab._add_complex()

            self.assertEqual(tab.table_list.rowCount(), 0)
            mock_warning.assert_called_once()

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_crawler_tab_advanced_filter_updates_table_and_card(self):
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "advanced_filter.db"))
            tab = CrawlerTab(db)
            tab.check_compact_duplicates.setChecked(False)

            sample = [
                {
                    "단지명": "A단지",
                    "단지ID": "11111",
                    "거래유형": "매매",
                    "매매가": "10000",
                    "보증금": "",
                    "월세": "",
                    "면적(㎡)": 84.0,
                    "면적(평)": 25.4,
                    "평당가_표시": "394만원",
                    "층/방향": "10층 남향",
                    "타입/특징": "테스트",
                    "매물ID": "A1",
                    "수집시각": "2026-02-20 10:00:00",
                    "is_new": True,
                    "price_change": -100,
                },
                {
                    "단지명": "B단지",
                    "단지ID": "22222",
                    "거래유형": "매매",
                    "매매가": "20000",
                    "보증금": "",
                    "월세": "",
                    "면적(㎡)": 84.0,
                    "면적(평)": 25.4,
                    "평당가_표시": "788만원",
                    "층/방향": "3층 동향",
                    "타입/특징": "테스트",
                    "매물ID": "B1",
                    "수집시각": "2026-02-20 10:00:01",
                    "is_new": False,
                    "price_change": 0,
                },
            ]
            tab._on_items_batch(sample)
            self.assertEqual(tab.result_table.rowCount(), 2)

            filters = {
                "price_min": 0,
                "price_max": 9999999,
                "area_min": 0,
                "area_max": 500,
                "floor_low": True,
                "floor_mid": True,
                "floor_high": True,
                "only_new": True,
                "only_price_down": False,
                "only_price_change": False,
                "include_keywords": [],
                "exclude_keywords": [],
            }
            tab.set_advanced_filters(filters)
            self.assertEqual(tab.result_table.rowCount(), 1)

            tab.btn_view_mode.setChecked(True)
            tab._toggle_view_mode()
            self.assertEqual(len(tab.card_view._all_data), 1)

            tab.set_advanced_filters(None)
            self.assertEqual(tab.result_table.rowCount(), 2)
            self.assertEqual(len(tab.card_view._all_data), 2)

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_crawler_tab_export_scope_preserves_visible_order_and_raw_data(self):
        from PyQt6.QtCore import Qt
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "ui_export_scope.db"))
            tab = CrawlerTab(db)

            items = [
                {
                    "단지명": "Alpha단지",
                    "단지ID": "70001",
                    "거래유형": "매매",
                    "매매가": "10000",
                    "보증금": "",
                    "월세": "",
                    "면적(평)": 30.0,
                    "평당가_표시": "333만",
                    "층/방향": "10층",
                    "타입/특징": "alpha",
                    "매물ID": "A1",
                    "수집시각": "2026-03-15 10:00:00",
                    "자산유형": "APT",
                },
                {
                    "단지명": "Beta단지",
                    "단지ID": "70002",
                    "거래유형": "매매",
                    "매매가": "30000",
                    "보증금": "",
                    "월세": "",
                    "면적(평)": 30.0,
                    "평당가_표시": "1000만",
                    "층/방향": "11층",
                    "타입/특징": "beta",
                    "매물ID": "A2",
                    "수집시각": "2026-03-15 10:00:01",
                    "자산유형": "APT",
                },
            ]

            tab._on_items_batch(items)
            tab.result_table.sortItems(tab.COL_PRICE_SORT, Qt.SortOrder.DescendingOrder)

            visible = tab._export_items_for_scope("visible")
            raw = tab._export_items_for_scope("raw")

            self.assertEqual([item["매물ID"] for item in visible], ["A2", "A1"])
            self.assertEqual([item["매물ID"] for item in raw], ["A1", "A2"])

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_crawler_tab_renders_favorites_with_asset_scoped_keys(self):
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "ui_favorite_scope.db"))
            tab = CrawlerTab(db)
            tab.view_mode = "card"
            tab.favorite_keys_provider = lambda: {("VL", "A1", "71001")}
            tab.collected_data = [
                {
                    "단지명": "Scope단지",
                    "단지ID": "71001",
                    "거래유형": "매매",
                    "매매가": "10000",
                    "보증금": "",
                    "월세": "",
                    "면적(평)": 30.0,
                    "평당가_표시": "333만",
                    "층/방향": "10층",
                    "타입/특징": "apt",
                    "매물ID": "A1",
                    "수집시각": "2026-03-15 10:00:00",
                    "자산유형": "APT",
                },
                {
                    "단지명": "Scope단지",
                    "단지ID": "71001",
                    "거래유형": "매매",
                    "매매가": "10000",
                    "보증금": "",
                    "월세": "",
                    "면적(평)": 30.0,
                    "평당가_표시": "333만",
                    "층/방향": "10층",
                    "타입/특징": "vl",
                    "매물ID": "A1",
                    "수집시각": "2026-03-15 10:00:01",
                    "자산유형": "VL",
                },
            ]

            tab._rebuild_result_views_from_collected_data()

            rendered = {
                (row["자산유형"], bool(row.get("is_favorite")))
                for row in tab.card_view._all_data
            }
            self.assertIn(("APT", False), rendered)
            self.assertIn(("VL", True), rendered)

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_scheduled_geo_run_uses_schedule_geo_profile_without_overwriting_last_manual_coords(self):
        from src.ui.app import RealEstateApp

        with patch("src.ui.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            app = RealEstateApp()

        with (
            patch("src.ui.app.settings.update", return_value=None),
            patch.object(app.geo_tab, "_save_last_geo_coordinates") as mock_save_last,
            patch.object(app.geo_tab, "start_crawling") as mock_geo_start,
            patch.object(app.crawler_tab, "start_crawling") as mock_complex_start,
        ):
            app.schedule_mode_combo.setCurrentIndex(app.schedule_mode_combo.findData("geo_sweep"))
            app.schedule_geo_lat.setValue(37.4321)
            app.schedule_geo_lon.setValue(127.1234)
            app.schedule_geo_zoom.setValue(14)
            app.schedule_geo_rings.setValue(2)
            app.schedule_geo_step.setValue(360)
            app.schedule_geo_dwell.setValue(900)
            app.schedule_geo_asset_apt.setChecked(False)
            app.schedule_geo_asset_vl.setChecked(True)
            app._run_scheduled()

        self.assertAlmostEqual(app.geo_tab.spin_lat.value(), 37.4321, places=4)
        self.assertAlmostEqual(app.geo_tab.spin_lon.value(), 127.1234, places=4)
        self.assertEqual(app.geo_tab.spin_zoom.value(), 14)
        self.assertEqual(app.geo_tab.spin_rings.value(), 2)
        self.assertEqual(app.geo_tab.spin_step.value(), 360)
        self.assertEqual(app.geo_tab.spin_dwell.value(), 900)
        self.assertFalse(app.geo_tab.check_asset_apt.isChecked())
        self.assertTrue(app.geo_tab.check_asset_vl.isChecked())
        mock_save_last.assert_not_called()
        mock_geo_start.assert_called_once()
        mock_complex_start.assert_not_called()

        if hasattr(app, "schedule_timer") and app.schedule_timer:
            app.schedule_timer.stop()
        if hasattr(app, "db") and app.db:
            app.db.close()
        app.deleteLater()
        self._qt_app.processEvents()


if __name__ == "__main__":
    unittest.main()
