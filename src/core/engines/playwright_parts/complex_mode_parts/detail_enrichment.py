from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING

from src.core.services.detail_fetcher import apply_mobile_detail, fetch_mobile_article_detail

if TYPE_CHECKING:
    from src.core.engines.playwright_engine import *  # noqa: F403

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
            enrich_enabled = bool(getattr(self.thread, "detail_enrichment_enabled", True))
            try:
                max_detail = max(0, int(getattr(self.thread, "detail_enrichment_max_per_complex", 0) or 0))
            except (TypeError, ValueError):
                max_detail = 0

            if not enrich_enabled:
                to_enrich: list[dict] = []
                passthrough = list(detail_candidates)
                self.thread.stats["detail_enrichment_disabled"] = 1
                self.thread.stats["detail_fetch_skipped_count"] = (
                    int(self.thread.stats.get("detail_fetch_skipped_count", 0)) + len(passthrough)
                )
            elif max_detail > 0 and len(detail_candidates) > max_detail:
                to_enrich = list(detail_candidates[:max_detail])
                passthrough = list(detail_candidates[max_detail:])
                cap_n = len(passthrough)
                self.thread.stats["detail_cap_truncated"] = (
                    int(self.thread.stats.get("detail_cap_truncated", 0)) + cap_n
                )
                self.thread.stats["detail_fetch_skipped_count"] = (
                    int(self.thread.stats.get("detail_fetch_skipped_count", 0)) + cap_n
                )
            else:
                to_enrich = list(detail_candidates)
                passthrough = []

            detailed_items = (
                await self._enrich_items_with_mobile_details(to_enrich) if to_enrich else []
            )
            for detailed_item in list(detailed_items) + list(passthrough):
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

    def _detail_worker_count(self, item_count: int) -> int:
        try:
            configured = max(1, int(getattr(self.thread, "playwright_detail_workers", 1) or 1))
        except (TypeError, ValueError):
            configured = 1
        # Cap under rate-limit pressure or front-api-only mode.
        if bool(getattr(self, "_detail_rate_limited", False)):
            configured = min(configured, 1)
        elif bool(getattr(self, "_detail_prefer_front_api_only", False)):
            configured = min(configured, 2)
        elif int(self.thread.stats.get("detail_host_unreachable_count", 0) or 0) >= 2:
            configured = min(configured, 2)
        return min(max(1, item_count), configured)

    def _record_detail_outcome(self, item: dict, detail: dict | None) -> dict:
        """Apply detail and classify success after list-meta merge (audit H-4)."""
        merged = apply_mobile_detail(dict(item), detail if isinstance(detail, dict) else {})
        parse_state = str(merged.get("detail_parse_state", "") or "")
        source = str(merged.get("detail_source", "") or "")
        if merged.get("detail_host_unreachable"):
            self.thread.stats["detail_host_unreachable_count"] = (
                int(self.thread.stats.get("detail_host_unreachable_count", 0)) + 1
            )
        meta = {}
        if isinstance(detail, dict):
            meta = dict(detail.get("_detail_meta", {}) or {})
        if meta.get("front_api_rate_limited") or parse_state == "rate_limited":
            self.thread.stats["detail_front_api_rate_limited_count"] = (
                int(self.thread.stats.get("detail_front_api_rate_limited_count", 0)) + 1
            )
            self._detail_rate_limited = True
            self._detail_prefer_front_api_only = True

        has_list_broker = bool(str(item.get("부동산상호", "") or "").strip())
        has_merged_broker = bool(str(merged.get("부동산상호", "") or "").strip())
        # Fields that typically require detail/front-api (not list-only realtorName).
        detail_core = (
            bool(str(merged.get("중개사이름", "") or "").strip())
            or bool(str(merged.get("전화1", "") or "").strip())
            or bool(str(merged.get("전화2", "") or "").strip())
            or int(merged.get("기전세금(원)", 0) or 0) > 0
        )

        if parse_state == "success" or (parse_state == "partial" and detail_core):
            self.thread.stats["detail_success_count"] = int(self.thread.stats.get("detail_success_count", 0)) + 1
            self.thread.stats["detail_fetch_success"] = int(self.thread.stats.get("detail_fetch_success", 0)) + 1
            if parse_state == "partial":
                self.thread.stats["detail_partial_count"] = (
                    int(self.thread.stats.get("detail_partial_count", 0)) + 1
                )
        elif has_list_broker or has_merged_broker:
            # List-level broker name only — not a hard detail failure (audit H-4).
            self.thread.stats["detail_list_meta_only_count"] = (
                int(self.thread.stats.get("detail_list_meta_only_count", 0)) + 1
            )
            self.thread.stats["detail_partial_count"] = (
                int(self.thread.stats.get("detail_partial_count", 0)) + 1
            )
            merged["detail_source"] = "list_meta" if not detail_core else (source or "list_meta")
            merged["detail_parse_state"] = "partial"
            merged["상세소스"] = merged["detail_source"]
            merged["상세수집상태"] = "partial"
        else:
            self.thread.stats["detail_fail_count"] = int(self.thread.stats.get("detail_fail_count", 0)) + 1
        return merged

    async def _enrich_items_with_mobile_details(self, items: list[dict]) -> list[dict]:
        if not items or self._page_pool is None:
            return items

        # Per-complex flags (reset each batch).
        self._detail_rate_limited = bool(getattr(self, "_detail_rate_limited", False))
        prefer_api_only = bool(getattr(self.thread, "detail_front_api_only", False)) or bool(
            getattr(self, "_detail_prefer_front_api_only", False)
        )
        if int(self.thread.stats.get("detail_host_unreachable_count", 0) or 0) >= 3:
            prefer_api_only = True
        self._detail_prefer_front_api_only = prefer_api_only

        n = len(items)
        ordered: list[dict | None] = [None] * n

        async def _fetch_one(index: int, item: dict) -> None:
            if bool(getattr(self, "_detail_abort_remaining", False)):
                ordered[index] = apply_mobile_detail(dict(item), {})
                self.thread.stats["detail_fetch_skipped_count"] = (
                    int(self.thread.stats.get("detail_fetch_skipped_count", 0)) + 1
                )
                return

            page = await self._acquire_detail_page()
            detail: dict = {}
            try:
                article_no = str(item.get("매물ID", "") or item.get(_LEGACY_ARTICLE_ID_KEY, ""))
                self.thread.stats["detail_fetch_total"] = int(self.thread.stats.get("detail_fetch_total", 0)) + 1
                front_api_enabled = bool(getattr(self.thread, "detail_front_api_enabled", True))
                if bool(getattr(self, "_detail_rate_limited", False)):
                    # After 429, skip network detail; keep list meta only.
                    front_api_enabled = False
                    prefer_local = True
                else:
                    prefer_local = bool(getattr(self, "_detail_prefer_front_api_only", False))

                if front_api_enabled or not prefer_local:
                    detail = await self._async_retry(
                        f"mobile detail {article_no}",
                        lambda: fetch_mobile_article_detail(
                            page,
                            article_no,
                            navigation_timeout_ms=self._navigation_timeout_ms(),
                            front_api_enabled=front_api_enabled,
                            prefer_front_api_only=prefer_local and front_api_enabled,
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
                if detail_meta.get("front_api_rate_limited"):
                    self._detail_rate_limited = True
                    self._detail_prefer_front_api_only = True
                    # Abort remaining heavy detail after first hard rate limit for this batch.
                    self._detail_abort_remaining = True
            except Exception:
                detail = {}
            finally:
                await self._release_detail_page(page)

            ordered[index] = self._record_detail_outcome(item, detail)

        queue: asyncio.Queue[tuple[int, dict]] = asyncio.Queue()
        for idx, item in enumerate(items):
            queue.put_nowait((idx, item))
        interrupted = False
        self._detail_abort_remaining = False

        async def _worker() -> None:
            while not self.thread._should_stop():
                try:
                    index, item = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    await _fetch_one(index, item)
                finally:
                    queue.task_done()

        worker_count = self._detail_worker_count(n)
        self.thread.stats["detail_workers_used"] = worker_count
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

        # Preserve input order on full completion; on stop return only finished slots.
        if interrupted:
            return [row for row in ordered if isinstance(row, dict)]
        result: list[dict] = []
        for idx, item in enumerate(items):
            filled = ordered[idx]
            result.append(filled if isinstance(filled, dict) else dict(item))
        return result
