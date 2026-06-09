from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING

from src.utils.helpers import ChromeParamHelper

if TYPE_CHECKING:
    from src.core.engines.playwright_engine import *  # noqa: F403


class PlaywrightBlockingRuntimeMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    async def _setup_blocking(self, context):
        if not self.thread.block_heavy_resources:
            return

        async def _route(route):
            if route.request.resource_type in ("image", "media", "font"):
                await route.abort()
                return
            await route.continue_()

        await context.route("**/*", _route)

    async def _classify_page_state(self, page):
        final_url = str(getattr(page, "url", "") or "")
        title = ""
        try:
            title = await page.title()
        except Exception:
            title = ""

        lower_url = final_url.lower()
        lower_title = title.lower()
        block_reason = ""
        if "/404" in lower_url or lower_url.endswith("404"):
            block_reason = "redirect_404"
        elif "not found" in lower_title:
            block_reason = "title_not_found"
        else:
            for pattern in getattr(self.thread, "BLOCKED_PAGE_PATTERNS", ()):
                token = str(pattern or "").lower()
                if token and (token in lower_url or token in lower_title):
                    block_reason = f"pattern:{token}"
                    break

        self.thread.stats["playwright_last_final_url"] = final_url
        self.thread.stats["playwright_last_page_title"] = title
        self.thread.stats["playwright_last_block_reason"] = block_reason
        return {
            "final_url": final_url,
            "title": title,
            "block_reason": block_reason,
            "block_like_redirect": bool(block_reason),
        }
