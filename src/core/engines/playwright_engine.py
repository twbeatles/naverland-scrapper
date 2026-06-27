from __future__ import annotations

import asyncio
from urllib.parse import urlencode

from src.core.services.detail_fetcher import apply_mobile_detail, fetch_mobile_article_detail
from src.core.services.map_geometry import build_grid_sweep_coords, clamp_korea
from src.core.services.article_api import (
    MAX_ARTICLE_API_PAGES,
    article_api_has_more_pages,
    article_api_path_kind,
    article_api_real_estate_type,
    build_article_api_url,
)
from src.core.services.response_capture import (
    TRADE_CODE_MAP,
    detect_trade_type,
    normalize_article_payload,
    normalize_marker_payload,
)
from src.utils.helpers import ChromeParamHelper
from src.utils.logger import get_logger
from .base import CrawlerEngine

try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    async_playwright = None
    PLAYWRIGHT_AVAILABLE = False

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False


logger = get_logger("PlaywrightEngine")

_TRADE_TO_CODE = {value: key for key, value in TRADE_CODE_MAP.items()}
_LEGACY_ARTICLE_ID_KEY = "\uf9cd\u317b\u042aID"
PLAYWRIGHT_MEMORY_THRESHOLD_MB = 500
PLAYWRIGHT_RETRY_ATTEMPTS = 3
PLAYWRIGHT_RETRY_BASE_DELAY_SEC = 0.35


from src.utils.mixin_rebind import rebind_inherited_methods

from src.core.engines.playwright_parts.runtime import PlaywrightRuntimeMixin
from src.core.engines.playwright_parts.complex_mode import PlaywrightComplexModeMixin
from src.core.engines.playwright_parts.geo_mode import PlaywrightGeoModeMixin


class PlaywrightCrawlerEngine(
    PlaywrightRuntimeMixin,
    PlaywrightComplexModeMixin,
    PlaywrightGeoModeMixin,
    CrawlerEngine,
):
    engine_name = "playwright"



rebind_inherited_methods(
    PlaywrightCrawlerEngine,
    mixin_classes=[
        PlaywrightRuntimeMixin,
        PlaywrightComplexModeMixin,
        PlaywrightGeoModeMixin,
    ],
    globals_dict=globals(),
)