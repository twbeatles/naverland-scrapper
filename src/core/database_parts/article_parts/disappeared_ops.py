from __future__ import annotations

import sqlite3
import time
from typing import Any, TYPE_CHECKING

from src.utils.helpers import DateTimeHelper
from src.utils.logger import get_logger

logger = get_logger("DB")

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


class ComplexDatabaseDisappearedOpsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    def mark_disappeared_articles(self, asset_type=None):
        if self.is_write_disabled():
            return 0
        conn = self._pool.get_connection()
        try:
            with self._write_lock:
                try:
                    conn.execute("PRAGMA busy_timeout=3000")
                except Exception:
                    pass
                c = conn.cursor()
                sql = """
                    UPDATE article_history
                    SET status='disappeared'
                    WHERE last_seen < CURRENT_DATE AND status='active'
                """
                params: list[Any] = []
                if asset_type:
                    asset_where, asset_params = self._asset_scope_where(asset_type)
                    sql += f" AND {asset_where}"
                    params.extend(asset_params)
                c.execute(sql, params)
                updated = c.rowcount if c.rowcount != -1 else 0
                conn.commit()
                if updated > 0:
                    logger.info(f"mark disappeared articles: {updated}")
                return updated
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            if self._is_corruption_sqlite_error(e):
                self._disable_writes("database_corruption", e)
            logger.error(f"mark disappeared articles failed: {e}")
            return 0
        finally:
            try:
                conn.execute("PRAGMA busy_timeout=30000")
            except Exception:
                pass
            self._pool.return_connection(conn)

    def mark_disappeared_articles_for_targets(self, targets: list[tuple[str, ...]]) -> int:
        if self.is_write_disabled():
            return 0

        normalized_triples: list[tuple[str, str, str]] = []
        for pair in targets or []:
            if not isinstance(pair, (list, tuple)):
                continue
            if len(pair) >= 3:
                asset_type = self._normalize_listing_asset_type(pair[0])
                complex_id = str(pair[1] or "").strip()
                trade_type = str(pair[2] or "").strip()
            elif len(pair) >= 2:
                asset_type = "APT"
                complex_id = str(pair[0] or "").strip()
                trade_type = str(pair[1] or "").strip()
            else:
                continue
            if asset_type and complex_id and trade_type:
                normalized_triples.append((asset_type, complex_id, trade_type))

        if not normalized_triples:
            return 0

        def _iter_chunks(rows, chunk_size):
            size = max(1, int(chunk_size or 1))
            for idx in range(0, len(rows), size):
                yield rows[idx : idx + size]

        conn = self._pool.get_connection()
        try:
            with self._write_lock:
                try:
                    conn.execute("PRAGMA busy_timeout=3000")
                except Exception:
                    pass
                c = conn.cursor()
                updated = 0
                triple_chunk_size = min(200, max(1, 900 // 3))

                for triple_chunk in _iter_chunks(normalized_triples, triple_chunk_size):
                    clauses = []
                    params = []
                    for asset_type, complex_id, trade_type in triple_chunk:
                        asset_where, asset_params = self._asset_scope_where(asset_type)
                        clauses.append(f"(({asset_where}) AND complex_id = ? AND trade_type = ?)")
                        params.extend(asset_params)
                        params.extend([complex_id, trade_type])
                    where_triples = " OR ".join(clauses)
                    c.execute(
                        f"""
                        UPDATE article_history
                        SET status='disappeared'
                        WHERE last_seen < CURRENT_DATE
                          AND status='active'
                          AND ({where_triples})
                        """,
                        params,
                    )
                    updated += c.rowcount if c.rowcount != -1 else 0

                conn.commit()
                if updated > 0:
                    logger.info(f"mark disappeared articles for targets: {updated}")
                return updated
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            if self._is_corruption_sqlite_error(e):
                self._disable_writes("database_corruption", e)
            logger.error(f"mark disappeared articles for targets failed: {e}")
            return 0
        finally:
            try:
                conn.execute("PRAGMA busy_timeout=30000")
            except Exception:
                pass
            self._pool.return_connection(conn)

    def count_disappeared_articles_for_targets(self, targets: list[tuple[str, ...]]) -> int:
        normalized_triples: list[tuple[str, str, str]] = []
        for pair in targets or []:
            if not isinstance(pair, (list, tuple)):
                continue
            if len(pair) >= 3:
                asset_type = self._normalize_listing_asset_type(pair[0])
                complex_id = str(pair[1] or "").strip()
                trade_type = str(pair[2] or "").strip()
            elif len(pair) >= 2:
                asset_type = "APT"
                complex_id = str(pair[0] or "").strip()
                trade_type = str(pair[1] or "").strip()
            else:
                continue
            if asset_type and complex_id and trade_type:
                normalized_triples.append((asset_type, complex_id, trade_type))

        if not normalized_triples:
            return 0

        def _iter_chunks(rows, chunk_size):
            size = max(1, int(chunk_size or 1))
            for idx in range(0, len(rows), size):
                yield rows[idx : idx + size]

        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            total = 0
            triple_chunk_size = min(200, max(1, 900 // 3))
            for triple_chunk in _iter_chunks(normalized_triples, triple_chunk_size):
                clauses = []
                params = []
                for asset_type, complex_id, trade_type in triple_chunk:
                    asset_where, asset_params = self._asset_scope_where(asset_type)
                    clauses.append(f"(({asset_where}) AND complex_id = ? AND trade_type = ?)")
                    params.extend(asset_params)
                    params.extend([complex_id, trade_type])
                row = c.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM article_history
                    WHERE status='disappeared'
                      AND ({' OR '.join(clauses)})
                    """,
                    params,
                ).fetchone()
                total += int(row[0] if row else 0)
            return total
        except Exception as e:
            logger.error(f"count disappeared articles for targets failed: {e}")
            return 0
        finally:
            self._pool.return_connection(conn)

    def get_disappeared_articles(self, limit=50):
        conn = self._pool.get_connection()
        try:
            rows = conn.cursor().execute(
                """
                SELECT * FROM article_history
                WHERE status='disappeared'
                ORDER BY last_seen DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"get disappeared articles failed: {e}")
            return []
        finally:
            self._pool.return_connection(conn)

    def count_disappeared_articles(self):
        conn = self._pool.get_connection()
        try:
            row = conn.cursor().execute(
                "SELECT COUNT(*) FROM article_history WHERE status='disappeared'"
            ).fetchone()
            return row[0] if row else 0
        except Exception as e:
            logger.error(f"count disappeared articles failed: {e}")
            return 0
        finally:
            self._pool.return_connection(conn)
