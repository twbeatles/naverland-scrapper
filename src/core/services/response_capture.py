from __future__ import annotations

from typing import Any

from src.core.services.gap_analysis import enrich_gap_fields
from src.utils.helpers import AreaConverter, DateTimeHelper, PriceConverter, PricePerPyeongCalculator


TRADE_CODE_MAP = {
    "A1": "매매",
    "B1": "전세",
    "B2": "월세",
}


def _first(payload: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def detect_trade_type(article: dict[str, Any], requested_trade_type: str = "") -> str:
    trade_name = str(
        _first(article, "tradeTypeName", "tradTpNm", default=requested_trade_type or "")
    ).strip()
    if trade_name in ("매매", "전세", "월세"):
        return trade_name

    trade_code = str(_first(article, "tradeTypeCode", "tradeType", "tradTpCd", default="")).upper()
    return TRADE_CODE_MAP.get(trade_code, requested_trade_type or "매매")


def detect_asset_type(article: dict[str, Any], fallback: str = "") -> str:
    code = str(
        _first(article, "realEstateTypeCode", "rletTpCd", "estateType", default=fallback or "")
    ).upper()
    if code in {"APT", "VL"}:
        return code
    name = str(_first(article, "realEstateTypeName", "rletTpNm", "estateTypeName", default=""))
    if any(token in name for token in ("빌라", "연립", "다세대")):
        return "VL"
    if any(token in name for token in ("아파트", "APT")):
        return "APT"
    return fallback or "APT"


def normalize_price_fields(article: dict[str, Any], trade_type: str) -> tuple[str, str, str]:
    raw_price = str(
        _first(
            article,
            "dealOrWarrantPrc",
            "price",
            "priceText",
            "formattedPrice",
            default="",
        )
    ).strip()
    rent = str(_first(article, "rentPrc", "monthlyRent", default="")).strip()
    sale_price = ""
    deposit = ""
    monthly = ""

    if trade_type == "매매":
        sale_price = raw_price.replace("매매", "").strip()
    elif trade_type == "전세":
        deposit = raw_price.replace("전세", "").strip()
    else:
        raw_monthly = raw_price.replace("월세", "").strip()
        if "/" in raw_monthly:
            left, _, right = raw_monthly.partition("/")
            deposit = left.strip()
            monthly = right.strip()
        else:
            deposit = raw_monthly
        if not monthly and rent:
            monthly = rent

    return sale_price, deposit, monthly


def normalize_marker_payload(marker: dict[str, Any], asset_type: str = "") -> dict[str, Any]:
    cid = str(_first(marker, "complexNo", "houseNo", default="")).strip()
    marker_id = str(_first(marker, "markerId", default="")).strip()
    if not cid:
        cid = marker_id
    if not marker_id:
        marker_id = cid
    name = str(_first(marker, "complexName", "houseName", default="")).strip()
    lat = _to_float(_first(marker, "latitude", "lat", default=0.0))
    lon = _to_float(_first(marker, "longitude", "lon", "lng", default=0.0))
    count = int(_first(marker, "articleCount", "dealCount", "totalCount", "count", "cnt", default=0) or 0)
    kind = detect_asset_type(marker, fallback=asset_type)
    return {
        "complex_id": cid,
        "complex_name": name or f"단지_{cid}",
        "asset_type": kind,
        "marker_id": marker_id,
        "count": count,
        "lat": lat,
        "lon": lon,
    }


def normalize_article_payload(
    article: dict[str, Any],
    complex_name: str,
    complex_id: str,
    requested_trade_type: str = "",
    *,
    asset_type: str = "",
    mode: str = "complex",
    lat: float | None = None,
    lon: float | None = None,
    zoom: int | None = None,
    marker_id: str = "",
) -> dict[str, Any]:
    trade_type = detect_trade_type(article, requested_trade_type=requested_trade_type)
    sale_price, deposit, monthly = normalize_price_fields(article, trade_type)

    area_sqm = _to_float(_first(article, "area1", "spc1", "supplyArea", "articleArea", default=0.0))
    if area_sqm <= 0:
        area_sqm = _to_float(_first(article, "area2", "spc2", "exclusiveArea", default=0.0))
    pyeong = AreaConverter.sqm_to_pyeong(area_sqm) if area_sqm > 0 else 0.0
    price_text = sale_price if trade_type == "매매" else deposit
    price_int = PriceConverter.to_int(price_text)
    floor = str(_first(article, "floorInfo", "floor", default="")).strip()
    direction = str(_first(article, "direction", default="")).strip()
    floor_info = " ".join(part for part in [floor, direction] if part).strip()
    feature = _first(
        article,
        "articleFeatureDesc",
        "articleFeatureDescription",
        "tagList",
        "featureDesc",
        default="",
    )
    if isinstance(feature, list):
        feature = ", ".join(str(x) for x in feature if x)

    item = {
        "단지명": str(complex_name or _first(article, "articleName", default=f"단지_{complex_id}")),
        "단지ID": str(complex_id or ""),
        "매물ID": str(_first(article, "articleNo", "atclNo", default="")),
        "거래유형": trade_type,
        "매매가": sale_price,
        "보증금": deposit,
        "월세": monthly,
        "면적(㎡)": round(area_sqm, 2) if area_sqm > 0 else 0.0,
        "면적(평)": pyeong,
        "평당가": PricePerPyeongCalculator.calculate(price_int, pyeong) if pyeong > 0 else 0,
        "평당가_표시": PricePerPyeongCalculator.format(
            PricePerPyeongCalculator.calculate(price_int, pyeong) if pyeong > 0 else 0
        ),
        "층/방향": floor_info,
        "타입/특징": str(feature or ""),
        "수집시각": DateTimeHelper.now_string(),
        "자산유형": detect_asset_type(article, fallback=asset_type),
        "수집모드": str(mode or "complex"),
        "위도": float(lat) if lat is not None else 0.0,
        "경도": float(lon) if lon is not None else 0.0,
        "줌": int(zoom or 0),
        "마커ID": str(marker_id or ""),
        "부동산상호": "",
        "중개사이름": "",
        "전화1": "",
        "전화2": "",
        "기전세금(원)": 0,
        "전세_기간(년)": 0,
        "전세_기간내_최고(원)": 0,
        "전세_기간내_최저(원)": 0,
        "갭금액(원)": 0,
        "갭비율": 0.0,
    }
    return enrich_gap_fields(item)
