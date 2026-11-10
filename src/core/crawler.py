import gc  # noqa: F401  # star-carried: `from src.core.crawler import *` in crawler_parts/* (do not remove)
import random  # noqa: F401  # star-carried: `from src.core.crawler import *` in crawler_parts/* (do not remove)
import time  # noqa: F401  # star-carried: `from src.core.crawler import *` in crawler_parts/* (do not remove)
import traceback  # noqa: F401  # star-carried: `from src.core.crawler import *` in crawler_parts/* (do not remove)

from PySide6.QtCore import QThread, Signal

from src.core.crawler_parts.dom_scroll_parse import (  # noqa: F401  # BlockedPageError star-carried (do not remove)
    BlockedPageError,
    CrawlerDomScrollParseMixin,
)
from src.core.crawler_parts.history_alerts import CrawlerHistoryAlertsMixin
from src.core.crawler_parts.selenium_flow import CrawlerSeleniumFlowMixin
from src.core.crawler_parts.state_runtime import CrawlerStateRuntimeMixin
from src.core.engines import PlaywrightCrawlerEngine, SeleniumCrawlerEngine  # noqa: F401  # star-carried (do not remove)
from src.core.item_parser import ItemParser  # noqa: F401  # star-carried (do not remove)
from src.core.models.crawl_models import GeoSweepConfig  # noqa: F401  # star-carried (do not remove)
from src.utils.constants import CRAWL_SPEED_PRESETS  # noqa: F401  # star-carried (do not remove)
from src.utils.helpers import (  # noqa: F401  # star-carried (do not remove)
    ChromeParamHelper,
    DateTimeHelper,
    PriceConverter,
    get_complex_url,
)
from src.utils.mixin_rebind import rebind_inherited_methods
from src.utils.retry_handler import RetryCancelledError, RetryHandler  # noqa: F401  # star-carried (do not remove)

try:
    import undetected_chromedriver as uc  # noqa: F401  # star-carried: selenium_flow uses via star (do not remove)
    from selenium.common.exceptions import NoSuchElementException, TimeoutException  # noqa: F401  # star-carried (do not remove)
    from selenium.webdriver.support import expected_conditions as EC  # noqa: F401  # star-carried (do not remove)
    from selenium.webdriver.support.ui import WebDriverWait  # noqa: F401  # star-carried (do not remove)
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False

try:
    from bs4 import BeautifulSoup  # noqa: F401  # star-carried (do not remove)
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    import psutil  # noqa: F401  # star-carried (do not remove)
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


# 메모리 임계치 (MB) - 초과 시 드라이버 재시작
MEMORY_THRESHOLD_MB = 500




class CrawlerThread(
    CrawlerStateRuntimeMixin,
    CrawlerHistoryAlertsMixin,
    CrawlerSeleniumFlowMixin,
    CrawlerDomScrollParseMixin,
    QThread,
):
    log_signal = Signal(str, int)
    progress_signal = Signal(int, str, int)  # percent, current_name, remaining_seconds
    item_signal = Signal(dict)  # deprecated: items_signal(list[dict]) 사용 권장
    items_signal = Signal(list)
    stats_signal = Signal(dict)
    complex_finished_signal = Signal(str, str, str, int)
    finished_signal = Signal(list)
    error_signal = Signal(str)
    alert_triggered_signal = Signal(str, str, str, float, int)
    discovered_complex_signal = Signal(dict)
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
    


rebind_inherited_methods(
    CrawlerThread,
    mixin_classes=[
        CrawlerStateRuntimeMixin,
        CrawlerHistoryAlertsMixin,
        CrawlerSeleniumFlowMixin,
        CrawlerDomScrollParseMixin,
    ],
    globals_dict=globals(),
)
