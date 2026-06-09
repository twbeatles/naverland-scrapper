from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING
from urllib.parse import urlencode

from src.core.services.map_geometry import build_grid_sweep_coords, clamp_korea
from src.core.services.response_capture import TRADE_CODE_MAP, normalize_marker_payload

if TYPE_CHECKING:
    from src.core.engines.playwright_engine import *  # noqa: F403

_TRADE_TO_CODE: dict[str, str] = {value: key for key, value in TRADE_CODE_MAP.items()}


class PlaywrightGeoMapControlMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    async def _get_ms(self):
        if not self._desktop_page:
            return None
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(self._desktop_page.url)
        ms = parse_qs(parsed.query).get("ms", [None])[0]
        if not ms:
            return None
        try:
            lat, lon, zoom = ms.split(",")
            return float(lat), float(lon), float(zoom)
        except Exception:
            return None

    async def _wheel_to_zoom(self, target_zoom: int, delay_ms: int = 300):
        if not self._desktop_page:
            return
        for _ in range(20):
            if self.thread._should_stop():
                return
            current = await self._get_ms()
            if not current:
                await self._desktop_page.wait_for_timeout(delay_ms)
                continue
            _, _, zoom = current
            zoom = round(zoom)
            if zoom == target_zoom:
                return
            await self._desktop_page.mouse.move(960, 540)
            await self._desktop_page.mouse.wheel(0, -300 if target_zoom > zoom else 300)
            await self._desktop_page.wait_for_timeout(delay_ms)

    async def _drag_to_latlon(self, lat: float, lon: float, tolerance_px: float = 3.5):
        if not self._desktop_page:
            return
        import math

        from src.core.services.map_geometry import ll_to_pixel

        for _ in range(18):
            if self.thread._should_stop():
                return
            current = await self._get_ms()
            if not current:
                await self._desktop_page.wait_for_timeout(300)
                continue
            current_lat, current_lon, zoom = current
            x1, y1 = ll_to_pixel(current_lat, current_lon, zoom)
            x2, y2 = ll_to_pixel(lat, lon, zoom)
            dx, dy = x2 - x1, y2 - y1
            distance = math.hypot(dx, dy)
            if distance <= tolerance_px:
                return
            step = min(800.0, distance)
            ratio = step / (distance + 1e-9)
            mx, my = dx * ratio, dy * ratio
            await self._desktop_page.mouse.move(960, 540)
            await self._desktop_page.mouse.down()
            await self._desktop_page.mouse.move(960 - mx, 540 - my, steps=20)
            await self._desktop_page.mouse.up()
            await self._desktop_page.wait_for_timeout(350)

    async def _human_like_recenter(self, lat: float, lon: float, zoom: int):
        await self._wheel_to_zoom(max(9, zoom - 5))
        await self._drag_to_latlon(lat, lon)
        await self._wheel_to_zoom(zoom)
        await self._drag_to_latlon(lat, lon)
