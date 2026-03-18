from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


class ComplexDatabaseCrawlSnapshotOpsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    def _append_snapshot_asset_filter(self, sql_parts: list[str], params: list[Any], asset_type) -> None:
        if self._is_all_filter_value(asset_type):
            return
        asset_token = self._normalize_asset_type(asset_type)
        if asset_token == "APT":
            sql_parts.append("AND (asset_type = ? OR COALESCE(asset_type, '') = '')")
            params.append("APT")
        else:
            sql_parts.append("AND asset_type = ?")
            params.append(asset_token)

    def _append_snapshot_metric_filter(
        self,
        sql_parts: list[str],
        params: list[Any],
        *,
        trade_type=None,
        price_metric=None,
        include_legacy_monthly: bool = False,
    ) -> None:
        trade_type_token = str(trade_type or "").strip()
        if trade_type_token:
            sql_parts.append("AND trade_type = ?")
            params.append(trade_type_token)
        if not include_legacy_monthly:
            sql_parts.append("AND COALESCE(legacy_monthly, 0) = 0")
        if self._is_all_filter_value(price_metric):
            if trade_type_token == "월세":
                sql_parts.append("AND price_metric = ?")
                params.append("rent")
            return
        metric_token = self._normalize_price_metric(price_metric, trade_type=trade_type_token)
        sql_parts.append("AND price_metric = ?")
        params.append(metric_token)

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
    
    def get_complex_price_history(
        self,
        complex_id,
        trade_type=None,
        pyeong=None,
        asset_type=None,
        price_metric=None,
        include_legacy_monthly: bool = False,
    ):
        conn = self._pool.get_connection()
        try:
            sql_parts = [
                """
                SELECT snapshot_date, trade_type, pyeong, min_price, max_price, avg_price, item_count,
                       COALESCE(price_metric, 'price') AS price_metric,
                       COALESCE(legacy_monthly, 0) AS legacy_monthly
                FROM price_snapshots
                WHERE complex_id = ?
                """
            ]
            params = [complex_id]
            self._append_snapshot_metric_filter(
                sql_parts,
                params,
                trade_type=trade_type,
                price_metric=price_metric,
                include_legacy_monthly=include_legacy_monthly,
            )
            self._append_snapshot_asset_filter(sql_parts, params, asset_type)

            sql_parts.append("ORDER BY snapshot_date DESC, pyeong")

            raw_rows = self._fetchall_safe(
                conn,
                " ".join(sql_parts),
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
                (
                    snapshot_date,
                    row_trade_type,
                    row_pyeong,
                    min_price,
                    max_price,
                    avg_price,
                    _item_count,
                    row_price_metric,
                    row_legacy_monthly,
                ) = normalized
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
                        row_price_metric,
                        row_legacy_monthly,
                    )
                )

            if skipped:
                logger.debug(f"price history skipped malformed rows: {skipped}")
            logger.debug(
                f"가격 히스토리 조회: {len(result)}건 "
                f"(조건: trade={trade_type}, pyeong={pyeong}, asset={asset_type}, metric={price_metric})"
            )
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
        price_metric="price",
        legacy_monthly=0,
    ):
        """Store one price snapshot row."""
        conn = self._pool.get_connection()
        try:
            asset_token = self._normalize_asset_type(asset_type)
            metric_token = self._normalize_price_metric(price_metric, trade_type=trade_type)
            conn.cursor().execute(
                'INSERT INTO price_snapshots (complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count, asset_type, price_metric, legacy_monthly) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    complex_id,
                    trade_type,
                    pyeong,
                    min_price,
                    max_price,
                    avg_price,
                    item_count,
                    asset_token,
                    metric_token,
                    max(0, self._coerce_int(legacy_monthly, default=0)),
                )
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
                    metric_token = self._normalize_price_metric(None, trade_type=trade_type)
                    legacy_monthly = 0
                elif len(values) == 8:
                    first_token = str(values[0] or "").strip().upper()
                    if first_token in {"APT", "VL"}:
                        asset_token = values[0]
                        complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count = values[1:8]
                        metric_token = self._normalize_price_metric(None, trade_type=trade_type)
                        legacy_monthly = 0
                    else:
                        complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count, asset_token = values
                        metric_token = self._normalize_price_metric(None, trade_type=trade_type)
                        legacy_monthly = 0
                elif len(values) == 10:
                    first_token = str(values[0] or "").strip().upper()
                    if first_token in {"APT", "VL"}:
                        asset_token = values[0]
                        (
                            complex_id,
                            trade_type,
                            pyeong,
                            min_price,
                            max_price,
                            avg_price,
                            item_count,
                            metric_token,
                            legacy_monthly,
                        ) = values[1:10]
                    else:
                        (
                            complex_id,
                            trade_type,
                            pyeong,
                            min_price,
                            max_price,
                            avg_price,
                            item_count,
                            asset_token,
                            metric_token,
                            legacy_monthly,
                        ) = values
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
                        self._normalize_price_metric(metric_token, trade_type=trade_type),
                        max(0, self._coerce_int(legacy_monthly, default=0)),
                    )
                )
            if not normalized_rows:
                return 0
            conn.cursor().executemany(
                '''
                INSERT INTO price_snapshots (
                    complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count,
                    asset_type, price_metric, legacy_monthly
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    
    def get_price_snapshot_pyeongs(
        self,
        complex_id,
        asset_type=None,
        trade_type=None,
        price_metric=None,
        include_legacy_monthly: bool = False,
    ):
        conn = self._pool.get_connection()
        try:
            sql_parts = ["SELECT DISTINCT pyeong FROM price_snapshots WHERE complex_id = ?"]
            params = [complex_id]
            self._append_snapshot_metric_filter(
                sql_parts,
                params,
                trade_type=trade_type,
                price_metric=price_metric,
                include_legacy_monthly=include_legacy_monthly,
            )
            self._append_snapshot_asset_filter(sql_parts, params, asset_type)
            sql_parts.append("ORDER BY pyeong")
            rows = self._fetchall_safe(
                conn,
                " ".join(sql_parts),
                params=params,
                context="가격 스냅샷 평형 조회(price_snapshots)",
            )
            result = []
            for row in rows:
                try:
                    parsed = self._coerce_float(row["pyeong"], default=None)
                except Exception:
                    parsed = None
                if parsed is not None:
                    result.append(parsed)
            return result
        except Exception as e:
            self._log_corruption_detected("가격 스냅샷 평형 조회", e)
            logger.error(f"가격 스냅샷 평형 조회 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)

    def get_price_snapshots(
        self,
        complex_id,
        trade_type=None,
        asset_type=None,
        pyeong=None,
        price_metric=None,
        include_legacy_monthly: bool = False,
    ):
        """Load stored price snapshot rows."""
        conn = self._pool.get_connection()
        try:
            sql_parts = [
                """
                SELECT snapshot_date, trade_type, pyeong, min_price, max_price, avg_price, item_count,
                       COALESCE(price_metric, 'price') AS price_metric,
                       COALESCE(legacy_monthly, 0) AS legacy_monthly
                FROM price_snapshots
                WHERE complex_id = ?
                """
            ]
            params = [complex_id]
            self._append_snapshot_metric_filter(
                sql_parts,
                params,
                trade_type=trade_type,
                price_metric=price_metric,
                include_legacy_monthly=include_legacy_monthly,
            )
            self._append_snapshot_asset_filter(sql_parts, params, asset_type)
            if not self._is_all_filter_value(pyeong):
                parsed_pyeong = self._coerce_float(pyeong, default=None)
                if parsed_pyeong is not None:
                    sql_parts.append("AND pyeong = ?")
                    params.append(parsed_pyeong)
            
            sql_parts.append('ORDER BY snapshot_date DESC, trade_type, pyeong')
            
            raw_rows = self._fetchall_safe(
                conn,
                " ".join(sql_parts),
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
            logger.debug(
                f"price snapshots loaded: {len(result)} "
                f"(asset={asset_type}, trade={trade_type}, metric={price_metric})"
            )
            return result
        except Exception as e:
            self._log_corruption_detected("가격 스냅샷 조회", e)
            logger.error(f"가격 스냅샷 조회 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
    
