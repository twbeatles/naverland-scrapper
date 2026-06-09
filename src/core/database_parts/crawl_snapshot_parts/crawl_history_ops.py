from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


class ComplexDatabaseCrawlHistoryOpsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    def add_crawl_history(
        self,
        name,
        cid,
        types,
        count,
        *,
        engine="",
        mode="complex",
        source_lat=None,
        source_lon=None,
        source_zoom=None,
        asset_type="",
        run_status="success",
    ):
        if self.is_write_disabled():
            return False
        conn = self._pool.get_connection()
        try:
            with self._write_lock:
                try:
                    conn.execute("PRAGMA busy_timeout=1200")
                except Exception:
                    pass
                for attempt in range(3):
                    try:
                        conn.cursor().execute(
                            """
                            INSERT INTO crawl_history (
                                complex_name, complex_id, trade_types, item_count,
                                engine, mode, source_lat, source_lon, source_zoom, asset_type, run_status
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                name,
                                cid,
                                types,
                                count,
                                engine,
                                mode,
                                float(source_lat or 0),
                                float(source_lon or 0),
                                int(source_zoom or 0),
                                asset_type,
                                str(run_status or "success"),
                            ),
                        )
                        conn.commit()
                        return True
                    except sqlite3.OperationalError as e:
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        if self._is_locked_sqlite_error(e) and attempt < 2:
                            time.sleep(0.1 * (attempt + 1))
                            continue
                        if self._is_corruption_sqlite_error(e):
                            self._disable_writes("database_corruption", e)
                        logger.error(f"크롤링 이력 저장 실패: {e}")
                        return False
                    except sqlite3.DatabaseError as e:
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        if self._is_corruption_sqlite_error(e):
                            self._disable_writes("database_corruption", e)
                        logger.error(f"크롤링 이력 저장 실패: {e}")
                        return False
        except Exception as e:
            logger.error(f"크롤링 이력 저장 실패: {e}")
            return False
        finally:
            try:
                conn.execute("PRAGMA busy_timeout=30000")
            except Exception:
                pass
            self._pool.return_connection(conn)

    def get_crawl_history(self, limit=100):
        conn = self._pool.get_connection()
        try:
            result = self._fetchall_safe(
                conn,
                "SELECT complex_name, complex_id, "
                "COALESCE(NULLIF(asset_type, ''), 'APT') AS asset_type, "
                "COALESCE(engine, '') AS engine, "
                "COALESCE(mode, 'complex') AS mode, "
                "COALESCE(run_status, 'success') AS run_status, "
                "trade_types, item_count, crawled_at "
                "FROM crawl_history ORDER BY crawled_at DESC LIMIT ?",
                params=(limit,),
                context="크롤링 이력 조회(crawl_history)",
            )
            return result
        except Exception as e:
            self._log_corruption_detected("크롤링 이력 조회", e)
            logger.error(f"크롤링 이력 조회 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
