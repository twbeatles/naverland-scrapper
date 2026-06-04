# -*- mode: python ; coding: utf-8 -*-

from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


# NOTE: In PyInstaller 6.x, the spec may be executed via `exec()` without `__file__`.
# Assume the spec is invoked from repository root.
# Rechecked on 2026-03-21 (.spec/doc/gitignore/runtime-status/performance refactor pass):
# no extra hidden imports/hooks required.
# Rechecked on 2026-03-25 (repo-wide pyright/encoding/live-smoke consistency pass):
# `app_entry.py --live-smoke`, `.vscode/settings.json`, `pyrightconfig.json`,
# and repo-wide typing/encoding guardrails are runtime/editor-only changes and
# do not require extra PyInstaller datas, hidden imports, or hooks.
# Rechecked on 2026-04-10 (live-site reliability/doc/spec/gitignore pass):
# detail parser front-api mapping, 429 fast-fallback name lookup cooldown,
# expanded live smoke probes/CLI flags, and helper-based URL family cleanup
# remain runtime/UI-only and do not require extra PyInstaller datas, hidden
# imports, or hooks.
# Rechecked on 2026-04-11 (schedule/asset-scope/CI reliability pass):
# actual-start-gated schedule slot consumption, scheduled task snapshot/restore,
# asset-scoped runtime item dedupe, and static-check-only CI policy remain
# runtime/test/documentation-level changes and do not require extra PyInstaller
# datas, hidden imports, or hooks.
# Rechecked on 2026-04-16 (asset-scope/monthly-history/dashboard/doc-sync pass):
# VL houses URL asset preservation, complex task `(asset_type, complex_id)` dedupe,
# scoped disappeared-count dashboard stats, 월세 rent-priority history comparison,
# 즐겨찾기 column cleanup, and GitHub Actions static-check-only policy remain
# runtime/test/documentation-level changes and do not require extra PyInstaller
# datas, hidden imports, or hooks.
# Rechecked on 2026-04-27 (implementation gap closure/doc/spec/gitignore pass):
# scheduled complex Playwright APT/VL loading, Selenium VL exclusion, article-only
# URL reverse lookup, monthly UI rent-priority price metrics, Selenium monthly DOM
# parser fallback, and mixin rebind meta-tests are Python/runtime/test/doc changes
# and do not require extra PyInstaller datas, hidden imports, or hooks.
# Workspace typing/encoding guardrails (`pyrightconfig.json`, `.editorconfig`) and
# UI performance refactors (`src/ui/widgets/cards.py`, dashboard first-open lazy init,
# lightweight startup preflight)
# do not require spec changes.
# Functional reliability changes (monthly snapshot metric split, schedule geo full profile,
# atomic JSON runtime state storage/quarantine, VL houses URL parsing, DB restore crawler
# shutdown hardening) are also Python/runtime-level only and do not require extra
# PyInstaller datas/hooks.
# Rechecked on 2026-05-03 (functional implementation hardening/doc/gitignore/CI pass):
# asset-scoped legacy DB methods, daily-latest price snapshot upserts, schedule hydration
# save guard, filtered-out history/alert exclusion, article-only browser fallback,
# detail metadata preservation/export columns, expanded live smoke JSON logging, and
# core pytest CI subset are Python/runtime/test/documentation changes. Existing
# Playwright hidden imports, runtime hook, and optional Chromium bundle rules remain
# sufficient; no extra PyInstaller datas, hidden imports, or hooks are required.
# Rechecked on 2026-05-04 (implementation review closure/doc deletion/gitignore/build pass):
# Geo marker switch stats exposure, DEFAULT_COLUMNS-based export defaults, expanded
# fast CI subset, confirmed-empty cache refinement, trade-type-scoped history cache,
# and batch article browser fallback session reuse are all Python/runtime/test/doc
# changes. The existing Playwright hidden imports, runtime hook, and Chromium bundle
# collection remain sufficient; no additional datas, hidden imports, or hooks are required.
# Rechecked on 2026-05-11 (live-site sample refresh and functional hardening pass):
# ExportResult, live-smoke sample/article-count checks, `complexNumber` parser support,
# browser-backed name lookup fallback, packaged article fallback local Chrome preference,
# ConnectionPoolCloseResult, analysis asset scope, and mixin rebind meta-tests are all Python/runtime/test/doc changes. Existing
# Playwright hidden imports, runtime hook, and Chromium bundle collection remain
# sufficient; no additional datas, hidden imports, or hooks are required.
# Rechecked on 2026-05-15 (functional risk closure/doc/spec/gitignore/publish pass):
# direct-lookup-only name cooldown, optional `--live-smoke-detail-fields`, smoke
# runtime metadata logging, Geo empty-asset start/save blocking, and manual APT/VL
# selector are Python/runtime/UI/test/doc changes. Existing Playwright hidden
# imports, runtime hook, and Chromium bundle collection remain sufficient; no
# additional datas, hidden imports, or hooks are required.
# Rechecked on 2026-06-04 (functional audit hardening/doc/spec/gitignore/publish pass):
# Selenium fallback prefill finalization, DB rollback guards, CSV/XLSX formula
# escaping, URL batch generation guards, Playwright navigation timeout settings,
# bounded detail enrichment tasks, and Geo empty-asset policy normalization are
# Python/runtime/UI/test/doc changes. Existing Playwright/Selenium hidden imports,
# runtime hook, Chromium bundle collection, and lxml/html5lib exclusions remain
# sufficient; no additional datas, hidden imports, or hooks are required.
# 2026-03-19 functional consistency batch (recently-viewed article-open routing,
# schedule slot/catch-up persistence, dashboard stale-state clear + trend summary,
# deprecated `result_tab_mode` cleanup) is likewise runtime/UI-only and does not
# require additional PyInstaller datas, hidden imports, or hooks.
# 2026-03-21 performance refactor batch (compact dirty-row live rendering,
# lightweight favorite key hydration, hidden-tab stale refresh, perf baseline/doc sync)
# is likewise runtime/UI-only and does not require additional PyInstaller datas,
# hidden imports, or hooks.
project_dir = Path.cwd().resolve()
# Default distribution profile is onedir with bundled Chromium.
# This avoids onefile extraction overhead and matches the current README/doc baseline.
# Force onefile explicitly with NAVERLAND_ONEFILE=1.
build_onefile = os.environ.get("NAVERLAND_ONEFILE", "0") == "1"
# Chromium-bundled build is the default so frozen apps work on machines without
# a preinstalled Playwright browser. Set NAVERLAND_BUNDLE_CHROMIUM=0 for slim builds.
# Runtime preflight still blocks startup when the effective crawl_engine is `playwright`
# and Playwright Chromium is neither installed locally nor bundled.
bundle_chromium = os.environ.get("NAVERLAND_BUNDLE_CHROMIUM", "1") == "1"
windows_only_selenium_manager = os.environ.get("NAVERLAND_WINDOWS_ONLY_SELENIUM_MANAGER", "1") == "1"
# Keep windowed mode by default. Enable console explicitly when debugging startup failures.
enable_console = os.environ.get("NAVERLAND_CONSOLE", "0") == "1"

app_name = "naverland_onefile" if build_onefile else "naverland"
if not bundle_chromium:
    app_name = f"{app_name}_slim"

# Keep hidden-imports minimal but reliable for modules that use dynamic imports.
hiddenimports: list[str] = [
    # Matplotlib Qt backend is imported conditionally in `src/ui/widgets/chart.py`
    # and `src/ui/widgets/dashboard.py`.
    "matplotlib.backends.backend_qtagg",
]
hiddenimports += collect_submodules("undetected_chromedriver")
hiddenimports += collect_submodules("selenium.webdriver.common.devtools")
hiddenimports += collect_submodules("playwright")

datas: list[tuple[str, str]] = []
runtime_hooks = [str(project_dir / "src" / "utils" / "runtime_playwright.py")]
if bundle_chromium:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser_path = Path(p.chromium.executable_path)
        browser_root = browser_path.parent.parent if browser_path.exists() else None
        if browser_root and browser_root.exists():
            # Preserve the browser revision directory so Playwright can still
            # resolve `<PLAYWRIGHT_BROWSERS_PATH>/<revision>/...` at runtime.
            datas.append(
                (
                    str(browser_root),
                    str(Path("ms-playwright") / browser_root.name),
                )
            )
        else:
            print("[spec] NAVERLAND_BUNDLE_CHROMIUM=1 but Chromium executable was not found.")
    except Exception as exc:
        print(f"[spec] Chromium bundle detection failed: {exc}")

# Exclude obviously-unused modules to reduce bundle size.
excludes: list[str] = [
    "matplotlib.tests",
    "numpy.tests",
    "numpy.testing",
    "numpy.f2py",
    "numpy.distutils",
    "pytest",
    "pydoc",
    "tkinter",
    # Test-only plugin; do not bundle into production binary.
    "langsmith",
    "langsmith.pytest_plugin",
    # Optional parsers/backends that get picked up when installed, but are not required by this project.
    "lxml",
    "html5lib",
    "tornado",
    "gi",
    "setuptools_scm",
    "cython",
    "Cython",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebChannel",
]


a = Analysis(
    ["app_entry.py"],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=runtime_hooks,
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

if windows_only_selenium_manager:
    def _keep_windows_selenium_manager(entry: tuple[str, str, str]) -> bool:
        dest, _src, _kind = entry
        norm = dest.replace("\\", "/")
        if norm.startswith("selenium/webdriver/common/macos/"):
            return False
        if norm.startswith("selenium/webdriver/common/linux/"):
            return False
        return True

    a.datas = [entry for entry in a.datas if _keep_windows_selenium_manager(entry)]
    a.binaries = [entry for entry in a.binaries if _keep_windows_selenium_manager(entry)]

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries if build_onefile else [],
    a.datas if build_onefile else [],
    [],
    exclude_binaries=not build_onefile,
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=enable_console,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if not build_onefile:
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name=app_name,
    )
