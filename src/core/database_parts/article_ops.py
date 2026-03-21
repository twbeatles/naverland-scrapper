from __future__ import annotations

import sqlite3
import time
from typing import Any, TYPE_CHECKING

from src.utils.helpers import DateTimeHelper
from src.utils.logger import get_logger

logger = get_logger("DB")

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


class ComplexDatabaseArticleOpsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    @staticmethod
    def _normalize_listing_asset_type(asset_type) -> str:
        token = str(asset_type or "APT").strip().upper()
        return token if token in {"APT", "VL"} else "APT"

    @classmethod
    def _asset_scope_where(
        cls,
        asset_type,
        *,
        column_name: str = "asset_type",
        include_legacy_empty_for_apt: bool = True,
    ) -> tuple[str, list[str]]:
        token = cls._normalize_listing_asset_type(asset_type)
        if include_legacy_empty_for_apt and token == "APT":
            return f"({column_name} = ? OR COALESCE({column_name}, '') = '')", [token]
        return f"{column_name} = ?", [token]

    def get_article_history_state_bulk(self, complex_id, trade_type=None, asset_type=None):
        conn = self._pool.get_connection()
        try:
            sql = """
                SELECT article_id, price, status, last_price, price_change
                FROM article_history
                WHERE complex_id = ?
            """
            params: list[Any] = [complex_id]
            if asset_type:
                asset_where, asset_params = self._asset_scope_where(asset_type)
                sql += f" AND {asset_where}"
                params.extend(asset_params)
            if trade_type:
                sql += " AND trade_type = ?"
                params.append(trade_type)

            rows = conn.cursor().execute(sql, params).fetchall()
            result = {}
            for row in rows:
                aid = row["article_id"]
                if not aid:
                    continue
                result[str(aid)] = {
                    "price": int(row["price"] or 0),
                    "status": str(row["status"] or "active"),
                    "last_price": int(row["last_price"] or 0),
                    "price_change": int(row["price_change"] or 0),
                }
            return result
        except Exception as e:
            logger.error(f"article history bulk read failed: {e}")
            return {}
        finally:
            self._pool.return_connection(conn)

    def upsert_article_history_bulk(self, rows):
        if not rows:
            return 0
        if self.is_write_disabled():
            return 0

        normalized = []
        for row in rows:
            if isinstance(row, dict):
                payload = {
                    "article_id": str(row.get("article_id", "") or ""),
                    "complex_id": str(row.get("complex_id", "") or ""),
                    "complex_name": str(row.get("complex_name", "") or ""),
                    "trade_type": str(row.get("trade_type", "") or ""),
                    "price": int(row.get("price", 0) or 0),
                    "price_text": str(row.get("price_text", "") or ""),
                    "area_pyeong": float(row.get("area", row.get("area_pyeong", 0)) or 0),
                    "floor_info": str(row.get("floor", row.get("floor_info", "")) or ""),
                    "feature": str(row.get("feature", "") or ""),
                    "last_price": int(row.get("last_price", row.get("price", 0)) or row.get("price", 0) or 0),
                    "asset_type": self._normalize_listing_asset_type(row.get("asset_type", "APT")),
                    "source_mode": str(row.get("source_mode", "complex") or "complex"),
                    "source_lat": float(row.get("source_lat", 0) or 0),
                    "source_lon": float(row.get("source_lon", 0) or 0),
                    "source_zoom": int(row.get("source_zoom", 0) or 0),
                    "marker_id": str(row.get("marker_id", "") or ""),
                    "broker_office": str(row.get("broker_office", "") or ""),
                    "broker_name": str(row.get("broker_name", "") or ""),
                    "broker_phone1": str(row.get("broker_phone1", "") or ""),
                    "broker_phone2": str(row.get("broker_phone2", "") or ""),
                    "prev_jeonse_won": int(row.get("prev_jeonse_won", 0) or 0),
                    "jeonse_period_years": int(row.get("jeonse_period_years", 0) or 0),
                    "jeonse_max_won": int(row.get("jeonse_max_won", 0) or 0),
                    "jeonse_min_won": int(row.get("jeonse_min_won", 0) or 0),
                    "gap_amount_won": int(row.get("gap_amount_won", 0) or 0),
                    "gap_ratio": float(row.get("gap_ratio", 0.0) or 0.0),
                }
            else:
                try:
                    (
                        article_id,
                        complex_id,
                        complex_name,
                        trade_type,
                        price,
                        price_text,
                        area,
                        floor,
                        feature,
                        last_price,
                    ) = row
                except Exception:
                    continue
                payload = {
                    "article_id": str(article_id or ""),
                    "complex_id": str(complex_id or ""),
                    "complex_name": str(complex_name or ""),
                    "trade_type": str(trade_type or ""),
                    "price": int(price or 0),
                    "price_text": str(price_text or ""),
                    "area_pyeong": float(area or 0),
                    "floor_info": str(floor or ""),
                    "feature": str(feature or ""),
                    "last_price": int(last_price or price or 0),
                    "asset_type": "APT",
                    "source_mode": "complex",
                    "source_lat": 0.0,
                    "source_lon": 0.0,
                    "source_zoom": 0,
                    "marker_id": "",
                    "broker_office": "",
                    "broker_name": "",
                    "broker_phone1": "",
                    "broker_phone2": "",
                    "prev_jeonse_won": 0,
                    "jeonse_period_years": 0,
                    "jeonse_max_won": 0,
                    "jeonse_min_won": 0,
                    "gap_amount_won": 0,
                    "gap_ratio": 0.0,
                }

            if not payload["article_id"] or not payload["complex_id"] or payload["price"] <= 0:
                continue
            normalized.append(payload)

        if not normalized:
            return 0

        conn = self._pool.get_connection()
        try:
            with self._write_lock:
                try:
                    conn.execute("PRAGMA busy_timeout=5000")
                except Exception:
                    pass
                for attempt in range(3):
                    try:
                        conn.cursor().executemany(
                            """
                            INSERT INTO article_history (
                                article_id, complex_id, complex_name, trade_type,
                                price, price_text, area_pyeong, floor_info, feature,
                                first_seen, last_seen, last_price, price_change, status,
                                asset_type, source_mode, source_lat, source_lon, source_zoom, marker_id,
                                broker_office, broker_name, broker_phone1, broker_phone2,
                                prev_jeonse_won, jeonse_period_years, jeonse_max_won, jeonse_min_won,
                                gap_amount_won, gap_ratio
                            ) VALUES (
                                :article_id, :complex_id, :complex_name, :trade_type,
                                :price, :price_text, :area_pyeong, :floor_info, :feature,
                                CURRENT_DATE, CURRENT_DATE, :last_price, 0, 'active',
                                :asset_type, :source_mode, :source_lat, :source_lon, :source_zoom, :marker_id,
                                :broker_office, :broker_name, :broker_phone1, :broker_phone2,
                                :prev_jeonse_won, :jeonse_period_years, :jeonse_max_won, :jeonse_min_won,
                                :gap_amount_won, :gap_ratio
                            )
                            ON CONFLICT(asset_type, article_id, complex_id) DO UPDATE SET
                                complex_name = excluded.complex_name,
                                trade_type = excluded.trade_type,
                                price = excluded.price,
                                price_text = excluded.price_text,
                                area_pyeong = excluded.area_pyeong,
                                floor_info = excluded.floor_info,
                                feature = excluded.feature,
                                asset_type = excluded.asset_type,
                                source_mode = excluded.source_mode,
                                source_lat = excluded.source_lat,
                                source_lon = excluded.source_lon,
                                source_zoom = excluded.source_zoom,
                                marker_id = excluded.marker_id,
                                broker_office = excluded.broker_office,
                                broker_name = excluded.broker_name,
                                broker_phone1 = excluded.broker_phone1,
                                broker_phone2 = excluded.broker_phone2,
                                prev_jeonse_won = excluded.prev_jeonse_won,
                                jeonse_period_years = excluded.jeonse_period_years,
                                jeonse_max_won = excluded.jeonse_max_won,
                                jeonse_min_won = excluded.jeonse_min_won,
                                gap_amount_won = excluded.gap_amount_won,
                                gap_ratio = excluded.gap_ratio,
                                last_seen = CURRENT_DATE,
                                last_price = article_history.price,
                                price_change = excluded.price - article_history.price,
                                status = 'active'
                            """,
                            normalized,
                        )
                        conn.commit()
                        return len(normalized)
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
                        logger.error(f"article history bulk upsert failed: {e}")
                        return 0
                    except sqlite3.DatabaseError as e:
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        if self._is_corruption_sqlite_error(e):
                            self._disable_writes("database_corruption", e)
                        logger.error(f"article history bulk upsert failed: {e}")
                        return 0
        except Exception as e:
            logger.error(f"article history bulk upsert failed: {e}")
            return 0
        finally:
            try:
                conn.execute("PRAGMA busy_timeout=30000")
            except Exception:
                pass
            self._pool.return_connection(conn)

    def check_article_history(self, article_id, complex_id, current_price):
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            c.execute(
                "SELECT price, status FROM article_history WHERE article_id = ? AND complex_id = ?",
                (article_id, complex_id),
            )
            row = c.fetchone()
            if not row:
                return True, 0, 0
            last_price = row["price"]
            price_change = current_price - last_price
            return False, price_change, last_price
        except Exception as e:
            logger.error(f"article history read failed: {e}")
            return False, 0, 0
        finally:
            self._pool.return_connection(conn)

    def update_article_history(
        self,
        article_id,
        complex_id,
        complex_name,
        trade_type,
        price,
        price_text,
        area,
        floor,
        feature,
        extra=None,
    ):
        if self.is_write_disabled():
            return False
        conn = self._pool.get_connection()
        try:
            with self._write_lock:
                c = conn.cursor()
                extra = dict(extra or {})
                asset_type = self._normalize_listing_asset_type(extra.get("asset_type", "APT"))
                asset_where, asset_params = self._asset_scope_where(asset_type)

                c.execute(
                    f"SELECT price, first_seen FROM article_history WHERE article_id = ? AND complex_id = ? AND {asset_where}",
                    [article_id, complex_id, *asset_params],
                )
                row = c.fetchone()
                if row:
                    last_price = row["price"]
                    price_change = price - last_price
                    c.execute(
                        """
                        UPDATE article_history
                        SET complex_name=?, trade_type=?, price=?, price_text=?, area_pyeong=?, floor_info=?, feature=?,
                            asset_type=?, source_mode=?, source_lat=?, source_lon=?, source_zoom=?, marker_id=?,
                            broker_office=?, broker_name=?, broker_phone1=?, broker_phone2=?,
                            prev_jeonse_won=?, jeonse_period_years=?, jeonse_max_won=?, jeonse_min_won=?,
                            gap_amount_won=?, gap_ratio=?, last_seen=CURRENT_DATE,
                            last_price=?, price_change=?, status='active'
                        WHERE article_id=? AND complex_id=? AND asset_type=?
                        """,
                        (
                            complex_name,
                            trade_type,
                            price,
                            price_text,
                            area,
                            floor,
                            feature,
                            asset_type,
                            str(extra.get("source_mode", "complex") or "complex"),
                            float(extra.get("source_lat", 0) or 0),
                            float(extra.get("source_lon", 0) or 0),
                            int(extra.get("source_zoom", 0) or 0),
                            str(extra.get("marker_id", "") or ""),
                            str(extra.get("broker_office", "") or ""),
                            str(extra.get("broker_name", "") or ""),
                            str(extra.get("broker_phone1", "") or ""),
                            str(extra.get("broker_phone2", "") or ""),
                            int(extra.get("prev_jeonse_won", 0) or 0),
                            int(extra.get("jeonse_period_years", 0) or 0),
                            int(extra.get("jeonse_max_won", 0) or 0),
                            int(extra.get("jeonse_min_won", 0) or 0),
                            int(extra.get("gap_amount_won", 0) or 0),
                            float(extra.get("gap_ratio", 0.0) or 0.0),
                            last_price,
                            price_change,
                            article_id,
                            complex_id,
                            asset_type,
                        ),
                    )
                else:
                    c.execute(
                        """
                        INSERT INTO article_history (
                            article_id, complex_id, complex_name, trade_type,
                            price, price_text, area_pyeong, floor_info, feature,
                            first_seen, last_seen, last_price, price_change, status,
                            asset_type, source_mode, source_lat, source_lon, source_zoom, marker_id,
                            broker_office, broker_name, broker_phone1, broker_phone2,
                            prev_jeonse_won, jeonse_period_years, jeonse_max_won, jeonse_min_won,
                            gap_amount_won, gap_ratio
                        ) VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_DATE, CURRENT_DATE, ?, 0, 'active',
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                        )
                        """,
                        (
                            article_id,
                            complex_id,
                            complex_name,
                            trade_type,
                            price,
                            price_text,
                            area,
                            floor,
                            feature,
                            price,
                            asset_type,
                            str(extra.get("source_mode", "complex") or "complex"),
                            float(extra.get("source_lat", 0) or 0),
                            float(extra.get("source_lon", 0) or 0),
                            int(extra.get("source_zoom", 0) or 0),
                            str(extra.get("marker_id", "") or ""),
                            str(extra.get("broker_office", "") or ""),
                            str(extra.get("broker_name", "") or ""),
                            str(extra.get("broker_phone1", "") or ""),
                            str(extra.get("broker_phone2", "") or ""),
                            int(extra.get("prev_jeonse_won", 0) or 0),
                            int(extra.get("jeonse_period_years", 0) or 0),
                            int(extra.get("jeonse_max_won", 0) or 0),
                            int(extra.get("jeonse_min_won", 0) or 0),
                            int(extra.get("gap_amount_won", 0) or 0),
                            float(extra.get("gap_ratio", 0.0) or 0.0),
                        ),
                    )

                conn.commit()
                return True
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            if self._is_corruption_sqlite_error(e):
                self._disable_writes("database_corruption", e)
            logger.error(f"article history update failed: {e}")
            return False
        finally:
            self._pool.return_connection(conn)

    def get_article_history_stats(self, complex_id=None):
        conn = self._pool.get_connection()
        try:
            today = DateTimeHelper.now_string("%Y-%m-%d")
            if complex_id:
                result = conn.cursor().execute(
                    """
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN first_seen = ? THEN 1 ELSE 0 END) as new_today,
                        SUM(CASE WHEN price_change > 0 THEN 1 ELSE 0 END) as price_up,
                        SUM(CASE WHEN price_change < 0 THEN 1 ELSE 0 END) as price_down
                    FROM article_history WHERE complex_id = ?
                    """,
                    (today, complex_id),
                ).fetchone()
            else:
                result = conn.cursor().execute(
                    """
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN first_seen = ? THEN 1 ELSE 0 END) as new_today,
                        SUM(CASE WHEN price_change > 0 THEN 1 ELSE 0 END) as price_up,
                        SUM(CASE WHEN price_change < 0 THEN 1 ELSE 0 END) as price_down
                    FROM article_history
                    """,
                    (today,),
                ).fetchone()

            return {
                "total": result[0] or 0,
                "new_today": result[1] or 0,
                "price_up": result[2] or 0,
                "price_down": result[3] or 0,
            }
        except Exception as e:
            logger.error(f"article history stats failed: {e}")
            return {"total": 0, "new_today": 0, "price_up": 0, "price_down": 0}
        finally:
            self._pool.return_connection(conn)

    def cleanup_old_articles(self, days=30):
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            c.execute(
                """
                DELETE FROM article_history
                WHERE julianday('now') - julianday(last_seen) > ?
                """,
                (days,),
            )
            deleted = c.rowcount
            conn.commit()
            logger.info(f"cleanup old article history: {deleted} rows, days>{days}")
            return deleted
        except Exception as e:
            logger.error(f"cleanup old article history failed: {e}")
            return 0
        finally:
            self._pool.return_connection(conn)

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

    def mark_disappeared_articles(self):
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
                c.execute(
                    """
                    UPDATE article_history
                    SET status='disappeared'
                    WHERE last_seen < CURRENT_DATE AND status='active'
                    """
                )
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
                    where_triples = " OR ".join(
                        ["(asset_type = ? AND complex_id = ? AND trade_type = ?)"] * len(triple_chunk)
                    )
                    params = []
                    for asset_type, complex_id, trade_type in triple_chunk:
                        params.extend([asset_type, complex_id, trade_type])
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
