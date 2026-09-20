from __future__ import annotations

from typing import Any
from src.core.managers_parts.schedule_normalize import _clamp_int
from src.core.managers_parts.settings_manager import get_settings


def collection_runtime_kwargs(settings_obj: Any = None) -> dict[str, Any]:
    """Kwargs shared by complex/geo crawler thread construction."""
    src = settings_obj if settings_obj is not None else get_settings()
    getter = src.get if hasattr(src, "get") else (lambda k, d=None: d)
    return {
        "include_pre_sale_rights": bool(getter("include_pre_sale_rights", False)),
        "detail_enrichment_enabled": bool(getter("detail_enrichment_enabled", True)),
        "detail_enrichment_max_per_complex": _clamp_int(
            getter("detail_enrichment_max_per_complex", 0), 0, 0, 500
        ),
        "detail_front_api_enabled": bool(getter("detail_front_api_enabled", True)),
        "detail_front_api_only": bool(getter("detail_front_api_only", False)),
        "article_api_page_delay_ms": _clamp_int(
            getter("article_api_page_delay_ms", 150), 150, 0, 2000
        ),
    }
