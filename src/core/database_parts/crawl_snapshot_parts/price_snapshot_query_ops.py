from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


class ComplexDatabasePriceSnapshotQueryOpsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

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
            self._append_latest_snapshot_filter(sql_parts)

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
            self._append_latest_snapshot_filter(sql_parts)
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
            self._append_latest_snapshot_filter(sql_parts)
            
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
