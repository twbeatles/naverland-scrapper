from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING

from src.utils.helpers import ChromeParamHelper

if TYPE_CHECKING:
    from src.core.engines.playwright_engine import *  # noqa: F403


class PlaywrightContextRuntimeMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    async def _create_context(self, browser, label: str, **kwargs):
        import os

        storage_state_path = self._storage_state_path(label)
        storage_state = storage_state_path if os.path.exists(storage_state_path) else None
        if storage_state:
            try:
                context = await browser.new_context(storage_state=storage_state, **kwargs)
                self.thread.stats["playwright_session_reused"] = (
                    int(self.thread.stats.get("playwright_session_reused", 0)) + 1
                )
                self.thread.log(f"Playwright 세션 재사용: {label}", 10)
                return context
            except Exception as exc:
                self.thread.log(f"Playwright storage_state 로드 실패({label}), 새 세션으로 진행: {exc}", 30)
        return await browser.new_context(**kwargs)

    async def _save_context_state(self, context, label: str):
        if context is None:
            return
        storage_state_path = self._storage_state_path(label)
        try:
            await context.storage_state(path=storage_state_path)
        except Exception:
            return

    async def _warmup_runtime_pages(self):
        desktop_page = self._desktop_page
        if desktop_page is not None:
            for url in ("https://fin.land.naver.com/", "https://new.land.naver.com/"):
                await self._warmup_page(desktop_page, url, label="desktop")
        if self._page_pool is None or self._page_pool.empty():
            return
        page = await self._page_pool.get()
        try:
            await self._warmup_page(page, "https://m.land.naver.com/", label="mobile")
        finally:
            await self._page_pool.put(page)

    async def _warmup_page(self, page, url: str, *, label: str) -> bool:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=self._navigation_timeout_ms())
            try:
                await page.wait_for_load_state("networkidle", timeout=2500)
            except Exception:
                pass
            self.thread.stats["playwright_warmup_count"] = (
                int(self.thread.stats.get("playwright_warmup_count", 0)) + 1
            )
            return True
        except Exception as exc:
            self.thread.log(f"Playwright warm-up 실패({label}, {url}): {exc}", 10)
            return False
