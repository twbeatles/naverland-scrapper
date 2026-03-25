import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.preflight import (
    find_conflict_markers,
    find_missing_dependencies,
    get_effective_crawl_engine,
    run_preflight_checks,
)


class TestPreflight(unittest.TestCase):
    def test_find_conflict_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src_dir = base / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            ok_file = src_dir / "ok.py"
            bad_file = src_dir / "bad.py"

            ok_file.write_text("print(1)\n", encoding="utf-8")
            bad_file.write_text(
                "<<<<<<< HEAD\nprint(1)\n=======\nprint(2)\n>>>>>>> x\n",
                encoding="utf-8",
            )

            found = find_conflict_markers(base, ["src"])
            self.assertEqual(found, ["src/bad.py"])

    def test_find_missing_dependencies(self):
        missing = find_missing_dependencies(["json", "package_that_does_not_exist_123"])
        self.assertIn("package_that_does_not_exist_123", missing)
        self.assertNotIn("json", missing)

    def test_run_preflight_checks_failure_on_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src_dir = base / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            (src_dir / "bad.py").write_text(
                "<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n",
                encoding="utf-8",
            )

            ok, errors = run_preflight_checks(
                base_dir=base,
                data_dir=base / "data",
                log_dir=base / "logs",
            )
            self.assertFalse(ok)
            self.assertTrue(any("머지 충돌" in err for err in errors))

    def test_get_effective_crawl_engine_defaults_to_playwright_on_missing_or_invalid_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "settings.json"
            self.assertEqual(get_effective_crawl_engine(settings_path), "playwright")
            settings_path.write_text("{invalid", encoding="utf-8")
            self.assertEqual(get_effective_crawl_engine(settings_path), "playwright")

    def test_run_preflight_checks_fails_when_playwright_engine_requires_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_dir = base / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "settings.json").write_text('{"crawl_engine": "playwright"}', encoding="utf-8")
            with (
                patch("src.utils.preflight.find_conflict_markers", return_value=[]),
                patch("src.utils.preflight.find_missing_dependencies", return_value=[]),
                patch("src.utils.preflight.find_internal_import_failures", return_value=[]),
                patch("src.utils.preflight.find_missing_playwright_browser", return_value="chromium"),
                patch.dict(
                    os.environ,
                    {
                        "NAVERLAND_SKIP_PLAYWRIGHT_BROWSER_CHECK": "",
                        "NAVERLAND_REQUIRE_PLAYWRIGHT_BROWSER": "",
                    },
                    clear=False,
                ),
            ):
                ok, errors = run_preflight_checks(
                    base_dir=base,
                    data_dir=data_dir,
                    log_dir=base / "logs",
                )
            self.assertFalse(ok)
            self.assertTrue(any("Playwright 브라우저" in err for err in errors))

    def test_run_preflight_checks_accepts_local_chrome_without_playwright_chromium(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_dir = base / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "settings.json").write_text('{"crawl_engine": "playwright"}', encoding="utf-8")
            with (
                patch("src.utils.preflight.find_conflict_markers", return_value=[]),
                patch("src.utils.preflight.find_missing_dependencies", return_value=[]),
                patch("src.utils.preflight.find_internal_import_failures", return_value=[]),
                patch("src.utils.preflight.ChromeParamHelper.get_chrome_executable_path", return_value="C:\\Chrome\\chrome.exe"),
                patch("src.utils.preflight.find_missing_playwright_browser", return_value=""),
                patch.dict(
                    os.environ,
                    {
                        "NAVERLAND_SKIP_PLAYWRIGHT_BROWSER_CHECK": "",
                        "NAVERLAND_REQUIRE_PLAYWRIGHT_BROWSER": "",
                    },
                    clear=False,
                ),
            ):
                ok, errors = run_preflight_checks(
                    base_dir=base,
                    data_dir=data_dir,
                    log_dir=base / "logs",
                )
            self.assertTrue(ok)
            self.assertEqual(errors, [])

    def test_run_preflight_checks_warns_only_when_effective_engine_is_selenium(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_dir = base / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "settings.json").write_text('{"crawl_engine": "selenium"}', encoding="utf-8")
            with (
                patch("src.utils.preflight.find_conflict_markers", return_value=[]),
                patch("src.utils.preflight.find_missing_dependencies", return_value=[]),
                patch("src.utils.preflight.find_internal_import_failures", return_value=[]),
                patch("src.utils.preflight.find_missing_playwright_browser", return_value="chromium"),
                patch.dict(
                    os.environ,
                    {
                        "NAVERLAND_SKIP_PLAYWRIGHT_BROWSER_CHECK": "",
                        "NAVERLAND_REQUIRE_PLAYWRIGHT_BROWSER": "",
                    },
                    clear=False,
                ),
            ):
                ok, errors = run_preflight_checks(
                    base_dir=base,
                    data_dir=data_dir,
                    log_dir=base / "logs",
                )
            self.assertTrue(ok)
            self.assertEqual(errors, [])

    def test_run_preflight_checks_skip_env_overrides_require_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_dir = base / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "settings.json").write_text('{"crawl_engine": "playwright"}', encoding="utf-8")
            with (
                patch("src.utils.preflight.find_conflict_markers", return_value=[]),
                patch("src.utils.preflight.find_missing_dependencies", return_value=[]),
                patch("src.utils.preflight.find_internal_import_failures", return_value=[]),
                patch("src.utils.preflight.find_missing_playwright_browser") as browser_check,
                patch.dict(
                    os.environ,
                    {
                        "NAVERLAND_SKIP_PLAYWRIGHT_BROWSER_CHECK": "1",
                        "NAVERLAND_REQUIRE_PLAYWRIGHT_BROWSER": "1",
                    },
                    clear=False,
                ),
            ):
                ok, errors = run_preflight_checks(
                    base_dir=base,
                    data_dir=data_dir,
                    log_dir=base / "logs",
                )
            browser_check.assert_not_called()
            self.assertTrue(ok)
            self.assertEqual(errors, [])

    def test_startup_profile_skips_internal_import_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_dir = base / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            with (
                patch("src.utils.preflight.find_conflict_markers", return_value=[]),
                patch("src.utils.preflight.find_missing_dependencies", return_value=[]),
                patch("src.utils.preflight.find_internal_import_failures") as import_smoke,
                patch("src.utils.preflight.find_missing_playwright_browser", return_value=""),
            ):
                ok, errors = run_preflight_checks(
                    base_dir=base,
                    data_dir=data_dir,
                    log_dir=base / "logs",
                    profile="startup",
                )
            import_smoke.assert_not_called()
            self.assertTrue(ok)
            self.assertEqual(errors, [])

    def test_full_profile_keeps_internal_import_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_dir = base / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            with (
                patch("src.utils.preflight.find_conflict_markers", return_value=[]),
                patch("src.utils.preflight.find_missing_dependencies", return_value=[]),
                patch("src.utils.preflight.find_internal_import_failures", return_value=[]) as import_smoke,
                patch("src.utils.preflight.find_missing_playwright_browser", return_value=""),
            ):
                ok, errors = run_preflight_checks(
                    base_dir=base,
                    data_dir=data_dir,
                    log_dir=base / "logs",
                    profile="full",
                )
            import_smoke.assert_called_once()
            self.assertTrue(ok)
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
