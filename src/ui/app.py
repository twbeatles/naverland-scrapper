import importlib
import re  # noqa: F401  # star-carried: `from src.ui.app import *` in app_parts/* (do not remove)
import time  # noqa: F401  # star-carried (do not remove)
import webbrowser  # noqa: F401  # star-carried (do not remove)
from datetime import datetime, timedelta  # noqa: F401  # tests patch src.ui.app.datetime
from pathlib import Path  # noqa: F401  # star-carried (do not remove)
from typing import Any, List, Tuple  # noqa: F401  # star-carried (do not remove)

from PySide6.QtCore import Qt, QTime, QTimer  # noqa: F401  # star-carried + patch targets (do not remove)
from PySide6.QtGui import QAction, QColor, QKeySequence, QShortcut  # noqa: F401  # star-carried + patch targets (do not remove)
from PySide6.QtWidgets import (  # noqa: F401  # QMainWindow used in body; rest star-carried + patch targets (do not remove)
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from src.ui.input_wheel_guard import (  # noqa: F401  # star-carried (do not remove)
    apply_wheel_guard_recursively,
    install_global_wheel_guard,
)
from src.ui.styles import get_stylesheet  # noqa: F401  # star-carried (do not remove)
from src.ui.widgets.toast import ToastWidget  # noqa: F401  # star-carried (do not remove)
from src.utils.constants import APP_TITLE, APP_VERSION, SHORTCUTS  # noqa: F401  # star-carried (do not remove)
from src.utils.helpers import DateTimeHelper, get_article_url  # noqa: F401  # star-carried (do not remove)

try:
    _plyer_module = importlib.import_module("plyer")
    notification = getattr(_plyer_module, "notification", None)
    NOTIFICATION_AVAILABLE = notification is not None
except Exception:
    notification = None
    NOTIFICATION_AVAILABLE = False

# Fluent shell helpers (required in app globals for mixin rebind).
from qfluentwidgets import FluentIcon as FIF  # noqa: F401
from qfluentwidgets import NavigationInterface  # noqa: F401  # Fluent shell helper in app globals for mixin rebind (do not remove)

from src.core.database import ComplexDatabase  # noqa: F401  # tests patch src.ui.app.ComplexDatabase
from src.core.managers import (  # noqa: F401  # star-carried + patch targets (do not remove)
    FilterPresetManager,
    RecentlyViewedManager,
    SearchHistoryManager,
    get_settings,
    settings,
)
from src.ui.app_parts.db_maintenance import AppDatabaseMaintenanceMixin
from src.ui.app_parts.lifecycle import AppLifecycleMixin
from src.ui.app_parts.settings_preset import AppSettingsPresetMixin
from src.ui.app_parts.stats_schedule import AppStatsScheduleMixin
from src.ui.app_parts.tab_setup import (  # noqa: F401
    AppTabSetupMixin,
    _empty_state_qss,
    _secondary_label_qss,
)
from src.ui.dialogs import (  # noqa: F401  # star-carried + patch targets (do not remove)
    AboutDialog,
    AlertSettingDialog,
    ExcelTemplateDialog,
    PresetDialog,
    SettingsDialog,
    ShortcutsDialog,
)
from src.ui.fluent.navigation import (  # noqa: F401
    ROUTE_CRAWLER,
    ROUTE_DASHBOARD,
    ROUTE_DB,
    ROUTE_FAVORITES,
    ROUTE_GEO,
    ROUTE_GROUP,
    ROUTE_GUIDE,
    ROUTE_HISTORY,
    ROUTE_SCHEDULE,
    ROUTE_STATS,
    prepare_page,
    register_navigation,
    sync_nav_selection,
)
from src.ui.fluent.tab_bridge import TabCompatBridge  # noqa: F401
from src.ui.fluent.theme import apply_app_theme  # noqa: F401
from src.utils.logger import get_logger
from src.utils.mixin_rebind import rebind_inherited_methods

# Rebind globals for AppTabSetupMixin (tab labels must resolve on RealEstateApp).
from src.utils.ui_labels import (  # noqa: F401
    TAB_CRAWLER,
    TAB_DASHBOARD,
    TAB_DB,
    TAB_FAVORITES,
    TAB_GEO,
    TAB_GROUP,
    TAB_GUIDE,
    TAB_HISTORY,
    TAB_SCHEDULE,
    TAB_STATS,
)
from src.utils.update_controller import UpdateController  # noqa: F401

ui_logger = get_logger("UI")


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
