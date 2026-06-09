import importlib.util
import inspect
import unittest

from src.utils.mixin_rebind import iter_mixin_callable_names


@unittest.skipIf(importlib.util.find_spec("PyQt6") is None, "PyQt6 is not installed")
class TestMixinMethodRebinding(unittest.TestCase):
    @staticmethod
    def _mixin_callable_names(mixin_cls):
        return iter_mixin_callable_names(mixin_cls)

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

    def test_facade_modules_keep_public_imports(self):
        from src.core.database_parts.article_ops import ComplexDatabaseArticleOpsMixin
        from src.core.database_parts.crawl_snapshot_ops import ComplexDatabaseCrawlSnapshotOpsMixin
        from src.core.database_parts.schema import ComplexDatabaseSchemaMixin
        from src.core.engines.playwright_parts.complex_mode import PlaywrightComplexModeMixin
        from src.core.engines.playwright_parts.geo_mode import PlaywrightGeoModeMixin
        from src.core.engines.playwright_parts.runtime import PlaywrightRuntimeMixin
        from src.core.parser import ArticleLookupBrowserFallbackSession, NaverURLParser
        from src.ui.styles import COLORS, get_stylesheet
        from src.ui.widgets.crawler_tab_parts.crawl_control import CrawlerTabCrawlControlMixin
        from src.ui.widgets.crawler_tab_parts.result_render import CrawlerTabResultRenderMixin
        from src.ui.widgets.crawler_tab_parts.ui_setup import CrawlerTabUISetupMixin
        from src.ui.widgets.dashboard import ArticleCard, CardViewWidget, DashboardWidget, StatCard
        from src.utils.live_smoke import default_live_smoke_urls, run_live_smoke

        public_objects = [
            ComplexDatabaseArticleOpsMixin,
            ComplexDatabaseCrawlSnapshotOpsMixin,
            ComplexDatabaseSchemaMixin,
            PlaywrightComplexModeMixin,
            PlaywrightGeoModeMixin,
            PlaywrightRuntimeMixin,
            ArticleLookupBrowserFallbackSession,
            NaverURLParser,
            COLORS,
            get_stylesheet,
            CrawlerTabCrawlControlMixin,
            CrawlerTabResultRenderMixin,
            CrawlerTabUISetupMixin,
            ArticleCard,
            CardViewWidget,
            DashboardWidget,
            StatCard,
            default_live_smoke_urls,
            run_live_smoke,
        ]
        self.assertTrue(all(obj is not None for obj in public_objects))
