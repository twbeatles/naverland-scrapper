from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


class ComplexDatabaseAlertOpsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    def add_alert_setting(self, cid, name, ttype, amin, amax, pmin, pmax):
        conn = self._pool.get_connection()
        try:
            conn.cursor().execute(
                'INSERT INTO alert_settings (complex_id, complex_name, trade_type, area_min, area_max, price_min, price_max) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)', (cid, name, ttype, amin, amax, pmin, pmax)
            )
            conn.commit()
            logger.info(f"알림 설정 추가: {name}")
            return True
        except Exception as e:
            logger.error(f"알림 설정 추가 실패: {e}")
            return False
        finally:
            self._pool.return_connection(conn)

    def get_enabled_alert_rules(self, complex_id, trade_type=None):
        """활성 알림 규칙을 단지/거래유형 기준으로 조회한다."""
        conn = self._pool.get_connection()
        try:
            sql = (
                "SELECT id, complex_name, trade_type, area_min, area_max, price_min, price_max "
                "FROM alert_settings WHERE complex_id = ? AND enabled = 1"
            )
            params = [complex_id]
            if trade_type:
                sql += " AND trade_type = ?"
                params.append(trade_type)
            rows = conn.cursor().execute(sql, params).fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"활성 알림 규칙 조회 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)

    def record_alert_notification(self, alert_id: int, article_id: str, complex_id: str, notified_on=None) -> bool:
        """Record one alert notification row with same-day dedupe."""
        alert_id = int(alert_id or 0)
        article_id = str(article_id or "").strip()
        complex_id = str(complex_id or "").strip()
        if alert_id <= 0 or not article_id or not complex_id:
            return False

        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            if notified_on:
                notified_on = str(notified_on).strip()
                c.execute(
                    """
                    INSERT INTO article_alert_log (alert_id, article_id, complex_id, notified_on, created_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(alert_id, article_id, complex_id, notified_on) DO NOTHING
                    """,
                    (alert_id, article_id, complex_id, notified_on),
                )
            else:
                c.execute(
                    """
                    INSERT INTO article_alert_log (alert_id, article_id, complex_id, notified_on, created_at)
                    VALUES (?, ?, ?, CURRENT_DATE, CURRENT_TIMESTAMP)
                    ON CONFLICT(alert_id, article_id, complex_id, notified_on) DO NOTHING
                    """,
                    (alert_id, article_id, complex_id),
                )
            conn.commit()
            return (c.rowcount or 0) > 0
        except Exception as e:
            logger.error(f"알림 dedup 기록 실패: {e}")
            return False
        finally:
            self._pool.return_connection(conn)

    def get_all_alert_settings(self):
        conn = self._pool.get_connection()
        try:
            return conn.cursor().execute(
                'SELECT id, complex_id, complex_name, trade_type, area_min, area_max, price_min, price_max, enabled '
                'FROM alert_settings ORDER BY created_at DESC'
            ).fetchall()
        except Exception as e:
            logger.error(f"알림 설정 조회 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
    
    def toggle_alert_setting(self, aid, enabled):
        conn = self._pool.get_connection()
        try:
            conn.cursor().execute("UPDATE alert_settings SET enabled = ? WHERE id = ?", (1 if enabled else 0, aid))
            conn.commit()
        except Exception as e:
            logger.error(f"알림 설정 변경 실패: {e}")
        finally:
            self._pool.return_connection(conn)
    
    def delete_alert_setting(self, aid):
        conn = self._pool.get_connection()
        try:
            conn.cursor().execute("DELETE FROM alert_settings WHERE id = ?", (aid,))
            conn.commit()
        except Exception as e:
            logger.error(f"알림 설정 삭제 실패: {e}")
        finally:
            self._pool.return_connection(conn)
    
    def check_alerts(self, cid, ttype, area, price):
        conn = self._pool.get_connection()
        try:
            return conn.cursor().execute(
                'SELECT id, complex_name FROM alert_settings '
                'WHERE complex_id = ? AND trade_type = ? AND enabled = 1 '
                'AND area_min <= ? AND area_max >= ? AND price_min <= ? AND price_max >= ?',
                (cid, ttype, area, area, price, price)
            ).fetchall()
        except Exception as e:
            logger.error(f"알림 체크 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)

