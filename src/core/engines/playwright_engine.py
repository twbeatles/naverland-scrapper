from __future__ import annotations

import asyncio  # noqa: F401  # star-carried: `from src.core.engines.playwright_engine import *` in playwright_parts/* (do not remove)

from src.core.engines.playwright_parts.complex_mode import PlaywrightComplexModeMixin
from src.core.engines.playwright_parts.complex_mode_parts.article_api import (
    PlaywrightArticleApiMixin,  # noqa: F401  # star-carried: article_api.py uses via star (do not remove)
)
from src.core.engines.playwright_parts.geo_mode import PlaywrightGeoModeMixin
from src.core.engines.playwright_parts.runtime import PlaywrightRuntimeMixin
from src.core.services.article_api import (
    MAX_ARTICLE_API_PAGES,  # noqa: F401  # tests patch engine.MAX_ARTICLE_API_PAGES
    article_api_has_more_pages,  # noqa: F401  # star-carried: article_api.py uses via star (do not remove)
    article_api_list_count,  # noqa: F401  # star-carried (do not remove)
    article_api_path_kind,  # noqa: F401  # star-carried (do not remove)
    article_api_real_estate_type,  # noqa: F401  # star-carried (do not remove)
    build_article_api_url,  # noqa: F401  # star-carried (do not remove)
)
from src.core.services.collection_result import CollectionResult  # noqa: F401  # star-carried (do not remove)
from src.core.services.detail_fetcher import (  # noqa: F401  # star-carried + tests patch fetch (do not remove)
    apply_mobile_detail,
    fetch_mobile_article_detail,
)
from src.core.services.fin_article_api import (  # noqa: F401  # star-carried: fin_api.py uses via star (do not remove)
    parse_fin_article_list,
    parse_fin_bounded_complexes,
    parse_fin_complex_info,
)
from src.core.services.map_geometry import (  # noqa: F401  # star-carried (do not remove)
    build_grid_sweep_coords,
    clamp_korea,
    viewport_bounds,
)
from src.core.services.response_capture import (
    TRADE_CODE_MAP,
    detect_trade_type,  # noqa: F401  # tests patch engine.detect_trade_type
    normalize_article_payload,  # noqa: F401  # tests patch engine.normalize_article_payload
    normalize_marker_payload,  # noqa: F401  # star-carried: markers.py uses via star (do not remove)
)
from src.core.services.site_contract import (  # noqa: F401  # star-carried: runtime/browser + fin/markers parts use via star (do not remove)
    DESKTOP_USER_AGENT,
    FIN_API_ORIGIN_PAGE,
    FRONT_API_BOUNDED_COMPLEXES,
    FRONT_API_COMPLEX_ARTICLE_LIST,  # noqa: F401  # rebind-guard: test_playwright_engine_globals REQUIRED_GLOBALS (do not remove)
    HOST_FIN,  # noqa: F401  # rebind-guard: test_playwright_engine_globals REQUIRED_GLOBALS (do not remove)
    HOST_M,  # noqa: F401  # rebind-guard: test_playwright_engine_globals REQUIRED_GLOBALS (do not remove)
    HOST_NEW,
    build_complex_overview_url,  # noqa: F401  # rebind-guard: test_playwright_engine_globals REQUIRED_GLOBALS (do not remove)
    build_complex_page_url,
    build_fin_article_list_body,
    build_fin_bounded_complexes_body,
    build_fin_complex_info_url,
    build_geo_map_url,
    build_single_markers_url,
    fin_article_list_url,
    is_fin_html_dead_url,  # noqa: F401  # rebind-guard: test_playwright_engine_globals REQUIRED_GLOBALS (do not remove)
    trade_type_to_code,
)
from src.utils.helpers import ChromeParamHelper  # noqa: F401  # star-carried (do not remove)
from src.utils.logger import get_logger
from src.utils.mixin_rebind import rebind_inherited_methods

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
