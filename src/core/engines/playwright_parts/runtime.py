from __future__ import annotations

from src.core.engines.playwright_parts.runtime_parts.blocking import PlaywrightBlockingRuntimeMixin
from src.core.engines.playwright_parts.runtime_parts.browser import PlaywrightBrowserRuntimeMixin
from src.core.engines.playwright_parts.runtime_parts.contexts import PlaywrightContextRuntimeMixin
from src.core.engines.playwright_parts.runtime_parts.navigation import PlaywrightNavigationRuntimeMixin
from src.core.engines.playwright_parts.runtime_parts.response_tasks import PlaywrightResponseTaskRuntimeMixin


class PlaywrightRuntimeMixin(
    PlaywrightBrowserRuntimeMixin,
    PlaywrightContextRuntimeMixin,
    PlaywrightNavigationRuntimeMixin,
    PlaywrightBlockingRuntimeMixin,
    PlaywrightResponseTaskRuntimeMixin,
):
    pass
