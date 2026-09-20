from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403
    from src.core.database_parts.pool import ConnectionPool


class ComplexDatabaseRecoveryMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...
    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        logger.info(f"ComplexDatabase initialized: {self.db_path}")
        self._write_lock = Lock()
        self._write_disabled_reason = ""
        self._startup_recovery_notice = ""
        self._pool = self._initialize_database_with_recovery()

    def _initialize_database_with_recovery(self):
        from src.core.database_parts.pool import ConnectionPool

        try:
            pool = ConnectionPool(self.db_path)
            self._pool = pool
            self._init_tables()
            self._write_disabled_reason = ""
            return pool
        except Exception as exc:
            if not self._is_corruption_sqlite_error(exc):
                raise
            recovered_pool = self._recover_from_startup_corruption(exc)
            if recovered_pool is None:
                raise
            return recovered_pool

    def _recover_from_startup_corruption(self, exc):
        import shutil
        from pathlib import Path

        from src.core.database_parts.pool import ConnectionPool
        from src.utils.helpers import DateTimeHelper
        from src.utils.logger import get_logger

        runtime_logger = get_logger("DB")
        db_path = Path(self.db_path)
        runtime_logger.exception(f"Startup DB open failed; attempting recovery: {exc}")

        try:
            self._pool.close_all(timeout_ms=2000)
        except Exception as close_exc:
            runtime_logger.debug(f"Corrupted DB pool close ignored: {close_exc}")

        if not db_path.exists():
            runtime_logger.warning("Startup recovery aborted: DB file does not exist.")
            return None

        backup_dir = db_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        quarantined_db = backup_dir / (
            f"{db_path.stem}.startup_corrupt_{DateTimeHelper.file_timestamp()}{db_path.suffix}"
        )

        moved_any = False
        for suffix in ("", "-wal", "-shm"):
            source = Path(f"{db_path}{suffix}")
            if not source.exists():
                continue
            destination = quarantined_db if not suffix else Path(f"{quarantined_db}{suffix}")
            try:
                shutil.move(str(source), str(destination))
                moved_any = True
            except Exception as move_exc:
                runtime_logger.warning(
                    f"Corrupted DB quarantine failed for {source.name}: {move_exc}"
                )

        if not moved_any:
            runtime_logger.error("Startup recovery failed: could not quarantine corrupted DB files.")
            return None

        recovered_pool = ConnectionPool(db_path)
        self._pool = recovered_pool
        self._init_tables()
        self._write_disabled_reason = ""
        self._startup_recovery_notice = (
            f"손상된 DB를 분리하고 새 DB를 생성했습니다. 백업: {quarantined_db.name}"
        )
        runtime_logger.warning(self._startup_recovery_notice)
        return recovered_pool

    def get_startup_recovery_notice(self) -> str:
        return str(getattr(self, "_startup_recovery_notice", "") or "")

    @staticmethod
    def _sqlite_error_text(exc) -> str:
        try:
            return str(exc).lower()
        except Exception:
            return ""

    @classmethod
    def _is_locked_sqlite_error(cls, exc) -> bool:
        text = cls._sqlite_error_text(exc)
        return (
            "database is locked" in text
            or "database table is locked" in text
            or "database schema is locked" in text
        )

    @classmethod
    def _is_corruption_sqlite_error(cls, exc) -> bool:
        text = cls._sqlite_error_text(exc)
        return (
            "database disk image is malformed" in text
            or "malformed database schema" in text
            or "file is not a database" in text
        )

    def is_write_disabled(self) -> bool:
        return bool(self._write_disabled_reason)

    def get_write_disabled_reason(self) -> str:
        return str(self._write_disabled_reason or "")

    def _disable_writes(self, reason: str, exc=None):
        if self._write_disabled_reason:
            return
        self._write_disabled_reason = str(reason or "unknown")
        if exc is not None:
            logger.critical(
                f"DB writes disabled: {self._write_disabled_reason} ({exc})"
            )
        else:
            logger.critical(f"DB writes disabled: {self._write_disabled_reason}")

    def _log_corruption_detected(self, context: str, exc):
        if self._is_corruption_sqlite_error(exc):
            self._disable_writes("database_corruption", exc)
            logger.critical(
                f"DB corruption detected ({context}). Recover from backup or recreate the database."
            )
