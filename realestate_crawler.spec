# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for 네이버 부동산 크롤러 Pro Plus v13.0
Build command: pyinstaller realestate_crawler.spec --clean

v13.0: 모듈화된 구조 지원 (src/ 패키지)
"""

import sys
from pathlib import Path

# collect_all을 사용하여 동적 모듈 수집
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

block_cipher = None

# =============================================================================
# v13.0: 메인 엔트리포인트 변경 (모듈화된 구조)
# =============================================================================
SCRIPT_PATH = 'src/main.py'

# 추가 데이터/바이너리/hiddenimports 수집
datas = []
binaries = []
hiddenimports_extra = []

# =============================================================================
# src 패키지 전체를 데이터로 포함 (모듈 구조 유지)
# =============================================================================
datas += [
    ('src', 'src'),  # src 폴더 전체를 포함
]

# data 폴더가 있다면 포함 (설정 파일 등)
if Path('data').exists():
    datas += [('data', 'data')]

# =============================================================================
# 동적 모듈이 많은 패키지들 자동 수집
# =============================================================================
for pkg in ['undetected_chromedriver', 'selenium', 'openpyxl', 'plyer', 'bs4']:
    try:
        d, b, h = collect_all(pkg)
        datas.extend(d)
        binaries.extend(b)
        hiddenimports_extra.extend(h)
    except Exception as e:
        print(f"[WARN] collect_all failed for {pkg}: {e}")

# matplotlib 서브모듈 수집
try:
    hiddenimports_extra.extend(collect_submodules('matplotlib'))
except Exception as e:
    print(f"[WARN] collect_submodules failed for matplotlib: {e}")

a = Analysis(
    [SCRIPT_PATH],
    pathex=['.'],  # 현재 디렉토리를 경로에 추가
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        # =================================================================
        # v13.0: src 패키지 내부 모듈들 (모듈화된 구조)
        # =================================================================
        'src',
        'src.config',
        'src.main',
        
        # src.crawler 모듈
        'src.crawler',
        'src.crawler.worker',
        'src.crawler.driver',
        'src.crawler.parser',
        'src.crawler.cache',
        'src.crawler.handler',
        
        # src.database 모듈
        'src.database',
        'src.database.connection',
        'src.database.manager',
        
        # src.ui 모듈
        'src.ui',
        'src.ui.window',
        'src.ui.dialogs',
        'src.ui.widgets',
        'src.ui.styles',
        'src.ui.animations',
        
        # src.utils 모듈
        'src.utils',
        'src.utils.logger',
        'src.utils.helpers',
        'src.utils.managers',
        'src.utils.analytics',
        'src.utils.converters',
        'src.utils.paths',
        
        # =================================================================
        # PyQt6 핵심
        # =================================================================
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.sip',
        
        # =================================================================
        # Selenium / undetected_chromedriver 및 의존성
        # =================================================================
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.chrome',
        'selenium.webdriver.chrome.service',
        'selenium.webdriver.chrome.options',
        'selenium.webdriver.common',
        'selenium.webdriver.common.by',
        'selenium.webdriver.common.keys',
        'selenium.webdriver.support',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'selenium.webdriver.remote',
        'selenium.webdriver.remote.webdriver',
        'undetected_chromedriver',
        'undetected_chromedriver.patcher',
        'undetected_chromedriver.options',
        'undetected_chromedriver.webelement',
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
        'websockets',
        
        # =================================================================
        # BeautifulSoup
        # =================================================================
        'bs4',
        'bs4.builder',
        'bs4.builder._html5lib',
        'bs4.builder._htmlparser',
        'bs4.builder._lxml',
        'soupsieve',
        
        # =================================================================
        # openpyxl 전체
        # =================================================================
        'openpyxl',
        'openpyxl.cell',
        'openpyxl.cell.cell',
        'openpyxl.styles',
        'openpyxl.styles.fonts',
        'openpyxl.styles.fills',
        'openpyxl.styles.alignment',
        'openpyxl.utils',
        'openpyxl.utils.cell',
        'openpyxl.workbook',
        'openpyxl.workbook.workbook',
        'openpyxl.worksheet',
        'openpyxl.worksheet.worksheet',
        'openpyxl.writer',
        'openpyxl.writer.excel',
        'et_xmlfile',
        
        # =================================================================
        # matplotlib (PyQt6 호환 백엔드)
        # =================================================================
        'matplotlib',
        'matplotlib.pyplot',
        'matplotlib.backends',
        'matplotlib.backends.backend_qtagg',  # PyQt6용 백엔드
        'matplotlib.backends.backend_qt5agg', # 호환성용
        'matplotlib.backends.backend_agg',
        'matplotlib.figure',
        'matplotlib.dates',
        
        # =================================================================
        # plyer Windows 알림
        # =================================================================
        'plyer',
        'plyer.facades',
        'plyer.facades.notification',
        'plyer.platforms',
        'plyer.platforms.win',
        'plyer.platforms.win.notification',
        
        # =================================================================
        # 표준 라이브러리 (일부 동적 로드)
        # =================================================================
        'sqlite3',
        'json',
        'csv',
        'logging',
        'logging.handlers',
        'webbrowser',
        'queue',
        'pathlib',
        'threading',
        'typing',
        'socket',
        'urllib',
        'urllib.request',
        'urllib.error',
        'html.parser',
        'xml.etree.ElementTree',
        'multiprocessing',
        'io',
        'traceback',
        'random',
        're',
        'datetime',
        'time',
    ] + hiddenimports_extra,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 불필요한 모듈 제외
        'tkinter',
        'unittest',
        'test',
        'xmlrpc',
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
    name='NaverRealEstateCrawler_v13',
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
    icon=None,  # 아이콘 없음 (필요시 icon.ico 경로 지정)
    version=None,
    uac_admin=False,
)

# =============================================================================
# onedir 빌드용 (디버깅/개발용) - 필요시 주석 해제
# =============================================================================
# coll = COLLECT(
#     exe,
#     a.binaries,
#     a.zipfiles,
#     a.datas,
#     strip=False,
#     upx=True,
#     upx_exclude=[],
#     name='NaverRealEstateCrawler_v13',
# )
