from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING

from src.core.services.article_api import (
    MAX_ARTICLE_API_PAGES,
    article_api_has_more_pages,
    article_api_list_count,
    article_api_path_kind,
    article_api_real_estate_type,
    build_article_api_url,
)
from src.core.services.detail_fetcher import apply_mobile_detail, fetch_mobile_article_detail
from src.core.services.response_capture import TRADE_CODE_MAP, detect_trade_type, normalize_article_payload

if TYPE_CHECKING:
    from src.core.engines.playwright_engine import *  # noqa: F403

_TRADE_TO_CODE: dict[str, str] = {value: key for key, value in TRADE_CODE_MAP.items()}
_LEGACY_ARTICLE_ID_KEY = "\uf9cd\u317b\u042aID"


class PlaywrightArticleApiMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    def _article_api_timeout_ms(self) -> int:
        try:
            return min(20000, max(300, int(getattr(self.thread, "playwright_article_api_timeout_ms", 2500))))
        except (TypeError, ValueError):
            return 2500

    def _article_response_wait_ms(self) -> int:
        try:
            return min(20000, max(100, int(getattr(self.thread, "playwright_article_response_wait_ms", 1200))))
        except (TypeError, ValueError):
            return 1200

    @staticmethod
    def _article_api_path_kind(base_kind: str) -> str:
        return article_api_path_kind(base_kind)

    @staticmethod
    def _article_api_real_estate_type(path_asset: str) -> str:
        return article_api_real_estate_type(path_asset)

    def _build_article_api_url(
        self,
        base_kind: str,
        cid: str,
        trade_type: str,
        path_asset: str = "APT",
        *,
        page: int = 1,
    ) -> str:
        return build_article_api_url(base_kind, cid, trade_type, path_asset, page=page)

    def _article_api_headers(self, target_url: str) -> dict[str, str]:
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "referer": target_url,
        }
        auth_header = str(getattr(self, "_article_api_auth_header", "") or "").strip()
        if auth_header:
            headers["authorization"] = auth_header
        return headers

    def _remember_article_api_request_headers(self, response) -> None:
        try:
            request = getattr(response, "request", None)
            headers = dict(getattr(request, "headers", {}) or {}) if request is not None else {}
        except Exception:
            headers = {}
        auth_header = str(headers.get("authorization", "") or headers.get("Authorization", "") or "").strip()
        if auth_header:
            self._article_api_auth_header = auth_header

    def _ordered_entry_plans(self, target_url: str, plan_key: tuple[str, str, str]) -> list[dict]:
        plans = self._build_entry_plans(target_url)
        preferred = str(getattr(self, "_entry_plan_success_by_key", {}).get(plan_key, "") or "")
        if not preferred:
            return plans
        preferred_plans = [plan for plan in plans if str(plan.get("name", "")) == preferred]
        if not preferred_plans:
            return plans
        return preferred_plans + [plan for plan in plans if str(plan.get("name", "")) != preferred]

    def _remember_entry_plan_success(self, plan_key: tuple[str, str, str], plan_name: str) -> None:
        if not plan_name:
            return
        try:
            self._entry_plan_success_by_key[plan_key] = str(plan_name)
        except Exception:
            self._entry_plan_success_by_key = {plan_key: str(plan_name)}

    def _normalize_article_api_payload(
        self,
        payload,
        *,
        name: str,
        cid: str,
        trade_type: str,
        path_asset: str,
        mode: str,
        source_lat: float | None,
        source_lon: float | None,
        source_zoom: int | None,
        marker_id: str,
        seen_ids: set[str],
    ) -> tuple[list[dict], bool]:
        if not isinstance(payload, dict):
            return [], False
        article_list = payload.get("articleList") or payload.get("articles") or []
        if not isinstance(article_list, list):
            return [], False
        raw_items: list[dict] = []
        for article in article_list:
            if not isinstance(article, dict):
                continue
            if detect_trade_type(article, requested_trade_type=trade_type) != trade_type:
                continue
            payload_marker_id = "" if mode == "complex" else str(marker_id or cid or "")
            item = normalize_article_payload(
                article,
                complex_name=name,
                complex_id=cid,
                requested_trade_type=trade_type,
                asset_type=path_asset,
                mode=mode,
                lat=source_lat,
                lon=source_lon,
                zoom=source_zoom,
                marker_id=payload_marker_id,
            )
            aid = str(item.get("매물ID", "") or item.get(_LEGACY_ARTICLE_ID_KEY, "") or "")
            if not aid or aid in seen_ids:
                continue
            seen_ids.add(aid)
            raw_items.append(item)
        return raw_items, True

    def _article_api_fast_path_success(
        self,
        *,
        raw_items: list[dict],
        response_match_count: int,
        final_api_url: str,
    ) -> dict:
        self.thread.stats["article_api_fast_path_hit_count"] = (
            int(self.thread.stats.get("article_api_fast_path_hit_count", 0)) + 1
        )
        return {
            "raw_items": raw_items,
            "response_seen": True,
            "parse_success": True,
            "drain_timed_out": False,
            "response_match_count": response_match_count,
            "final_url": final_api_url,
            "block_like_redirect": False,
            "block_reason": "",
            "capture_failed": False,
            "failure_reason": "",
            "api_fast_path": True,
        }

    def _article_api_fast_path_fail_stats(self) -> None:
        self.thread.stats["article_api_fast_path_fail_count"] = (
            int(self.thread.stats.get("article_api_fast_path_fail_count", 0)) + 1
        )
        self.thread.stats["article_api_fast_path_fallback_count"] = (
            int(self.thread.stats.get("article_api_fast_path_fallback_count", 0)) + 1
        )

    async def _paginate_article_api_request_context(
        self,
        request_context,
        *,
        name: str,
        cid: str,
        trade_type: str,
        base_kind: str,
        path_asset: str,
        target_url: str,
        mode: str,
        source_lat: float | None,
        source_lon: float | None,
        source_zoom: int | None,
        marker_id: str,
        seen_ids: set[str],
        start_page: int = 1,
        existing_items: list[dict] | None = None,
    ) -> dict | None:
        all_raw_items: list[dict] = list(existing_items or [])
        final_api_url = ""
        response_match_count = 0
        first_page = max(1, int(start_page or 1))

        for page in range(first_page, MAX_ARTICLE_API_PAGES + 1):
            api_url = self._build_article_api_url(
                base_kind, cid, trade_type, path_asset, page=page
            )
            final_api_url = api_url
            response = await request_context.get(
                api_url,
                headers=self._article_api_headers(target_url),
                timeout=self._article_api_timeout_ms(),
            )
            response_match_count += 1
            status = getattr(response, "status", None)
            status_label = str(status if status is not None else "")
            self.thread.stats["article_api_last_status"] = status_label
            if status is not None and int(status) >= 400:
                if page == first_page and not all_raw_items:
                    self._article_api_fast_path_fail_stats()
                    return None
                break
            payload = await response.json()
            raw_items, valid_payload = self._normalize_article_api_payload(
                payload,
                name=name,
                cid=cid,
                trade_type=trade_type,
                path_asset=path_asset,
                mode=mode,
                source_lat=source_lat,
                source_lon=source_lon,
                source_zoom=source_zoom,
                marker_id=marker_id,
                seen_ids=seen_ids,
            )
            if not valid_payload:
                if page == first_page and not all_raw_items:
                    self._article_api_fast_path_fail_stats()
                    self.thread.stats["article_api_last_status"] = status_label or "invalid_payload"
                    return None
                break
            list_count = article_api_list_count(payload)
            all_raw_items.extend(raw_items)
            if not article_api_has_more_pages(payload, list_count):
                break

        if not all_raw_items and response_match_count == 0:
            return None
        return self._article_api_fast_path_success(
            raw_items=all_raw_items,
            response_match_count=response_match_count,
            final_api_url=final_api_url,
        )

    async def _fetch_article_api_fast_path(
        self,
        *,
        name: str,
        cid: str,
        trade_type: str,
        base_kind: str,
        path_asset: str,
        target_url: str,
        mode: str,
        source_lat: float | None,
        source_lon: float | None,
        source_zoom: int | None,
        marker_id: str,
        seen_ids: set[str],
    ) -> dict | None:
        if not bool(getattr(self.thread, "playwright_article_api_fast_path", True)):
            return None
        context = self._desktop_context
        request_context = getattr(context, "request", None) if context is not None else None
        if request_context is None or not hasattr(request_context, "get"):
            return None
        if not str(getattr(self, "_article_api_auth_header", "") or "").strip():
            return None

        try:
            return await self._paginate_article_api_request_context(
                request_context,
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
                start_page=1,
            )
        except Exception as exc:
            self._article_api_fast_path_fail_stats()
            self.thread.stats["article_api_last_status"] = f"{type(exc).__name__}"
            self.thread.log(f"   Article API fast path fallback({base_kind}/{cid}): {exc}", 10)
            return None

    async def _supplement_article_api_pages(
        self,
        *,
        name: str,
        cid: str,
        trade_type: str,
        base_kind: str,
        path_asset: str,
        target_url: str,
        mode: str,
        source_lat: float | None,
        source_lon: float | None,
        source_zoom: int | None,
        marker_id: str,
        seen_ids: set[str],
        existing_items: list[dict],
        last_payload: dict | None,
    ) -> list[dict]:
        if not str(getattr(self, "_article_api_auth_header", "") or "").strip():
            return list(existing_items or [])
        list_count = article_api_list_count(last_payload) if last_payload else len(existing_items or [])
        payload_for_more = last_payload if last_payload else {"articleList": [None] * list_count}
        if not article_api_has_more_pages(payload_for_more, list_count):
            return list(existing_items or [])
        context = self._desktop_context
        request_context = getattr(context, "request", None) if context is not None else None
        if request_context is None or not hasattr(request_context, "get"):
            return list(existing_items or [])
        try:
            result = await self._paginate_article_api_request_context(
                request_context,
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
                start_page=2,
                existing_items=list(existing_items or []),
            )
        except Exception:
            return list(existing_items or [])
        if result is None:
            return list(existing_items or [])
        return list(result.get("raw_items", []) or existing_items or [])
