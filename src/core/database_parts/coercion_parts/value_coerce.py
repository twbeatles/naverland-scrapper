from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403
    from src.core.database_parts.pool import ConnectionPool


import re


class ComplexDatabaseValueCoerceMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...
    _NUMERIC_RE = re.compile(r"-?\d+(?:\.\d+)?")
    def _fetchall_safe(self, conn, query: str, params=(), context: str = ""):
        try:
            return conn.cursor().execute(query, params).fetchall()
        except Exception as e:
            self._log_corruption_detected(context or "read", e)
            if context:
                logger.error(f"{context} query failed: {e}")
            else:
                logger.error(f"DB query failed: {e}")
            return []

    @classmethod
    def _coerce_float(cls, value, default: float | None = 0.0):
        if value is None:
            return default
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(",", "")
        if not text:
            return default
        text = text.strip()
        match = cls._NUMERIC_RE.search(text)
        if not match:
            return default
        try:
            return float(match.group(0))
        except (TypeError, ValueError):
            return default

    @classmethod
    def _coerce_int(cls, value, default=0):
        if value is None:
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        text = str(value).strip().replace(",", "")
        if not text:
            return default
        match = cls._NUMERIC_RE.search(text)
        if not match:
            return default
        try:
            return int(float(match.group(0)))
        except (TypeError, ValueError):
            return default

    @classmethod
    def _coerce_price(cls, value, default=0):
        if value is None:
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        text = str(value).strip().replace(",", "")
        if not text:
            return default
        parsed = PriceConverter.to_int(text)
        if parsed > 0:
            return parsed
        if text in {"0", "0.0"}:
            return 0
        return cls._coerce_int(text, default=default)
    @staticmethod
    def _is_all_filter_value(value) -> bool:
        token = str(value or "").strip().lower()
        return token in {"", "all", "전체"}

    @staticmethod
    def _row_value(row, key, index, default=None):
        if row is None:
            return default
        try:
            return row[key]
        except Exception:
            pass
        try:
            return row[index]
        except Exception:
            return default

    def _normalize_snapshot_row(self, row):
        snapshot_date = str(self._row_value(row, "snapshot_date", 0, "") or "")
        trade_type = str(self._row_value(row, "trade_type", 1, "") or "")
        pyeong = self._coerce_float(self._row_value(row, "pyeong", 2, None), default=None)
        if pyeong is None:
            return None
        min_price = self._coerce_price(self._row_value(row, "min_price", 3, 0), default=0)
        max_price = self._coerce_price(self._row_value(row, "max_price", 4, 0), default=0)
        avg_price = self._coerce_price(self._row_value(row, "avg_price", 5, 0), default=0)
        item_count = max(0, self._coerce_int(self._row_value(row, "item_count", 6, 0), default=0))
        price_metric = self._normalize_price_metric(
            self._row_value(row, "price_metric", 7, "price"),
            trade_type=trade_type,
        )
        legacy_monthly = max(0, self._coerce_int(self._row_value(row, "legacy_monthly", 8, 0), default=0))
        return (
            snapshot_date,
            trade_type,
            pyeong,
            min_price,
            max_price,
            avg_price,
            item_count,
            price_metric,
            legacy_monthly,
        )
