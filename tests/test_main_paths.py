import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils import paths


class TestMainPaths(unittest.TestCase):
    def test_bootstrap_runtime_paths_creates_data_and_log_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = Path(tmp) / "bootstrap-root"
            try:
                with patch.dict(os.environ, {"NAVERLAND_DATA_DIR": str(sandbox)}, clear=False):
                    base = paths.bootstrap_runtime_paths()
                    self.assertEqual(base, sandbox)
                    self.assertTrue(paths.get_data_dir().exists())
                    self.assertTrue(paths.get_log_dir().exists())
            finally:
                os.environ.pop("NAVERLAND_DATA_DIR", None)
                paths.reset_configured_paths()

    def test_path_getters_follow_configured_base_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = Path(tmp) / "getter-root"
            sandbox.mkdir(parents=True, exist_ok=True)
            try:
                paths.configure_paths(sandbox)
                self.assertEqual(paths.get_data_dir(), sandbox / "data")
                self.assertEqual(paths.get_log_dir(), sandbox / "logs")
                self.assertEqual(paths.get_db_path(), sandbox / "data" / "complexes.db")
                self.assertEqual(paths.get_settings_path(), sandbox / "data" / "settings.json")
                self.assertEqual(paths.get_presets_path(), sandbox / "data" / "presets.json")
                self.assertEqual(paths.get_cache_path(), sandbox / "data" / "crawl_cache.json")
                self.assertEqual(paths.get_history_path(), sandbox / "data" / "search_history.json")
            finally:
                paths.reset_configured_paths()


if __name__ == "__main__":
    unittest.main()