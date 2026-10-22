from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING

from src.core.services.fin_article_api import parse_fin_bounded_complexes
from src.core.services.map_geometry import build_grid_sweep_coords, viewport_bounds
from src.core.services.site_contract import (
    FRONT_API_BOUNDED_COMPLEXES,
    build_fin_bounded_complexes_body,
    trade_type_to_code,
)

if TYPE_CHECKING:
    from src.core.engines.playwright_engine import *  # noqa: F403


class PlaywrightGeoFinMarkerMixin:
    """Geo discovery via fin ``boundedComplexes`` (primary since 2026-10-22).

    The fin map list panel returns complexes (APT ``COMPLEX`` / VL ``VILLA``)
    with names and per-trade listing counts for a bounding box, so the sweep
    needs no map dragging: each grid point becomes one bbox query.
    """

    # Class attributes (facade rebind): discovery page cap per grid point.
    FIN_GEO_MAX_PAGES = 10
    FIN_GEO_PAGE_DELAY_SEC = 0.4

    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    async def _fetch_fin_bounded_complexes(
        self,
        discovered: dict[str, dict],
        *,
        asset_type: str,
        trade_type: str,
        lat: float,
        lon: float,
        zoom: int,
    ) -> tuple[bool, int]:
        """Page through one bbox. Returns (ok, newly added markers)."""
        import json

        include_pre = bool(getattr(self.thread, "include_pre_sale_rights", False))
        bounds = viewport_bounds(lat, lon, zoom)
        trade_code = trade_type_to_code(trade_type)
        stats = self.thread.stats
        last_info: list = []
        seed = ""
        added = 0
        for page_no in range(1, int(self.FIN_GEO_MAX_PAGES) + 1):
            if self.thread._should_stop():
                return True, added
            if page_no > 1:
                await asyncio.sleep(float(self.FIN_GEO_PAGE_DELAY_SEC))
            body = build_fin_bounded_complexes_body(
                asset_type=asset_type,
                trade_type=trade_type,
                bounds=bounds,
                zoom=zoom,
                last_info=last_info,
                seed=seed,
                include_pre=include_pre,
            )
            stats["geo_fin_api_attempt_count"] = int(stats.get("geo_fin_api_attempt_count", 0)) + 1
            try:
                status, text = await self._fin_fetch(FRONT_API_BOUNDED_COMPLEXES, method="POST", body=body)
            except Exception:
                status, text = 0, ""
            parsed = None
            if status == 200:
                try:
                    parsed = parse_fin_bounded_complexes(json.loads(text), trade_code=trade_code)
                except (TypeError, ValueError):
                    parsed = None
            if parsed is None:
                stats["geo_fin_api_fail_count"] = int(stats.get("geo_fin_api_fail_count", 0)) + 1
                stats["geo_fin_api_last_status"] = str(status)
                return False, added
            added += self._ingest_normalized_markers(discovered, parsed["markers"], asset_type=asset_type)
            if not parsed["has_next"] or not parsed["last_info"]:
                return True, added
            last_info = parsed["last_info"]
            seed = parsed["seed"] or seed
        stats["geo_fin_page_cap_count"] = int(stats.get("geo_fin_page_cap_count", 0)) + 1
        self.thread.log(
            f"   {asset_type}/{trade_type}: 한 구역의 단지가 많아 매물 많은 순 상위 "
            f"{int(self.FIN_GEO_MAX_PAGES) * 30}곳까지만 찾았습니다. 줌을 높이면 더 세밀하게 찾습니다.",
            20,
        )
        return True, added

    async def _scan_geo_asset_type_fin(
        self,
        asset_type: str,
        trade_type: str,
        lat: float,
        lon: float,
        zoom: int,
        geo,
    ) -> bool | None:
        """Grid sweep over fin bbox queries.

        ``None`` = fin unusable from the first query (caller falls back to the
        new.land map); ``True`` = sweep finished (later failures mark the geo
        run incomplete instead of switching sources mid-sweep).
        """
        discovered = getattr(self, "_geo_discovered_ref", None)
        if not isinstance(discovered, dict):
            discovered = {}
            self._geo_discovered_ref = discovered
        coords = build_grid_sweep_coords(lat, lon, zoom, rings=geo.rings, step_px=geo.step_px)
        total = len(coords)
        for idx, (target_lat, target_lon) in enumerate(coords, 1):
            if self.thread._should_stop():
                break
            self.thread.log(f"   {asset_type}/{trade_type} 탐색 {idx}/{total}", 10)
            ok, _added = await self._fetch_fin_bounded_complexes(
                discovered,
                asset_type=asset_type,
                trade_type=trade_type,
                lat=target_lat,
                lon=target_lon,
                zoom=zoom,
            )
            if not ok:
                if idx == 1:
                    return None
                self.thread._mark_geo_incomplete("fin_marker_fail", f"{asset_type}/{trade_type}/{idx}")
            if idx < total:
                # The geo "dwell" setting is the pause between zones on the fin path.
                dwell_sec = max(0.0, float(getattr(geo, "dwell_ms", 0) or 0) / 1000.0)
                await asyncio.sleep(max(float(self.FIN_GEO_PAGE_DELAY_SEC), dwell_sec))
        self.thread.stats["geo_marker_switch_last_method"] = "fin_bounded_complexes"
        return True
