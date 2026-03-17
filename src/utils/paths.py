import os
import shutil
import sqlite3
import sys
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger("Paths")

FROZEN_APP_DIR_NAME = "NaverlandScrapperProPlus"
RUNTIME_DATA_FILENAMES = (
    "complexes.db",
    "settings.json",
    "presets.json",
    "crawl_cache.json",
    "search_history.json",
    "recently_viewed.json",
)


def is_frozen_runtime() -> bool:
    return bool(getattr(sys, "frozen", False))


def _local_appdata_root() -> Path:
    raw = os.environ.get("LOCALAPPDATA")
    if raw:
        return Path(raw)
    return Path.home() / "AppData" / "Local"


def get_base_dir():
    """실행 파일 기준의 기본 디렉토리를 반환"""
    if is_frozen_runtime():
        return _local_appdata_root() / FROZEN_APP_DIR_NAME
    return Path(__file__).resolve().parent.parent.parent


def get_resource_path(relative_path):
    """번들/일반 실행 환경에서 리소스 경로를 반환"""
    if is_frozen_runtime():
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


def _can_migrate_sqlite_file(path: Path) -> bool:
    conn = None
    try:
        conn = sqlite3.connect(str(path), timeout=5)
        conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchall()
        conn.execute("PRAGMA quick_check").fetchone()
        return True
    except Exception as e:
        logger.warning(f"레거시 DB 마이그레이션 건너뜀 ({path}): {e}")
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _migrate_sqlite_file(source: Path, target: Path):
    source_conn = None
    target_conn = None
    try:
        source_conn = sqlite3.connect(str(source), timeout=15)
        target_conn = sqlite3.connect(str(target), timeout=15)
        source_conn.backup(target_conn)
        target_conn.commit()
    finally:
        if target_conn is not None:
            try:
                target_conn.close()
            except Exception:
                pass
        if source_conn is not None:
            try:
                source_conn.close()
            except Exception:
                pass


def _migrate_legacy_frozen_runtime_data():
    if not is_frozen_runtime():
        return

    legacy_data_dir = Path(sys.executable).parent / "data"
    if not legacy_data_dir.exists():
        return
    try:
        if legacy_data_dir.resolve() == DATA_DIR.resolve():
            return
    except Exception:
        pass

    for filename in RUNTIME_DATA_FILENAMES:
        source = legacy_data_dir / filename
        target = DATA_DIR / filename
        if not source.exists() or target.exists():
            continue
        try:
            if source.suffix.lower() == ".db":
                if not _can_migrate_sqlite_file(source):
                    continue
                _migrate_sqlite_file(source, target)
            else:
                shutil.copy2(source, target)
            logger.info(f"레거시 실행 폴더 데이터 마이그레이션 완료: {source} -> {target}")
        except Exception as e:
            logger.warning(f"레거시 실행 폴더 데이터 마이그레이션 실패 ({source}): {e}")


def ensure_directories():
    """필수 디렉토리 생성"""
    for directory in [DATA_DIR, LOG_DIR]:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"디렉토리 확인: {directory}")
        except Exception as e:
            logger.error(f"디렉토리 생성 실패: {directory} - {e}")
    _migrate_legacy_frozen_runtime_data()
