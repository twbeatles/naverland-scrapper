from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING

from src.core.services.map_geometry import viewport_bounds
from src.core.services.response_capture import normalize_marker_payload
from src.core.services.site_contract import build_single_markers_url

if TYPE_CHECKING:
    from src.core.engines.playwright_engine import *  # noqa: F403


class PlaywrightGeoMarkerMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    def _ingest_marker_payload(
        self,
        discovered: dict[str, dict],
        payload: Any,
        *,
        asset_type: str,
        stats: dict | None = None,
    ) -> int:
        if not isinstance(payload, list):
            return 0
        added = 0
        asset = str(asset_type or "APT").strip().upper() or "APT"
        for raw_marker in payload:
            marker = normalize_marker_payload(raw_marker, asset_type=asset)
            cid = marker.get("complex_id", "")
            if not cid:
                continue
            dedupe_key = f"{asset}:{cid}"
            current = discovered.get(dedupe_key)
            marker_count = int(marker.get("count", 0) or 0)
            current_count = int(current.get("count", 0) or 0) if current else -1
            if current is None or marker_count > current_count:
                discovered[dedupe_key] = marker
                added += 1
                self.thread.stats["geo_discovered_count"] = len(discovered)
                self.thread.register_discovered_complex(marker)
                self.thread.emit_stats()
            else:
                if stats is not None:
                    stats["dedup_skipped"] = int(stats.get("dedup_skipped", 0)) + 1
                    self.thread.stats["geo_dedup_count"] = int(stats.get("dedup_skipped", 0) or 0)
                    self.thread.emit_stats()
        return added

    async def _fetch_single_markers_api(
        self,
        discovered: dict[str, dict],
        *,
        asset_type: str,
        trade_type: str,
        lat: float,
        lon: float,
        zoom: int,
    ) -> int:
        """Direct single-markers/2.0 request (fallback when DOM marker switch fails)."""
        context = self._desktop_context
        request_context = getattr(context, "request", None) if context is not None else None
        if request_context is None or not hasattr(request_context, "get"):
            return 0
        bounds = viewport_bounds(lat, lon, zoom)
        include_pre = bool(getattr(self.thread, "include_pre_sale_rights", False))
        url = build_single_markers_url(
            asset_type=asset_type,
            trade_type=trade_type,
            zoom=zoom,
            left_lon=bounds["leftLon"],
            right_lon=bounds["rightLon"],
            top_lat=bounds["topLat"],
            bottom_lat=bounds["bottomLat"],
            include_pre=include_pre,
        )
        self.thread.stats["geo_marker_api_attempt_count"] = (
            int(self.thread.stats.get("geo_marker_api_attempt_count", 0)) + 1
        )
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "ko-KR,ko;q=0.9",
            "referer": "https://new.land.naver.com/complexes",
        }
        try:
            response = await request_context.get(url, headers=headers, timeout=12000)
            status = int(getattr(response, "status", 0) or 0)
            if status >= 400:
                self.thread.stats["geo_marker_api_fail_count"] = (
                    int(self.thread.stats.get("geo_marker_api_fail_count", 0)) + 1
                )
                return 0
            payload = await response.json()
        except Exception:
            self.thread.stats["geo_marker_api_fail_count"] = (
                int(self.thread.stats.get("geo_marker_api_fail_count", 0)) + 1
            )
            return 0
        added = self._ingest_marker_payload(discovered, payload, asset_type=asset_type)
        if added > 0:
            self.thread.stats["geo_marker_api_hit_count"] = (
                int(self.thread.stats.get("geo_marker_api_hit_count", 0)) + 1
            )
            self.thread.stats["geo_marker_switch_last_method"] = "single_markers_api"
        return added

    def _build_marker_handler(self, discovered: dict[str, dict]):
        pending_tasks: set[asyncio.Task] = set()
        stats = {"dedup_skipped": 0}

        async def _consume(response):
            if self.thread._should_stop():
                return
            url = response.url
            if ("complexes/single-markers" not in url) and ("houses/single-markers" not in url):
                return
            try:
                payload = await response.json()
            except Exception:
                return
            asset = "VL" if "houses/" in url else "APT"
            self._ingest_marker_payload(discovered, payload, asset_type=asset, stats=stats)

        def _handle(response):
            try:
                self._spawn_response_task(pending_tasks, _consume(response))
            except Exception:
                return None

        return _handle, pending_tasks, stats

    async def _switch_to_listing_markers(self):
        if not self._desktop_page:
            return False
        self.thread.stats["geo_marker_switch_attempt_count"] = (
            int(self.thread.stats.get("geo_marker_switch_attempt_count", 0)) + 1
        )
        attempts: list[tuple[str, Any]] = []
        for text in ["상세매물검색", "매물", "매물검색", "매물 보기"]:
            attempts.append((f"text:{text}", self._desktop_page.locator(f"text={text}").first))
        for selector in [
            'button[aria-label*="매물"]',
            '[role="button"][aria-label*="매물"]',
            'button:has-text("매물")',
            '[class*="marker"] button',
            '[class*="map"] button:has-text("매물")',
            '[class*="filter"] button:has-text("매물")',
            '[class*="type"] button:has-text("매물")',
        ]:
            attempts.append((f"selector:{selector}", self._desktop_page.locator(selector).first))

        for label, locator in attempts:
            try:
                await locator.click(timeout=1200)
                await self._desktop_page.wait_for_timeout(500)
                self.thread.stats["geo_marker_switch_success_count"] = (
                    int(self.thread.stats.get("geo_marker_switch_success_count", 0)) + 1
                )
                self.thread.stats["geo_marker_switch_last_method"] = label
                self.thread.emit_stats()
                return True
            except Exception:
                continue
        try:
            await self._desktop_page.locator('button:has-text("유형")').first.click(timeout=1200)
            await self._desktop_page.wait_for_timeout(300)
            await self._desktop_page.locator("text=매물").first.click(timeout=1200)
            await self._desktop_page.wait_for_timeout(500)
            self.thread.stats["geo_marker_switch_success_count"] = (
                int(self.thread.stats.get("geo_marker_switch_success_count", 0)) + 1
            )
            self.thread.stats["geo_marker_switch_last_method"] = "type_menu:text:매물"
            self.thread.emit_stats()
            return True
        except Exception:
            self.thread.stats["geo_marker_switch_fail_count"] = (
                int(self.thread.stats.get("geo_marker_switch_fail_count", 0)) + 1
            )
            self.thread.emit_stats()
            return False
