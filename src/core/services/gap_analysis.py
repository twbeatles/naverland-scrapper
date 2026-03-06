from __future__ import annotations

from src.utils.helpers import PriceConverter


def sale_price_text_to_won(price_text: str) -> int:
    return max(0, int(PriceConverter.to_int(price_text or "") or 0)) * 10_000


def enrich_gap_fields(item: dict) -> dict:
    if not isinstance(item, dict):
        return {}

    trade_type = str(item.get("거래유형", "") or "")
    prev_jeonse_won = int(item.get("기전세금(원)", 0) or 0)
    if trade_type != "매매" or prev_jeonse_won <= 0:
        item.setdefault("갭금액(원)", 0)
        item.setdefault("갭비율", 0.0)
        return item

    sale_won = sale_price_text_to_won(str(item.get("매매가", "") or ""))
    if sale_won <= 0:
        item["갭금액(원)"] = 0
        item["갭비율"] = 0.0
        return item

    gap_amount = sale_won - prev_jeonse_won
    gap_ratio = float(gap_amount) / float(sale_won) if sale_won else 0.0
    item["갭금액(원)"] = int(gap_amount)
    item["갭비율"] = float(gap_ratio)
    return item
