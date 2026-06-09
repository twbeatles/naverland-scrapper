from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING
from urllib.parse import urlencode

from src.core.services.map_geometry import build_grid_sweep_coords, clamp_korea
from src.core.services.response_capture import TRADE_CODE_MAP, normalize_marker_payload

if TYPE_CHECKING:
    from src.core.engines.playwright_engine import *  # noqa: F403

_TRADE_TO_CODE: dict[str, str] = {value: key for key, value in TRADE_CODE_MAP.items()}


class PlaywrightGeoMarkerMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

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
            if not isinstance(payload, list):
                return
            asset = "VL" if "houses/" in url else "APT"
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
                    self.thread.stats["geo_discovered_count"] = len(discovered)
                    self.thread.register_discovered_complex(marker)
                    self.thread.emit_stats()
                else:
                    stats["dedup_skipped"] = int(stats.get("dedup_skipped", 0)) + 1
                    self.thread.stats["geo_dedup_count"] = int(stats.get("dedup_skipped", 0) or 0)
                    self.thread.emit_stats()

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
