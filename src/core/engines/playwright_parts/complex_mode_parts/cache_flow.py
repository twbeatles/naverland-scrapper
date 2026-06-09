from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING
from urllib.parse import urlencode

from src.core.services.detail_fetcher import apply_mobile_detail, fetch_mobile_article_detail
from src.core.services.response_capture import TRADE_CODE_MAP, detect_trade_type, normalize_article_payload

if TYPE_CHECKING:
    from src.core.engines.playwright_engine import *  # noqa: F403

_TRADE_TO_CODE: dict[str, str] = {value: key for key, value in TRADE_CODE_MAP.items()}
_LEGACY_ARTICLE_ID_KEY = "\uf9cd\u317b\u042aID"


class PlaywrightComplexCacheFlowMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    async def _crawl_target_with_cache(
        self,
        name: str,
        cid: str,
        trade_type: str,
        *,
        asset_type: str = "",
        mode: str = "complex",
        source_lat: float | None = None,
        source_lon: float | None = None,
        source_zoom: int | None = None,
        marker_id: str = "",
    ) -> dict:
        cache = self.thread.cache
        mode_token = str(mode or "complex").strip().lower()
        is_complex_mode = mode_token == "complex"
        normalized_asset_type = str(asset_type or "APT").strip().upper() or "APT"
        cache_asset_type = normalized_asset_type if is_complex_mode else str(asset_type or "")
        cache_marker_id = "" if is_complex_mode else str(marker_id or cid or "")
        cache_ctx = {
            "mode": mode_token,
            "asset_type": cache_asset_type,
            "source_lat": source_lat,
            "source_lon": source_lon,
            "source_zoom": source_zoom,
            "marker_id": cache_marker_id,
        }
        if cache:
            cached = cache.get(cid, trade_type, **cache_ctx)
            if cached is None and is_complex_mode and cache_asset_type == "APT":
                legacy_candidates = [
                    {"mode": "complex", "asset_type": "", "marker_id": str(cid or "")},
                    {"mode": "complex", "asset_type": "APT", "marker_id": str(cid or "")},
                    {},
                ]
                for legacy_ctx in legacy_candidates:
                    legacy_cached = cache.get(cid, trade_type, **legacy_ctx)
                    if legacy_cached is None:
                        continue
                    cache.set(cid, trade_type, legacy_cached, **cache_ctx)
                    cached = legacy_cached
                    break
            if cached is not None:
                self.thread.log(f"   캐시 히트: {len(cached)}건 로드")
                self.thread.stats["cache_hits"] = self.thread.stats.get("cache_hits", 0) + 1
                matched = await self._process_raw_items_with_filtered_details(
                    list(cached or []),
                    trade_type,
                )
                return {
                    "count": matched,
                    "raw_count": len(cached),
                    "cache_hit": True,
                    "response_match_count": 0,
                    "capture_failed": False,
                    "block_like_redirect": False,
                    "block_reason": "",
                    "failure_reason": "",
                    "final_url": "",
                }

        collect_result = await self._collect_target_raw_items(
            name,
            cid,
            trade_type,
            asset_type=cache_asset_type if is_complex_mode else asset_type,
            mode=mode_token,
            source_lat=source_lat,
            source_lon=source_lon,
            source_zoom=source_zoom,
            marker_id=cache_marker_id if is_complex_mode else marker_id,
        )
        if bool(collect_result.get("capture_failed", False)) or bool(collect_result.get("block_like_redirect", False)):
            recovery_reason = str(
                collect_result.get("failure_reason", "")
                or collect_result.get("block_reason", "")
                or "capture recovery"
            )
            if await self._maybe_enable_headed_fallback(recovery_reason):
                collect_result = await self._collect_target_raw_items(
                    name,
                    cid,
                    trade_type,
                    asset_type=cache_asset_type if is_complex_mode else asset_type,
                    mode=mode_token,
                    source_lat=source_lat,
                    source_lon=source_lon,
                    source_zoom=source_zoom,
                    marker_id=cache_marker_id if is_complex_mode else marker_id,
                )
        raw_items = list(collect_result.get("raw_items", []) or [])
        response_seen = bool(collect_result.get("response_seen", False))
        parse_success = bool(collect_result.get("parse_success", response_seen))
        drain_timed_out = bool(collect_result.get("drain_timed_out", False))
        response_match_count = int(collect_result.get("response_match_count", 0) or 0)
        final_url = str(collect_result.get("final_url", "") or "")
        block_like_redirect = bool(collect_result.get("block_like_redirect", False))
        block_reason = str(collect_result.get("block_reason", "") or "")
        capture_failed = bool(collect_result.get("capture_failed", False))
        failure_reason = str(collect_result.get("failure_reason", "") or "")
        if response_seen:
            self.thread.stats["response_seen_count"] = int(self.thread.stats.get("response_seen_count", 0)) + 1
        if parse_success:
            self.thread.stats["parse_success_count"] = int(self.thread.stats.get("parse_success_count", 0)) + 1
        elif response_seen:
            self.thread.stats["parse_fail_count"] = int(self.thread.stats.get("parse_fail_count", 0)) + 1
        self.thread.stats["response_match_count"] = int(self.thread.stats.get("response_match_count", 0)) + response_match_count
        if final_url:
            self.thread.stats["playwright_last_final_url"] = final_url
        if block_reason:
            self.thread.stats["playwright_last_block_reason"] = block_reason
        if block_like_redirect:
            self.thread.stats["block_like_redirect_count"] = int(self.thread.stats.get("block_like_redirect_count", 0)) + 1
        if capture_failed:
            self.thread.stats["capture_failed_count"] = int(self.thread.stats.get("capture_failed_count", 0)) + 1
        if cache:
            if raw_items:
                cache.set(cid, trade_type, raw_items, **cache_ctx)
            else:
                ttl_seconds = int(max(0, self.thread.negative_cache_ttl_minutes) * 60)
                if (
                    response_seen
                    and parse_success
                    and not drain_timed_out
                    and not capture_failed
                    and not block_like_redirect
                    and ttl_seconds > 0
                ):
                    cache.set(
                        cid,
                        trade_type,
                        [],
                        ttl_seconds=ttl_seconds,
                        reason="confirmed_empty",
                        **cache_ctx,
                    )
                elif drain_timed_out:
                    self.thread.log("   ⚠️ drain timeout detected, negative cache skipped", 30)
                elif capture_failed or block_like_redirect:
                    self.thread.log("   ⚠️ capture failure detected, negative cache skipped", 30)
        matched = await self._process_raw_items_with_filtered_details(raw_items, trade_type)
        return {
            "count": matched,
            "raw_count": len(raw_items),
            "cache_hit": False,
            "response_seen": response_seen,
            "parse_success": parse_success,
            "drain_timed_out": drain_timed_out,
            "response_match_count": response_match_count,
            "capture_failed": capture_failed,
            "block_like_redirect": block_like_redirect,
            "block_reason": block_reason,
            "failure_reason": failure_reason,
            "final_url": final_url,
        }
