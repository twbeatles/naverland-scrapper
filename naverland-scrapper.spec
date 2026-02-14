# -*- mode: python ; coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


# NOTE: In PyInstaller 6.17, the spec is executed via `exec()` without `__file__`.
# Assume the spec is invoked from repository root.
project_dir = Path.cwd().resolve()

# Keep hidden-imports minimal but reliable for modules that use dynamic imports.
hiddenimports: list[str] = [
    # Matplotlib Qt backend is imported conditionally in `src/ui/widgets/chart.py`.
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends.backend_qt5agg",
]
hiddenimports += collect_submodules("undetected_chromedriver")
hiddenimports += collect_submodules("selenium.webdriver.common.devtools")

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
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="naverland",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="naverland",
)
