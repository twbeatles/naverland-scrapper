import sys
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger("Paths")


def get_base_dir():
    """실행 파일 기준의 기본 디렉토리를 반환"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


def get_resource_path(relative_path):
    """번들/일반 실행 환경에서 리소스 경로를 반환"""
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            base_path = Path(getattr(sys, "_MEIPASS"))
        else:
            base_path = Path(sys.executable).parent
    else:
        base_path = Path(__file__).resolve().parent.parent.parent
    return base_path / relative_path


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
    for directory in [DATA_DIR, LOG_DIR]:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"디렉토리 확인: {directory}")
        except Exception as e:
            logger.error(f"디렉토리 생성 실패: {directory} - {e}")
