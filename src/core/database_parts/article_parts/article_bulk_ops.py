from __future__ import annotations

import sqlite3
import time
from typing import Any, TYPE_CHECKING

from src.utils.helpers import DateTimeHelper
from src.utils.logger import get_logger

logger = get_logger("DB")

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


class ComplexDatabaseArticleBulkOpsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

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
