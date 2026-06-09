import sys, os, re, json, csv, time, random, shutil, logging, sqlite3, webbrowser
import importlib
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
    _plyer_module = importlib.import_module("plyer")
    notification = getattr(_plyer_module, "notification", None)
    NOTIFICATION_AVAILABLE = notification is not None
except Exception:
    notification = None
    NOTIFICATION_AVAILABLE = False

from src.utils.constants import APP_TITLE, APP_VERSION, SHORTCUTS
from src.utils.logger import get_logger
from src.core.database import ComplexDatabase
from src.core.managers import SettingsManager, FilterPresetManager, SearchHistoryManager, RecentlyViewedManager
from src.ui.styles import get_stylesheet
from src.ui.input_wheel_guard import install_global_wheel_guard, apply_wheel_guard_recursively
from src.utils.helpers import DateTimeHelper, get_article_url

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

from src.utils.mixin_rebind import rebind_inherited_methods

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


rebind_inherited_methods(
    RealEstateApp,
    mixin_classes=[
        AppLifecycleMixin,
        AppTabSetupMixin,
        AppStatsScheduleMixin,
        AppSettingsPresetMixin,
        AppDatabaseMaintenanceMixin,
    ],
    globals_dict=globals(),
)