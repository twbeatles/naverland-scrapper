from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING

from src.utils.helpers import ChromeParamHelper

if TYPE_CHECKING:
    from src.core.engines.playwright_engine import *  # noqa: F403


class PlaywrightNavigationRuntimeMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    def _build_entry_plans(self, target_url: str) -> list[dict]:
        target = str(target_url or "").strip()
        if not target:
            return []
        return [
            {"name": "direct", "warmups": [], "target": target},
            {"name": "new_home_then_target", "warmups": ["https://new.land.naver.com/"], "target": target},
            {
                "name": "fin_then_new_target",
                "warmups": ["https://fin.land.naver.com/", "https://new.land.naver.com/"],
                "target": target,
            },
            {
                "name": "mobile_then_new_target",
                "warmups": ["https://m.land.naver.com/", "https://new.land.naver.com/"],
                "target": target,
            },
        ]

    async def _run_entry_plan(self, page, plan: dict, *, label: str) -> None:
        plan_name = str((plan or {}).get("name", "") or "direct")
        target = str((plan or {}).get("target", "") or "")
        warmups = list((plan or {}).get("warmups", []) or [])
        self.thread.stats["playwright_last_entry_plan"] = plan_name
        for idx, warmup in enumerate(warmups, 1):
            await self._async_retry(
                f"{label} warmup {plan_name} {idx}/{len(warmups)}",
                lambda warmup_url=warmup: page.goto(
                    warmup_url,
                    wait_until="domcontentloaded",
                    timeout=self._navigation_timeout_ms(),
                ),
            )
            try:
                await page.wait_for_load_state("networkidle", timeout=2500)
            except Exception:
                pass
            await page.wait_for_timeout(350)
        await self._async_retry(
            f"{label} target {plan_name}",
            lambda: page.goto(
                target,
                wait_until="domcontentloaded",
                timeout=self._navigation_timeout_ms(),
            ),
        )

    async def _maybe_enable_headed_fallback(self, reason: str = "") -> bool:
        if self._headed_fallback_used:
            return False
        if not bool(self._launched_headless):
            return False
        self.thread.log(f"Playwright headed fallback 전환: {reason or 'capture recovery'}", 30)
        self._headed_fallback_used = True
        self.thread.stats["playwright_headed_fallback_used"] = 1
        self._launch_headless_override = False
        await self._shutdown_async()
        await self._ensure_started()
        return True
