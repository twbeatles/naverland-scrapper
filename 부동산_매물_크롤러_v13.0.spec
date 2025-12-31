# -*- mode: python ; coding: utf-8 -*-
# 네이버 부동산 크롤러 v13.0 PyInstaller Spec 파일
# 빌드 명령: pyinstaller "부동산_매물_크롤러_v13.0.spec"

import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# 숨겨진 의존성 수집
hiddenimports = [
    # PyQt6
    'PyQt6.QtCore',
    'PyQt6.QtWidgets', 
    'PyQt6.QtGui',
    'PyQt6.sip',
    # 네트워크/브라우저
    'undetected_chromedriver',
    'selenium',
    'selenium.webdriver',
    'selenium.webdriver.chrome',
    'selenium.webdriver.chrome.service',
    'selenium.webdriver.chrome.options',
    'selenium.webdriver.common.by',
    'selenium.webdriver.support.ui',
    'selenium.webdriver.support.expected_conditions',
    # HTML 파싱
    'bs4',
    'beautifulsoup4',
    # 엑셀
    'openpyxl',
    'openpyxl.workbook',
    'openpyxl.utils',
    # 차트 (선택적)
    'matplotlib',
    'matplotlib.pyplot',
    'matplotlib.figure',
    'matplotlib.backends.backend_qt5agg',
    # 알림 (선택적)
    'plyer',
    'plyer.platforms.win.notification',
    # 표준 라이브러리
    'sqlite3',
    'json',
    'csv',
    'logging',
    'logging.handlers',
    'urllib.request',
    'urllib.error',
    'threading',
    'queue',
    'pathlib',
    'datetime',
    'socket',
    'email',
    'email.message',
]

# 제외할 모듈 (용량 최적화)
excludes = [
    'tkinter',
    'test',
    'unittest',
    'pydoc',
    'doctest',
    'numpy.tests',
    'scipy',
    'pandas',
]

a = Analysis(
    ['부동산 매물 크롤러 v13.0.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='네이버부동산크롤러_v13.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI 앱이므로 콘솔 숨김
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 아이콘 파일이 있으면 경로 지정: icon='app.ico'
)
