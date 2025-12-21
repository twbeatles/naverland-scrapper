# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for 네이버 부동산 크롤러 Pro Plus v12.0
Build command: pyinstaller realestate_crawler.spec
"""

import sys
from pathlib import Path

block_cipher = None

# 메인 스크립트 경로
SCRIPT_PATH = '부동산 매물 크롤러 v12.0.py'

a = Analysis(
    [SCRIPT_PATH],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # PyQt6 관련
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.sip',
        # BeautifulSoup
        'bs4',
        'bs4.builder',
        'bs4.builder._html5lib',
        'bs4.builder._htmlparser',
        'bs4.builder._lxml',
        # undetected-chromedriver
        'undetected_chromedriver',
        'undetected_chromedriver.patcher',
        # openpyxl
        'openpyxl',
        'openpyxl.cell',
        'openpyxl.styles',
        'openpyxl.utils',
        # 기타
        'sqlite3',
        'json',
        'csv',
        'logging',
        'logging.handlers',
        'webbrowser',
        # 선택적 의존성
        'plyer',
        'matplotlib',
        'matplotlib.backends.backend_qt5agg',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 불필요한 모듈 제외
        'tkinter',
        'unittest',
        'test',
        'xmlrpc',
        'distutils',
        '_distutils_hack',
        'pkg_resources',
        'setuptools',
        'numpy.random._examples',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='NaverRealEstateCrawler_v12',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI 애플리케이션이므로 콘솔 숨김
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 아이콘 없음 (필요시 .ico 파일 경로 지정)
    version=None,
    uac_admin=False,
)

# onedir 빌드용 (디버깅/개발용)
# coll = COLLECT(
#     exe,
#     a.binaries,
#     a.zipfiles,
#     a.datas,
#     strip=False,
#     upx=True,
#     upx_exclude=[],
#     name='NaverRealEstateCrawler_v12',
# )
