from __future__ import annotations

import re
from src.core.services.detail_fetcher_parts.field_keys import (
    _AGENT_NAME_KEYS,
    _OFFICE_KEYS,
    _PHONE_KEYS,
    _PREV_JEONSE_KEYS,
)
from src.core.services.detail_fetcher_parts.money import parse_kr_money_to_won
from src.core.services.detail_fetcher_parts.text_extract import (
    _find_named_value,
    _phone_list_from_value,
)


def _merge_detail_field_maps(base: dict, extra: dict | None) -> dict:
    merged = dict(base or {})
    for key, value in dict(extra or {}).items():
        if key.startswith("_"):
            continue
        if value in (None, "", [], {}):
            continue
        current = merged.get(key)
        if current in (None, "", 0, 0.0):
            merged[key] = value
    return merged


def _fields_from_named_tree(source_tree) -> dict:
    fields = {
        "부동산상호": "",
        "중개사이름": "",
        "전화1": "",
        "전화2": "",
        "전세_기간(년)": 0,
        "전세_기간내_최고(원)": 0,
        "전세_기간내_최저(원)": 0,
        "기전세금(원)": 0,
    }
    office = _find_named_value(source_tree, _OFFICE_KEYS)
    if office not in (None, "", [], {}):
        fields["부동산상호"] = str(office).strip()

    agent_name = _find_named_value(source_tree, _AGENT_NAME_KEYS)
    if agent_name not in (None, "", [], {}):
        # Avoid treating office-like blobs as a person name when nested "name" matches first.
        token = str(agent_name).strip()
        if token and token != fields["부동산상호"] and not re.search(r"\d{2,}", token):
            fields["중개사이름"] = token

    phone_value = _find_named_value(source_tree, _PHONE_KEYS)
    phones = _phone_list_from_value(phone_value)
    if not phones:
        phones = _phone_list_from_value(source_tree)
    if phones:
        fields["전화1"] = phones[0]
        if len(phones) >= 2:
            fields["전화2"] = phones[1]

    prev_jeonse_value = _find_named_value(source_tree, _PREV_JEONSE_KEYS)
    prev_jeonse = parse_kr_money_to_won(str(prev_jeonse_value or ""))
    if prev_jeonse:
        fields["기전세금(원)"] = prev_jeonse
    return fields


def _backfill_fields_from_artifacts(fields: dict, artifacts: dict | None) -> dict:
    artifacts = dict(artifacts or {})
    source_tree = {
        "hydration_state": artifacts.get("hydration_state", {}),
        "responses": artifacts.get("responses", []),
    }
    extracted = _fields_from_named_tree(source_tree)
    return _merge_detail_field_maps(fields, extracted)
