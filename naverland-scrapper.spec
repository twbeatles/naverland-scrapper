# -*- mode: python ; coding: utf-8 -*-

from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


# NOTE: In PyInstaller 6.x, the spec may be executed via `exec()` without `__file__`.
# Assume the spec is invoked from repository root.
# Rechecked on 2026-03-17 (.spec/doc/gitignore/runtime-status/performance consistency pass):
# no extra hidden imports/hooks required.
# Workspace typing/encoding guardrails (`pyrightconfig.json`, `.editorconfig`) and
# UI performance refactors (`src/ui/widgets/cards.py`, dashboard deferred chart init)
# do not require spec changes.
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
