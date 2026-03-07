import sys, os, re, json, csv, time, random, shutil, logging, sqlite3, webbrowser
from queue import Queue, Empty as QueueEmpty, Full as QueueFull
from pathlib import Path
from datetime import datetime, timedelta
from threading import Lock
from typing import Optional, List, Dict, Any, Tuple
from logging.handlers import RotatingFileHandler
from json import JSONDecodeError
from urllib.error import URLError, HTTPError
from urllib.request import urlopen, Request
from socket import timeout as SocketTimeout
import gc

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QTableWidget, QTableWidgetItem, QTextBrowser, QProgressBar,
    QTabWidget, QGroupBox, QSplitter, QScrollArea, QFrame, QListWidget,
    QListWidgetItem, QHeaderView, QMessageBox, QFileDialog, QInputDialog, 
    QTimeEdit, QStatusBar, QMenu, QSystemTrayIcon, QStyle, QApplication,
    QDialog, QDialogButtonBox, QSlider, QAbstractItemView, QToolTip, QSizePolicy, QStackedWidget
)
from PyQt6.QtCore import Qt, QTimer, QTime, QThread, pyqtSignal, QUrl, QPoint
from PyQt6.QtGui import QAction, QColor, QShortcut, QKeySequence, QFont, QDesktopServices, QCursor

try:
    from plyer import notification
    NOTIFICATION_AVAILABLE = True
except ImportError:
    NOTIFICATION_AVAILABLE = False

from src.utils.constants import APP_TITLE, APP_VERSION, SHORTCUTS
from src.utils.logger import get_logger
from src.core.database import ComplexDatabase
from src.core.managers import SettingsManager, FilterPresetManager, SearchHistoryManager, RecentlyViewedManager
from src.ui.styles import get_stylesheet
from src.utils.helpers import DateTimeHelper, get_article_url

from src.ui.widgets.crawler_tab import CrawlerTab
from src.ui.widgets.geo_crawler_tab import GeoCrawlerTab
from src.ui.widgets.database_tab import DatabaseTab
from src.ui.widgets.group_tab import GroupTab
from src.ui.widgets.tabs import FavoritesTab

from src.ui.widgets.dashboard import DashboardWidget
from src.ui.widgets.chart import ChartWidget
from src.ui.widgets.components import SortableTableWidgetItem
from src.ui.dialogs import (
    SettingsDialog,
    ShortcutsDialog,
    AboutDialog,
    URLBatchDialog,
    PresetDialog,
    AlertSettingDialog,
    ExcelTemplateDialog,
)
from src.ui.widgets.toast import ToastWidget

settings = SettingsManager()
ui_logger = get_logger("UI")

import inspect
import types

from src.ui.app_parts.tab_setup import AppTabSetupMixin
from src.ui.app_parts.stats_schedule import AppStatsScheduleMixin
from src.ui.app_parts.settings_preset import AppSettingsPresetMixin
from src.ui.app_parts.db_maintenance import AppDatabaseMaintenanceMixin
from src.ui.app_parts.lifecycle import AppLifecycleMixin


class RealEstateApp(
    AppLifecycleMixin,
    AppTabSetupMixin,
    AppStatsScheduleMixin,
    AppSettingsPresetMixin,
    AppDatabaseMaintenanceMixin,
    QMainWindow,
):
    pass


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
    RealEstateApp,
    [
    "__init__",
    "_restore_window_geometry",
    "_init_ui",
    "_setup_schedule_tab",
    "_setup_history_tab",
    "_setup_stats_tab",
    "_setup_dashboard_tab",
    "_setup_favorites_tab",
    "_setup_guide_tab",
    "_init_menu",
    "_init_shortcuts",
    "_register_shortcut",
    "_start_crawling",
    "_stop_crawling",
    "_save_excel",
    "_save_csv",
    "_save_json",
    "_init_tray",
    "_init_timers",
    "_load_initial_data",
    "_ensure_chart_widget",
    "_ensure_dashboard_widget",
    "_on_crawl_data_collected",
    "_on_alert_triggered",
    "_on_dashboard_warning",
    "_load_schedule_groups",
    "_check_schedule",
    "_run_scheduled",
    "_update_group_empty_state",
    "_update_group_action_state",
    "_update_group_complex_empty_state",
    "_update_group_complex_action_state",
    "_update_schedule_state",
    "_load_history",
    "_parse_pyeong_value",
    "_format_pyeong_value",
    "_load_stats_complexes",
    "_load_stats",
    "_on_stats_complex_changed",
    "_toggle_theme",
    "_show_settings",
    "_apply_settings",
    "_save_preset",
    "_load_preset",
    "_show_alert_settings",
    "_show_shortcuts",
    "_show_about",
    "_enter_maintenance_mode",
    "_exit_maintenance_mode",
    "_show_advanced_filter",
    "_apply_advanced_filter",
    "_filter_results_advanced",
    "_clear_advanced_filter",
    "_render_results",
    "_restore_summary",
    "_is_default_advanced_filter",
    "_refresh_favorite_keys",
    "_on_favorite_toggled",
    "_check_advanced_filter",
    "_show_url_batch_dialog",
    "_add_complexes_from_url",
    "_add_complexes_from_dialog",
    "_show_excel_template_dialog",
    "_save_excel_template",
    "_backup_db",
    "_restore_db",
    "_refresh_tab",
    "_focus_search",
    "_minimize_to_tray",
    "_show_from_tray",
    "_tray_activated",
    "_shutdown",
    "_quit_app",
    "closeEvent",
    "show_toast",
    "_reposition_toasts",
    "_toggle_view_mode",
    "show_notification",
    "_show_recently_viewed_dialog",
    ],
)
