"""Shared completeness contract for network, cache and persistence boundaries."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict

COLLECTION_SCHEMA_VERSION = 2


def observation_date(now: datetime | None = None) -> str:
    """Match SQLite CURRENT_DATE (UTC); scheduling remains local wall time."""
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).date().isoformat()


class CollectionResult(TypedDict, total=False):
    raw_items: list[dict]
    collection_status: Literal["complete", "partial", "failed"]
    failure_reason: str
    last_successful_page: int
    failed_page: int
    invalid_row_count: int
    response_seen: bool
    parse_success: bool
    capture_failed: bool
    drain_timed_out: bool
    response_match_count: int
    final_url: str
    block_like_redirect: bool
    block_reason: str
    api_fast_path: bool


def article_list_from_payload(payload: Any) -> list | None:
    """An explicit empty list is valid; missing keys/error envelopes are not."""
    if not isinstance(payload, dict) or payload.get("success") is False:
        return None
    for key in ("code", "detailCode"):
        code = str(payload.get(key, "") or "").upper()
        if code and code not in {"0", "200", "OK", "SUCCESS"}:
            return None
    for key in ("isMoreData", "moreData"):
        if key in payload and not isinstance(payload[key], bool):
            return None
    for key in ("articleList", "articles"):
        if key in payload:
            value = payload[key]
            return value if isinstance(value, list) else None
    return None


def result_is_complete(result: dict) -> bool:
    return (
        result.get("collection_status") == "complete"
        and not result.get("capture_failed")
        and not result.get("drain_timed_out")
        and not result.get("block_like_redirect")
    )


def collection_fingerprint(*, include_pre: bool = False) -> str:
    return f"articles-v{COLLECTION_SCHEMA_VERSION}:pre={int(include_pre)}"


def record_collection_result(stats: dict, result: dict, *, cid: str, asset_type: str,
                             trade_type: str, count: int, raw_count: int) -> None:
    """Keep only lineage/quality counters; never persist authentication or contact data."""
    stats.setdefault("collection_results", []).append({
        "complex_id": str(cid), "asset_type": asset_type, "trade_type": trade_type,
        "collection_status": result.get("collection_status", "failed"),
        "raw_count": raw_count, "matched_count": count,
        "failure_reason": str(result.get("failure_reason", "")),
        "last_successful_page": int(result.get("last_successful_page", 0)),
        "failed_page": int(result.get("failed_page", 0)),
        "cache_hit": bool(result.get("cache_hit", False)),
    })


def filter_fingerprint(area_filter: dict, price_filter: dict) -> str:
    encoded = json.dumps([area_filter, price_filter], sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def snapshot_block_reason(*, stopped=False, stats=None, area_filter=None, price_filter=None) -> str:
    stats = stats or {}
    if stopped:
        return "수집이 중단되어 기존 가격 통계를 유지합니다."
    if (area_filter or {}).get("enabled") or (price_filter or {}).get("enabled"):
        return "수집 필터가 적용되어 기존 전체 가격 통계를 유지합니다."
    if (stats.get("collection_incomplete_count", 0) or stats.get("history_save_failed", False)
            or any(r.get("collection_status") != "complete" for r in stats.get("collection_results", []))):
        return "일부 수집·저장이 완료되지 않아 기존 가격 통계를 유지합니다."
    if stats.get("geo_incomplete", False):
        return "지도 탐색이 완료되지 않아 기존 가격 통계를 유지합니다."
    if any(r.get("cache_hit") for r in stats.get("collection_results", [])):
        return "캐시 결과가 포함되어 기존 가격 통계를 유지합니다."
    return ""
