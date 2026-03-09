from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


class ComplexDatabaseBackupRestoreOpsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    @staticmethod
    def _integrity_check_file(db_path: Path) -> bool:
        conn = None
        try:
            conn = sqlite3.connect(str(db_path), timeout=30)
            row = conn.cursor().execute("PRAGMA integrity_check").fetchone()
            if not row:
                return False
            return str(row[0]).strip().lower() == "ok"
        except Exception as e:
            logger.error(f"SQLite integrity_check 실패 ({db_path}): {e}")
            return False
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def _validate_restored_database(self) -> int:
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            row = c.execute("PRAGMA integrity_check").fetchone()
            if not row or str(row[0]).strip().lower() != "ok":
                raise RuntimeError(f"복원 DB integrity_check 실패: {row[0] if row else 'empty'}")

            names = {
                r[0]
                for r in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            missing = [t for t in self._RESTORE_REQUIRED_TABLES if t not in names]
            if missing:
                raise RuntimeError(f"복원 DB 필수 테이블 누락: {', '.join(missing)}")

            count_row = c.execute("SELECT COUNT(*) FROM complexes").fetchone()
            return int(count_row[0] if count_row else 0)
        finally:
            self._pool.return_connection(conn)

    def backup_database(self, path):
        backup_path = Path(path)
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if backup_path.resolve() == self.db_path.resolve():
                logger.error("백업 실패: 원본 DB와 동일한 경로는 사용할 수 없습니다.")
                return False
        except Exception:
            pass

        source_conn = None
        target_conn = None
        try:
            source_conn = self._pool.get_connection()
            target_conn = sqlite3.connect(str(backup_path), timeout=30)
            source_conn.backup(target_conn)
            target_conn.commit()
        except Exception as e:
            logger.error(f"백업 실패: {e}")
            return False
        finally:
            if target_conn is not None:
                try:
                    target_conn.close()
                except Exception:
                    pass
            if source_conn is not None:
                self._pool.return_connection(source_conn)

        verify_conn = None
        try:
            verify_conn = sqlite3.connect(str(backup_path), timeout=30)
            row = verify_conn.cursor().execute("SELECT COUNT(*) FROM complexes").fetchone()
            if not row:
                logger.error("백업 검증 실패: complexes 집계 결과가 비어 있습니다.")
                return False
            if not self._integrity_check_file(backup_path):
                logger.error("백업 검증 실패: integrity_check 불일치")
                return False
            logger.info(f"백업 완료: {backup_path} (complexes={int(row[0])})")
            return True
        except Exception as e:
            logger.error(f"백업 검증 실패: {e}")
            return False
        finally:
            if verify_conn is not None:
                try:
                    verify_conn.close()
                except Exception:
                    pass
    
    def restore_database(self, path):
        """DB 복원 - 유지보수와 롤백을 포함한 안전한 복원 로직."""
        restore_path = Path(path)
        logger.info(f"복원 시작: {restore_path}")

        if not restore_path.exists():
            logger.error(f"복원 파일이 존재하지 않음: {restore_path}")
            return False
        if not self._integrity_check_file(restore_path):
            logger.error(f"복원 파일 integrity_check 실패: {restore_path}")
            return False

        rollback_path = self.db_path.with_suffix(".db.pre_restore")
        temp_restore_path = self.db_path.with_suffix(".db.restore_tmp")
        rollback_ready = False

        try:
            if temp_restore_path.exists():
                temp_restore_path.unlink()
        except OSError as e:
            logger.warning(f"임시 복원 파일 정리 실패 (무시): {e}")

        try:
            if self.db_path.exists():
                rollback_ready = self.backup_database(rollback_path)
                if not rollback_ready:
                    logger.error("복원 중단: 롤백용 사전 백업 생성 실패")
                    return False

            if self._pool:
                self._pool.close_all(timeout_ms=8000)

            shutil.copy2(restore_path, temp_restore_path)
            os.replace(temp_restore_path, self.db_path)

            self._pool = ConnectionPool(self.db_path)
            self._init_tables()
            complex_count = self._validate_restored_database()
            self._write_disabled_reason = ""
            logger.info(f"복원 완료: complexes={complex_count}")

            if rollback_ready and rollback_path.exists():
                try:
                    rollback_path.unlink()
                except OSError as e:
                    logger.debug(f"사전 백업 파일 삭제 실패 (무시): {e}")
            return True

        except Exception as e:
            logger.exception(f"복원 실패: {e}")
            try:
                if temp_restore_path.exists():
                    temp_restore_path.unlink()
            except OSError:
                pass

            if rollback_ready and rollback_path.exists():
                try:
                    logger.info("복원 실패로 롤백을 시도합니다.")
                    os.replace(rollback_path, self.db_path)
                    self._pool = ConnectionPool(self.db_path)
                    self._init_tables()
                    self._validate_restored_database()
                    logger.info("롤백 복구 완료")
                except Exception as rb_e:
                    logger.error(f"롤백 복구 실패: {rb_e}")
            elif self.db_path.exists():
                try:
                    self._pool = ConnectionPool(self.db_path)
                    self._init_tables()
                except Exception as reinit_e:
                    logger.error(f"복원 실패 후 연결 재초기화 실패: {reinit_e}")
            return False

    def close(self):
        """DB 연결 종료."""
        try:
            if self._pool:
                self._pool.close_all()
        except Exception as e:
            logger.debug(f"DB 종료 실패 (무시): {e}")

