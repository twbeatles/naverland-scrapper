import importlib
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestRuntimePaths(unittest.TestCase):
    def _reload_paths(self):
        import src.utils.paths as paths

        return importlib.reload(paths)

    def test_frozen_runtime_uses_local_appdata_base_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe_dir = Path(tmp) / "dist"
            exe_dir.mkdir(parents=True, exist_ok=True)
            exe_path = exe_dir / "naverland.exe"
            exe_path.write_text("", encoding="utf-8")
            appdata_root = Path(tmp) / "LocalAppData"
            appdata_root.mkdir(parents=True, exist_ok=True)

            with (
                patch.object(sys, "frozen", True, create=True),
                patch.object(sys, "executable", str(exe_path)),
                patch.dict(os.environ, {"LOCALAPPDATA": str(appdata_root)}, clear=False),
            ):
                paths = self._reload_paths()
                self.assertEqual(
                    paths.BASE_DIR,
                    appdata_root / "NaverlandScrapperProPlus",
                )
                self.assertEqual(paths.DATA_DIR, paths.BASE_DIR / "data")
                self.assertEqual(paths.LOG_DIR, paths.BASE_DIR / "logs")

            self._reload_paths()

    def test_ensure_directories_migrates_valid_legacy_frozen_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe_dir = Path(tmp) / "dist"
            legacy_data_dir = exe_dir / "data"
            legacy_data_dir.mkdir(parents=True, exist_ok=True)
            exe_path = exe_dir / "naverland.exe"
            exe_path.write_text("", encoding="utf-8")
            appdata_root = Path(tmp) / "LocalAppData"
            appdata_root.mkdir(parents=True, exist_ok=True)

            legacy_db = legacy_data_dir / "complexes.db"
            conn = sqlite3.connect(str(legacy_db))
            try:
                conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)")
                conn.execute("INSERT INTO sample (name) VALUES ('legacy')")
                conn.commit()
            finally:
                conn.close()

            with (
                patch.object(sys, "frozen", True, create=True),
                patch.object(sys, "executable", str(exe_path)),
                patch.dict(os.environ, {"LOCALAPPDATA": str(appdata_root)}, clear=False),
            ):
                paths = self._reload_paths()
                paths.ensure_directories()

                migrated_db = paths.DATA_DIR / "complexes.db"
                self.assertTrue(migrated_db.exists())
                check_conn = sqlite3.connect(str(migrated_db))
                try:
                    row = check_conn.execute("SELECT name FROM sample").fetchone()
                finally:
                    check_conn.close()
                self.assertEqual(row[0], "legacy")

            self._reload_paths()
