"""Detail-fetcher facade (SOLID split).

Responsibility groups live in :mod:`src.core.services.detail_fetcher_parts`:

- ``money`` — Korean-won amount parsing (SRP: price syntax).
- ``page_primitives`` — navigation / body-read / task-drain primitives.
- ``hydration`` — embedded JSON state extraction.
- ``text_extract`` — corpus / named-value / phone extraction.
- ``field_keys`` — detail-field key vocabularies.
- ``field_merge`` — named-tree mapping and field-map merging.
- ``front_api`` — fin.land front-API session and artifact supplement.
- ``artifacts`` — per-article artifact collectors.
- ``detail_parse`` — detail-field parsing, scoring and meta building.
- ``orchestrator`` — :func:`fetch_mobile_article_detail` workflow.
- ``apply`` — :func:`apply_mobile_detail` result application.

This module re-exports the full previous public surface so existing
``from src.core.services.detail_fetcher import ...`` imports keep working.
"""
from __future__ import annotations

from src.core.services.detail_fetcher_parts.money import parse_kr_money_to_won
from src.core.services.detail_fetcher_parts.page_primitives import (
    _drain_pending_tasks,
    _goto_detail_url,
    _is_meaningful_body,
    _is_not_found_body,
    _read_body_text,
    _spawn_response_task,
)
from src.core.services.detail_fetcher_parts.hydration import _read_hydration_state
from src.core.services.detail_fetcher_parts.text_extract import (
    _build_detail_corpus,
    _find_named_value,
    _first_phone_from_value,
    _flatten_text_fragments,
    _phone_list_from_value,
)
from src.core.services.detail_fetcher_parts.field_keys import (
    _AGENT_NAME_KEYS,
    _OFFICE_KEYS,
    _PHONE_KEYS,
    _PREV_JEONSE_KEYS,
)
from src.core.services.detail_fetcher_parts.field_merge import (
    _backfill_fields_from_artifacts,
    _fields_from_named_tree,
    _merge_detail_field_maps,
)
from src.core.services.detail_fetcher_parts.front_api import (
    _fetch_front_api_json,
    _request_context_from_page,
    _supplement_front_api_artifacts,
    _warm_front_api_session,
    build_front_api_agent_url,
    build_front_api_basic_info_url,
    parse_front_api_agent_payload,
)
from src.core.services.detail_fetcher_parts.artifacts import (
    _collect_detail_artifacts,
    _collect_inline_artifacts,
)
from src.core.services.detail_fetcher_parts.detail_parse import (
    _build_detail_meta,
    _detail_candidate_score,
    _detail_core_field_score,
    _merge_detail_artifacts,
    _parse_detail_fields,
)
from src.core.services.detail_fetcher_parts.orchestrator import fetch_mobile_article_detail
from src.core.services.detail_fetcher_parts.apply import apply_mobile_detail

__all__ = [
    "parse_kr_money_to_won",
    "_is_not_found_body",
    "_is_meaningful_body",
    "_goto_detail_url",
    "_spawn_response_task",
    "_drain_pending_tasks",
    "_read_body_text",
    "_read_hydration_state",
    "_flatten_text_fragments",
    "_build_detail_corpus",
    "_find_named_value",
    "_first_phone_from_value",
    "_phone_list_from_value",
    "_OFFICE_KEYS",
    "_AGENT_NAME_KEYS",
    "_PHONE_KEYS",
    "_PREV_JEONSE_KEYS",
    "_merge_detail_field_maps",
    "_fields_from_named_tree",
    "_backfill_fields_from_artifacts",
    "build_front_api_agent_url",
    "build_front_api_basic_info_url",
    "parse_front_api_agent_payload",
    "_request_context_from_page",
    "_fetch_front_api_json",
    "_warm_front_api_session",
    "_supplement_front_api_artifacts",
    "_collect_detail_artifacts",
    "_collect_inline_artifacts",
    "_parse_detail_fields",
    "_detail_core_field_score",
    "_detail_candidate_score",
    "_merge_detail_artifacts",
    "_build_detail_meta",
    "fetch_mobile_article_detail",
    "apply_mobile_detail",
]
