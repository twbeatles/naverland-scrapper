# -*- mode: python ; coding: utf-8 -*-
# 네이버 부동산 크롤러 v14.0 PyInstaller Spec 파일 (모듈화 버전)
# 빌드 명령: pyinstaller naverland_crawler.spec

import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# ============================================================
# 빌드 모드 설정
# ============================================================
ONEFILE = True  # True: 단일 exe 파일, False: 폴더 구조

# ============================================================
# 숨겨진 의존성 (필수 모듈)
# ============================================================
hiddenimports = [
    # PyQt6 (필수)
    'PyQt6.QtCore',
    'PyQt6.QtWidgets', 
    'PyQt6.QtGui',
    'PyQt6.sip',
    
    # 프로젝트 모듈 (src/)
    'src',
    'src.main',
    'src.core',
    'src.core.crawler',
    'src.core.database',
    'src.core.parser',
    'src.core.cache',
    'src.core.analysis',
    'src.core.export',
    'src.core.managers',
    'src.ui',
    'src.ui.app',
    'src.ui.styles',
    'src.ui.widgets',
    'src.ui.widgets.components',
    'src.ui.widgets.dashboard',
    'src.ui.widgets.toast',
    'src.ui.widgets.chart',
    'src.ui.widgets.dialogs',
    'src.ui.widgets.tabs',
    'src.ui.dialogs',
    'src.ui.dialogs.preset',
    'src.ui.dialogs.settings',
    'src.ui.dialogs.filter',
    'src.ui.dialogs.batch',
    'src.ui.dialogs.excel',
    'src.ui.dialogs.search',
    'src.ui.dialogs.common',
    'src.utils',
    'src.utils.constants',
    'src.utils.helpers',
    'src.utils.logger',
    'src.utils.paths',
    'src.utils.retry',
    'src.utils.plot',
    'src.utils.retry_handler',
    'src.utils.error_handler',
    
    # Selenium/Chrome (필수)
    'undetected_chromedriver',
    'selenium.webdriver',
    'selenium.webdriver.chrome.service',
    'selenium.webdriver.chrome.options',
    'selenium.webdriver.common.by',
    'selenium.webdriver.support.ui',
    'selenium.webdriver.support.expected_conditions',
    
    # HTML 파싱 (필수)
    'bs4',
    'bs4.builder._htmlparser',
    
    # 엑셀 (필수)
    'openpyxl',
    'openpyxl.workbook',
    'openpyxl.cell',
    'openpyxl.styles',
    'openpyxl.utils',
    
    # 차트
    'matplotlib',
    'matplotlib.pyplot',
    'matplotlib.figure',
    'matplotlib.backends.backend_qtagg',
    
    # 알림 (선택적)
    'plyer.platforms.win.notification',
    
    # 표준 라이브러리
    'sqlite3',
    'json',
    'csv',
    'logging.handlers',
]

# ============================================================
# 제외할 모듈 (경량화)
# ============================================================
excludes = [
    # GUI 프레임워크 (사용 안함)
    'tkinter', '_tkinter', 'Tkinter',
    
    # 테스트/문서 (불필요)
    'test', 'tests', 'unittest', 'pydoc', 'doctest', 'pdb',
    
    # 과학 계산 (불필요)
    'numpy.testing', 'numpy.distutils', 'numpy.f2py',
    'scipy', 'pandas',
    
    # matplotlib 불필요 백엔드
    'matplotlib.backends.backend_gtk',
    'matplotlib.backends.backend_gtk3',
    'matplotlib.backends.backend_gtk3agg',
    'matplotlib.backends.backend_macosx',
    'matplotlib.backends.backend_pdf',
    'matplotlib.backends.backend_ps',
    'matplotlib.backends.backend_svg',
    'matplotlib.backends.backend_tkagg',
    'matplotlib.backends.backend_webagg',
    'matplotlib.backends.backend_wx',
    'matplotlib.tests',
    
    # IPython/Jupyter (불필요)
    'IPython', 'jupyter', 'notebook',
    
    # 기타
    'lib2to3', 'distutils', 'setuptools', 'pkg_resources',
]

# ============================================================
# Analysis
# ============================================================
a = Analysis(
    ['src/main.py'],  # 새로운 진입점
    pathex=['.'],
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

# ============================================================
# PYZ
# ============================================================
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# ============================================================
# EXE
# ============================================================
if ONEFILE:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='NaverLandCrawler_v14.0',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=['vcruntime140.dll', 'python*.dll', 'Qt*.dll'],
        runtime_tmpdir=None,
        console=False,  # GUI 앱
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,  # 아이콘: icon='assets/icon.ico'
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='NaverLandCrawler_v14.0',
        debug=False,
        strip=False,
        upx=True,
        console=False,
        icon=None,
    )
    
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='NaverLandCrawler_v14.0',
    )
