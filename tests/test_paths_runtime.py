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

    def test_frozen_runtime_uses_xdg_data_home_on_linux(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe_dir = Path(tmp) / "dist"
            exe_dir.mkdir(parents=True, exist_ok=True)
            exe_path = exe_dir / "naverland"
            exe_path.write_text("", encoding="utf-8")
            xdg_root = Path(tmp) / "xdg-data"
            xdg_root.mkdir(parents=True, exist_ok=True)

            with (
                patch.object(sys, "frozen", True, create=True),
                patch.object(sys, "executable", str(exe_path)),
                patch.object(sys, "platform", "linux"),
                patch.dict(os.environ, {"XDG_DATA_HOME": str(xdg_root)}, clear=False),
            ):
                paths = self._reload_paths()
                self.assertEqual(
                    paths.BASE_DIR,
                    xdg_root / "NaverlandScrapperProPlus",
                )

            self._reload_paths()

    def test_configure_paths_overrides_base_dir_for_sandbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = Path(tmp) / "sandbox-root"
            sandbox.mkdir(parents=True, exist_ok=True)
            paths = self._reload_paths()
            try:
                configured = paths.configure_paths(sandbox)
                self.assertEqual(configured, sandbox)
                self.assertEqual(paths.BASE_DIR, sandbox)
                self.assertEqual(paths.DATA_DIR, sandbox / "data")
                self.assertEqual(paths.SETTINGS_PATH, sandbox / "data" / "settings.json")
            finally:
                paths.reset_configured_paths()
            self._reload_paths()

    def test_apply_runtime_path_overrides_from_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = Path(tmp) / "env-root"
            paths = self._reload_paths()
            try:
                with patch.dict(os.environ, {"NAVERLAND_DATA_DIR": str(sandbox)}, clear=False):
                    configured = paths.apply_runtime_path_overrides_from_env()
                    self.assertEqual(configured, sandbox)
                    self.assertEqual(paths.BASE_DIR, sandbox)
                    self.assertTrue(paths.DATA_DIR.exists())
            finally:
                os.environ.pop("NAVERLAND_DATA_DIR", None)
                paths.reset_configured_paths()
            self._reload_paths()
