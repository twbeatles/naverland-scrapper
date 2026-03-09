from __future__ import annotations

import asyncio
from urllib.parse import urlencode

from src.core.services.detail_fetcher import apply_mobile_detail, fetch_mobile_article_detail
from src.core.services.map_geometry import build_grid_sweep_coords, clamp_korea
from src.core.services.response_capture import (
    TRADE_CODE_MAP,
    detect_trade_type,
    normalize_article_payload,
    normalize_marker_payload,
)
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


import inspect
import types

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



def _clone_function_with_globals(func):
    cloned = types.FunctionType(
        func.__code__,
        globals(),
        name=func.__name__,
        argdefs=func.__defaults__,
        closure=func.__closure__,
    )
    cloned.__kwdefaults__ = getattr(func, "__kwdefaults__", None)
    cloned.__annotations__ = dict(getattr(func, "__annotations__", {}))
    cloned.__doc__ = func.__doc__
    cloned.__module__ = __name__
    return cloned


def _rebind_inherited_methods(cls, method_names):
    for name in method_names:
        raw = inspect.getattr_static(cls, name, None)
        if raw is None:
            continue
        if isinstance(raw, staticmethod):
            setattr(cls, name, staticmethod(_clone_function_with_globals(raw.__func__)))
        elif isinstance(raw, classmethod):
            setattr(cls, name, classmethod(_clone_function_with_globals(raw.__func__)))
        elif inspect.isfunction(raw):
            setattr(cls, name, _clone_function_with_globals(raw))
    return cls


_rebind_inherited_methods(
    PlaywrightCrawlerEngine,
    [
    "__init__",
    "run",
    "close",
    "_run",
    "_ensure_runtime_stats",
    "_sleep_async_interruptible",
    "_async_retry",
    "_check_memory_and_recycle_if_needed",
    "_ensure_started",
    "_shutdown_async",
    "_setup_blocking",
    "_spawn_response_task",
    "_drain_pending_response_tasks",
    "_run_complex_mode",
    "_run_geo",
    "_build_marker_handler",
    "_scan_geo_asset_type",
    "_crawl_target_with_cache",
    "_collect_target_raw_items",
    "_enrich_items_with_mobile_details",
    "_candidate_paths",
    "_get_ms",
    "_wheel_to_zoom",
    "_drag_to_latlon",
    "_human_like_recenter",
    "_switch_to_listing_markers",
    ],
)
