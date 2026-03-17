import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils import runtime_playwright


class TestRuntimePlaywright(unittest.TestCase):
    def test_resolve_playwright_browsers_path_prefers_bundled_internal_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe_dir = root / "dist"
            bundled = exe_dir / "_internal" / "ms-playwright"
            bundled.mkdir(parents=True, exist_ok=True)

            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(runtime_playwright.sys, "frozen", True, create=True),
                patch.object(runtime_playwright.sys, "executable", str(exe_dir / "naverland.exe")),
            ):
                resolved = runtime_playwright.resolve_playwright_browsers_path()

            self.assertEqual(resolved, str(bundled))

    def test_resolve_playwright_browsers_path_falls_back_to_localappdata_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe_dir = root / "dist"
            user_cache = root / "LocalAppData" / "ms-playwright"
            user_cache.mkdir(parents=True, exist_ok=True)

            with (
                patch.dict(os.environ, {"LOCALAPPDATA": str(root / "LocalAppData")}, clear=True),
                patch.object(runtime_playwright.sys, "frozen", True, create=True),
                patch.object(runtime_playwright.sys, "executable", str(exe_dir / "naverland.exe")),
            ):
                resolved = runtime_playwright.resolve_playwright_browsers_path()

            self.assertEqual(resolved, str(user_cache))

    def test_configure_playwright_browsers_path_sets_env_when_candidate_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundled = root / "bundle" / "ms-playwright"
            bundled.mkdir(parents=True, exist_ok=True)

            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(runtime_playwright, "_iter_browser_path_candidates", return_value=[bundled]),
            ):
                resolved = runtime_playwright.configure_playwright_browsers_path()
                configured = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")

            self.assertEqual(resolved, str(bundled))
            self.assertEqual(configured, str(bundled))


if __name__ == "__main__":
    unittest.main()
