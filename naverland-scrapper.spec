# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — slim by default, optional Chromium / Selenium extras.

Design goals (2026-08-05 Fluent; rechecked 2026-08-12 site reform):
  1) Only pull what this app imports (PyQt6, qfluentwidgets, playwright, matplotlib,
     openpyxl, selenium/undetected_chromedriver as optional fallback).
  2) Block accidental ML/data-science packages on polluted PYTHONPATH
     (torch, sklearn, transformers, cv2, dask, pandas, …).
  3) Avoid collect_submodules("playwright") / full selenium.devtools mega-graphs
     unless explicitly requested.
  4) Keep Chromium bundle opt-out for slim artifacts.
  5) 2026-08-12: site_contract / article_api / detail_fetcher / geo markers are pure
     Python under src/ — no extra datas. Analysis follows static imports from app_entry.
     Optional pin below is only a safety net if Analysis pruning ever drops them.

Environment:
  NAVERLAND_ONEFILE=1              → single-file EXE
  NAVERLAND_BUNDLE_CHROMIUM=0      → no Playwright browser datas (slim)
  NAVERLAND_CONSOLE=1              → show console
  NAVERLAND_INCLUDE_SELENIUM=0     → exclude selenium + undetected_chromedriver
  NAVERLAND_INCLUDE_DEVTOOLS=1     → include selenium.webdriver.common.devtools
  NAVERLAND_WINDOWS_ONLY_SELENIUM_MANAGER=1 (default) strip non-Windows selenium managers
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


# NOTE: In PyInstaller 6.x, the spec may be executed via `exec()` without `__file__`.
# Assume the spec is invoked from repository root.
project_dir = Path.cwd().resolve()

# qfluentwidgets is shared by PyQt6-Fluent-Widgets and PySide6-Fluent-Widgets.
# This app uses PyQt6 and excludes PySide6; the PySide6 variant would freeze
# then crash with ModuleNotFoundError: No module named 'PySide6'.
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))
from src.utils.preflight import find_qfluentwidgets_binding_mismatch  # noqa: E402

_qfluent_binding_error = find_qfluentwidgets_binding_mismatch()
if _qfluent_binding_error:
    raise SystemExit(f"[spec] {_qfluent_binding_error}")

build_onefile = os.environ.get("NAVERLAND_ONEFILE", "0") == "1"
bundle_chromium = os.environ.get("NAVERLAND_BUNDLE_CHROMIUM", "1") == "1"
windows_only_selenium_manager = (
    os.environ.get("NAVERLAND_WINDOWS_ONLY_SELENIUM_MANAGER", "1") == "1"
)
enable_console = os.environ.get("NAVERLAND_CONSOLE", "0") == "1"
include_selenium = os.environ.get("NAVERLAND_INCLUDE_SELENIUM", "1") == "1"
include_devtools = os.environ.get("NAVERLAND_INCLUDE_DEVTOOLS", "0") == "1"

app_name = "naverland_onefile" if build_onefile else "naverland"
if not bundle_chromium:
    app_name = f"{app_name}_slim"
if not include_selenium:
    app_name = f"{app_name}_pw"


def _collect_submodules_skip(package: str, *skip_parts: str) -> list[str]:
    try:
        mods = collect_submodules(package)
    except Exception as exc:
        print(f"[spec] collect_submodules({package!r}) failed: {exc}")
        return []
    if not skip_parts:
        return list(mods)
    return [m for m in mods if not any(part in m for part in skip_parts)]


# ── Hidden imports (minimal + intentional) ────────────────────────────
hiddenimports: list[str] = [
    "cryptography.hazmat.backends.openssl",
    "cryptography.hazmat.bindings._rust",
    # Conditional matplotlib backend
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends.backend_agg",
    # plyer notifications (dynamic)
    "plyer",
    "plyer.platforms.win.notification",
    "plyer.platforms.win.libs.balloontip",
    # Fluent (import name qfluentwidgets)
    "qfluentwidgets",
    "qframelesswindow",
    "darkdetect",
]

# Fluent: collect package modules but drop unused multimedia/webengine.
hiddenimports += _collect_submodules_skip(
    "qfluentwidgets", ".multimedia", ".webengine", ".gallery"
)
hiddenimports += _collect_submodules_skip("qframelesswindow", ".webengine")

# Playwright: rely on package hook; only pin entry surfaces we use.
# Full collect_submodules("playwright") pulls huge optional trees.
hiddenimports += [
    "playwright",
    "playwright.sync_api",
    "playwright.async_api",
    "playwright._impl._api_structures",
    "playwright._impl._driver",
]

# Site reform modules (static imports normally suffice; pin for frozen Analysis safety).
hiddenimports += [
    "src.core.services.site_contract",
    "src.core.services.article_api",
    "src.core.services.detail_fetcher",
    "src.core.services.response_capture",
    "src.core.services.map_geometry",
    "src.core.crawl_lock",
]

if include_selenium:
    hiddenimports += [
        "selenium",
        "selenium.webdriver",
        "selenium.webdriver.chrome",
        "selenium.webdriver.chrome.options",
        "selenium.webdriver.chrome.service",
        "selenium.webdriver.common.by",
        "selenium.webdriver.support.ui",
        "selenium.webdriver.support.expected_conditions",
        "undetected_chromedriver",
    ]
    if include_devtools:
        # Large: only when explicitly needed for CDP debugging builds.
        hiddenimports += _collect_submodules_skip("selenium.webdriver.common.devtools")
    # else: do not pin CDP version modules — missing versions become hard Analysis errors.

# Deduplicate while preserving order
_seen: set[str] = set()
_deduped: list[str] = []
for _name in hiddenimports:
    if _name not in _seen:
        _seen.add(_name)
        _deduped.append(_name)
hiddenimports = _deduped

# ── Datas (optional Chromium) ─────────────────────────────────────────
datas: list[tuple[str, str]] = []
runtime_hooks = [str(project_dir / "src" / "utils" / "runtime_playwright.py")]
if bundle_chromium:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser_path = Path(p.chromium.executable_path)
        browser_root = browser_path.parent.parent if browser_path.exists() else None
        if browser_root and browser_root.exists():
            browser_roots: list[Path] = []
            revision = browser_root.name.rsplit("-", 1)[-1] if "-" in browser_root.name else ""
            candidate_names = [browser_root.name]
            if revision:
                candidate_names.append(f"chromium_headless_shell-{revision}")
            for candidate_name in candidate_names:
                candidate_root = browser_root.parent / candidate_name
                if candidate_root.exists() and candidate_root not in browser_roots:
                    browser_roots.append(candidate_root)
                elif candidate_name != browser_root.name:
                    print(f"[spec] Chromium companion browser root was not found: {candidate_root}")
            for root in browser_roots:
                datas.append((str(root), str(Path("ms-playwright") / root.name)))
        else:
            print("[spec] NAVERLAND_BUNDLE_CHROMIUM=1 but Chromium executable was not found.")
    except Exception as exc:
        print(f"[spec] Chromium bundle detection failed: {exc}")

# ── Excludes (aggressive size guard) ──────────────────────────────────
excludes: list[str] = [
    # Dev / test
    "pytest",
    "py",
    "pydoc",
    "doctest",
    "unittest",
    "test",
    "tests",
    "IPython",
    "jupyter",
    "notebook",
    "sphinx",
    # GUI toolkits we do not use
    "tkinter",
    "PySide2",
    "PySide6",
    "PyQt5",
    "wx",
    # Qt modules not required by this app
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebEngineQuick",
    "PyQt6.QtWebChannel",
    "PyQt6.QtBluetooth",
    "PyQt6.QtNfc",
    "PyQt6.QtPositioning",
    "PyQt6.QtSensors",
    "PyQt6.QtSerialPort",
    "PyQt6.QtRemoteObjects",
    "PyQt6.Qt3DCore",
    "PyQt6.Qt3DRender",
    "PyQt6.QtMultimedia",
    "PyQt6.QtMultimediaWidgets",
    "PyQt6.QtPdf",
    "PyQt6.QtPdfWidgets",
    "PyQt6.QtQuick",
    "PyQt6.QtQuickWidgets",
    "PyQt6.QtQml",
    "PyQt6.QtTextToSpeech",
    # Heavy stacks often present on polluted PYTHONPATH
    "torch",
    "torchvision",
    "torchaudio",
    "transformers",
    "tensorflow",
    "keras",
    "sklearn",
    "scikit-learn",
    "cv2",
    "opencv",
    "dask",
    "distributed",
    "pandas",
    "pyarrow",
    "polars",
    "onnxruntime",
    "tensorboard",
    "sympy",
    "numba",
    "llvmlite",
    "skimage",
    "imageio",
    "statsmodels",
    "seaborn",
    "bokeh",
    "plotly",
    "xarray",
    "huggingface_hub",
    "datasets",
    "tokenizers",
    "sentencepiece",
    "langchain",
    "langsmith",
    "openai",
    "anthropic",
    # Optional HTML parsers / servers not required
    "lxml",
    "html5lib",
    "tornado",
    "aiohttp",
    "fastapi",
    "uvicorn",
    "flask",
    "django",
    # Build tools
    "setuptools_scm",
    "cython",
    "Cython",
    "numpy.f2py",
    "numpy.distutils",
    "numpy.tests",
    "numpy.testing",
    "matplotlib.tests",
    "scipy.tests",
    "gi",
]

if not include_selenium:
    excludes += [
        "selenium",
        "undetected_chromedriver",
    ]

# Prefer not pulling scipy if matplotlib can run without it (may still resolve via env).
# Keep scipy excluded; matplotlib Agg/QtAgg usually works without full scipy.
excludes += ["scipy"]


from PyInstaller.building.build_main import Analysis, COLLECT, EXE, PYZ  # noqa: E402


a = Analysis(
    ["app_entry.py"],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={
        # Prefer minimal matplotlib backend discovery when supported.
        "matplotlib": {"backends": "QtAgg,Agg"},
    },
    runtime_hooks=runtime_hooks,
    excludes=excludes,
    noarchive=False,
    optimize=0,
)


def _ban_path(name: str) -> bool:
    """Return True if this TOC entry should be dropped from the bundle."""
    norm = name.replace("\\", "/").lower()
    banned_prefixes = (
        "torch",
        "torchvision",
        "torchaudio",
        "transformers",
        "tensorflow",
        "sklearn",
        "cv2",
        "opencv",
        "dask",
        "pandas",
        "pyarrow",
        "onnxruntime",
        "tensorboard",
        "sympy",
        "numba",
        "skimage",
        "scipy",
        "IPython",
        "jupyter",
        "langsmith",
        "langchain",
        "huggingface",
        "tokenizers",
        "datasets",
        "pyqt6/qt6/qml",
        "pyqt6/qt6/translations",
        "pyqt6/qt6/plugins/sqldrivers",
        "pyqt6/qt6/plugins/geoservices",
        "pyqt6/qt6/plugins/sensors",
        "pyqt6/qt6/plugins/position",
        "pyqt6/qt6/plugins/webview",
        "pyqt6/qt6/plugins/multimedia",
        "pyqt6/qt6/plugins/mediaservice",
        "pyqt6.qtmultimedia",
        "pyqt6.qtwebengine",
        "pyqt6.qtquick",
        "pyqt6.qtqml",
        "pyqt6.qt3d",
        "pyqt6.qtpdf",
        "pyqt6.qtbluetooth",
        "pyqt6.qtsensors",
        "pyqt6.qtpositioning",
        "qfluentwidgets/multimedia",
        "matplotlib/tests",
        "numpy/tests",
        "numpy/f2py",
    )
    if any(norm.startswith(p) or f"/{p}" in f"/{norm}" for p in banned_prefixes):
        return True
    if not include_selenium and (
        norm.startswith("selenium") or "undetected_chromedriver" in norm
    ):
        return True
    return False


def _filter_toc(entries):
    kept = []
    dropped = 0
    for entry in entries:
        # TOC tuples: (name, path, typecode) or similar; name is index 0
        name = entry[0] if isinstance(entry, (list, tuple)) else str(entry)
        if _ban_path(str(name)):
            dropped += 1
            continue
        kept.append(entry)
    if dropped:
        print(f"[spec] Filtered {dropped} heavy/unwanted TOC entries")
    return kept


a.pure = _filter_toc(a.pure)
a.binaries = _filter_toc(a.binaries)
a.datas = _filter_toc(a.datas)

if windows_only_selenium_manager and include_selenium:

    def _keep_windows_selenium_manager(entry: tuple) -> bool:
        dest = entry[0]
        norm = str(dest).replace("\\", "/")
        if norm.startswith("selenium/webdriver/common/macos/"):
            return False
        if norm.startswith("selenium/webdriver/common/linux/"):
            return False
        return True

    a.datas = [e for e in a.datas if _keep_windows_selenium_manager(e)]
    a.binaries = [e for e in a.binaries if _keep_windows_selenium_manager(e)]

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
