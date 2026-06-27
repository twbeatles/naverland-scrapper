from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from src.core.services.response_capture import TRADE_CODE_MAP

_TRADE_TO_CODE: dict[str, str] = {value: key for key, value in TRADE_CODE_MAP.items()}
DEFAULT_ARTICLE_API_PAGE_SIZE = 20
MAX_ARTICLE_API_PAGES = 50


def article_api_path_kind(base_kind: str) -> str:
    return "house" if str(base_kind or "") == "houses" else "complex"


def article_api_real_estate_type(path_asset: str) -> str:
    asset = str(path_asset or "APT").strip().upper()
    if asset == "VL":
        return "VL:DDDGG:JWJT:SGJT"
    return "APT:ABYG:JGC"


def build_article_api_query_params(
    trade_type: str,
    path_asset: str = "APT",
    *,
    page: int = 1,
) -> dict[str, str]:
    page_num = max(1, int(page or 1))
    return {
        "realEstateType": article_api_real_estate_type(path_asset),
        "tradeType": _TRADE_TO_CODE.get(trade_type, "A1"),
        "tag": "::::::::",
        "rentPriceMin": "0",
        "rentPriceMax": "900000000",
        "priceMin": "0",
        "priceMax": "900000000",
        "areaMin": "0",
        "areaMax": "900000000",
        "oldBuildYears": "",
        "recentlyBuildYears": "",
        "minHouseHoldCount": "",
        "maxHouseHoldCount": "",
        "showArticle": "false",
        "sameAddressGroup": "false",
        "minMaintenanceCost": "",
        "maxMaintenanceCost": "",
        "priceType": "RETAIL",
        "directions": "",
        "page": str(page_num),
        "buildingNos": "",
        "areaNos": "",
        "type": "list",
        "order": "rank",
    }


def build_article_api_url(
    base_kind: str,
    cid: str,
    trade_type: str,
    path_asset: str = "APT",
    *,
    page: int = 1,
) -> str:
    path_kind = article_api_path_kind(base_kind)
    params = build_article_api_query_params(trade_type, path_asset, page=page)
    return f"https://new.land.naver.com/api/articles/{path_kind}/{cid}?" + urlencode(params)


def article_api_has_more_pages(
    payload: Any,
    articles_on_page: int,
    *,
    page_size: int = DEFAULT_ARTICLE_API_PAGE_SIZE,
) -> bool:
    if not isinstance(payload, dict):
        return False
    if "isMoreData" in payload:
        return bool(payload.get("isMoreData"))
    if "moreData" in payload:
        return bool(payload.get("moreData"))
    return int(articles_on_page or 0) >= max(1, int(page_size or DEFAULT_ARTICLE_API_PAGE_SIZE))