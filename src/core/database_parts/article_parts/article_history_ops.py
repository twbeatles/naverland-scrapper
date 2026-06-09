from __future__ import annotations

import sqlite3
import time
from typing import Any, TYPE_CHECKING

from src.utils.helpers import DateTimeHelper
from src.utils.logger import get_logger

logger = get_logger("DB")

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


class ComplexDatabaseArticleHistoryOpsMixin:
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
                SELECT article_id, price, price_text, status, last_price, price_change
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
                    "price_text": str(row["price_text"] or ""),
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

    def check_article_history(self, article_id, complex_id, current_price, asset_type=None):
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            sql = "SELECT price, status FROM article_history WHERE article_id = ? AND complex_id = ?"
            params: list[Any] = [article_id, complex_id]
            if asset_type:
                asset_where, asset_params = self._asset_scope_where(asset_type)
                sql += f" AND {asset_where}"
                params.extend(asset_params)
            c.execute(sql, params)
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

    def get_article_history_stats(self, complex_id=None, asset_type=None):
        conn = self._pool.get_connection()
        try:
            today = DateTimeHelper.now_string("%Y-%m-%d")
            sql_parts = [
                """
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN first_seen = ? THEN 1 ELSE 0 END) as new_today,
                        SUM(CASE WHEN price_change > 0 THEN 1 ELSE 0 END) as price_up,
                        SUM(CASE WHEN price_change < 0 THEN 1 ELSE 0 END) as price_down
                    FROM article_history
                    WHERE 1=1
                """
            ]
            params: list[Any] = [today]
            if complex_id:
                sql_parts.append("AND complex_id = ?")
                params.append(complex_id)
            if asset_type:
                asset_where, asset_params = self._asset_scope_where(asset_type)
                sql_parts.append(f"AND {asset_where}")
                params.extend(asset_params)
            result = conn.cursor().execute(" ".join(sql_parts), params).fetchone()

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

    def cleanup_old_articles(self, days=30, asset_type=None):
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            sql = """
                DELETE FROM article_history
                WHERE julianday('now') - julianday(last_seen) > ?
            """
            params: list[Any] = [days]
            if asset_type:
                asset_where, asset_params = self._asset_scope_where(asset_type)
                sql += f" AND {asset_where}"
                params.extend(asset_params)
            c.execute(sql, params)
            deleted = c.rowcount
            conn.commit()
            logger.info(f"cleanup old article history: {deleted} rows, days>{days}")
            return deleted
        except Exception as e:
            logger.error(f"cleanup old article history failed: {e}")
            return 0
        finally:
            self._pool.return_connection(conn)
