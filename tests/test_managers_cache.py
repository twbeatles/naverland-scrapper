import os
import sys
import tempfile
import unittest
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.cache import CrawlCache
from src.core.managers import (
    SettingsManager,
    FilterPresetManager,
    SearchHistoryManager,
    RecentlyViewedManager,
)


class TestCacheAndManagers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_crawl_cache_set_get_clear(self):
        cache_path = self.tmp_path / "crawl_cache.json"
        with patch("src.core.cache.CACHE_PATH", cache_path):
            cache = CrawlCache(ttl_minutes=30)
            cache.set("12345", "매매", [{"id": 1}])

            data = cache.get("12345", "매매")
            self.assertIsNotNone(data)
            if data is None:
                self.fail("cache data should not be None")
            self.assertEqual(data[0]["id"], 1)

            cache.clear()
            self.assertIsNone(cache.get("12345", "매매"))

    def test_crawl_cache_write_back_flush(self):
        cache_path = self.tmp_path / "crawl_cache.json"
        with patch("src.core.cache.CACHE_PATH", cache_path):
            cache = CrawlCache(ttl_minutes=30, write_back_interval_sec=999, max_entries=2000)
            with patch.object(cache, "_save", wraps=cache._save) as mock_save:
                for i in range(10):
                    cache.set(f"1{i}", "매매", [{"id": i}])
                self.assertEqual(mock_save.call_count, 0)
                cache.flush()
                self.assertEqual(mock_save.call_count, 1)
                self.assertTrue(cache_path.exists())

    def test_crawl_cache_legacy_items_compatibility(self):
        cache_path = self.tmp_path / "crawl_cache.json"
        legacy_payload = {
            "12345_매매": {
                "cached_at": datetime.now().isoformat(),
                "items": [{"id": 7}],
            }
        }
        cache_path.write_text(json.dumps(legacy_payload, ensure_ascii=False), encoding="utf-8")

        with patch("src.core.cache.CACHE_PATH", cache_path):
            cache = CrawlCache(ttl_minutes=30)
            data = cache.get("12345", "매매")
            self.assertIsNotNone(data)
            self.assertEqual(data[0]["id"], 7)

            cache.set("99999", "매매", [{"id": 9}])
            cache.flush()
            stored = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertIn("raw_items", stored["99999_매매"])
            self.assertNotIn("items", stored["99999_매매"])

    def test_settings_and_preset_and_history_managers(self):
        settings_path = self.tmp_path / "settings.json"
        presets_path = self.tmp_path / "presets.json"
        history_path = self.tmp_path / "search_history.json"

        with (
            patch("src.core.managers.SETTINGS_PATH", settings_path),
            patch("src.core.managers.PRESETS_PATH", presets_path),
            patch("src.core.managers.HISTORY_PATH", history_path),
        ):
            SettingsManager._instance = None
            settings = SettingsManager()
            settings.set("theme", "light")
            self.assertEqual(settings.get("theme"), "light")
            self.assertEqual(settings.get("history_batch_size"), 200)
            self.assertEqual(settings.get("result_filter_debounce_ms"), 220)
            self.assertEqual(settings.get("max_log_lines"), 1500)
            self.assertTrue(settings.get("startup_lazy_noncritical_tabs"))
            self.assertTrue(settings.get("compact_duplicate_listings"))
            settings.update(
                {
                    "history_batch_size": 320,
                    "result_filter_debounce_ms": 260,
                    "max_log_lines": 2400,
                    "startup_lazy_noncritical_tabs": False,
                    "compact_duplicate_listings": False,
                }
            )
            self.assertEqual(settings.get("history_batch_size"), 320)
            self.assertEqual(settings.get("result_filter_debounce_ms"), 260)
            self.assertEqual(settings.get("max_log_lines"), 2400)
            self.assertFalse(settings.get("startup_lazy_noncritical_tabs"))
            self.assertFalse(settings.get("compact_duplicate_listings"))

            presets = FilterPresetManager()
            presets.add("기본", {"trade": "매매"})
            self.assertIn("기본", presets.get_all_names())

            history = SearchHistoryManager(max_items=5)
            history.add({"complexes": ["11111"]})
            self.assertEqual(len(history.get_recent()), 1)

    def test_recently_viewed_manager(self):
        storage_path = self.tmp_path / "recently_viewed.json"
        with patch.object(RecentlyViewedManager, "STORAGE_PATH", storage_path):
            mgr = RecentlyViewedManager()
            mgr.add({"매물ID": "A1", "단지명": "단지A"})
            mgr.add({"매물ID": "A2", "단지명": "단지A"})

            rows = mgr.get_recent(10)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["매물ID"], "A2")


if __name__ == "__main__":
    unittest.main()
