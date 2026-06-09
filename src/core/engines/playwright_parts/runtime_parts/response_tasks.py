from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING

from src.utils.helpers import ChromeParamHelper

if TYPE_CHECKING:
    from src.core.engines.playwright_engine import *  # noqa: F403


class PlaywrightResponseTaskRuntimeMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    @staticmethod
    def _spawn_response_task(pending_tasks: set[asyncio.Task], coro) -> None:
        task = asyncio.create_task(coro)
        pending_tasks.add(task)
        task.add_done_callback(lambda done: pending_tasks.discard(done))

    async def _drain_pending_response_tasks(
        self,
        pending_tasks: set[asyncio.Task],
        *,
        label: str,
        timeout_ms: int | None = None,
    ) -> tuple[int, bool]:
        wait_count = len(pending_tasks)
        timed_out = False
        if wait_count <= 0:
            return 0, False
        if timeout_ms is None:
            try:
                timeout_ms = int(getattr(self.thread, "playwright_response_drain_timeout_ms", 3000))
            except (TypeError, ValueError):
                timeout_ms = 3000
        self.thread.stats["response_drain_wait_count"] = (
            int(self.thread.stats.get("response_drain_wait_count", 0)) + wait_count
        )
        self.thread.log(f"   응답 처리 대기중 ({label}): {wait_count}", 10)
        try:
            await asyncio.wait_for(
                asyncio.gather(*list(pending_tasks), return_exceptions=True),
                timeout=max(0.1, float(timeout_ms) / 1000.0),
            )
        except asyncio.TimeoutError:
            timed_out = True
            self.thread.stats["response_drain_timeout_count"] = (
                int(self.thread.stats.get("response_drain_timeout_count", 0)) + 1
            )
            for task in list(pending_tasks):
                if not task.done():
                    task.cancel()
            if pending_tasks:
                await asyncio.gather(*list(pending_tasks), return_exceptions=True)
            self.thread.log(f"   타깃 응답 처리 대기 타임아웃 ({label}): {wait_count}", 30)
        self.thread.emit_stats()
        return wait_count, timed_out
