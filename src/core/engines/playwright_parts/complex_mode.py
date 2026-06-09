from __future__ import annotations

from src.core.engines.playwright_parts.complex_mode_parts.article_api import PlaywrightArticleApiMixin
from src.core.engines.playwright_parts.complex_mode_parts.cache_flow import PlaywrightComplexCacheFlowMixin
from src.core.engines.playwright_parts.complex_mode_parts.detail_enrichment import PlaywrightDetailEnrichmentMixin
from src.core.engines.playwright_parts.complex_mode_parts.loop import PlaywrightComplexLoopMixin
from src.core.engines.playwright_parts.complex_mode_parts.paths import PlaywrightComplexPathsMixin
from src.core.engines.playwright_parts.complex_mode_parts.response_capture import PlaywrightResponseCaptureMixin


class PlaywrightComplexModeMixin(
    PlaywrightComplexLoopMixin,
    PlaywrightComplexCacheFlowMixin,
    PlaywrightArticleApiMixin,
    PlaywrightResponseCaptureMixin,
    PlaywrightDetailEnrichmentMixin,
    PlaywrightComplexPathsMixin,
):
    pass
