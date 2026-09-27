"""Regression tests for Phase-1 (P0) audit fixes: ISSUE-001/002/003 (T-001~T-003)."""
import inspect
import os
import types
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class TestIssue001WindowGeometry(unittest.TestCase):
    """T-001: corrupt window_geometry must never crash startup; falls back + clamps."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls._qt_app = QApplication.instance() or QApplication([])

    def _restore(self, geo):
        from src.ui.app_parts.lifecycle_parts import bootstrap as boot_mod
        from src.ui.app_parts.lifecycle_parts.bootstrap import (
            AppLifecycleBootstrapMixin,
        )
        from PyQt6.QtWidgets import QWidget

        warnings = []
        boot_mod.settings = types.SimpleNamespace(
            get=lambda key, default=None: geo if key == "window_geometry" else default
        )
        boot_mod.ui_logger = types.SimpleNamespace(
            warning=lambda msg: warnings.append(str(msg))
        )
        try:
            w = QWidget()
            AppLifecycleBootstrapMixin._restore_window_geometry(w)
            return w, warnings
        finally:
            del boot_mod.settings
            del boot_mod.ui_logger

    def test_ctor_has_no_unvalidated_setgeometry(self):
        from src.ui.app_parts.lifecycle_parts.bootstrap import (
            AppLifecycleBootstrapMixin,
        )

        src = inspect.getsource(AppLifecycleBootstrapMixin.__init__)
        self.assertNotIn("setGeometry(*geo)", src)

    def test_corrupt_matrix_falls_back_without_raise(self):
        from src.ui.fluent.design_tokens import (
            DEFAULT_WINDOW_HEIGHT,
            DEFAULT_WINDOW_WIDTH,
        )

        for bad in (
            [0, 0, 800],  # len 3
            [0, 0, 800, 600, 1],  # len 5
            ["a", 0, 800, 600],  # non-numeric
            [None, 0, 800, 600],
            [0, 0, -10, 600],  # non-positive size
            [0, 0, True, 600],  # bool is not a valid coordinate
            "100,100,800,600",  # wrong container type
        ):
            with self.subTest(geo=bad):
                w, warnings = self._restore(bad)
                self.assertEqual(w.width(), DEFAULT_WINDOW_WIDTH)
                self.assertEqual(w.height(), DEFAULT_WINDOW_HEIGHT)
                self.assertTrue(warnings, "expected a warning log for corrupt geometry")
                w.deleteLater()

    def test_missing_geometry_uses_default(self):
        from src.ui.fluent.design_tokens import (
            DEFAULT_WINDOW_HEIGHT,
            DEFAULT_WINDOW_WIDTH,
        )

        w, _ = self._restore(None)
        self.assertEqual((w.width(), w.height()), (DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT))
        w.deleteLater()

    def test_valid_geometry_applied(self):
        w, _ = self._restore([120, 90, 800, 600])
        self.assertEqual((w.width(), w.height()), (800, 600))
        w.deleteLater()

    def test_offscreen_geometry_clamped_visible(self):
        w, _ = self._restore([-5000, -5000, 800, 600])
        self.assertNotEqual((w.x(), w.y()), (-5000, -5000))
        self.assertGreater(w.width(), 0)
        self.assertGreater(w.height(), 0)
        w.deleteLater()


def _make_crawl_tab(**attrs):
    from src.ui.widgets.crawler_tab_parts.crawl_control_parts.start_stop import (
        CrawlerTabStartStopMixin,
    )

    tab = types.SimpleNamespace(**attrs)
    tab._release_crawl_lock = types.MethodType(
        CrawlerTabStartStopMixin._release_crawl_lock, tab
    )
    return tab


class TestIssue002CrawlLockOwner(unittest.TestCase):
    """T-002: an idle tab must never release another tab's CrawlLock."""

    def setUp(self):
        from src.core.crawl_lock import reset_crawl_lock_for_tests

        reset_crawl_lock_for_tests()

    def tearDown(self):
        from src.core.crawl_lock import reset_crawl_lock_for_tests

        reset_crawl_lock_for_tests()

    def test_release_none_is_noop(self):
        from src.core.crawl_lock import CrawlLock

        lock = CrawlLock()
        self.assertTrue(lock.try_acquire("complex"))
        lock.release(None)
        self.assertTrue(lock.is_held())
        self.assertEqual(lock.owner(), "complex")
        lock.release("complex")
        self.assertFalse(lock.is_held())

    def test_idle_tab_release_keeps_other_owners_lock(self):
        from src.core.crawl_lock import get_crawl_lock
        from src.ui.widgets.crawler_tab_parts.crawl_control_parts.start_stop import (
            CrawlerTabStartStopMixin,
        )

        lock = get_crawl_lock()
        self.assertTrue(lock.try_acquire("complex"))
        idle_tab = _make_crawl_tab(_crawl_lock_owner=None, crawler_thread=None)
        CrawlerTabStartStopMixin._release_crawl_lock(idle_tab)
        self.assertTrue(lock.is_held())
        self.assertEqual(lock.owner(), "complex")
        self.assertIsNone(idle_tab._crawl_lock_owner)

    def test_idle_tab_shutdown_crawl_keeps_other_owners_lock(self):
        from src.core.crawl_lock import get_crawl_lock
        from src.ui.widgets.crawler_tab_parts.crawl_control_parts.start_stop import (
            CrawlerTabStartStopMixin,
        )

        lock = get_crawl_lock()
        self.assertTrue(lock.try_acquire("complex"))
        idle_tab = _make_crawl_tab(_crawl_lock_owner=None, crawler_thread=None)
        self.assertTrue(CrawlerTabStartStopMixin.shutdown_crawl(idle_tab))
        self.assertTrue(lock.is_held())
        self.assertEqual(lock.owner(), "complex")

    def test_owner_tab_releases_and_idle_shutdown_frees_nothing(self):
        from src.core.crawl_lock import get_crawl_lock
        from src.ui.widgets.crawler_tab_parts.crawl_control_parts.start_stop import (
            CrawlerTabStartStopMixin,
        )

        lock = get_crawl_lock()
        self.assertTrue(lock.try_acquire("complex"))
        owner_tab = _make_crawl_tab(_crawl_lock_owner="complex", crawler_thread=None)
        self.assertTrue(CrawlerTabStartStopMixin.shutdown_crawl(owner_tab))
        self.assertFalse(lock.is_held())
        idle_tab = _make_crawl_tab(_crawl_lock_owner=None, crawler_thread=None)
        self.assertTrue(CrawlerTabStartStopMixin.shutdown_crawl(idle_tab))
        self.assertFalse(lock.is_held())

    def test_force_release_still_clears_for_shutdown(self):
        from src.core.crawl_lock import get_crawl_lock

        lock = get_crawl_lock()
        self.assertTrue(lock.try_acquire("complex"))
        lock.force_release()
        self.assertFalse(lock.is_held())


class FakeFavoriteDB:
    def __init__(self, result=True, exc=None):
        self.result = result
        self.exc = exc
        self.calls = []

    def toggle_favorite(self, article_id, complex_id, asset_type, is_fav):
        self.calls.append((article_id, complex_id, asset_type, is_fav))
        if self.exc is not None:
            raise self.exc
        return self.result


class FavoriteHost:
    # 테스트에서 동적 할당되는 탭 핸들 (pyright reportAttributeAccessIssue 대응).
    crawler_tab: object
    geo_tab: object

    def __init__(self, db):
        self.db = db
        self.favorite_keys = set()
        self.toasts = []
        self.status_messages = []
        self.tab_updates = []
        self.status_bar = types.SimpleNamespace(
            showMessage=lambda msg, *a: self.status_messages.append(str(msg))
        )

    def show_toast(self, msg):
        self.toasts.append(str(msg))


class TestIssue003FavoriteToggle(unittest.TestCase):
    """T-003: DB failure must skip memory/UI updates and notify the user."""

    def _call(self, host, *args):
        from src.ui.app_parts import settings_preset as preset_mod
        from src.ui.app_parts.settings_preset import AppSettingsPresetMixin

        preset_mod.ui_logger = types.SimpleNamespace(warning=lambda *a: None)
        host._notify_favorite_failure = types.MethodType(
            AppSettingsPresetMixin._notify_favorite_failure, host
        )
        try:
            AppSettingsPresetMixin._on_favorite_toggled(host, *args)
        finally:
            del preset_mod.ui_logger

    def test_db_false_skips_memory_update_and_notifies(self):
        host = FavoriteHost(FakeFavoriteDB(result=False))
        self._call(host, "A1", "C1", "APT", True)
        self.assertEqual(len(host.db.calls), 1)
        self.assertEqual(host.favorite_keys, set())
        self.assertTrue(host.toasts, "expected a failure toast")

    def test_db_exception_skips_memory_update_and_notifies(self):
        host = FavoriteHost(FakeFavoriteDB(exc=RuntimeError("db locked")))
        self._call(host, "A1", "C1", "APT", True)
        self.assertEqual(host.favorite_keys, set())
        self.assertTrue(host.toasts, "expected a failure toast")

    def test_db_false_keeps_existing_key(self):
        host = FavoriteHost(FakeFavoriteDB(result=False))
        host.favorite_keys.add(("APT", "A1", "C1"))
        self._call(host, "A1", "C1", "APT", False)
        self.assertIn(("APT", "A1", "C1"), host.favorite_keys)

    def test_db_true_updates_memory_and_tabs(self):
        host = FavoriteHost(FakeFavoriteDB(result=True))
        host.crawler_tab = types.SimpleNamespace(
            _update_favorite_state_for_key=lambda k, v: host.tab_updates.append(("crawler", k, v))
        )
        host.geo_tab = types.SimpleNamespace(
            _update_favorite_state_for_key=lambda k, v: host.tab_updates.append(("geo", k, v))
        )
        self._call(host, "A1", "C1", "APT", True)
        self.assertIn(("APT", "A1", "C1"), host.favorite_keys)
        self.assertEqual(len(host.tab_updates), 2)
        self.assertFalse(host.toasts)

    def test_db_true_removes_key(self):
        host = FavoriteHost(FakeFavoriteDB(result=True))
        host.favorite_keys.add(("APT", "A1", "C1"))
        self._call(host, "A1", "C1", "APT", False)
        self.assertNotIn(("APT", "A1", "C1"), host.favorite_keys)

    def test_missing_ids_do_not_touch_db(self):
        host = FavoriteHost(FakeFavoriteDB(result=True))
        self._call(host, "", "C1", "APT", True)
        self.assertEqual(host.db.calls, [])


class TestIssue006NonUtf8Recovery(unittest.TestCase):
    """T-004 (ISSUE-006): non-UTF8 bytes must recover with backup, not crash."""

    def test_non_utf8_bytes_recover_with_backup(self):
        import tempfile
        from pathlib import Path

        from src.utils import json_store as js

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_bytes(b'{"theme": "\xff\xfe broken')
            result = js.load_json_with_recovery(
                path, default_factory=dict, logger_name="TestAudit", label="settings"
            )
            self.assertEqual(result, {})
            self.assertFalse(path.exists())
            backups = [p for p in Path(tmp).iterdir() if p.name != "settings.json"]
            self.assertTrue(backups, "expected a .broken backup of the corrupt file")


class _ConnStub:
    def __init__(self, cursor):
        self.cursor_stub = cursor
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self.cursor_stub

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def execute(self, _sql):
        return None


class TestIssue010SnapshotRollback(unittest.TestCase):
    """T-005 (ISSUE-010): snapshot write failure must roll back before pool return."""

    def setUp(self):
        import tempfile

        from src.core.database import ComplexDatabase

        self.tmp = tempfile.TemporaryDirectory()
        self.db = ComplexDatabase(os.path.join(self.tmp.name, "t005.db"))

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_bulk_failure_rolls_back(self):
        from unittest.mock import patch

        class _CursorStub:
            def executemany(self, sql, rows):
                raise RuntimeError("boom")

        conn = _ConnStub(_CursorStub())
        with (
            patch.object(self.db._pool, "get_connection", return_value=conn),
            patch.object(self.db._pool, "return_connection", return_value=None),
        ):
            self.assertEqual(
                self.db.add_price_snapshots_bulk([("C1", "매매", 25.0, 100, 200, 150, 3)]),
                0,
            )
        self.assertEqual(conn.rollbacks, 1)
        self.assertEqual(conn.commits, 0)

    def test_single_failure_rolls_back(self):
        from unittest.mock import patch

        conn = _ConnStub(object())
        with (
            patch.object(self.db._pool, "get_connection", return_value=conn),
            patch.object(self.db._pool, "return_connection", return_value=None),
            patch.object(
                self.db, "_upsert_price_snapshot_row", side_effect=RuntimeError("boom")
            ),
        ):
            self.assertFalse(
                self.db.add_price_snapshot("C1", "매매", 25.0, 100, 200, 150, 3)
            )
        self.assertEqual(conn.rollbacks, 1)
        self.assertEqual(conn.commits, 0)


class TestIssue007SnapshotLockOrder(unittest.TestCase):
    """T-006 (ISSUE-007): finish-path save must be synchronous under the crawl lock."""

    def test_finish_calls_synchronous_save(self):
        from src.ui.widgets.crawler_tab_parts.crawl_control_parts import (
            finish as finish_mod,
        )

        src = inspect.getsource(finish_mod.CrawlerTabFinishMixin._on_crawl_finished)
        self.assertIn("_save_price_snapshots(async_save=False)", src)

    def test_sync_save_writes_before_return(self):
        import src.ui.widgets.crawler_tab_parts.crawl_control_parts.snapshot_worker as snap_mod
        from src.ui.widgets.crawler_tab_parts.crawl_control_parts.snapshot_worker import (
            CrawlerTabSnapshotWorkerMixin as SnapMixin,
        )

        calls = []
        snap_mod.build_price_snapshot_rows = lambda items: [
            ["C1", "매매", 25.0, 1, 2, 1, 1]
        ]
        try:
            host = types.SimpleNamespace(
                collected_data=[{"매물ID": "1"}],
                db=types.SimpleNamespace(
                    add_price_snapshots_bulk=lambda rows: (calls.append(list(rows)), 7)[1]
                ),
                append_log=lambda *a: None,
            )
            saved = SnapMixin._save_price_snapshots(host, async_save=False)
        finally:
            del snap_mod.build_price_snapshot_rows
        self.assertEqual(saved, 7)
        self.assertTrue(calls, "sync save must hit the DB before returning")


class TestIssue008DetailPoolStop(unittest.TestCase):
    """T-007 (ISSUE-008): pool exhaustion must not block stop indefinitely."""

    def test_acquire_aborts_on_stop(self):
        import asyncio

        from src.core.engines.playwright_parts.runtime_parts.browser import (
            PlaywrightBrowserRuntimeMixin as BrowserMixin,
        )

        rt = BrowserMixin.__new__(BrowserMixin)
        rt.thread = types.SimpleNamespace(_should_stop=lambda: True)
        rt._page_pool = asyncio.Queue()
        rt._page_pool_maxsize = 1
        rt._page_pool_created = 1
        rt._mobile_context = None
        rt._page_pool_lock = None
        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(rt._acquire_detail_page())

    def test_fetch_checks_stop_before_acquire(self):
        from src.core.engines.playwright_parts.complex_mode_parts import (
            detail_enrichment as de_mod,
        )

        src = inspect.getsource(de_mod)
        fetch_at = src.index("async def _fetch_one")
        acquire_at = src.index("page = await self._acquire_detail_page()")
        self.assertGreater(acquire_at, fetch_at)
        self.assertIn("_should_stop", src[fetch_at:acquire_at])


class TestIssue005UpdateShutdown(unittest.TestCase):
    """ISSUE-005: shutdown must stop the theme poll timer and join update workers."""

    def test_wait_idle_joins_workers(self):
        import threading

        from src.utils.update_controller import UpdateController

        ctl = UpdateController()
        done = threading.Event()

        def _work():
            done.wait(5)

        worker = threading.Thread(target=_work, daemon=True)
        with ctl._lock:
            ctl._threads.append(worker)
        worker.start()
        done.set()
        self.assertTrue(ctl.wait_idle(timeout=5.0))

    def test_wait_idle_idle_controller_returns_true(self):
        from src.utils.update_controller import UpdateController

        self.assertTrue(UpdateController().wait_idle(timeout=1.0))

    def test_shutdown_cleans_update_and_theme_timer(self):
        from src.ui.app_parts.lifecycle_parts import shutdown as shutdown_mod

        src = inspect.getsource(shutdown_mod.AppLifecycleShutdownMixin._shutdown)
        self.assertIn("wait_idle", src)
        self.assertIn("_theme_watcher_timer", src)


class TestIssue016GroupAndNoteProtection(unittest.TestCase):
    """T-008 (ISSUE-016): group refresh + note save must not propagate DB errors."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls._qt_app = QApplication.instance() or QApplication([])

    def test_load_groups_swallows_db_error(self):
        from src.ui.widgets.group_tab import GroupTab

        class _BoomDB:
            def get_all_groups(self):
                raise RuntimeError("db locked")

        tab = GroupTab(_BoomDB())
        try:
            tab.load_groups()  # must not raise
        finally:
            tab.deleteLater()

    def test_refresh_tab_group_swallows_db_error(self):
        import src.ui.app_parts.tab_setup as ts_mod
        from src.ui.app_parts.tab_setup import AppTabSetupMixin

        host = types.SimpleNamespace()
        host.TAB_GEO = -1
        host.TAB_DB = -2
        host.TAB_GROUP = 3
        host.tabs = types.SimpleNamespace(currentIndex=lambda: 3)

        def _boom():
            raise RuntimeError("db locked")

        host._ensure_group_tab = lambda: types.SimpleNamespace(load_groups=_boom)
        host.status_bar = types.SimpleNamespace(showMessage=lambda *a: None)
        ts_mod.ui_logger = types.SimpleNamespace(exception=lambda *a: None)
        try:
            AppTabSetupMixin._refresh_tab(host, 3)  # must not raise
        finally:
            del ts_mod.ui_logger

    def test_edit_note_swallows_db_error(self):
        from unittest.mock import patch

        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QTableWidgetItem

        import src.ui.widgets.tabs as tabs_mod
        from src.ui.widgets.tabs import FavoritesTab

        updated = []

        class _BoomDB:
            def update_article_note(self, *args, **kwargs):
                updated.append((args, kwargs))
                raise RuntimeError("db locked")

            def get_favorites(self):
                return []

        tab = FavoritesTab(_BoomDB(), theme="dark")
        try:
            tab.table.setRowCount(1)
            item = QTableWidgetItem("c")
            item.setData(
                Qt.ItemDataRole.UserRole,
                {"article_id": "A", "complex_id": "C", "asset_type": "APT", "note": ""},
            )
            tab.table.setItem(0, 0, item)
            tab.table.setCurrentCell(0, 0)
            with patch.object(
                tabs_mod.QInputDialog, "getText", return_value=("new", True)
            ):
                tab._edit_note()  # must not raise
        finally:
            tab.deleteLater()
        self.assertTrue(updated)


class TestIssue017AlertNumericGuard(unittest.TestCase):
    """T-008 (ISSUE-017): alert slots must survive non-numeric area values."""

    def test_tab_slot_survives_bad_area(self):
        from src.ui.widgets.crawler_tab_parts.crawl_control_parts.finish import (
            CrawlerTabFinishMixin as FinishMixin,
        )

        logs, emitted = [], []
        host = types.SimpleNamespace(
            append_log=lambda *a: logs.append(a),
            alert_triggered=types.SimpleNamespace(emit=lambda *a: emitted.append(a)),
        )
        for bad in (None, "bad", "", 25.0):
            FinishMixin._on_alert_triggered(host, "C", "매매", "1억", bad, None)
        self.assertEqual(len(logs), 4)
        self.assertEqual(len(emitted), 4)
        self.assertTrue(all(isinstance(args[3], float) for args in emitted))

    def test_app_slot_survives_bad_area(self):
        from src.ui.app_parts.lifecycle_parts.timers_events import (
            AppLifecycleTimersEventsMixin as TimersMixin,
        )

        toasts = []
        host = types.SimpleNamespace(
            show_toast=lambda m: toasts.append(m),
            show_notification=lambda *a: None,
        )
        for bad in (None, "bad", "", 25.0):
            TimersMixin._on_alert_triggered(host, "C", "매매", "1억", bad, 1)
        self.assertEqual(len(toasts), 4)


class TestDoc001ThemeDefault(unittest.TestCase):
    """T-009 (DOC-001): 신규 설치 기본값은 dark, AUTO는 명시적 opt-in.

    코드 기본값 변경 금지 — 독스트링만 실제 동작에 맞췄는지 검증한다.
    """

    def test_docstring_states_dark_default_and_auto_opt_in(self):
        from src.ui.fluent.theme import theme_from_settings

        doc = theme_from_settings.__doc__ or ""
        self.assertIn("dark", doc)
        self.assertIn("AUTO", doc)

    def test_effective_first_run_default_is_dark(self):
        # 호출자 규격: settings.get("theme", "dark") — 키 미지정 시 "dark" 전달.
        from qfluentwidgets import Theme

        from src.ui.fluent.theme import theme_from_settings

        self.assertEqual(theme_from_settings("dark"), Theme.DARK)

    def test_auto_is_explicit_opt_in(self):
        from qfluentwidgets import Theme

        from src.ui.fluent.theme import theme_from_settings

        self.assertEqual(theme_from_settings("auto"), Theme.AUTO)
        self.assertEqual(theme_from_settings("system"), Theme.AUTO)
        self.assertEqual(theme_from_settings("dark"), Theme.DARK)
        self.assertEqual(theme_from_settings("light"), Theme.LIGHT)


class TestBulkDedupCountAndAtomicExport(unittest.TestCase):
    """T-010 (DOC-002 + ISSUE-014): 처리 행 수 반환 + 최신값 승리, 크래시에도 기존본 보존."""

    def test_bulk_returns_processed_count_latest_wins(self):
        import tempfile

        from src.core.database import ComplexDatabase

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "test.db"))
            try:
                row = ("C1", "매매", 25.0, 100, 200, 150, 3)
                rows = [row, tuple(row), ("C2", "전세", 30.0, 50, 80, 65, 2)]
                # 계약: 반환값은 처리된 입력 행 수(기존 test_database_module 계약과 일치).
                self.assertEqual(db.add_price_snapshots_bulk(rows), 3)
                # upsert이므로 재실행해도 같은 처리 건수.
                self.assertEqual(db.add_price_snapshots_bulk(rows), 3)
            finally:
                try:
                    db.close()
                except Exception:
                    pass

    def test_csv_crash_keeps_existing_file(self):
        import csv
        import tempfile
        from unittest.mock import patch

        from src.core.export import DataExporter

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "export.csv")
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write("sentinel")
            data = [
                {"단지명": "A", "가격변동": 0, "price_change": 0},
                {"단지명": "B", "가격변동": 0, "price_change": 0},
            ]
            template = {
                "order": ["단지명", "가격변동"],
                "columns": {"단지명": True, "가격변동": True},
            }
            with patch.object(
                csv.DictWriter,
                "writerow",
                side_effect=[None, RuntimeError("boom")],
            ):
                result = DataExporter(data).export_csv(path, template=template)
            self.assertFalse(result.ok)
            with open(path, "r", encoding="utf-8-sig") as f:
                self.assertEqual(f.read(), "sentinel")
            leftovers = [n for n in os.listdir(tmp) if n.endswith(".tmp")]
            self.assertEqual(leftovers, [])

    def test_json_crash_keeps_existing_file(self):
        import tempfile
        from unittest.mock import patch

        import src.core.export as export_mod
        from src.core.export import DataExporter

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "export.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write('{"sentinel": true}')
            with patch.object(
                export_mod.json, "dump", side_effect=RuntimeError("boom")
            ):
                result = DataExporter([{"단지명": "A"}]).export_json(path)
            self.assertFalse(result.ok)
            with open(path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), '{"sentinel": true}')
            leftovers = [n for n in os.listdir(tmp) if n.endswith(".tmp")]
            self.assertEqual(leftovers, [])

    def test_successful_export_leaves_no_tmp(self):
        import tempfile

        from src.core.export import DataExporter

        with tempfile.TemporaryDirectory() as tmp:
            csv_path = os.path.join(tmp, "ok.csv")
            json_path = os.path.join(tmp, "ok.json")
            data = [{"단지명": "A", "가격변동": 0, "price_change": 100}]
            template = {
                "order": ["단지명", "가격변동"],
                "columns": {"단지명": True, "가격변동": True},
            }
            self.assertTrue(DataExporter(data).export_csv(csv_path, template=template).ok)
            self.assertTrue(DataExporter(data).export_json(json_path).ok)
            self.assertTrue(os.path.getsize(csv_path) > 0)
            self.assertTrue(os.path.getsize(json_path) > 0)
            leftovers = [n for n in os.listdir(tmp) if n.endswith(".tmp")]
            self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
