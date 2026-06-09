from __future__ import annotations

import sqlite3
import time
from typing import Any, TYPE_CHECKING

from src.utils.helpers import DateTimeHelper
from src.utils.logger import get_logger

logger = get_logger("DB")

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


class ComplexDatabaseFavoriteOpsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    def toggle_favorite(self, article_id, complex_id, asset_type="APT", is_active=True):
        if isinstance(asset_type, bool):
            is_active = bool(asset_type)
            asset_type = "APT"
        asset_token = self._normalize_listing_asset_type(asset_type)
        conn = self._pool.get_connection()
        try:
            if is_active:
                conn.cursor().execute(
                    """
                    INSERT INTO article_favorites
                    (asset_type, article_id, complex_id, is_favorite, created_at, updated_at)
                    VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT(asset_type, article_id, complex_id) DO UPDATE SET
                        is_favorite=1,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (asset_token, article_id, complex_id),
                )
            else:
                conn.cursor().execute(
                    """
                    UPDATE article_favorites
                    SET is_favorite=0, updated_at=CURRENT_TIMESTAMP
                    WHERE article_id=? AND complex_id=? AND asset_type=?
                    """,
                    (article_id, complex_id, asset_token),
                )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"favorite toggle failed: {e}")
            return False
        finally:
            self._pool.return_connection(conn)

    def update_article_note(self, article_id, complex_id, note, asset_type="APT"):
        asset_token = self._normalize_listing_asset_type(asset_type)
        conn = self._pool.get_connection()
        try:
            conn.cursor().execute(
                """
                UPDATE article_favorites
                SET note=?, updated_at=CURRENT_TIMESTAMP
                WHERE article_id=? AND complex_id=? AND asset_type=?
                """,
                (note, article_id, complex_id, asset_token),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"article note update failed: {e}")
            return False
        finally:
            self._pool.return_connection(conn)

    def get_favorites(self):
        conn = self._pool.get_connection()
        try:
            rows = conn.cursor().execute(
                """
                SELECT h.*, f.is_favorite, f.note,
                       f.created_at AS favorite_created_at,
                       f.updated_at AS favorite_updated_at
                FROM article_history h
                JOIN article_favorites f
                  ON h.article_id = f.article_id
                 AND h.complex_id = f.complex_id
                 AND COALESCE(NULLIF(h.asset_type, ''), 'APT') = COALESCE(NULLIF(f.asset_type, ''), 'APT')
                WHERE f.is_favorite = 1
                ORDER BY f.updated_at DESC
                """
            ).fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"favorite list read failed: {e}")
            return []
        finally:
            self._pool.return_connection(conn)

    def get_favorite_keys(self):
        conn = self._pool.get_connection()
        try:
            rows = conn.cursor().execute(
                """
                SELECT COALESCE(NULLIF(asset_type, ''), 'APT') AS asset_type, article_id, complex_id
                FROM article_favorites
                WHERE is_favorite = 1
                """
            ).fetchall()
            keys = set()
            for row in rows:
                article_id = str(row["article_id"] or "")
                complex_id = str(row["complex_id"] or "")
                asset_type = self._normalize_listing_asset_type(row["asset_type"])
                if article_id and complex_id:
                    keys.add((asset_type, article_id, complex_id))
            return keys
        except Exception as e:
            logger.error(f"favorite key read failed: {e}")
            return set()
        finally:
            self._pool.return_connection(conn)

    def get_article_favorite_info(self, article_id, complex_id, asset_type="APT"):
        asset_token = self._normalize_listing_asset_type(asset_type)
        conn = self._pool.get_connection()
        try:
            row = conn.cursor().execute(
                """
                SELECT is_favorite, note
                FROM article_favorites
                WHERE article_id=? AND complex_id=? AND asset_type=?
                """,
                (article_id, complex_id, asset_token),
            ).fetchone()
            if row:
                return dict(row)
            return {"is_favorite": 0, "note": ""}
        except Exception as e:
            logger.error(f"favorite info read failed: {e}")
            return {"is_favorite": 0, "note": ""}
        finally:
            self._pool.return_connection(conn)
