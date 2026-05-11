import importlib.util
import inspect
import unittest


@unittest.skipIf(importlib.util.find_spec("PyQt6") is None, "PyQt6 is not installed")
class TestMixinMethodRebinding(unittest.TestCase):
    @staticmethod
    def _mixin_callable_names(mixin_cls):
        names = []
        for name, raw in mixin_cls.__dict__.items():
            if name.startswith("__"):
                continue
            obj = raw.__func__ if isinstance(raw, (staticmethod, classmethod)) else raw
            if inspect.isfunction(obj):
                names.append(name)
        return names

    def assert_all_mixin_methods_rebound(self, target_cls, mixin_classes):
        missing = []
        for mixin_cls in mixin_classes:
            for name in self._mixin_callable_names(mixin_cls):
                if name not in target_cls.__dict__:
                    missing.append(f"{mixin_cls.__name__}.{name}")
        self.assertEqual(missing, [])

    def test_all_mixin_methods_are_rebound_to_runtime_classes(self):
        from src.core.database import (
            ComplexDatabase,
            ComplexDatabaseAlertOpsMixin,
            ComplexDatabaseArticleOpsMixin,
            ComplexDatabaseBackupRestoreOpsMixin,
            ComplexDatabaseCoercionMixin,
            ComplexDatabaseComplexGroupOpsMixin,
            ComplexDatabaseCrawlSnapshotOpsMixin,
            ComplexDatabaseSchemaMixin,
        )
        from src.core.crawler import (
            CrawlerDomScrollParseMixin,
            CrawlerHistoryAlertsMixin,
            CrawlerSeleniumFlowMixin,
            CrawlerStateRuntimeMixin,
            CrawlerThread,
        )
        from src.core.engines.playwright_engine import (
            PlaywrightComplexModeMixin,
            PlaywrightCrawlerEngine,
            PlaywrightGeoModeMixin,
            PlaywrightRuntimeMixin,
        )
        from src.ui.app import (
            AppDatabaseMaintenanceMixin,
            AppLifecycleMixin,
            AppSettingsPresetMixin,
            AppStatsScheduleMixin,
            AppTabSetupMixin,
            RealEstateApp,
        )
        from src.ui.widgets.crawler_tab import (
            CrawlerTab,
            CrawlerTabCrawlControlMixin,
            CrawlerTabFiltersSearchMixin,
            CrawlerTabIOActionsMixin,
            CrawlerTabResultRenderMixin,
            CrawlerTabUISetupMixin,
        )

        self.assert_all_mixin_methods_rebound(
            ComplexDatabase,
            [
                ComplexDatabaseCoercionMixin,
                ComplexDatabaseSchemaMixin,
                ComplexDatabaseComplexGroupOpsMixin,
                ComplexDatabaseCrawlSnapshotOpsMixin,
                ComplexDatabaseArticleOpsMixin,
                ComplexDatabaseAlertOpsMixin,
                ComplexDatabaseBackupRestoreOpsMixin,
            ],
        )
        self.assert_all_mixin_methods_rebound(
            RealEstateApp,
            [
                AppLifecycleMixin,
                AppTabSetupMixin,
                AppStatsScheduleMixin,
                AppSettingsPresetMixin,
                AppDatabaseMaintenanceMixin,
            ],
        )
        self.assert_all_mixin_methods_rebound(
            CrawlerTab,
            [
                CrawlerTabUISetupMixin,
                CrawlerTabCrawlControlMixin,
                CrawlerTabResultRenderMixin,
                CrawlerTabFiltersSearchMixin,
                CrawlerTabIOActionsMixin,
            ],
        )
        self.assert_all_mixin_methods_rebound(
            CrawlerThread,
            [
                CrawlerStateRuntimeMixin,
                CrawlerHistoryAlertsMixin,
                CrawlerSeleniumFlowMixin,
                CrawlerDomScrollParseMixin,
            ],
        )
        self.assert_all_mixin_methods_rebound(
            PlaywrightCrawlerEngine,
            [
                PlaywrightRuntimeMixin,
                PlaywrightComplexModeMixin,
                PlaywrightGeoModeMixin,
            ],
        )

    def test_crawler_tab_helper_methods_are_rebound(self):
        from src.ui.widgets.crawler_tab import CrawlerTab

        for name in ("_normalize_task_asset_type", "_build_row_searchable_text"):
            self.assertIn(name, CrawlerTab.__dict__)
            self.assertIsNotNone(inspect.getattr_static(CrawlerTab, name, None))

    def test_crawler_thread_target_helpers_are_rebound_and_stale_entry_removed(self):
        from src.core.crawler import CrawlerThread

        for name in ("_normalize_target_asset_type", "_normalize_target_entry", "_iter_targets"):
            self.assertIn(name, CrawlerThread.__dict__)
            self.assertIsNotNone(inspect.getattr_static(CrawlerThread, name, None))
        self.assertNotIn("_is_confirmed_empty_state", CrawlerThread.__dict__)

    def test_playwright_filtered_detail_helper_is_rebound(self):
        from src.core.engines.playwright_engine import PlaywrightCrawlerEngine

        self.assertIn("_process_raw_items_with_filtered_details", PlaywrightCrawlerEngine.__dict__)
        self.assertIsNotNone(
            inspect.getattr_static(PlaywrightCrawlerEngine, "_process_raw_items_with_filtered_details", None)
        )
