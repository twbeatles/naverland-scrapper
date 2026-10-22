"""fin.land ``POST /front-api/v1/complex/article/list`` parsing (live 2026-10-22).

Each ``result.list`` item is a same-listing group::

    {"representativeArticleInfo": {...},
     "duplicatedArticleInfo": {"representativePriceInfo": {...},
                               "articleInfoList": [{...}, ...]}}

``totalCount`` counts groups. The legacy new.land collection used
``sameAddressGroup=false`` (one row per ad), so groups are expanded here and
each ad is reshaped into the legacy field names that
:func:`normalize_article_payload` already understands.
"""

from __future__ import annotations

from typing import Any

from src.core.services.response_capture import TRADE_CODE_MAP

FIN_TRADE_CODE_MAP = dict(TRADE_CODE_MAP)

# Site MAP_DIRECTION_LABEL (bundle, 2026-10-22).
DIRECTION_LABELS = {
    "EE": "동향",
    "EN": "북동향",
    "ES": "남동향",
    "NN": "북향",
    "SS": "남향",
    "WN": "북서향",
    "WS": "남서향",
    "WW": "서향",
}

_ASSET_BY_REAL_ESTATE_TYPE = {
    "A01": "APT",
    "A04": "APT",
    "B01": "APT",
    "A05": "VL",
    "A06": "VL",
    "A07": "VL",
    "C02": "VL",
}

# articleCountInfoDto key per trade code (boundedComplexes, complex/article/stats).
_TRADE_COUNT_KEYS = {"A1": "dealCount", "B1": "leaseDepositCount", "B2": "leaseMonthlyCount"}


def won_to_man(value: Any) -> int:
    try:
        won = int(float(value or 0))
    except (TypeError, ValueError):
        return 0
    return max(0, won // 10000)


def format_man_price(man: int) -> str:
    """Legacy new.land text: ``31억``, ``8억 5,000``, ``9,500`` (만원 단위)."""
    value = int(man or 0)
    if value <= 0:
        return ""
    uk, rest = divmod(value, 10000)
    if uk and rest:
        return f"{uk}억 {rest:,}"
    if uk:
        return f"{uk}억"
    return f"{rest:,}"


def direction_label(code: Any) -> str:
    token = str(code or "").strip().upper()
    return DIRECTION_LABELS.get(token, token)


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _group_price_range(group_price: dict, trade_code: str) -> tuple[str, str]:
    key = "dealPrice" if trade_code == "A1" else "warrantyPrice"
    span = _dict(group_price.get(key))
    max_man = won_to_man(span.get("maxPrice"))
    min_man = won_to_man(span.get("minPrice"))
    return format_man_price(max_man), format_man_price(min_man)


def fin_article_to_legacy(article: dict, *, group: dict | None = None) -> dict:
    """Reshape one fin ad into new.land Article API field names."""
    article = _dict(article)
    group = _dict(group)
    trade_code = str(article.get("tradeType", "") or "").strip().upper()
    price = _dict(article.get("priceInfo"))
    space = _dict(article.get("spaceInfo"))
    detail = _dict(article.get("articleDetail"))
    verification = _dict(article.get("verificationInfo"))
    broker = _dict(article.get("brokerInfo"))
    coords = _dict(_dict(article.get("address")).get("coordinates"))

    if trade_code == "A1":
        price_text = format_man_price(won_to_man(price.get("dealPrice")))
    else:
        price_text = format_man_price(won_to_man(price.get("warrantyPrice")))
    rent_text = ""
    if trade_code == "B2":
        rent_text = format_man_price(won_to_man(price.get("rentPrice")))
        if price_text and rent_text:
            price_text = f"{price_text}/{rent_text}"
        elif rent_text:
            price_text = f"0/{rent_text}"

    group_info = _dict(group.get("duplicatedArticleInfo"))
    group_ads = group_info.get("articleInfoList")
    same_count = len(group_ads) if isinstance(group_ads, list) else 0
    same_max, same_min = _group_price_range(_dict(group_info.get("representativePriceInfo")), trade_code)
    confirm = str(verification.get("articleConfirmDate", "") or "").replace("-", "")
    real_estate = str(article.get("realEstateType", "") or "").strip().upper()

    return {
        "articleNo": str(article.get("articleNumber", "") or "").strip(),
        "articleName": str(article.get("articleName", "") or ""),
        "tradeTypeCode": trade_code,
        "tradeTypeName": FIN_TRADE_CODE_MAP.get(trade_code, ""),
        "realEstateTypeCode": _ASSET_BY_REAL_ESTATE_TYPE.get(real_estate, ""),
        "dealOrWarrantPrc": price_text,
        "rentPrc": rent_text,
        "area1": space.get("supplySpace") or 0,
        "area2": space.get("exclusiveSpace") or 0,
        "areaName": str(space.get("supplySpaceName", "") or ""),
        "floorInfo": str(detail.get("floorInfo", "") or ""),
        "direction": direction_label(detail.get("direction")),
        "articleFeatureDesc": str(detail.get("articleFeatureDescription", "") or ""),
        "articleConfirmYmd": confirm,
        "buildingName": str(article.get("dongName", "") or ""),
        "sameAddrCnt": same_count,
        "sameAddrMaxPrc": same_max,
        "sameAddrMinPrc": same_min,
        "verificationTypeCode": str(verification.get("verificationType", "") or ""),
        "isDirectTrade": bool(detail.get("directTrade", False)),
        "realtorName": str(broker.get("brokerageName", "") or ""),
        "cpName": str(broker.get("brokerName", "") or broker.get("cpId", "") or ""),
        "latitude": coords.get("yCoordinate") or 0,
        "longitude": coords.get("xCoordinate") or 0,
        "managementFeeAmount": price.get("managementFeeAmount"),
    }


def parse_fin_article_list(payload: Any) -> dict | None:
    """Validate the envelope and expand groups.

    Returns ``None`` for error envelopes / missing keys (caller falls back);
    an explicit empty ``list`` is a valid, complete page.
    """
    if not isinstance(payload, dict):
        return None
    if payload.get("isSuccess") is False:
        return None
    code = str(payload.get("detailCode", "") or "").strip().lower()
    if code and code != "success":
        return None
    result = payload.get("result")
    if not isinstance(result, dict):
        return None
    groups = result.get("list")
    if not isinstance(groups, list):
        return None
    articles: list[Any] = []
    for group in groups:
        if not isinstance(group, dict):
            articles.append(group)
            continue
        dup = _dict(group.get("duplicatedArticleInfo"))
        ads = dup.get("articleInfoList")
        if not isinstance(ads, list) or not ads:
            ads = [group.get("representativeArticleInfo")]
        for ad in ads:
            articles.append(fin_article_to_legacy(ad, group=group) if isinstance(ad, dict) else ad)
    last_info = result.get("lastInfo")
    return {
        "articles": articles,
        "group_count": len(groups),
        "has_next": bool(result.get("hasNextPage")),
        "last_info": list(last_info) if isinstance(last_info, list) else [],
        "seed": str(result.get("seed", "") or ""),
        "total_count": int(result.get("totalCount", 0) or 0),
    }


def parse_fin_complex_info(payload: Any) -> dict:
    """``GET /front-api/v1/complex`` -> name/address/coords summary."""
    if not isinstance(payload, dict) or payload.get("isSuccess") is False:
        return {}
    result = _dict(payload.get("result"))
    if not result:
        return {}
    address = _dict(result.get("address"))
    coords = _dict(result.get("coordinates"))
    parts = [address.get("city"), address.get("division"), address.get("sector"), address.get("jibun")]
    return {
        "name": str(result.get("name", "") or "").strip(),
        "asset_type": _ASSET_BY_REAL_ESTATE_TYPE.get(str(result.get("type", "") or "").upper(), "APT"),
        "address": " ".join(str(p) for p in parts if p),
        "road_address": str(address.get("roadName", "") or ""),
        "legal_division_number": str(address.get("legalDivisionNumber", "") or ""),
        "latitude": coords.get("yCoordinate"),
        "longitude": coords.get("xCoordinate"),
        "household_count": int(result.get("totalHouseholdNumber", 0) or 0),
        "dong_count": int(result.get("dongCount", 0) or 0),
        "use_approval_date": str(result.get("useApprovalDate", "") or ""),
    }


def parse_fin_bounded_complexes(payload: Any, *, trade_code: str = "A1") -> dict | None:
    """``POST /complex/boundedComplexes`` page -> marker rows + cursor.

    Rows follow :func:`normalize_marker_payload` keys so the geo pipeline is
    unchanged. ``count`` is the listing count for ``trade_code``; complexes
    without listings for that trade are dropped. ``None`` = error envelope.
    """
    if not isinstance(payload, dict) or payload.get("isSuccess") is False:
        return None
    code = str(payload.get("detailCode", "") or "").strip().lower()
    if code and code != "success":
        return None
    result = payload.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("list"), list):
        return None
    count_key = _TRADE_COUNT_KEYS.get(str(trade_code or "A1").upper(), "dealCount")
    markers: list[dict] = []
    for item in result["list"]:
        if not isinstance(item, dict):
            continue
        is_villa = str(item.get("type", "") or "").upper() == "VILLA"
        body = _dict(item.get("villa") if is_villa else item.get("complex"))
        info = _dict(body.get("villaInfo") if is_villa else body.get("complexInfo"))
        cid = str(info.get("complexNumber", "") or "").strip()
        if not cid:
            continue
        try:
            count = int(_dict(body.get("articleCountInfoDto")).get(count_key, 0) or 0)
        except (TypeError, ValueError):
            count = 0
        if count <= 0:
            continue
        coords = _dict(_dict(info.get("address")).get("coordinates"))
        asset = "VL" if is_villa else _ASSET_BY_REAL_ESTATE_TYPE.get(str(info.get("type", "") or "").upper(), "APT")
        markers.append(
            {
                "complex_id": cid,
                "complex_name": str(info.get("name", "") or "").strip() or f"단지_{cid}",
                "asset_type": asset,
                "marker_id": cid,
                "count": count,
                "lat": float(coords.get("yCoordinate") or 0.0),
                "lon": float(coords.get("xCoordinate") or 0.0),
                "household_count": int(info.get("totalHouseholdNumber", 0) or 0),
            }
        )
    last_info = result.get("lastInfo")
    return {
        "markers": markers,
        "item_count": len(result["list"]),
        "has_next": bool(result.get("hasNextPage")),
        "last_info": list(last_info) if isinstance(last_info, list) else [],
        "seed": str(result.get("seed", "") or ""),
        "total_count": int(result.get("totalCount", 0) or 0),
    }
