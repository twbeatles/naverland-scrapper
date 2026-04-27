import importlib.util
import inspect
import unittest


@unittest.skipIf(importlib.util.find_spec("PyQt6") is None, "PyQt6 is not installed")
class TestMixinMethodRebinding(unittest.TestCase):
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

