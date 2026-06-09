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
from src.utils.helpers import PriceConverter, ChromeParamHelper, DateTimeHelper, get_complex_url
from src.utils.retry_handler import RetryCancelledError, RetryHandler
from src.core.engines import PlaywrightCrawlerEngine, SeleniumCrawlerEngine
from src.core.item_parser import ItemParser
from src.core.models.crawl_models import GeoSweepConfig

# 메모리 임계치 (MB) - 초과 시 드라이버 재시작
MEMORY_THRESHOLD_MB = 500

from src.utils.mixin_rebind import rebind_inherited_methods

from src.core.crawler_parts.state_runtime import CrawlerStateRuntimeMixin
from src.core.crawler_parts.history_alerts import CrawlerHistoryAlertsMixin
from src.core.crawler_parts.selenium_flow import CrawlerSeleniumFlowMixin
from src.core.crawler_parts.dom_scroll_parse import CrawlerDomScrollParseMixin, BlockedPageError


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