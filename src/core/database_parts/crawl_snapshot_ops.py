from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


class ComplexDatabaseCrawlSnapshotOpsMixin:
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
    
    def get_complex_price_history(self, complex_id, trade_type=None, pyeong=None, asset_type=None):
        conn = self._pool.get_connection()
        try:
            sql = '''
                SELECT snapshot_date, trade_type, pyeong, min_price, max_price, avg_price, item_count
                FROM price_snapshots
                WHERE complex_id = ?
            '''
            params = [complex_id]

            if not self._is_all_filter_value(trade_type):
                sql += ' AND trade_type = ?'
                params.append(trade_type)
            if not self._is_all_filter_value(asset_type):
                asset_token = self._normalize_asset_type(asset_type)
                if asset_token == "APT":
                    sql += " AND (asset_type = ? OR COALESCE(asset_type, '') = '')"
                    params.append("APT")
                else:
                    sql += " AND asset_type = ?"
                    params.append(asset_token)

            sql += ' ORDER BY snapshot_date DESC, pyeong'

            raw_rows = self._fetchall_safe(
                conn,
                sql,
                params=params,
                context="가격 히스토리 조회(price_snapshots)",
            )
            pyeong_filter = None
            if not self._is_all_filter_value(pyeong):
                pyeong_filter = self._coerce_float(pyeong, default=None)
                if pyeong_filter is None:
                    logger.debug(f"평형 값 파싱 실패: {pyeong}")

            result = []
            skipped = 0
            for row in raw_rows:
                normalized = self._normalize_snapshot_row(row)
                if normalized is None:
                    skipped += 1
                    continue
                snapshot_date, row_trade_type, row_pyeong, min_price, max_price, avg_price, _item_count = normalized
                if pyeong_filter is not None and abs(row_pyeong - pyeong_filter) > 1e-6:
                    continue
                result.append(
                    (
                        snapshot_date,
                        row_trade_type,
                        row_pyeong,
                        min_price,
                        max_price,
                        avg_price,
                    )
                )

            if skipped:
                logger.debug(f"price history skipped malformed rows: {skipped}")
            logger.debug(f"가격 히스토리 조회: {len(result)}건 (조건: {trade_type}, {pyeong}, {asset_type})")
            return result
        except Exception as e:
            self._log_corruption_detected("가격 히스토리 조회", e)
            logger.error(f"가격 히스토리 조회 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
    
    def add_price_snapshot(
        self,
        complex_id,
        trade_type,
        pyeong,
        min_price,
        max_price,
        avg_price,
        item_count,
        *,
        asset_type="APT",
    ):
        """Store one price snapshot row."""
        conn = self._pool.get_connection()
        try:
            asset_token = self._normalize_asset_type(asset_type)
            conn.cursor().execute(
                'INSERT INTO price_snapshots (complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count, asset_type) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count, asset_token)
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"가격 스냅샷 저장 실패: {e}")
            return False
        finally:
            self._pool.return_connection(conn)

    def add_price_snapshots_bulk(self, rows):
        """Store price snapshots in bulk."""
        if not rows:
            return 0
        conn = self._pool.get_connection()
        try:
            normalized_rows = []
            skipped = 0
            for row in rows:
                if not isinstance(row, (list, tuple)):
                    skipped += 1
                    continue
                values = list(row)
                if len(values) == 7:
                    complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count = values
                    asset_token = "APT"
                elif len(values) == 8:
                    first_token = str(values[0] or "").strip().upper()
                    if first_token in {"APT", "VL"}:
                        asset_token = values[0]
                        complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count = values[1:8]
                    else:
                        complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count, asset_token = values
                else:
                    skipped += 1
                    continue

                parsed_pyeong = self._coerce_float(pyeong, default=None)
                if parsed_pyeong is None:
                    skipped += 1
                    continue
                normalized_rows.append(
                    (
                        str(complex_id or ""),
                        str(trade_type or ""),
                        parsed_pyeong,
                        self._coerce_price(min_price, default=0),
                        self._coerce_price(max_price, default=0),
                        self._coerce_price(avg_price, default=0),
                        max(0, self._coerce_int(item_count, default=0)),
                        self._normalize_asset_type(asset_token),
                    )
                )
            if not normalized_rows:
                return 0
            conn.cursor().executemany(
                '''
                INSERT INTO price_snapshots (
                    complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count, asset_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                normalized_rows
            )
            conn.commit()
            if skipped:
                logger.debug(f"price snapshot bulk skipped malformed rows: {skipped}")
            return len(normalized_rows)
        except Exception as e:
            logger.error(f"가격 스냅샷 일괄 저장 실패: {e}")
            return 0
        finally:
            self._pool.return_connection(conn)
    
    def get_price_snapshots(self, complex_id, trade_type=None, asset_type=None):
        """Load stored price snapshot rows."""
        conn = self._pool.get_connection()
        try:
            sql = '''
                SELECT snapshot_date, trade_type, pyeong, min_price, max_price, avg_price, item_count
                FROM price_snapshots 
                WHERE complex_id = ?
            '''
            params = [complex_id]
            
            if not self._is_all_filter_value(trade_type):
                sql += ' AND trade_type = ?'
                params.append(trade_type)
            if not self._is_all_filter_value(asset_type):
                asset_token = self._normalize_asset_type(asset_type)
                if asset_token == "APT":
                    sql += " AND (asset_type = ? OR COALESCE(asset_type, '') = '')"
                    params.append("APT")
                else:
                    sql += " AND asset_type = ?"
                    params.append(asset_token)
            
            sql += ' ORDER BY snapshot_date DESC, trade_type, pyeong'
            
            raw_rows = self._fetchall_safe(
                conn,
                sql,
                params=params,
                context="가격 스냅샷 조회(price_snapshots)",
            )
            result = []
            skipped = 0
            for row in raw_rows:
                normalized = self._normalize_snapshot_row(row)
                if normalized is None:
                    skipped += 1
                    continue
                result.append(normalized)

            if skipped:
                logger.debug(f"price snapshot skipped malformed rows: {skipped}")
            logger.debug(f"price snapshots loaded: {len(result)} (asset={asset_type})")
            return result
        except Exception as e:
            self._log_corruption_detected("가격 스냅샷 조회", e)
            logger.error(f"가격 스냅샷 조회 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
    
