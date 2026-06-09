from __future__ import annotations

from collections import defaultdict
from typing import Any

from src.utils.helpers import PriceConverter


def _normalize_asset_type(asset_type: Any) -> str:
    token = str(asset_type or "APT").strip().upper() or "APT"
    return token if token in {"APT", "VL"} else "APT"


def build_price_snapshot_rows(items: list[dict] | tuple[dict, ...]) -> list[tuple]:
    """Build daily price snapshot rows from collected crawl items."""
    if not items:
        return []

    grouped: dict[tuple[str, str, str, float, str], list[int]] = defaultdict(list)
    for item in items:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("단지ID", "") or "").strip()
        trade_type = str(item.get("거래유형", "") or "").strip()
        if not cid or not trade_type:
            continue

        asset_type = _normalize_asset_type(item.get("자산유형", "APT"))
        try:
            pyeong = float(item.get("면적(평)", 0) or 0)
        except (TypeError, ValueError):
            pyeong = 0.0
        pyeong_group = round(pyeong / 5) * 5

        if trade_type == "매매":
            metric_prices = [("price", PriceConverter.to_int(item.get("매매가", "0")))]
        elif trade_type == "전세":
            metric_prices = [("price", PriceConverter.to_int(item.get("보증금", "0")))]
        elif trade_type == "월세":
            metric_prices = [
                ("deposit", PriceConverter.to_int(item.get("보증금", "0"))),
                ("rent", PriceConverter.to_int(item.get("월세", "0"))),
            ]
        else:
            metric_prices = []

        for price_metric, price in metric_prices:
            if price <= 0:
                continue
            key = (asset_type, cid, trade_type, float(pyeong_group), price_metric)
            grouped[key].append(int(price))

    rows: list[tuple] = []
    for (asset_type, cid, trade_type, pyeong, price_metric), prices in grouped.items():
        if not prices:
            continue
        rows.append(
            (
                cid,
                trade_type,
                pyeong,
                min(prices),
                max(prices),
                sum(prices) // len(prices),
                len(prices),
                asset_type,
                price_metric,
                0,
            )
        )
    return rows
