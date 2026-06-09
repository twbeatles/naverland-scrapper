from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING
from urllib.parse import urlencode

from src.core.services.map_geometry import build_grid_sweep_coords, clamp_korea
from src.core.services.response_capture import TRADE_CODE_MAP, normalize_marker_payload

if TYPE_CHECKING:
    from src.core.engines.playwright_engine import *  # noqa: F403

_TRADE_TO_CODE: dict[str, str] = {value: key for key, value in TRADE_CODE_MAP.items()}


class PlaywrightGeoScanMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    async def _run_geo(self):
        await self._ensure_started()
        geo = self.thread.geo_config
        if not geo:
            raise RuntimeError("geo_config가 없습니다.")
        if not self._desktop_page:
            raise RuntimeError("desktop page 초기화 실패")

        lat, lon = clamp_korea(geo.lat, geo.lon)
        zoom = int(geo.zoom or 15)
        discovered: dict[str, dict] = {}
        self.thread.log(
            f"지도 탐색 시작: lat={lat:.5f}, lon={lon:.5f}, zoom={zoom}, 자산={','.join(geo.asset_types)}"
        )

        marker_handler, marker_pending_tasks, marker_stats = self._build_marker_handler(discovered)
        marker_wait_count = 0
        marker_drain_timed_out = False
        self._desktop_page.on("response", marker_handler)
        try:
            for asset_type in geo.asset_types:
                if self.thread._should_stop():
                    break
                for trade_type in self.thread.trade_types:
                    if self.thread._should_stop():
                        break
                    try:
                        await self._scan_geo_asset_type(asset_type, trade_type, lat, lon, zoom, geo)
                    except Exception as exc:
                        self.thread._mark_geo_incomplete(
                            "geo_scan_failure",
                            f"{asset_type}/{trade_type}",
                        )
                        self.thread.log(
                            f"   geo scan failure: {asset_type}/{trade_type} - {exc}",
                            30,
                        )
        finally:
            try:
                self._desktop_page.remove_listener("response", marker_handler)
            except Exception:
                pass
            marker_wait_count, marker_drain_timed_out = await self._drain_pending_response_tasks(
                marker_pending_tasks,
                label="geo_marker",
            )

        dedup_removed = int(marker_stats.get("dedup_skipped", 0))
        if marker_drain_timed_out:
            self.thread._mark_geo_incomplete("marker_drain_timeout", "geo_marker")
        self.thread.log(
            f"지도 탐색 요약: 발견 단지 {len(discovered)}, 중복 제거 {dedup_removed}, 응답 처리 대기 {marker_wait_count}",
            10,
        )
        self.thread.stats["geo_discovered_count"] = len(discovered)
        self.thread.stats["geo_dedup_count"] = dedup_removed
        self.thread.emit_stats()

        persistence_allowed = self.thread._should_persist_geo_results()
        flushed_count = self.thread._flush_discovered_complex_registrations()
        if self.thread.geo_incomplete:
            reason_summary = self.thread._geo_incomplete_reason_summary() or "unknown"
            persistence_note = ""
            if not persistence_allowed:
                persistence_note = " (safety mode: auto-register/history/disappeared skipped)"
            self.thread.log(f"Geo incomplete: {reason_summary}{persistence_note}", 30)
        elif flushed_count:
            self.thread.log(f"   geo discovered complexes registered: {flushed_count}", 10)

        ordered = sorted(discovered.values(), key=lambda row: (-int(row.get("count", 0)), row.get("complex_name", "")))
        if not ordered:
            self.thread.log("지도 탐색 결과 단지를 찾지 못했습니다.", 30)
            return

        processed_pairs = set()
        total = len(ordered) * max(1, len(self.thread.trade_types))
        current = 0
        force_incomplete_history = bool(self.thread.geo_incomplete and not self.thread.geo_incomplete_safety_mode)
        for row in ordered:
            if self.thread._should_stop():
                break
            name = str(row.get("complex_name", ""))
            cid = str(row.get("complex_id", ""))
            asset_type = str(row.get("asset_type", "APT"))
            complex_count = 0
            attempted_trade_types = []
            complex_trade_types = []
            for trade_type in self.thread.trade_types:
                if self.thread._should_stop():
                    break
                if trade_type not in attempted_trade_types:
                    attempted_trade_types.append(trade_type)
                await self._check_memory_and_recycle_if_needed("geo_loop")
                current += 1
                self.thread.progress_signal.emit(
                    int(current / total * 100) if total else 0,
                    f"{name} ({trade_type})",
                    self.thread._estimate_remaining_seconds(current, total),
                )
                try:
                    result = await self._crawl_target_with_cache(
                        name,
                        cid,
                        trade_type,
                        asset_type=asset_type,
                        mode="geo_sweep",
                        source_lat=lat,
                        source_lon=lon,
                        source_zoom=zoom,
                        marker_id=str(row.get("marker_id", "")),
                    )
                    if bool(result.get("block_like_redirect", False)):
                        raise RuntimeError(str(result.get("block_reason", "") or "block-like redirect"))
                    if bool(result.get("capture_failed", False)):
                        raise RuntimeError(str(result.get("failure_reason", "") or "capture failed after navigation"))
                    count = int(result.get("count", 0))
                    complex_count += count
                    if trade_type not in complex_trade_types:
                        complex_trade_types.append(trade_type)
                    processed_pairs.add((asset_type, cid, trade_type))
                    self.thread.stats["by_trade_type"][trade_type] = (
                        self.thread.stats["by_trade_type"].get(trade_type, 0) + count
                    )
                    reset_streak = getattr(self.thread, "_reset_block_detection_streak", None)
                    if callable(reset_streak):
                        reset_streak()
                except Exception as exc:
                    self.thread.log(f"   {name}({trade_type}) 수집 실패: {exc}", 40)
                    is_block_like = getattr(self.thread, "_is_block_like_error", None)
                    block_like = bool(is_block_like(exc)) if callable(is_block_like) else False
                    if block_like:
                        register_block = getattr(self.thread, "_register_block_detection", None)
                        should_cooldown = bool(register_block(str(exc))) if callable(register_block) else False
                        if should_cooldown:
                            self.thread.log(
                                f"   ⏸️ 차단 신호 3회 연속 감지, {int(self.thread._block_cooldown_seconds)}초 쿨다운",
                                30,
                            )
                            if not await self._sleep_async_interruptible(self.thread._block_cooldown_seconds):
                                break
                    else:
                        reset_streak = getattr(self.thread, "_reset_block_detection_streak", None)
                        if callable(reset_streak):
                            reset_streak()
            if not attempted_trade_types:
                continue
            run_status = self.thread._determine_run_status(
                self.thread.trade_types,
                complex_trade_types,
                attempted_trade_types,
                force_incomplete=force_incomplete_history,
            )
            history_trade_types = complex_trade_types or attempted_trade_types
            if not persistence_allowed:
                continue
            if not complex_trade_types and not force_incomplete_history:
                self.thread.log(f"   {name}({asset_type}) 거래 성공 없음: 이력 기록을 생략합니다.", 30)
                continue
            self.thread.record_crawl_history(
                name,
                cid,
                ",".join(history_trade_types),
                int(complex_count),
                engine=self.engine_name,
                mode="geo_sweep",
                source_lat=lat,
                source_lon=lon,
                source_zoom=zoom,
                asset_type=asset_type,
                run_status=run_status,
            )
            if complex_trade_types:
                self.thread.complex_finished_signal.emit(name, cid, ",".join(complex_trade_types), int(complex_count))
        self.thread._finalize_disappeared_articles(processed_pairs)

    async def _scan_geo_asset_type(
        self,
        asset_type: str,
        trade_type: str,
        lat: float,
        lon: float,
        zoom: int,
        geo,
    ):
        if not self._desktop_page:
            return False
        base_kind = "houses" if asset_type == "VL" else "complexes"
        trade_code = _TRADE_TO_CODE.get(trade_type, "A1")
        url = (
            f"https://new.land.naver.com/{base_kind}?"
            + urlencode({"ms": f"{lat},{lon},{zoom}", "a": asset_type, "tradeTypes": trade_code})
        )
        last_failure = ""
        for plan in self._build_entry_plans(url):
            try:
                await self._run_entry_plan(
                    self._desktop_page,
                    plan,
                    label=f"geo {asset_type}/{trade_type}",
                )
                page_state = await self._classify_page_state(self._desktop_page)
                if bool(page_state.get("block_like_redirect", False)):
                    last_failure = str(
                        page_state.get("block_reason", "") or page_state.get("final_url", "") or "block-like redirect"
                    )
                    continue
                try:
                    await self._async_retry(
                        "geo canvas wait",
                        lambda: self._desktop_page.wait_for_selector("canvas", timeout=15000),
                    )
                except Exception:
                    self.thread.log("geo canvas wait timeout", 10)
                await self._human_like_recenter(lat, lon, zoom)
                switched = await self._switch_to_listing_markers()
                if not switched:
                    self.thread._mark_geo_incomplete(
                        "marker_switch_fail",
                        f"{asset_type}/{trade_type}",
                    )
                    return False
                coords = build_grid_sweep_coords(lat, lon, zoom, rings=geo.rings, step_px=geo.step_px)
                dwell_ms = max(100, int(geo.dwell_ms))
                total = len(coords)
                for idx, (target_lat, target_lon) in enumerate(coords, 1):
                    if self.thread._should_stop():
                        break
                    self.thread.log(f"   {asset_type}/{trade_type} 탐색 {idx}/{total}", 10)
                    await self._drag_to_latlon(target_lat, target_lon)
                    try:
                        await self._desktop_page.mouse.wheel(0, -40)
                    except Exception:
                        pass
                    await self._desktop_page.wait_for_timeout(dwell_ms)
                return True
            except Exception as exc:
                last_failure = str(exc)
                self.thread.log(
                    f"   geo entry plan 실패({asset_type}/{trade_type}, {plan.get('name', 'direct')}): {exc}",
                    20,
                )
                continue
        if await self._maybe_enable_headed_fallback(last_failure or f"geo {asset_type}/{trade_type}"):
            return await self._scan_geo_asset_type(asset_type, trade_type, lat, lon, zoom, geo)
        raise RuntimeError(f"block-like redirect: {last_failure or url}")
