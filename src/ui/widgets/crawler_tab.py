from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QTableWidget, 
    QTableWidgetItem, QCheckBox, QAbstractItemView, QHeaderView, QTabWidget, 
    QGroupBox, QSplitter, QScrollArea, QFrame, QStackedWidget, QTextBrowser, 
    QDialog, QMessageBox, QFileDialog, QSizePolicy, QStyle, QApplication, QMenu,
    QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox
)


from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRegularExpression
from PyQt6.QtGui import QTextCursor, QRegularExpressionValidator
import webbrowser
import re

from src.utils.helpers import PriceConverter, DateTimeHelper, get_article_url
from src.core.managers import SettingsManager
from src.core.crawler import CrawlerThread
from src.core.cache import CrawlCache
from src.core.export import DataExporter
from src.ui.widgets.components import (
    SearchBar, SpeedSlider, ProgressWidget, SummaryCard
)
from src.ui.widgets.dashboard import CardViewWidget
from src.ui.dialogs import (
    MultiSelectDialog,
    URLBatchDialog,
    RecentSearchDialog,
    ExcelTemplateDialog,
    AdvancedFilterDialog,
)
from src.ui.styles import COLORS
from src.utils.logger import get_logger

settings = SettingsManager()
logger = get_logger("CrawlerTab")

import inspect
import types

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
    CrawlerTab,
    [
    "__init__",
    "_init_ui",
    "_configure_filter_spinbox",
    "_setup_options_group",
    "_setup_filter_group",
    "_setup_complex_list_group",
    "_setup_speed_group",
    "_setup_action_group",
    "_setup_result_area",
    "_queue_splitter_state_save",
    "_save_splitter_state",
    "_restore_splitter_state",
    "_load_state",
    "set_theme",
    "_on_speed_changed",
    "_default_sort_criterion",
    "_apply_default_sort_settings",
    "update_runtime_settings",
    "_toggle_area_filter",
    "_toggle_price_filter",
    "_add_complex",
    "_normalize_task_name",
    "_find_task_row_by_cid",
    "_append_task_row",
    "_emit_task_duplicate_skip",
    "add_task",
    "_add_row",
    "_dedupe_target_entries",
    "_normalize_task_table",
    "clear_tasks",
    "_delete_complex",
    "_clear_list",
    "_save_to_db",
    "_show_db_load_dialog",
    "_show_group_load_dialog",
    "_show_recent_search_dialog",
    "_show_url_batch_dialog",
    "_add_complexes_from_url",
    "_open_complex_url",
    "_toggle_compact_duplicates",
    "_update_advanced_filter_badge",
    "_apply_advanced_filter_items",
    "_favorite_key_for_item",
    "_favorite_keys_snapshot",
    "_decorate_favorite_state",
    "set_advanced_filters",
    "_area_float",
    "_extract_price_values",
    "_get_compact_key",
    "_normalize_price_change",
    "_merge_compact_item",
    "_reset_result_state",
    "_rebuild_result_views_from_collected_data",
    "_toggle_view_mode",
    "start_crawling",
    "stop_crawling",
    "shutdown_crawl",
    "_on_crawl_finished",
    "append_log",
    "_on_items_batch",
    "_sync_row_search_cache",
    "_format_won_value",
    "_format_gap_ratio",
    "_build_row_payload_from_data",
    "_build_row_payload_from_table",
    "_build_payload_lookup_by_url",
    "_apply_current_filter_to_row",
    "_set_result_row",
    "_append_rows_compact_batch",
    "_sort_compact_rows",
    "_render_compact_rows",
    "_append_rows_batch",
    "_on_complex_finished",
    "_on_alert_triggered",
    "_update_stats_ui",
    "_on_search_text_changed",
    "_apply_search_filter",
    "_rebuild_row_search_cache_from_table",
    "_is_default_advanced_filter",
    "_floor_category",
    "_check_advanced_filter",
    "_advanced_filtered_data_for_cards",
    "_apply_card_filters",
    "open_advanced_filter_dialog",
    "clear_advanced_filters",
    "_filter_results",
    "_sort_results",
    "_save_price_snapshots",
    "get_filter_state",
    "set_filter_state",
    "_visible_export_items",
    "_export_items_for_scope",
    "_save_with_export_scope",
    "show_save_menu",
    "save_excel",
    "save_csv",
    "save_json",
    "_show_excel_template_dialog",
    "_open_article_url",
    ],
)
