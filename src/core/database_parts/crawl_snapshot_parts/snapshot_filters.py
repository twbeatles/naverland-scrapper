from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


class ComplexDatabaseSnapshotFilterMixin:
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

    def _append_latest_snapshot_filter(self, sql_parts: list[str]) -> None:
        sql_parts.append(
            """
            AND id IN (
                SELECT MAX(id)
                FROM price_snapshots
                GROUP BY
                    snapshot_date,
                    COALESCE(NULLIF(asset_type, ''), 'APT'),
                    complex_id,
                    trade_type,
                    pyeong,
                    COALESCE(price_metric, 'price'),
                    COALESCE(legacy_monthly, 0)
            )
            """
        )

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
