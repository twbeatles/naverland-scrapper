from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING

from src.core.services.detail_fetcher import apply_mobile_detail, fetch_mobile_article_detail
from src.core.services.response_capture import detect_trade_type, normalize_article_payload
from src.core.services.site_contract import HOST_NEW, build_complex_page_url

if TYPE_CHECKING:
    from src.core.engines.playwright_engine import *  # noqa: F403

_LEGACY_ARTICLE_ID_KEY = "\uf9cd\u317b\u042aID"


class PlaywrightResponseCaptureMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    async def _collect_target_raw_items(
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
        await self._ensure_started()
        raw_items: list[dict] = []
        seen_ids: set[str] = set()
        response_seen = False
        parse_success = False
        parse_failed = False
        drain_timed_out = False
        response_match_count = 0
        final_url = ""
        block_like_redirect = False
        block_reason = ""
        confirmed_capture = False
        confirmed_parse_success = False
        capture_last_payload: dict | None = None
        active_base_kind = "complexes"
        active_path_asset = str(asset_type or "APT")
        active_target_url = f"{HOST_NEW}/complexes/{cid}"
        include_pre = bool(getattr(self.thread, "include_pre_sale_rights", False))
        self._article_supplement_result = {}
        capture_invalid_rows = False

        # fin.land front-api is the primary source since the 2026-10 site switch;
        # new.land Article API / response capture below remain as fallback.
        if self._fin_front_api_enabled(active_path_asset):
            try:
                fin_result = await self._fetch_fin_article_list(
                    name=name,
                    cid=cid,
                    trade_type=trade_type,
                    path_asset=active_path_asset,
                    mode=mode,
                    source_lat=source_lat,
                    source_lon=source_lon,
                    source_zoom=source_zoom,
                    marker_id=marker_id,
                    seen_ids=seen_ids,
                )
            except Exception as exc:
                fin_result = None
                self._record_fin_api_failure(type(exc).__name__, status=type(exc).__name__)
                self.thread.log(f"   fin front-api 실패({cid}), new.land 경로로 전환: {exc}", 20)
            if fin_result is not None:
                return fin_result
            seen_ids.clear()

        for base_kind, path_asset in self._candidate_paths(asset_type):
            # Use live map keys (a / b / e); bare path_asset + tradeTypes is ignored by site.
            target_url = build_complex_page_url(
                cid,
                base_kind=base_kind,
                path_asset=path_asset,
                trade_type=trade_type,
                lat=source_lat,
                lon=source_lon,
                zoom=source_zoom,
                include_pre=include_pre,
            )
            active_base_kind = base_kind
            active_path_asset = path_asset
            active_target_url = target_url
            api_result = await self._fetch_article_api_fast_path(
                name=name,
                cid=cid,
                trade_type=trade_type,
                base_kind=base_kind,
                path_asset=path_asset,
                target_url=target_url,
                mode=mode,
                source_lat=source_lat,
                source_lon=source_lon,
                source_zoom=source_zoom,
                marker_id=marker_id,
                seen_ids=seen_ids,
            )
            if api_result is not None:
                return api_result

            page = self._desktop_page
            if page is None:
                break
            plan_key = (str(mode or "complex"), str(asset_type or "APT").upper(), str(base_kind or ""))
            for plan in self._ordered_entry_plans(target_url, plan_key):
                pending_tasks: set[asyncio.Task] = set()
                response_event = asyncio.Event()
                plan_response_seen = False
                plan_parse_success = False
                plan_parse_failed = False
                plan_block_like_redirect = False
                plan_block_reason = ""
                plan_final_url = ""

                async def _consume(response):
                    nonlocal response_seen, parse_success, parse_failed, response_match_count
                    nonlocal plan_response_seen, plan_parse_success, plan_parse_failed
                    nonlocal capture_last_payload, capture_invalid_rows
                    url = response.url
                    expected = f"/api/articles/{'house' if base_kind == 'houses' else 'complex'}/{cid}"
                    if expected not in url:
                        return
                    response_match_count += 1
                    response_seen = True
                    plan_response_seen = True
                    self._remember_article_api_request_headers(response)
                    if int(getattr(response, "status", 200) or 200) >= 400:
                        parse_failed = True
                        plan_parse_failed = True
                        response_event.set()
                        return
                    try:
                        payload = await response.json()
                    except Exception:
                        parse_failed = True
                        plan_parse_failed = True
                        response_event.set()
                        return
                    items, valid = self._normalize_article_api_payload(
                        payload, name=name, cid=cid, trade_type=trade_type,
                        path_asset=path_asset, mode=mode, source_lat=source_lat,
                        source_lon=source_lon, source_zoom=source_zoom,
                        marker_id=marker_id, seen_ids=seen_ids,
                    )
                    raw_items.extend(items)
                    if not valid:
                        capture_invalid_rows = capture_invalid_rows or bool(items)
                        parse_failed = True
                        plan_parse_failed = True
                        response_event.set()
                        return
                    capture_last_payload = payload
                    parse_success = True
                    plan_parse_success = True
                    response_event.set()

                def _handle(response):
                    try:
                        self._spawn_response_task(pending_tasks, _consume(response))
                    except Exception:
                        return None

                page.on("response", _handle)
                try:
                    await self._run_entry_plan(
                        page,
                        plan,
                        label=f"article {base_kind}/{cid}",
                    )
                    try:
                        await asyncio.wait_for(
                            response_event.wait(),
                            timeout=max(0.1, float(self._article_response_wait_ms()) / 1000.0),
                        )
                    except Exception:
                        pass
                    if response_event.is_set() and (
                        raw_items or (plan_response_seen and plan_parse_success and not plan_parse_failed)
                    ):
                        plan_final_url = str(getattr(page, "url", "") or "")
                    else:
                        try:
                            await self._async_retry(
                                f"article load {base_kind}/{cid}",
                                lambda: page.wait_for_load_state("networkidle", timeout=6000),
                            )
                        except Exception:
                            pass
                        for text in ["매매", trade_type]:
                            try:
                                await page.locator(f"text={text}").first.click(timeout=1000)
                                await page.wait_for_timeout(400)
                            except Exception:
                                continue
                        await page.wait_for_timeout(1800)
                        page_state = await self._classify_page_state(page)
                        plan_final_url = str(page_state.get("final_url", "") or "")
                        plan_block_like_redirect = bool(page_state.get("block_like_redirect", False))
                        plan_block_reason = str(page_state.get("block_reason", "") or "")
                except Exception as exc:
                    self.thread.log(
                        f"   entry plan 실패({base_kind}/{cid}, {plan.get('name', 'direct')}): {exc}",
                        20,
                    )
                finally:
                    try:
                        page.remove_listener("response", _handle)
                    except Exception:
                        pass
                    _, timed_out = await self._drain_pending_response_tasks(
                        pending_tasks,
                        label=f"article_capture:{base_kind}/{cid}:{plan.get('name', 'direct')}",
                    )
                    drain_timed_out = drain_timed_out or bool(timed_out)

                if plan_final_url:
                    final_url = plan_final_url
                block_like_redirect = bool(plan_block_like_redirect and not raw_items)
                if plan_block_reason:
                    block_reason = plan_block_reason
                if plan_response_seen and plan_parse_success:
                    confirmed_capture = True
                    confirmed_parse_success = True
                    self._remember_entry_plan_success(plan_key, str(plan.get("name", "direct") or "direct"))
                if raw_items:
                    break
                if plan_response_seen and plan_parse_success and not plan_parse_failed and not plan_block_like_redirect:
                    break
            if raw_items:
                break

        if capture_last_payload is not None:
            raw_items = await self._supplement_article_api_pages(
                name=name,
                cid=cid,
                trade_type=trade_type,
                base_kind=active_base_kind,
                path_asset=active_path_asset,
                target_url=active_target_url,
                mode=mode,
                source_lat=source_lat,
                source_lon=source_lon,
                source_zoom=source_zoom,
                marker_id=marker_id,
                seen_ids=seen_ids,
                existing_items=raw_items,
                last_payload=capture_last_payload,
            )

        capture_failed = bool(not raw_items and not confirmed_capture and (block_like_redirect or not response_seen or parse_failed))
        failure_reason = ""
        if block_like_redirect:
            failure_reason = f"block-like redirect: {block_reason or final_url or 'unknown'}"
        elif not response_seen:
            failure_reason = f"response capture missing: {final_url or 'no_final_url'}"
        elif parse_failed and not confirmed_capture:
            failure_reason = f"response parse failed: {final_url or 'no_final_url'}"

        supplement = dict(getattr(self, "_article_supplement_result", {}) or {})
        complete = bool(
            confirmed_capture and not drain_timed_out and not capture_invalid_rows
            and supplement.get("collection_status") == "complete"
        )
        if not complete:
            failure_reason = failure_reason or str(supplement.get("failure_reason") or "capture_incomplete")

        return {
            "raw_items": raw_items,
            "response_seen": response_seen,
            "parse_success": bool(confirmed_parse_success or (parse_success and not parse_failed)),
            "drain_timed_out": drain_timed_out,
            "response_match_count": response_match_count,
            "final_url": final_url,
            "block_like_redirect": block_like_redirect,
            "block_reason": block_reason,
            "capture_failed": capture_failed,
            "failure_reason": failure_reason,
            "collection_status": "complete" if complete else ("partial" if raw_items else "failed"),
            "last_successful_page": int(supplement.get("last_successful_page", 0)),
            "failed_page": int(supplement.get("failed_page", 0)),
        }
