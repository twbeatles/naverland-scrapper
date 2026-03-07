from __future__ import annotations


class ComplexDatabaseBackupRestoreOpsMixin:
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
            logger.error(f"SQLite integrity_check ?ㅽ뙣 ({db_path}): {e}")
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
                raise RuntimeError(f"蹂듭썝 DB integrity_check ?ㅽ뙣: {row[0] if row else 'empty'}")

            names = {
                r[0]
                for r in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            missing = [t for t in self._RESTORE_REQUIRED_TABLES if t not in names]
            if missing:
                raise RuntimeError(f"蹂듭썝 DB ?꾩닔 ?뚯씠釉??꾨씫: {', '.join(missing)}")

            count_row = c.execute("SELECT COUNT(*) FROM complexes").fetchone()
            return int(count_row[0] if count_row else 0)
        finally:
            self._pool.return_connection(conn)

    def backup_database(self, path):
        backup_path = Path(path)
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if backup_path.resolve() == self.db_path.resolve():
                logger.error("諛깆뾽 ?ㅽ뙣: ?먮낯 DB? ?숈씪??寃쎈줈???ъ슜?????놁뒿?덈떎.")
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
            logger.error(f"諛깆뾽 ?ㅽ뙣: {e}")
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
                logger.error("諛깆뾽 寃利??ㅽ뙣: complexes 吏묎퀎 寃곌낵媛 鍮꾩뼱 ?덉뒿?덈떎.")
                return False
            if not self._integrity_check_file(backup_path):
                logger.error("backup validation failed: integrity_check mismatch")
                return False
            logger.info(f"諛깆뾽 ?꾨즺: {backup_path} (complexes={int(row[0])})")
            return True
        except Exception as e:
            logger.error(f"諛깆뾽 寃利??ㅽ뙣: {e}")
            return False
        finally:
            if verify_conn is not None:
                try:
                    verify_conn.close()
                except Exception:
                    pass
    
    def restore_database(self, path):
        """DB 蹂듭썝 - ?좎?蹂댁닔/?숈떆???덉쟾 蹂듭썝 濡쒖쭅"""
        restore_path = Path(path)
        logger.info(f"蹂듭썝 ?쒖옉: {restore_path}")

        if not restore_path.exists():
            logger.error(f"蹂듭썝 ?뚯씪??議댁옱?섏? ?딆쓬: {restore_path}")
            return False
        if not self._integrity_check_file(restore_path):
            logger.error(f"蹂듭썝 ?뚯씪 integrity_check ?ㅽ뙣: {restore_path}")
            return False

        rollback_path = self.db_path.with_suffix(".db.pre_restore")
        temp_restore_path = self.db_path.with_suffix(".db.restore_tmp")
        rollback_ready = False

        try:
            if temp_restore_path.exists():
                temp_restore_path.unlink()
        except OSError as e:
            logger.warning(f"?꾩떆 蹂듭썝 ?뚯씪 ?뺣━ ?ㅽ뙣 (臾댁떆): {e}")

        try:
            if self.db_path.exists():
                rollback_ready = self.backup_database(rollback_path)
                if not rollback_ready:
                    logger.error("蹂듭썝 以묐떒: 濡ㅻ갚???ъ쟾 諛깆뾽 ?앹꽦 ?ㅽ뙣")
                    return False

            if self._pool:
                self._pool.close_all(timeout_ms=8000)

            shutil.copy2(restore_path, temp_restore_path)
            os.replace(temp_restore_path, self.db_path)

            self._pool = ConnectionPool(self.db_path)
            self._init_tables()
            complex_count = self._validate_restored_database()
            self._write_disabled_reason = ""
            logger.info(f"restore complete: complexes={complex_count}")

            if rollback_ready and rollback_path.exists():
                try:
                    rollback_path.unlink()
                except OSError as e:
                    logger.debug(f"?ъ쟾 諛깆뾽 ?뚯씪 ??젣 ?ㅽ뙣 (臾댁떆): {e}")
            return True

        except Exception as e:
            logger.exception(f"蹂듭썝 ?ㅽ뙣: {e}")
            try:
                if temp_restore_path.exists():
                    temp_restore_path.unlink()
            except OSError:
                pass

            if rollback_ready and rollback_path.exists():
                try:
                    logger.info("蹂듭썝 ?ㅽ뙣濡?濡ㅻ갚???쒕룄?⑸땲??")
                    os.replace(rollback_path, self.db_path)
                    self._pool = ConnectionPool(self.db_path)
                    self._init_tables()
                    self._validate_restored_database()
                    logger.info("濡ㅻ갚 蹂듦뎄 ?꾨즺")
                except Exception as rb_e:
                    logger.error(f"濡ㅻ갚 蹂듦뎄 ?ㅽ뙣: {rb_e}")
            elif self.db_path.exists():
                try:
                    self._pool = ConnectionPool(self.db_path)
                    self._init_tables()
                except Exception as reinit_e:
                    logger.error(f"蹂듭썝 ?ㅽ뙣 ???곌껐? ?ъ큹湲고솕 ?ㅽ뙣: {reinit_e}")
            return False

    def close(self):
        """DB ?곌껐 ? 醫낅즺"""
        try:
            if self._pool:
                self._pool.close_all()
        except Exception as e:
            logger.debug(f"DB 醫낅즺 ?ㅽ뙣 (臾댁떆): {e}")

