from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


class ComplexDatabasePriceSnapshotWriteOpsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

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
            self._upsert_price_snapshot_row(
                conn.cursor(),
                (
                    str(complex_id or ""),
                    str(trade_type or ""),
                    self._coerce_float(pyeong, default=0.0),
                    self._coerce_price(min_price, default=0),
                    self._coerce_price(max_price, default=0),
                    self._coerce_price(avg_price, default=0),
                    max(0, self._coerce_int(item_count, default=0)),
                    asset_token,
                    metric_token,
                    max(0, self._coerce_int(legacy_monthly, default=0)),
                ),
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
            cursor = conn.cursor()
            deduped_rows = {}
            for row in normalized_rows:
                (
                    complex_id,
                    trade_type,
                    pyeong,
                    _min_price,
                    _max_price,
                    _avg_price,
                    _item_count,
                    asset_type,
                    price_metric,
                    legacy_monthly,
                ) = row
                key = (asset_type, complex_id, trade_type, pyeong, price_metric, legacy_monthly)
                deduped_rows[key] = row
            cursor.executemany(self._price_snapshot_upsert_sql(), list(deduped_rows.values()))
            conn.commit()
            if skipped:
                logger.debug(f"price snapshot bulk skipped malformed rows: {skipped}")
            return len(normalized_rows)
        except Exception as e:
            logger.error(f"가격 스냅샷 일괄 저장 실패: {e}")
            return 0
        finally:
            self._pool.return_connection(conn)

    @staticmethod
    def _price_snapshot_upsert_sql() -> str:
        return """
            INSERT INTO price_snapshots (
                complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count,
                asset_type, price_metric, legacy_monthly
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(
                snapshot_date,
                asset_type,
                complex_id,
                trade_type,
                pyeong,
                price_metric,
                legacy_monthly
            ) DO UPDATE SET
                min_price = excluded.min_price,
                max_price = excluded.max_price,
                avg_price = excluded.avg_price,
                item_count = excluded.item_count
        """

    def _upsert_price_snapshot_row(self, cursor, row) -> None:
        cursor.execute(self._price_snapshot_upsert_sql(), row)
