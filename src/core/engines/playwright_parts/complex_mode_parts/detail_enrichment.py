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


class PlaywrightDetailEnrichmentMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    async def _process_raw_items_with_filtered_details(
        self,
        raw_items: list[dict],
        trade_type: str,
    ) -> int:
        matched_count = 0
        detail_candidates: list[dict] = []

        for raw_item in raw_items or []:
            if not isinstance(raw_item, dict):
                continue
            item = dict(raw_item)
            if self.thread._check_filters(item, trade_type):
                detail_candidates.append(item)
                continue
            self.thread.stats["filtered_out"] = int(self.thread.stats.get("filtered_out", 0)) + 1
            self.thread.stats["detail_fetch_skipped_count"] = (
                int(self.thread.stats.get("detail_fetch_skipped_count", 0)) + 1
            )

        if detail_candidates:
            detailed_items = await self._enrich_items_with_mobile_details(detail_candidates)
            for detailed_item in detailed_items:
                processed_item = self.thread._enrich_item_with_history_and_alerts(dict(detailed_item))
                if self.thread._check_filters(processed_item, trade_type):
                    if self.thread._push_item(processed_item):
                        matched_count += 1
                else:
                    self.thread.stats["filtered_out"] = int(self.thread.stats.get("filtered_out", 0)) + 1

        self.thread._flush_history_updates(force=True)
        self.thread._flush_pending_items_if_needed(force=True)
        self.thread.emit_stats()
        return matched_count

    async def _enrich_items_with_mobile_details(self, items: list[dict]) -> list[dict]:
        if not items or self._page_pool is None:
            return items

        async def _fetch_one(item: dict) -> dict:
            page = await self._page_pool.get()
            detail_success = False
            try:
                article_no = str(item.get("매물ID", "") or item.get(_LEGACY_ARTICLE_ID_KEY, ""))
                self.thread.stats["detail_fetch_total"] = int(self.thread.stats.get("detail_fetch_total", 0)) + 1
                detail = await self._async_retry(
                    f"mobile detail {article_no}",
                    lambda: fetch_mobile_article_detail(
                        page,
                        article_no,
                        navigation_timeout_ms=self._navigation_timeout_ms(),
                    ),
                )
                detail_meta = dict(detail.get("_detail_meta", {}) or {}) if isinstance(detail, dict) else {}
                missing_field_count = int(detail_meta.get("missing_field_count", 0) or 0)
                if missing_field_count > 0:
                    self.thread.stats["detail_missing_field_total"] = (
                        int(self.thread.stats.get("detail_missing_field_total", 0)) + missing_field_count
                    )
                network_response_count = int(detail_meta.get("network_response_count", 0) or 0)
                if network_response_count > 0:
                    self.thread.stats["detail_network_response_total"] = (
                        int(self.thread.stats.get("detail_network_response_total", 0)) + network_response_count
                    )
                hydration_hit = int(detail_meta.get("hydration_hit", 0) or 0)
                if hydration_hit > 0:
                    self.thread.stats["detail_hydration_hit_count"] = (
                        int(self.thread.stats.get("detail_hydration_hit_count", 0)) + hydration_hit
                    )
                parse_state = str(detail_meta.get("detail_parse_state", "") or "")
                if parse_state == "partial":
                    self.thread.stats["detail_partial_count"] = (
                        int(self.thread.stats.get("detail_partial_count", 0)) + 1
                    )
                if detail and parse_state != "failed":
                    detail_success = True
                    self.thread.stats["detail_fetch_success"] = (
                        int(self.thread.stats.get("detail_fetch_success", 0)) + 1
                    )
            except Exception:
                detail = {}
            finally:
                await self._page_pool.put(page)
            if detail_success:
                self.thread.stats["detail_success_count"] = int(self.thread.stats.get("detail_success_count", 0)) + 1
            else:
                self.thread.stats["detail_fail_count"] = int(self.thread.stats.get("detail_fail_count", 0)) + 1
            return apply_mobile_detail(dict(item), detail)

        queue: asyncio.Queue[dict] = asyncio.Queue()
        for item in items:
            queue.put_nowait(item)
        result = []
        interrupted = False

        async def _worker() -> None:
            while not self.thread._should_stop():
                try:
                    item = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    result.append(await _fetch_one(item))
                finally:
                    queue.task_done()

        worker_count = min(len(items), max(1, int(getattr(self.thread, "playwright_detail_workers", 1) or 1)))
        tasks = [asyncio.create_task(_worker()) for _ in range(worker_count)]
        try:
            pending_tasks = set(tasks)
            while pending_tasks:
                if self.thread._should_stop():
                    interrupted = True
                    break
                done, pending_tasks = await asyncio.wait(
                    pending_tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in done:
                    try:
                        await task
                    except Exception:
                        continue
        finally:
            if interrupted:
                for task in tasks:
                    if not task.done():
                        task.cancel()
            pending = [task for task in tasks if not task.done()]
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
        return result
