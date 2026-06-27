from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QTableWidget, 
    QTableWidgetItem, QCheckBox, QAbstractItemView, QHeaderView, QTabWidget, 
    QGroupBox, QSplitter, QScrollArea, QFrame, QStackedWidget, QTextBrowser, 
    QDialog, QMessageBox, QFileDialog, QSizePolicy, QStyle, QApplication, QMenu,
    QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox
)


from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRegularExpression, QThread
from PyQt6.QtGui import QTextCursor, QRegularExpressionValidator
import webbrowser
import re

from src.utils.helpers import PriceConverter, DateTimeHelper, get_article_url, get_complex_url
from src.core.services.price_snapshots import build_price_snapshot_rows
from src.core.managers import settings
from src.ui.widgets.components import (
    SearchBar, SpeedSlider, ProgressWidget, SummaryCard, SortableTableWidgetItem
)
from src.ui.widgets.cards import CardViewWidget
from src.ui.dialogs import (
    MultiSelectDialog,
    URLBatchDialog,
    RecentSearchDialog,
    ExcelTemplateDialog,
    AdvancedFilterDialog,
)
from src.ui.styles import COLORS
from src.utils.logger import get_logger


logger = get_logger("CrawlerTab")

CrawlerThread = None
CrawlCache = None
DataExporter = None


class PriceSnapshotSaveThread(QThread):
    saved_signal = pyqtSignal(int)
    failed_signal = pyqtSignal(str)

    def __init__(self, db, items, parent=None):
        super().__init__(parent)
        self._db = db
        self._items = [dict(item or {}) for item in (items or []) if isinstance(item, dict)]

    def run(self):
        try:
            rows = build_price_snapshot_rows(self._items)
            saved = self._db.add_price_snapshots_bulk(rows) if rows else 0
            self.saved_signal.emit(int(saved or 0))
        except Exception as exc:
            self.failed_signal.emit(str(exc))


def _get_crawler_thread_cls():
    global CrawlerThread
    if CrawlerThread is None:
        from src.core.crawler import CrawlerThread as _CrawlerThread

        CrawlerThread = _CrawlerThread
    return CrawlerThread


def _get_crawl_cache_cls():
    global CrawlCache
    if CrawlCache is None:
        from src.core.cache import CrawlCache as _CrawlCache

        CrawlCache = _CrawlCache
    return CrawlCache


def _get_data_exporter_cls():
    global DataExporter
    if DataExporter is None:
        from src.core.export import DataExporter as _DataExporter

        DataExporter = _DataExporter
    return DataExporter

from src.utils.mixin_rebind import rebind_inherited_methods

from src.ui.widgets.crawler_tab_parts.ui_setup import CrawlerTabUISetupMixin
from src.ui.widgets.crawler_tab_parts.crawl_control import CrawlerTabCrawlControlMixin
from src.ui.widgets.crawler_tab_parts.result_render import CrawlerTabResultRenderMixin
from src.ui.widgets.crawler_tab_parts.filters_search import CrawlerTabFiltersSearchMixin
from src.ui.widgets.crawler_tab_parts.io_actions import CrawlerTabIOActionsMixin


class CrawlerTab(
    CrawlerTabUISetupMixin,
    CrawlerTabCrawlControlMixin,
    CrawlerTabResultRenderMixin,
    CrawlerTabFiltersSearchMixin,
    CrawlerTabIOActionsMixin,
    QWidget,
):
    """크롤링 및 데이터 수집 탭"""
    COL_COMPLEX = 0
    COL_TRADE = 1
    COL_PRICE = 2
    COL_AREA = 3
    COL_PYEONG_PRICE = 4
    COL_FLOOR = 5
    COL_FEATURE = 6
    COL_DUP_COUNT = 7
    COL_NEW = 8
    COL_PRICE_CHANGE = 9
    COL_ASSET_TYPE = 10
    COL_PREV_JEONSE = 11
    COL_GAP_AMOUNT = 12
    COL_GAP_RATIO = 13
    COL_COLLECTED_AT = 14
    COL_LINK = 15
    COL_URL = 16
    COL_PRICE_SORT = 17
    
    # Signals
    data_collected = pyqtSignal(list)  # 수집 완료 시 데이터 전송
    crawling_started = pyqtSignal()
    crawling_stopped = pyqtSignal()
    status_message = pyqtSignal(str)
    alert_triggered = pyqtSignal(str, str, str, float, int)
    


rebind_inherited_methods(
    CrawlerTab,
    mixin_classes=[
        CrawlerTabUISetupMixin,
        CrawlerTabCrawlControlMixin,
        CrawlerTabResultRenderMixin,
        CrawlerTabFiltersSearchMixin,
        CrawlerTabIOActionsMixin,
    ],
    globals_dict=globals(),
)