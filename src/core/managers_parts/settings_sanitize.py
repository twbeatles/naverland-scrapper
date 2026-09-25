from __future__ import annotations

from copy import deepcopy
from typing import Any
from src.core.managers_parts.schedule_defaults import (
    DEFAULT_SETTINGS,
    DEPRECATED_SETTINGS_KEYS,
)
from src.core.managers_parts.schedule_normalize import (
    _clamp_int,
    _normalize_schedule_config,
)


def _sanitize_settings_payload(value: Any) -> dict[str, Any]:
    from src.utils.result_columns import normalize_result_extra_columns

    sanitized = deepcopy(DEFAULT_SETTINGS)
    if not isinstance(value, dict):
        sanitized["schedule_config"] = _normalize_schedule_config(sanitized.get("schedule_config"))
        return sanitized

    for key, raw in value.items():
        if key in DEPRECATED_SETTINGS_KEYS:
            continue
        if key == "schedule_config":
            sanitized[key] = _normalize_schedule_config(raw)
            continue
        sanitized[key] = raw

    sanitized.pop("result_tab_mode", None)
    sanitized["schedule_config"] = _normalize_schedule_config(sanitized.get("schedule_config"))

    sanitized["include_pre_sale_rights"] = bool(sanitized.get("include_pre_sale_rights", False))
    sanitized["detail_enrichment_enabled"] = bool(sanitized.get("detail_enrichment_enabled", True))
    sanitized["detail_front_api_enabled"] = bool(sanitized.get("detail_front_api_enabled", True))
    sanitized["detail_front_api_only"] = bool(sanitized.get("detail_front_api_only", False))
    sanitized["card_show_extra_meta"] = bool(sanitized.get("card_show_extra_meta", True))
    sanitized["detail_enrichment_max_per_complex"] = _clamp_int(
        sanitized.get("detail_enrichment_max_per_complex", 0), 0, 0, 500
    )
    sanitized["article_api_page_delay_ms"] = _clamp_int(
        sanitized.get("article_api_page_delay_ms", 150), 150, 0, 2000
    )
    sanitized["playwright_detail_workers"] = _clamp_int(
        sanitized.get("playwright_detail_workers", 4), 4, 1, 16
    )
    sanitized["result_extra_columns"] = normalize_result_extra_columns(
        sanitized.get("result_extra_columns", [])
    )
    return sanitized
