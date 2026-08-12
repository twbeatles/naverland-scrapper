from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from src.core.services.site_contract import (
    HOST_NEW,
    article_api_real_estate_type as _contract_real_estate_type,
    trade_type_to_code,
)

DEFAULT_ARTICLE_API_PAGE_SIZE = 20
MAX_ARTICLE_API_PAGES = 50


def article_api_path_kind(base_kind: str) -> str:
    return "house" if str(base_kind or "") == "houses" else "complex"


def article_api_real_estate_type(path_asset: str, *, include_pre: bool = False) -> str:
    """Map app asset token to Naver `realEstateType` query value.

    Live UI (2026-08) defaults to APT:ABYG:JGC without PRE. Optional PRE covers 분양권.
    """
    return _contract_real_estate_type(path_asset, include_pre=include_pre)


def build_article_api_query_params(
    trade_type: str,
    path_asset: str = "APT",
    *,
    page: int = 1,
    include_pre: bool = False,
) -> dict[str, str]:
    page_num = max(1, int(page or 1))
    return {
        "realEstateType": article_api_real_estate_type(path_asset, include_pre=include_pre),
        "tradeType": trade_type_to_code(trade_type),
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
    include_pre: bool = False,
) -> str:
    path_kind = article_api_path_kind(base_kind)
    params = build_article_api_query_params(
        trade_type, path_asset, page=page, include_pre=include_pre
    )
    return f"{HOST_NEW}/api/articles/{path_kind}/{cid}?" + urlencode(params)


def article_api_list_count(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    article_list = payload.get("articleList") or payload.get("articles") or []
    return len(article_list) if isinstance(article_list, list) else 0


def article_api_has_more_pages(
    payload: Any,
    articles_on_page: int,
    *,
    page_size: int = DEFAULT_ARTICLE_API_PAGE_SIZE,
) -> bool:
    """Use pre-filter API list length (articles_on_page), not post-normalize counts."""
    if not isinstance(payload, dict):
        return False
    if "isMoreData" in payload:
        return bool(payload.get("isMoreData"))
    if "moreData" in payload:
        return bool(payload.get("moreData"))
    return int(articles_on_page or 0) >= max(1, int(page_size or DEFAULT_ARTICLE_API_PAGE_SIZE))