<<<<<<< HEAD
import sys
from pathlib import Path
from src.utils.logger import get_logger

logger = get_logger("Paths")

# 경로 설정 - 실행 파일 위치 기준으로 안정적으로 설정
def get_base_dir():
    """실행 파일의 디렉토리를 안정적으로 반환 (데이터 저장용)"""
    if getattr(sys, 'frozen', False):
        # PyInstaller로 패키징된 경우 - 실행 파일 위치 반환
        return Path(sys.executable).parent
    else:
        # 일반 Python 스크립트 실행
        return Path(__file__).resolve().parent.parent.parent # Adjusted for src/utils/paths.py location? 
        # CAUTION: The original code was file relative.
        # If I am in src/utils/paths.py, parent is utils, parent is src, parent is root.
        # Original: Path(__file__).resolve().parent (where the script is)
        # So I should point to the Project Root.
        
def get_resource_path(relative_path):
    """번들된 리소스 파일의 경로를 반환 (onefile 패키징 지원)"""
    if getattr(sys, 'frozen', False):
        # PyInstaller로 패키징된 경우
        if hasattr(sys, '_MEIPASS'):
            # onefile 모드: 임시 디렉토리에서 리소스 로드
            base_path = Path(sys._MEIPASS)
        else:
            # onedir 모드: 실행 파일 디렉토리에서 리소스 로드
            base_path = Path(sys.executable).parent
    else:
        # 일반 Python 스크립트 실행
        # src/utils/paths.py -> root
        base_path = Path(__file__).resolve().parent.parent.parent
    
    return base_path / relative_path

# Root of the project (where main script was)
# If we run from src/main.py, __file__ there will be src/main.py.
# If we import this module, __file__ is src/utils/paths.py.
# So BASE_DIR should be calculated relative to this file to be safe.
BASE_DIR = get_base_dir()
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
DB_PATH = DATA_DIR / "complexes.db"
SETTINGS_PATH = DATA_DIR / "settings.json"
PRESETS_PATH = DATA_DIR / "presets.json"
CACHE_PATH = DATA_DIR / "crawl_cache.json"
HISTORY_PATH = DATA_DIR / "search_history.json"

def ensure_directories():
    """필수 디렉토리 생성"""
    for d in [DATA_DIR, LOG_DIR]:
        try:
            d.mkdir(parents=True, exist_ok=True)
            logger.debug(f"디렉토리 확인: {d}")
        except Exception as e:
            logger.error(f"디렉토리 생성 실패: {d} - {e}")
=======
import sys
from pathlib import Path

# 경로 설정 - 실행 파일 위치 기준으로 안정적으로 설정
def get_base_dir():
    """실행 파일의 디렉토리를 안정적으로 반환 (데이터 저장용)"""
    if getattr(sys, 'frozen', False):
        # PyInstaller로 패키징된 경우 - 실행 파일 위치 반환
        return Path(sys.executable).parent
    else:
        # 일반 Python 스크립트 실행
        return Path(__file__).resolve().parent.parent.parent # Adjusted for src/utils/paths.py location? 
        # CAUTION: The original code was file relative.
        # If I am in src/utils/paths.py, parent is utils, parent is src, parent is root.
        # Original: Path(__file__).resolve().parent (where the script is)
        # So I should point to the Project Root.
        
def get_resource_path(relative_path):
    """번들된 리소스 파일의 경로를 반환 (onefile 패키징 지원)"""
    if getattr(sys, 'frozen', False):
        # PyInstaller로 패키징된 경우
        if hasattr(sys, '_MEIPASS'):
            # onefile 모드: 임시 디렉토리에서 리소스 로드
            base_path = Path(sys._MEIPASS)
        else:
            # onedir 모드: 실행 파일 디렉토리에서 리소스 로드
            base_path = Path(sys.executable).parent
    else:
        # 일반 Python 스크립트 실행
        # src/utils/paths.py -> root
        base_path = Path(__file__).resolve().parent.parent.parent
    
    return base_path / relative_path

# Root of the project (where main script was)
# If we run from src/main.py, __file__ there will be src/main.py.
# If we import this module, __file__ is src/utils/paths.py.
# So BASE_DIR should be calculated relative to this file to be safe.
BASE_DIR = get_base_dir()
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
DB_PATH = DATA_DIR / "complexes.db"
SETTINGS_PATH = DATA_DIR / "settings.json"
PRESETS_PATH = DATA_DIR / "presets.json"
CACHE_PATH = DATA_DIR / "crawl_cache.json"
HISTORY_PATH = DATA_DIR / "search_history.json"

def ensure_directories():
    """필수 디렉토리 생성"""
    for d in [DATA_DIR, LOG_DIR]:
        try:
            d.mkdir(parents=True, exist_ok=True)
            print(f"[INFO] 디렉토리 확인: {d}")
        except Exception as e:
            print(f"[ERROR] 디렉토리 생성 실패: {d} - {e}")
>>>>>>> d9c1bab01fe7f0174c099636906ac082e1c1c62b
