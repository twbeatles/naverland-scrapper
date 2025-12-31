# -*- mode: python ; coding: utf-8 -*-
# 네이버 부동산 크롤러 v13.0 PyInstaller Spec 파일 (ONEFILE + 경량화)
# 빌드 명령: pyinstaller "부동산_매물_크롤러_v13.0.spec"

import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# ============================================================
# 빌드 모드 설정
# ============================================================
ONEFILE = True  # True: 단일 exe 파일, False: 폴더 구조

# ============================================================
# 숨겨진 의존성 (필수 모듈만 최소화)
# ============================================================
hiddenimports = [
    # PyQt6 (필수)
    'PyQt6.QtCore',
    'PyQt6.QtWidgets', 
    'PyQt6.QtGui',
    'PyQt6.sip',
    
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
    
    # 차트 (선택적 - 제거 시 용량 감소)
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
    'email.message',
]

# ============================================================
# 제외할 모듈 (경량화 - 매우 공격적)
# ============================================================
excludes = [
    # GUI 프레임워크 (사용 안함)
    'tkinter',
    '_tkinter',
    'Tkinter',
    
    # 테스트/문서 (불필요)
    'test',
    'tests',
    'unittest',
    'pydoc',
    'doctest',
    'pdb',
    'profile',
    'pstats',
    
    # 과학 계산 (용량 큼, 불필요)
    'numpy.testing',
    'numpy.distutils',
    'numpy.f2py',
    'scipy',
    'pandas',
    'PIL.ImageQt',
    
    # matplotlib 불필요 백엔드
    'matplotlib.backends.backend_gtk',
    'matplotlib.backends.backend_gtk3',
    'matplotlib.backends.backend_gtk3agg',
    'matplotlib.backends.backend_gtk3cairo',
    'matplotlib.backends.backend_gtkagg',
    'matplotlib.backends.backend_gtkcairo',
    'matplotlib.backends.backend_macosx',
    'matplotlib.backends.backend_pdf',
    'matplotlib.backends.backend_pgf',
    'matplotlib.backends.backend_ps',
    'matplotlib.backends.backend_svg',
    'matplotlib.backends.backend_tkagg',
    'matplotlib.backends.backend_tk',
    'matplotlib.backends.backend_webagg',
    'matplotlib.backends.backend_wx',
    'matplotlib.backends.backend_wxagg',
    'matplotlib.backends.backend_wxcairo',
    'matplotlib.backends.backend_nbagg',
    'matplotlib.tests',
    
    # IPython/Jupyter (불필요)
    'IPython',
    'jupyter',
    'notebook',
    'ipykernel',
    
    # 디버깅/개발 도구
    'debugpy',
    'pydevd',
    
    # 기타 불필요
    'lib2to3',
    'distutils',
    'setuptools',
    'pkg_resources',
    'xmlrpc',
    'multiprocessing.popen_spawn_posix',
    'multiprocessing.popen_forkserver',
]

# ============================================================
# Analysis
# ============================================================
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

# ============================================================
# 추가 경량화: 불필요 파일 제거
# ============================================================
def filter_binaries(binaries):
    """불필요한 바이너리 제거"""
    excludes = [
        'api-ms-win',  # Windows API 재배포 (대부분 불필요)
        'ucrtbase',
        'libcrypto',
        'libssl',
        # matplotlib 폰트 (일부만 필요)
    ]
    return [b for b in binaries if not any(e in b[0].lower() for e in excludes)]

# 바이너리 필터링 (선택적 - 문제 발생 시 주석처리)
# a.binaries = filter_binaries(a.binaries)

# ============================================================
# PYZ (압축 아카이브)
# ============================================================
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# ============================================================
# EXE (실행 파일)
# ============================================================
if ONEFILE:
    # ONEFILE 모드: 단일 실행 파일 생성
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
        strip=False,  # Windows에서는 strip 비활성화 권장
        upx=True,     # UPX 압축 활성화 (용량 감소)
        upx_exclude=[
            'vcruntime140.dll',
            'python*.dll',
            'Qt*.dll',
        ],
        runtime_tmpdir=None,
        console=False,  # GUI 앱이므로 콘솔 숨김
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,  # 아이콘: icon='app.ico'
    )
else:
    # ONEDIR 모드: 폴더 구조 생성
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='네이버부동산크롤러_v13.0',
        debug=False,
        bootloader_ignore_signals=False,
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
        name='네이버부동산크롤러_v13.0',
    )
