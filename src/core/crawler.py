import time
import random
import gc
import traceback
from PyQt6.QtCore import QThread, pyqtSignal

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from src.utils.constants import CRAWL_SPEED_PRESETS
from src.utils.helpers import PriceConverter, ChromeParamHelper
from src.utils.retry_handler import RetryCancelledError, RetryHandler
from src.core.engines import PlaywrightCrawlerEngine, SeleniumCrawlerEngine
from src.core.item_parser import ItemParser
from src.core.models.crawl_models import GeoSweepConfig

# 메모리 임계치 (MB) - 초과 시 드라이버 재시작
MEMORY_THRESHOLD_MB = 500

import inspect
import types

from src.core.crawler_parts.state_runtime import CrawlerStateRuntimeMixin
from src.core.crawler_parts.history_alerts import CrawlerHistoryAlertsMixin
from src.core.crawler_parts.selenium_flow import CrawlerSeleniumFlowMixin
from src.core.crawler_parts.dom_scroll_parse import CrawlerDomScrollParseMixin


class CrawlerThread(
    CrawlerStateRuntimeMixin,
    CrawlerHistoryAlertsMixin,
    CrawlerSeleniumFlowMixin,
    CrawlerDomScrollParseMixin,
    QThread,
):
    log_signal = pyqtSignal(str, int)
    progress_signal = pyqtSignal(int, str, int)  # percent, current_name, remaining_seconds
    item_signal = pyqtSignal(dict)  # deprecated: items_signal(list[dict]) 사용 권장
    items_signal = pyqtSignal(list)
    stats_signal = pyqtSignal(dict)
    complex_finished_signal = pyqtSignal(str, str, str, int)
    finished_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)
    alert_triggered_signal = pyqtSignal(str, str, str, float, int)
    discovered_complex_signal = pyqtSignal(dict)
    BLOCKED_PAGE_PATTERNS = (
        "captcha",
        "캡차",
        "자동입력 방지",
        "자동 입력 방지",
        "접근이 제한",
        "접속이 제한",
        "비정상적인 접근",
        "서비스 이용이 제한",
        "verify you are human",
        "robot check",
        "access denied",
        "security check",
        "cloudflare",
        "bot detection",
    )
    


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
    CrawlerThread,
    [
    "__init__",
    "stop",
    "set_shutdown_mode",
    "_should_stop",
    "_sleep_interruptible",
    "_create_engine",
    "_estimate_remaining_seconds",
    "_get_speed_delay",
    "_pair_key",
    "_build_pair_sequence",
    "_remaining_pairs",
    "_mark_pair_processed",
    "_item_dedupe_key",
    "_is_block_like_error",
    "_register_block_detection",
    "_reset_block_detection_streak",
    "register_discovered_complex",
    "record_crawl_history",
    "_finalize_disappeared_articles",
    "_process_raw_items",
    "_run_fallback_selenium",
    "log",
    "_push_item",
    "_flush_pending_items_if_needed",
    "_build_stats_payload",
    "emit_stats",
    "_row_get",
    "_cache_key",
    "_get_history_state_map",
    "_get_alert_rules",
    "_flush_history_updates_fallback",
    "_notify_db_write_disabled",
    "_flush_history_updates",
    "_enrich_item_with_history_and_alerts",
    "_init_driver",
    "run",
    "_run_selenium_loop",
    "_crawl",
    "_crawl_once",
    "_is_confirmed_empty_state",
    "_detect_block_signal",
    "_assert_not_blocked_page",
    "_get_item_state",
    "_detect_scroll_container",
    "_scroll_once",
    "_scroll",
    "_parse",
    "_check_filters",
    ],
)
