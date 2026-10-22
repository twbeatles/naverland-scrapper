"""Naver Land site contract — hosts, query keys, and URL builders.

2026-08-12 live probe notes:
- new.land is the stable list/map host.
- fin.land HTML (/, /map, /articles/{id}) may 404 to financial.pstatic.net;
  front-api endpoints still exist but need a valid session.
- Map UI trade filter query key is ``b`` (not ``tradeTypes``).
- Marker API uses ``tradeType`` (singular) and ``realEstateType``.

2026-10-04 live probe notes:
- Keyword flow: ``/api/autocomplete`` (suggestions, no IDs) then
  ``/api/search`` (complexes with ``complexNo`` + regions with ``cortarNo``).
  Both need a browser session (cookie-less HTTP answers 429).
- ``single-markers/2.0`` bbox-only form returns ``[]``; the site always sends
  ``cortarNo`` (resolved via ``/api/cortars``) alongside the bbox.

2026-10-22 live probe notes (fin.land full switch, docs/NAVER_LAND_SURVEY_2026-10-22.md):
- fin.land ``/map?layer=`` SPA is the primary site; m.land already redirects there.
- front-api answers 200 to in-browser ``fetch`` from a fin.land origin page
  (no cookies needed) but 429 to out-of-browser requests and to any
  ``HeadlessChrome`` user agent.
- Complex article list: ``POST /front-api/v1/complex/article/list`` with
  cursor paging (``lastInfo`` + ``seed``); ``list`` items are same-listing
  groups that must be expanded to keep per-ad rows.
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

FRONT_API_BASE = f"{HOST_FIN}/front-api/v1"
FRONT_API_AGENT = f"{FRONT_API_BASE}/article/agent"
FRONT_API_BASIC_INFO = f"{FRONT_API_BASE}/article/basicInfo"
FRONT_API_MAINTENANCE = f"{FRONT_API_BASE}/article/maintenanceFee"
FRONT_API_COMPLEX = f"{FRONT_API_BASE}/complex"
FRONT_API_COMPLEX_ARTICLE_LIST = f"{FRONT_API_BASE}/complex/article/list"
FRONT_API_VILLA = f"{FRONT_API_BASE}/complex/villa"
FRONT_API_VILLA_ARTICLE_LIST = f"{FRONT_API_BASE}/complex/villa/article/list"
FRONT_API_BOUNDED_COMPLEXES = f"{FRONT_API_BASE}/complex/boundedComplexes"
FRONT_API_AUTOCOMPLETE = f"{FRONT_API_BASE}/search/autocomplete"

# Same-origin page used to issue front-api fetches without loading the map SPA
# (the SPA fires ~20 side requests per load and trips rate limits).
FIN_API_ORIGIN_PAGE = f"{HOST_FIN}/robots.txt"

# Must not contain "HeadlessChrome": front-api answers 429 to it (2026-10-22).
DESKTOP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)

FIN_ARTICLE_PAGE_SIZE = 30  # site ARTICLE_PAGINATION_SIZE (schema max 30)
FIN_ARTICLE_SORT = "RANKING_DESC"
FIN_REAL_ESTATE_APT = "A01"
FIN_COMPLEX_PAGE_SIZE = 30  # site COMPLEX_PAGINATION_SIZE
FIN_COMPLEX_SORT = "ARTICLE_COUNT_DESC"  # COMPLEX_LIST_SORT_TYPE.매물수순

# Map filter realEstateTypes per app asset token (bundle VILLA_REAL_ESTATE_TYPES =
# 연립 A05, 다세대 A06, 도시형생활주택 A07, 빌라·연립 C02). APT adds 재건축 A04.
FIN_REAL_ESTATE_TYPES = {
    "APT": ("A01", "A04"),
    "VL": ("A05", "A06", "A07", "C02"),
}
FIN_PRE_SALE_TYPE = "B01"

# Map / complex page query keys observed live
GEO_QUERY_ASSET = "a"  # e.g. APT:ABYG:JGC
GEO_QUERY_TRADE = "b"  # e.g. A1 (tradeTypes is dropped by the site)
GEO_QUERY_PRICE_TYPE = "e"  # RETAIL
GEO_QUERY_MS = "ms"

_TRADE_TO_CODE: dict[str, str] = {value: key for key, value in TRADE_CODE_MAP.items()}


def trade_type_to_code(trade_type: str) -> str:
    """App label (매매/전세/월세) or an existing code (A1/B1/B2) -> code."""
    token = str(trade_type or "").strip()
    if token.upper() in TRADE_CODE_MAP:
        return token.upper()
    return _TRADE_TO_CODE.get(token, "A1")


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


def build_front_api_article_key_url(article_no: str) -> str:
    """``/article/key`` -> complex/building keys plus exact ``realEstateType``/``tradeType``."""
    return f"{FRONT_API_BASE}/article/key?" + urlencode({"articleNumber": str(article_no or "").strip()})


def build_front_api_agent_url(article_no: str) -> str:
    aid = str(article_no or "").strip()
    return f"{FRONT_API_AGENT}?articleNumber={aid}"


def build_front_api_basic_info_url(
    article_no: str,
    *,
    real_estate_type: str = FIN_REAL_ESTATE_APT,
    trade_type: str = "매매",
) -> str:
    """``basicInfo`` needs ``articleNumber`` + type codes (``articleId`` -> 400)."""
    params = {
        "articleNumber": str(article_no or "").strip(),
        "realEstateType": str(real_estate_type or FIN_REAL_ESTATE_APT),
        "tradeType": trade_type_to_code(trade_type),
    }
    return f"{FRONT_API_BASIC_INFO}?" + urlencode(params)


def _is_villa(asset_type: str) -> bool:
    return str(asset_type or "").strip().upper() == "VL"


def build_fin_complex_info_url(complex_id: str, *, asset_type: str = "APT") -> str:
    """``/complex`` (APT) or ``/complex/villa`` (VL) info; unknown IDs return no ``result``."""
    base = FRONT_API_VILLA if _is_villa(asset_type) else FRONT_API_COMPLEX
    return f"{base}?" + urlencode({"complexNumber": str(complex_id or "").strip()})


def fin_article_list_url(asset_type: str = "APT") -> str:
    return FRONT_API_VILLA_ARTICLE_LIST if _is_villa(asset_type) else FRONT_API_COMPLEX_ARTICLE_LIST


def fin_real_estate_types(asset_type: str, *, include_pre: bool = False) -> list[str]:
    asset = "VL" if _is_villa(asset_type) else "APT"
    types = list(FIN_REAL_ESTATE_TYPES[asset])
    if include_pre and asset == "APT":
        types.append(FIN_PRE_SALE_TYPE)
    return types


def build_fin_bounded_complexes_body(
    *,
    asset_type: str,
    trade_type: str,
    bounds: dict[str, float],
    zoom: int,
    last_info: list | None = None,
    seed: str = "",
    include_pre: bool = False,
) -> dict[str, Any]:
    """Body for ``POST /complex/boundedComplexes`` (map list panel, live 2026-10-22).

    ``bounds`` uses the viewport keys from ``map_geometry.viewport_bounds``.
    ``hasArticle`` limits results to complexes with listings.
    """
    paging: dict[str, Any] = {
        "size": FIN_COMPLEX_PAGE_SIZE,
        "complexSortType": FIN_COMPLEX_SORT,
        "lastInfo": list(last_info or []),
    }
    if seed:
        paging["seed"] = str(seed)
    return {
        "filter": {
            "tradeTypes": [trade_type_to_code(trade_type)],
            "realEstateTypes": fin_real_estate_types(asset_type, include_pre=include_pre),
            "hasArticle": True,
        },
        "boundingBox": {
            "left": float(bounds["leftLon"]),
            "right": float(bounds["rightLon"]),
            "top": float(bounds["topLat"]),
            "bottom": float(bounds["bottomLat"]),
        },
        "precision": int(zoom or 15),
        "userChannelType": "PC",
        "complexPagingRequest": paging,
    }


def build_fin_article_list_body(
    complex_id: str,
    trade_type: str,
    *,
    last_info: list | None = None,
    seed: str = "",
    size: int = FIN_ARTICLE_PAGE_SIZE,
    sort: str = FIN_ARTICLE_SORT,
) -> dict[str, Any]:
    """Body for ``POST /complex/article/list`` (cursor paging via lastInfo/seed)."""
    body: dict[str, Any] = {
        "size": max(1, min(FIN_ARTICLE_PAGE_SIZE, int(size or FIN_ARTICLE_PAGE_SIZE))),
        "complexNumber": str(complex_id or "").strip(),
        "tradeTypes": [trade_type_to_code(trade_type)],
        "userChannelType": "PC",
        "articleSortType": str(sort or FIN_ARTICLE_SORT),
        "lastInfo": list(last_info or []),
    }
    if seed:
        body["seed"] = str(seed)
    return body


def build_fin_autocomplete_url(kind: str, keyword: str, *, page: int = 0, size: int = 10) -> str:
    """fin search autocomplete; ``kind`` is ``complexes`` or ``legalDivisions``.

    ``page`` is 0-based on fin (the legacy new.land search was 1-based).
    """
    params = {
        "keyword": str(keyword or ""),
        "size": str(max(1, int(size or 10))),
        "page": str(max(0, int(page or 0))),
    }
    return f"{FRONT_API_AUTOCOMPLETE}/{kind}?" + urlencode(params)


def build_fin_region_by_coordinate_url(lat: float, lon: float) -> str:
    """Coordinate -> legal division (``type=EUP`` = 읍·면·동 level)."""
    params = {"longitude": str(float(lon)), "latitude": str(float(lat)), "type": "EUP"}
    return f"{FRONT_API_BASE}/legalDivision/searchByCoordinate?" + urlencode(params)


def build_fin_complex_page_url(complex_id: str, *, asset_type: str = "APT") -> str:
    """Shareable fin complex link (307 -> ``map?layer=`` complex_detail)."""
    params = {"tab": "article"}
    if str(asset_type or "").strip().upper() == "VL":
        params["isVilla"] = "true"
    return f"{HOST_FIN}/complexes/{str(complex_id or '').strip()}?" + urlencode(params)


def build_complex_overview_url(complex_id: str, *, asset_type: str = "APT") -> str:
    cid = str(complex_id or "").strip()
    if str(asset_type or "").strip().upper() == "VL":
        return f"{HOST_NEW}/api/houses/{cid}?sameAddressGroup=false"
    return f"{COMPLEX_OVERVIEW_API}/{cid}"


def build_autocomplete_url(keyword: str) -> str:
    """Keyword suggestion endpoint (live 2026-10: ``/api/autocomplete``).

    Returns display strings with ``<strong class='text_input'>`` highlight;
    no IDs — resolve via :func:`build_search_url`.
    """
    params = {"keyword": str(keyword or "")}
    return f"{HOST_NEW}/api/autocomplete?" + urlencode(params)


def build_search_url(keyword: str, *, page: int = 1) -> str:
    """Keyword to complex/region resolver (live 2026-10: ``/api/search``).

    Response top-level keys: ``complexes`` (items carry ``complexNo``),
    ``regions`` (items carry ``cortarNo`` plus center lat/lon),
    ``isMoreData`` for pagination. Keys may be absent when nothing matches.
    """
    params = {"keyword": str(keyword or ""), "page": str(max(1, int(page or 1)))}
    return f"{HOST_NEW}/api/search?" + urlencode(params)


def build_cortars_url(*, zoom: int, center_lat: float, center_lon: float) -> str:
    """Region lookup for map sweeps (live 2026-10: ``/api/cortars``).

    Returns a single region object with ``cortarNo`` (plus center lat/lon).
    """
    params = {
        "zoom": str(int(zoom or 15)),
        "centerLat": str(center_lat),
        "centerLon": str(center_lon),
    }
    return f"{HOST_NEW}/api/cortars?" + urlencode(params)


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
    cortar_no: str = "",
) -> str:
    """Build complexes/houses single-markers/2.0 URL.

    Live 2026-10: the bbox-only form answers ``[]``; the site always sends
    ``cortarNo`` (resolved via :func:`build_cortars_url`) alongside the bbox.
    """
    is_vl = str(asset_type or "").strip().upper() == "VL"
    base = SINGLE_MARKERS_HOUSE if is_vl else SINGLE_MARKERS_COMPLEX
    params: dict[str, str] = {}
    if str(cortar_no or "").strip():
        params["cortarNo"] = str(cortar_no or "").strip()
    params.update(
        {
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
            "oldBuildYears": "",
            "recentlyBuildYears": "",
            "minHouseHoldCount": "",
            "maxHouseHoldCount": "",
            "showArticle": "false",
            "sameAddressGroup": "false",
            "minMaintenanceCost": "",
            "maxMaintenanceCost": "",
            "directions": "",
            "leftLon": str(left_lon),
            "rightLon": str(right_lon),
            "topLat": str(top_lat),
            "bottomLat": str(bottom_lat),
        }
    )
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
