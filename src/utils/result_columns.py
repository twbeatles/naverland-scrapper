"""Result table / export optional column catalog (lightweight, no DB)."""

from __future__ import annotations

from typing import Any

# Extra columns appended after the core 18 result-table columns. Default: hidden.
RESULT_EXTRA_COLUMN_DEFS: tuple[dict[str, str], ...] = (
    {"id": "confirm_date", "header": "확인일", "key": "확인일"},
    {"id": "building", "header": "동", "key": "동"},
    {"id": "area_name", "header": "타입명", "key": "타입명"},
    {"id": "same_addr", "header": "동일주소", "key": "동일주소건수"},
    {"id": "same_addr_max", "header": "동일주소최고", "key": "동일주소최고가"},
    {"id": "same_addr_min", "header": "동일주소최저", "key": "동일주소최저가"},
    {"id": "verify_type", "header": "확인유형", "key": "확인유형"},
    {"id": "detail_address", "header": "상세주소", "key": "상세주소"},
    {"id": "direct_trade", "header": "직거래", "key": "직거래"},
    {"id": "cp", "header": "정보제공", "key": "정보제공"},
    {"id": "broker_office", "header": "중개소", "key": "부동산상호"},
    {"id": "broker_phone", "header": "전화", "key": "전화1"},
)

RESULT_EXTRA_COLUMN_IDS: frozenset[str] = frozenset(d["id"] for d in RESULT_EXTRA_COLUMN_DEFS)

# Excel / export field keys for list meta (default off in template).
EXPORT_META_COLUMN_KEYS: tuple[str, ...] = (
    "확인일",
    "동",
    "타입명",
    "동일주소건수",
    "동일주소최고가",
    "동일주소최저가",
    "확인유형",
    "상세주소",
    "직거래",
    "정보제공",
)


def normalize_result_extra_columns(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = [value]
    else:
        try:
            candidates = list(value)
        except TypeError:
            return []
    ordered: list[str] = []
    for raw in candidates:
        token = str(raw or "").strip()
        if token in RESULT_EXTRA_COLUMN_IDS and token not in ordered:
            ordered.append(token)
    return ordered
