"""Naver Land site contract — hosts, query keys, and URL builders.

2026-08-12 live probe notes:
- new.land is the stable list/map host.
- fin.land HTML (/, /map, /articles/{id}) may 404 to financial.pstatic.net;
  front-api endpoints still exist but need a valid session.
- Map UI trade filter query key is ``b`` (not ``tradeTypes``).
- Marker API uses ``tradeType`` (singular) and ``realEstateType``.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from src.core.services.response_capture import TRADE_CODE_MAP

# --- Hosts -----------------------------------------------------------------

HOST_NEW = "https://new.land.naver.com"
HOST_FIN = "https://fin.land.naver.com"
HOST_M = "https://m.land.naver.com"

# --- Path / API fragments --------------------------------------------------

ARTICLE_API_PREFIX = f"{HOST_NEW}/api/articles"
COMPLEX_OVERVIEW_API = f"{HOST_NEW}/api/complexes/overview"
SINGLE_MARKERS_COMPLEX = f"{HOST_NEW}/api/complexes/single-markers/2.0"
SINGLE_MARKERS_HOUSE = f"{HOST_NEW}/api/houses/single-markers/2.0"

FRONT_API_AGENT = f"{HOST_FIN}/front-api/v1/article/agent"
FRONT_API_BASIC_INFO = f"{HOST_FIN}/front-api/v1/article/basicInfo"
FRONT_API_MAINTENANCE = f"{HOST_FIN}/front-api/v1/article/maintenanceFee"

# Map / complex page query keys observed live
GEO_QUERY_ASSET = "a"  # e.g. APT:ABYG:JGC
GEO_QUERY_TRADE = "b"  # e.g. A1 (tradeTypes is dropped by the site)
GEO_QUERY_PRICE_TYPE = "e"  # RETAIL
GEO_QUERY_MS = "ms"

_TRADE_TO_CODE: dict[str, str] = {value: key for key, value in TRADE_CODE_MAP.items()}


def trade_type_to_code(trade_type: str) -> str:
    return _TRADE_TO_CODE.get(str(trade_type or "").strip(), "A1")


def article_api_real_estate_type(path_asset: str, *, include_pre: bool = False) -> str:
    """Map app asset token to Naver ``realEstateType`` / map ``a=`` value."""
    asset = str(path_asset or "APT").strip().upper()
    if asset == "VL":
        return "VL:DDDGG:JWJT:SGJT"
    base = "APT:ABYG:JGC"
    if include_pre:
        return f"{base}:PRE"
    return base


def build_geo_map_url(
    *,
    base_kind: str,
    lat: float,
    lon: float,
    zoom: int,
    asset_type: str,
    trade_type: str,
    include_pre: bool = False,
) -> str:
    """Build new.land map URL with live-aligned query keys (``a``, ``b``, ``e``)."""
    kind = "houses" if str(base_kind or "") in {"houses", "house"} else "complexes"
    if str(asset_type or "").upper() == "VL":
        kind = "houses"
    params = {
        GEO_QUERY_MS: f"{lat},{lon},{zoom}",
        GEO_QUERY_ASSET: article_api_real_estate_type(asset_type, include_pre=include_pre),
        GEO_QUERY_TRADE: trade_type_to_code(trade_type),
        GEO_QUERY_PRICE_TYPE: "RETAIL",
    }
    return f"{HOST_NEW}/{kind}?" + urlencode(params)


def build_complex_page_url(
    cid: str,
    *,
    base_kind: str = "complexes",
    path_asset: str = "APT",
    trade_type: str = "매매",
    lat: float | None = None,
    lon: float | None = None,
    zoom: int | None = None,
    include_pre: bool = False,
) -> str:
    """Complex/house page URL used for navigation / response capture referer."""
    kind = "houses" if str(base_kind or "") in {"houses", "house"} or str(path_asset or "").upper() == "VL" else "complexes"
    params: dict[str, Any] = {
        GEO_QUERY_MS: f"{lat or 37.5},{lon or 127},{zoom or 16}",
        GEO_QUERY_ASSET: article_api_real_estate_type(path_asset, include_pre=include_pre),
        GEO_QUERY_TRADE: trade_type_to_code(trade_type),
        GEO_QUERY_PRICE_TYPE: "RETAIL",
    }
    return f"{HOST_NEW}/{kind}/{cid}?" + urlencode(params)


def build_front_api_agent_url(article_no: str) -> str:
    aid = str(article_no or "").strip()
    return f"{FRONT_API_AGENT}?articleNumber={aid}"


def build_front_api_basic_info_url(article_no: str) -> str:
    aid = str(article_no or "").strip()
    return f"{FRONT_API_BASIC_INFO}?articleId={aid}"


def build_complex_overview_url(complex_id: str, *, asset_type: str = "APT") -> str:
    cid = str(complex_id or "").strip()
    if str(asset_type or "").strip().upper() == "VL":
        return f"{HOST_NEW}/api/houses/{cid}?sameAddressGroup=false"
    return f"{COMPLEX_OVERVIEW_API}/{cid}"


def build_single_markers_url(
    *,
    asset_type: str,
    trade_type: str,
    zoom: int,
    left_lon: float,
    right_lon: float,
    top_lat: float,
    bottom_lat: float,
    include_pre: bool = False,
) -> str:
    """Build complexes/houses single-markers/2.0 URL (live 2026-08)."""
    is_vl = str(asset_type or "").strip().upper() == "VL"
    base = SINGLE_MARKERS_HOUSE if is_vl else SINGLE_MARKERS_COMPLEX
    params = {
        "zoom": str(int(zoom or 15)),
        "priceType": "RETAIL",
        "markerId": "",
        "markerType": "",
        "selectedComplexNo": "",
        "selectedComplexBuildingNo": "",
        "fakeComplexMarker": "",
        "realEstateType": article_api_real_estate_type(asset_type, include_pre=include_pre),
        "tradeType": trade_type_to_code(trade_type),
        "tag": "::::::::",
        "rentPriceMin": "0",
        "rentPriceMax": "900000000",
        "priceMin": "0",
        "priceMax": "900000000",
        "areaMin": "0",
        "areaMax": "900000000",
        "showArticle": "false",
        "sameAddressGroup": "false",
        "directions": "",
        "leftLon": str(left_lon),
        "rightLon": str(right_lon),
        "topLat": str(top_lat),
        "bottomLat": str(bottom_lat),
    }
    return f"{base}?" + urlencode(params)


def is_fin_html_dead_url(final_url: str, body_text: str = "") -> bool:
    """Heuristic: fin HTML redirected to pstatic 404 or empty not-found body."""
    url = str(final_url or "").lower()
    body = str(body_text or "")
    if "financial.pstatic.net/404" in url:
        return True
    if "페이지를 찾을 수 없습니다" in body and "fin.land" in url:
        return True
    if "요청하신 페이지를 찾을 수 없어요" in body:
        return True
    return False
