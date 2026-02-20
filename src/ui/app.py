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
from src.utils.helpers import DateTimeHelper, PriceConverter, get_article_url

from src.ui.widgets.crawler_tab import CrawlerTab
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
    AdvancedFilterDialog,
    ExcelTemplateDialog,
)
from src.ui.widgets.toast import ToastWidget

settings = SettingsManager()
ui_logger = get_logger("UI")

class RealEstateApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1400, 900)
        geo = settings.get("window_geometry")
        if geo: self.setGeometry(*geo)
        else: self.setGeometry(100, 100, 1500, 950)
        
        self.settings_manager = SettingsManager()
        self.preset_manager = FilterPresetManager()
        self.history_manager = SearchHistoryManager(max_items=settings.get("max_search_history", 20))
        self.recently_viewed = RecentlyViewedManager()
        self.advanced_filters = None
        self.collected_data = []
        self.is_scheduled_run = False
        self.retry_handler = None
        self.tray_icon = None
        self._is_shutting_down = False
        self.favorite_keys = set()
        self._shortcuts = {}
        self.db = ComplexDatabase()
        self._lazy_noncritical_tabs = bool(settings.get("startup_lazy_noncritical_tabs", True))
        self._noncritical_loaded = {
            "history": False,
            "stats": False,
            "favorites": False,
        }
        
        # v11.0: Toast 알림 시스템
        self.toast_widgets: List[ToastWidget] = []
        
        self.current_theme = settings.get("theme", "dark")
        self.setStyleSheet(get_stylesheet(self.current_theme))
        
        # UI 초기화
        self._init_ui()
        self._init_menu()
        self._init_shortcuts()
        self._init_tray()
        self._init_timers()
        self._load_initial_data()
        
        # 윈도우 설정
        self._restore_window_geometry()
        
        self.show_toast(f"환영합니다! {APP_TITLE} {APP_VERSION}입니다.")

    def _restore_window_geometry(self):
        geo = settings.get("window_geometry")
        if not geo:
            return
        if not isinstance(geo, (list, tuple)) or len(geo) != 4:
            return
        try:
            x, y, w, h = (int(geo[0]), int(geo[1]), int(geo[2]), int(geo[3]))
            self.setGeometry(x, y, w, h)
        except Exception:
            # Best-effort only; invalid saved geometry should not prevent startup.
            return
    
    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # 1. 수집기 탭
        self.crawler_tab = CrawlerTab(self.db, history_manager=self.history_manager, theme=self.current_theme)
        self.tabs.addTab(self.crawler_tab, "🏠 데이터 수집")
        
        # 2. 단지 DB 탭
        self.db_tab = DatabaseTab(self.db)
        self.tabs.addTab(self.db_tab, "💾 단지 DB")
        
        # 3. 그룹 관리 탭
        self.group_tab = GroupTab(self.db)
        self.tabs.addTab(self.group_tab, "📁 그룹 관리")
        
        self._setup_schedule_tab()
        self._setup_history_tab()
        self._setup_stats_tab()
        self._setup_dashboard_tab()
        self._setup_favorites_tab()
        self._setup_guide_tab()
        
        self.status_bar = self.statusBar()
        self.crawler_tab.data_collected.connect(self._on_crawl_data_collected)
        self.crawler_tab.status_message.connect(self.status_bar.showMessage)
        self.crawler_tab.alert_triggered.connect(self._on_alert_triggered)
        self.group_tab.groups_updated.connect(self._load_schedule_groups)
        
        self.tabs.currentChanged.connect(self._refresh_tab)

    
    
    # Obsolete setup methods removed (replaced by modular widgets)
    # _setup_crawler_tab, _setup_db_tab, _setup_groups_tab removed

    
    def _setup_schedule_tab(self):
        self.schedule_tab = QWidget()
        layout = QVBoxLayout(self.schedule_tab)
        sg = QGroupBox("⏰ 예약 크롤링")
        sl = QVBoxLayout()
        self.check_schedule = QCheckBox("예약 실행 활성화")
        sl.addWidget(self.check_schedule)
        tl = QHBoxLayout()
        tl.addWidget(QLabel("실행 시간:"))
        self.time_edit = QTimeEdit()
        self.time_edit.setTime(QTime(9, 0))
        tl.addWidget(self.time_edit)
        tl.addStretch()
        sl.addLayout(tl)
        gl = QHBoxLayout()
        gl.addWidget(QLabel("대상 그룹:"))
        self.schedule_group_combo = QComboBox()
        gl.addWidget(self.schedule_group_combo)
        gl.addStretch()
        sl.addLayout(gl)
        sg.setLayout(sl)
        layout.addWidget(sg)
        self.schedule_empty_label = QLabel("예약할 그룹이 없습니다.\n먼저 그룹을 생성하세요.")
        self.schedule_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.schedule_empty_label.setStyleSheet("color: #888; padding: 20px;")
        self.schedule_empty_label.hide()
        layout.addWidget(self.schedule_empty_label)
        layout.addStretch()
        self.tabs.addTab(self.schedule_tab, "⏰ 예약 설정")
    
    def _setup_history_tab(self):
        self.history_tab = QWidget()
        layout = QVBoxLayout(self.history_tab)
        bl = QHBoxLayout()
        btn_rf = QPushButton("🔄 새로고침")
        btn_rf.clicked.connect(self._load_history)
        bl.addWidget(btn_rf)
        bl.addStretch()
        layout.addLayout(bl)
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(["단지명", "단지ID", "거래유형", "수집건수", "수집시각"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.setAlternatingRowColors(True)
        layout.addWidget(self.history_table)
        self.tabs.addTab(self.history_tab, "📜 히스토리")
    
    def _setup_stats_tab(self):
        self.stats_tab = QWidget()
        layout = QVBoxLayout(self.stats_tab)
        fl = QHBoxLayout()
        fl.addWidget(QLabel("단지:"))
        self.stats_complex_combo = QComboBox()
        fl.addWidget(self.stats_complex_combo)
        fl.addWidget(QLabel("유형:"))
        self.stats_type_combo = QComboBox()
        self.stats_type_combo.addItems(["전체", "매매", "전세", "월세"])
        fl.addWidget(self.stats_type_combo)
        
        fl.addWidget(QLabel("면적:"))
        self.stats_pyeong_combo = QComboBox()
        self.stats_pyeong_combo.addItem("전체")
        fl.addWidget(self.stats_pyeong_combo)
        
        btn_load = QPushButton("📊 조회")
        btn_load.clicked.connect(self._load_stats)
        fl.addWidget(btn_load)
        fl.addStretch()
        layout.addLayout(fl)
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(6)
        self.stats_table.setHorizontalHeaderLabels(["날짜", "유형", "평형", "최저가", "최고가", "평균가"])
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.stats_table.setAlternatingRowColors(True)
        
        # v10.0: Chart Integration
        self.stats_splitter = QSplitter(Qt.Orientation.Vertical)
        self.stats_splitter.addWidget(self.stats_table)
        self.chart_widget = None
        self.chart_placeholder = QLabel("차트는 통계 조회 시 로드됩니다.")
        self.chart_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stats_splitter.addWidget(self.chart_placeholder)
        self.stats_splitter.setSizes([320, 280])
        
        layout.addWidget(self.stats_splitter)
        self.tabs.addTab(self.stats_tab, "📈 통계/변동")
    
    def _setup_dashboard_tab(self):
        """v13.0: 분석 대시보드 탭 (lazy load)"""
        self.dashboard_tab = QWidget()
        self.dashboard_layout = QVBoxLayout(self.dashboard_tab)
        self.dashboard_placeholder = QLabel("대시보드는 첫 진입 시 로드됩니다.")
        self.dashboard_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dashboard_layout.addWidget(self.dashboard_placeholder)
        self.dashboard_widget = None
        self.tabs.addTab(self.dashboard_tab, "📊 대시보드")
    
    def _setup_favorites_tab(self):
        """v13.0: 즐겨찾기 탭"""
        self.favorites_tab = FavoritesTab(
            self.db, theme=self.current_theme, favorite_toggled=self._on_favorite_toggled
        )
        self.tabs.addTab(self.favorites_tab, "⭐ 즐겨찾기")
    
    def _setup_guide_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml("""
        <h2>📖 사용 가이드</h2>
        <h3>🔍 단지 ID 찾는 방법</h3>
        <ol>
            <li>네이버 부동산 (<a href="https://new.land.naver.com">new.land.naver.com</a>) 접속</li>
            <li>원하는 아파트 단지 검색</li>
            <li>URL에서 <code>/complexes/</code> 뒤의 숫자가 단지 ID입니다</li>
            <li>예: <code>https://new.land.naver.com/complexes/<b>12345</b></code> → ID: 12345</li>
        </ol>
        <h3>⌨️ 단축키</h3>
        <table border="1" cellpadding="8" style="border-collapse: collapse;">
            <tr><th>기능</th><th>단축키</th></tr>
            <tr><td>🚀 크롤링 시작</td><td>Ctrl+R</td></tr>
            <tr><td>⏹️ 크롤링 중지</td><td>Ctrl+Shift+R</td></tr>
            <tr><td>💾 Excel 저장</td><td>Ctrl+S</td></tr>
            <tr><td>📄 CSV 저장</td><td>Ctrl+Shift+S</td></tr>
            <tr><td>🔍 검색</td><td>Ctrl+F</td></tr>
            <tr><td>⚙️ 설정</td><td>Ctrl+,</td></tr>
            <tr><td>🎨 테마 변경</td><td>Ctrl+T</td></tr>
            <tr><td>📥 트레이 최소화</td><td>Ctrl+M</td></tr>
        </table>
        <h3>💡 팁</h3>
        <ul>
            <li>🖱️ 결과 테이블에서 <b>더블클릭</b>하면 해당 매물 페이지로 이동합니다</li>
            <li>📊 요약 카드에서 실시간 수집 현황을 확인할 수 있습니다</li>
            <li>⏱️ 예상 남은 시간을 참고하여 작업 시간을 예측하세요</li>
            <li>🔔 알림 설정을 통해 원하는 조건의 매물을 알림받을 수 있습니다</li>
        </ul>
        """)
        layout.addWidget(browser)
        self.tabs.addTab(tab, "📖 가이드")
    
    def _init_menu(self):
        menubar = self.menuBar()
        
        # 파일 메뉴
        file_menu = menubar.addMenu("📂 파일")
        file_menu.addAction("💾 DB 백업", self._backup_db)
        file_menu.addAction("📂 DB 복원", self._restore_db)
        file_menu.addSeparator()
        file_menu.addAction("⚙️ 설정", self._show_settings)
        file_menu.addAction("❌ 종료", self._quit_app)
        
        # 보기 메뉴 (v13.0)
        view_menu = menubar.addMenu("👁️ 보기")
        view_menu.addAction("🕐 최근 본 매물", self._show_recently_viewed_dialog)
        view_menu.addSeparator()
        
        # 테마 메뉴
        theme_menu = view_menu.addMenu("🎨 테마")
        self.action_theme_dark = QAction("🌙 다크 모드", self, checkable=True)
        self.action_theme_dark.setChecked(self.current_theme == "dark")
        self.action_theme_dark.triggered.connect(lambda: self._toggle_theme("dark"))
        theme_menu.addAction(self.action_theme_dark)
        
        self.action_theme_light = QAction("☀️ 라이트 모드", self, checkable=True)
        self.action_theme_light.setChecked(self.current_theme == "light")
        self.action_theme_light.triggered.connect(lambda: self._toggle_theme("light"))
        theme_menu.addAction(self.action_theme_light)
        
        # 필터 메뉴
        filter_menu = menubar.addMenu("🔍 필터")
        filter_menu.addAction("💾 현재 필터 저장", self._save_preset)
        filter_menu.addAction("📂 필터 불러오기", self._load_preset)
        
        # 알림 메뉴
        alert_menu = menubar.addMenu("🔔 알림")
        alert_menu.addAction("⚙️ 알림 설정", self._show_alert_settings)
        
        # 도움말 메뉴
        help_menu = menubar.addMenu("❓ 도움말")
        help_menu.addAction("⌨️ 단축키", self._show_shortcuts)
        help_menu.addAction("ℹ️ 정보", self._show_about)
    
    def _init_shortcuts(self):
        self._register_shortcut(SHORTCUTS["start_crawl"], self._start_crawling)
        self._register_shortcut(SHORTCUTS["stop_crawl"], self._stop_crawling)
        self._register_shortcut(SHORTCUTS["save_excel"], self._save_excel)
        self._register_shortcut(SHORTCUTS["save_csv"], self._save_csv)
        self._register_shortcut(SHORTCUTS["refresh"], self._refresh_tab)
        self._register_shortcut(SHORTCUTS["search"], self._focus_search)
        self._register_shortcut(SHORTCUTS["toggle_theme"], self._toggle_theme)
        self._register_shortcut(SHORTCUTS["minimize_tray"], self._minimize_to_tray)
        self._register_shortcut(SHORTCUTS["quit"], self._quit_app)
        self._register_shortcut(SHORTCUTS["settings"], self._show_settings)

    def _register_shortcut(self, key_sequence, callback):
        shortcut = QShortcut(QKeySequence(key_sequence), self, callback)
        self._shortcuts[key_sequence] = shortcut

    # Shortcut handlers (delegate to modular widgets)
    def _start_crawling(self):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab.start_crawling()

    def _stop_crawling(self):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab.stop_crawling()

    def _save_excel(self):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab.save_excel()

    def _save_csv(self):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab.save_csv()

    def _save_json(self):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab.save_json()
    
    def _init_tray(self):
        self.tray_icon = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon(self)
            self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
            tray_menu = QMenu()
            tray_menu.addAction("🔼 열기", self._show_from_tray)
            tray_menu.addAction("❌ 종료", self._quit_app)
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.activated.connect(self._tray_activated)
            self.tray_icon.show()
    
    def _init_timers(self):
        self.schedule_timer = QTimer(self)
        self.schedule_timer.timeout.connect(self._check_schedule)
        self.schedule_timer.start(60000)
    
    def _load_initial_data(self):
        # self._load_db_complexes() - Handled by DatabaseTab
        # self._load_all_groups() - Handled by GroupTab
        if hasattr(self, 'db_tab'): self.db_tab.load_data()
        if hasattr(self, 'group_tab'): self.group_tab.load_groups()

        if not self._lazy_noncritical_tabs:
            self._load_history()
            self._noncritical_loaded["history"] = True
            self._load_stats_complexes()
            self._noncritical_loaded["stats"] = True
            self._refresh_favorite_keys()
            self._noncritical_loaded["favorites"] = True
        self._load_schedule_groups()
        
        # Connect signals after loading
        try:
            self.stats_complex_combo.currentIndexChanged.disconnect(self._on_stats_complex_changed)
        except Exception:
            pass
        self.stats_complex_combo.currentIndexChanged.connect(self._on_stats_complex_changed)

    def _ensure_chart_widget(self):
        if self.chart_widget is not None:
            return
        self.chart_widget = ChartWidget()
        idx = self.stats_splitter.indexOf(self.chart_placeholder)
        if idx >= 0:
            self.stats_splitter.insertWidget(idx, self.chart_widget)
        else:
            self.stats_splitter.addWidget(self.chart_widget)
        self.chart_placeholder.hide()
        self.chart_placeholder.deleteLater()

    def _ensure_dashboard_widget(self):
        if self.dashboard_widget is not None:
            return
        self.dashboard_widget = DashboardWidget(self.db, theme=self.current_theme)
        self.dashboard_layout.addWidget(self.dashboard_widget)
        self.dashboard_placeholder.hide()
        self.dashboard_placeholder.deleteLater()
        if self.collected_data:
            self.dashboard_widget.set_data(self.collected_data)

    def _on_crawl_data_collected(self, data):
        self.collected_data = list(data) if data else []
        self._load_history()
        self._noncritical_loaded["history"] = True
        self._load_stats_complexes()
        self._noncritical_loaded["stats"] = True
        if self.tabs.currentWidget() is self.stats_tab:
            self._load_stats()
        if self.dashboard_widget is not None:
            self.dashboard_widget.set_data(self.collected_data)
        if hasattr(self, "favorites_tab"):
            self.favorites_tab.refresh()
            self._noncritical_loaded["favorites"] = True
        self.status_bar.showMessage(f"✅ 수집 결과 반영 완료 ({len(self.collected_data)}건)")

    def _on_alert_triggered(self, complex_name, trade_type, price_text, area_pyeong, alert_id):
        message = f"{complex_name} {trade_type} {price_text} ({area_pyeong:.1f}평)"
        self.show_toast(f"🔔 조건 매물 발견: {message}")
        self.show_notification("조건 매물 알림", message)
    
    # Event handlers
    # Obsolete helpers removed (replaced by widgets: CrawlerTab, DatabaseTab, GroupTab)
    # _toggle_area_filter, _toggle_price_filter, _add_complex, _add_row, _delete_complex, _clear_list,
    # _save_to_db, _show_db_load_dialog, _show_group_load_dialog, _show_history_dialog, _open_complex_url,
    # _open_db_complex_url, _open_article_url, _filter_results, _filter_db_table, _sort_results,
    # _start_crawling, _stop_crawling, _update_log, _update_progress, _add_result, _update_stats,
    # _on_complex_done, _crawling_done, _save_price_snapshots, _crawling_error, _show_save_menu,
    # _save_excel, _save_csv, _save_json, _load_db_complexes, _delete_db_complex, _delete_db_complexes_multi,
    # _edit_memo, _update_db_empty_state, _update_db_action_state, _load_all_groups, _create_group,
    # _delete_group, _load_group_complexes, _add_to_group, _add_to_group_multi, _remove_from_group

    
    def _load_schedule_groups(self):
        self.schedule_group_combo.clear()
        for gid, name, _ in self.db.get_all_groups():
            self.schedule_group_combo.addItem(name, gid)
        self._update_schedule_state()
    
    def _check_schedule(self):
        if not self.check_schedule.isChecked(): return
        if self.schedule_group_combo.count() == 0: return
        now = QTime.currentTime()
        target = self.time_edit.time()
        
        # 분 단위 비교
        if now.hour() == target.hour() and now.minute() == target.minute():
            if not self.is_scheduled_run:
                self.is_scheduled_run = True
                self._run_scheduled()
        else:
            self.is_scheduled_run = False
    
    def _run_scheduled(self):
        gid = self.schedule_group_combo.currentData()
        if gid:
            if hasattr(self, 'crawler_tab'):
                # 탭 전환
                self.tabs.setCurrentWidget(self.crawler_tab)
                
                # CrawlerTab 초기화 및 데이터 로드
                self.crawler_tab.clear_tasks()
                for _, name, cid, _ in self.db.get_complexes_in_group(gid):
                    self.crawler_tab.add_task(name, cid)
                
                # 크롤링 시작
                self.crawler_tab.start_crawling()
                self.status_bar.showMessage(f"⏰ 예약 작업 시작: 그룹 {gid}")


    def _update_group_empty_state(self):
        has_groups = self.group_list.count() > 0
        if hasattr(self, "group_empty_label"):
            self.group_empty_label.setVisible(not has_groups)
        self.group_list.setEnabled(has_groups)
        if not has_groups:
            self.group_complex_table.setRowCount(0)
            self._update_group_complex_empty_state(0)

    def _update_group_action_state(self):
        has_selection = self.group_list.currentRow() >= 0
        has_groups = self.group_list.count() > 0
        if hasattr(self, "group_btn_delete"):
            self.group_btn_delete.setEnabled(has_selection)
        if hasattr(self, "group_btn_add"):
            self.group_btn_add.setEnabled(has_groups)
        if hasattr(self, "group_btn_add_multi"):
            self.group_btn_add_multi.setEnabled(has_groups)
        if not has_groups:
            if hasattr(self, "group_btn_remove"):
                self.group_btn_remove.setEnabled(False)

    def _update_group_complex_empty_state(self, count):
        is_empty = count == 0
        if hasattr(self, "group_complex_empty_label"):
            self.group_complex_empty_label.setVisible(is_empty)
        self.group_complex_table.setEnabled(not is_empty)

    def _update_group_complex_action_state(self):
        has_selection = self.group_complex_table.currentRow() >= 0
        if hasattr(self, "group_btn_remove"):
            self.group_btn_remove.setEnabled(has_selection)

    def _update_schedule_state(self):
        has_groups = self.schedule_group_combo.count() > 0
        self.check_schedule.setEnabled(has_groups)
        self.time_edit.setEnabled(has_groups)
        self.schedule_group_combo.setEnabled(has_groups)
        if hasattr(self, "schedule_empty_label"):
            self.schedule_empty_label.setVisible(not has_groups)
    
    # History Tab handlers
    def _load_history(self):
        self.history_table.setUpdatesEnabled(False)
        try:
            self.history_table.setRowCount(0)
            history = self.db.get_crawl_history()
            self.history_table.setRowCount(len(history))
            for row, (name, cid, ttype, cnt, date) in enumerate(history):
                self.history_table.setItem(row, 0, QTableWidgetItem(name))
                self.history_table.setItem(row, 1, QTableWidgetItem(cid))
                self.history_table.setItem(row, 2, QTableWidgetItem(ttype))
                self.history_table.setItem(row, 3, QTableWidgetItem(str(cnt)))
                self.history_table.setItem(row, 4, QTableWidgetItem(date))
        finally:
            self.history_table.setUpdatesEnabled(True)
    
    # Stats Tab handlers
    def _load_stats_complexes(self):
        self.stats_complex_combo.blockSignals(True)
        self.stats_complex_combo.clear()
        complexes = self.db.get_complexes_for_stats()
        for name, cid in complexes:
            self.stats_complex_combo.addItem(f"{name}", cid)
        self.stats_complex_combo.blockSignals(False)
    
    def _load_stats(self):
        cid = self.stats_complex_combo.currentData()
        if not cid:
            return
        ttype = self.stats_type_combo.currentText()
        if ttype == "전체": ttype = None
        
        # v10.0: 평형 필터
        pyeong_text = self.stats_pyeong_combo.currentText()
        pyeong = None
        if pyeong_text != "전체":
            try:
                pyeong = float(pyeong_text.replace("평", ""))
            except ValueError:
                ui_logger.warning(f"평형 파싱 실패: {pyeong_text}")
                pyeong = None
        
        snapshots = self.db.get_price_snapshots(cid, ttype)
        if pyeong:
            snapshots = [s for s in snapshots if s[2] == pyeong]
        
        self.stats_table.setUpdatesEnabled(False)
        chart_data = {"date": [], "avg": [], "min": [], "max": []}
        try:
            self.stats_table.setRowCount(0)
            self.stats_table.setRowCount(len(snapshots))
            # 차트용 데이터 수집
            for row, (date, typ, py, min_p, max_p, avg_p, cnt) in enumerate(snapshots):
                self.stats_table.setItem(row, 0, QTableWidgetItem(date))
                self.stats_table.setItem(row, 1, QTableWidgetItem(typ))
                self.stats_table.setItem(row, 2, QTableWidgetItem(f"{py}평"))
                self.stats_table.setItem(row, 3, SortableTableWidgetItem(str(min_p)))
                self.stats_table.setItem(row, 4, SortableTableWidgetItem(str(max_p)))
                self.stats_table.setItem(row, 5, SortableTableWidgetItem(str(avg_p)))
                
                # 같은 유형/평형만 차트에 표시 (첫 번째 데이터 기준)
                if not chart_data["date"] or (chart_data["type"] == typ and chart_data["py"] == py):
                     chart_data["type"] = typ
                     chart_data["py"] = py
                     chart_data["date"].append(date)
                     chart_data["avg"].append(avg_p)
                     chart_data["min"].append(min_p)
                     chart_data["max"].append(max_p)
        finally:
            self.stats_table.setUpdatesEnabled(True)
        
        # 차트 업데이트
        if chart_data["date"]:
            self._ensure_chart_widget()
            title = f"{self.stats_complex_combo.currentText()} - {chart_data.get('type','')} {chart_data.get('py',0)}평 가격 추이"
            self.chart_widget.update_chart(
                chart_data["date"], 
                chart_data["avg"], 
                chart_data["min"], 
                chart_data["max"],
                title
            )
    
    def _on_stats_complex_changed(self, index):
        """통계 탭 단지 변경 시 평형 콤보박스 업데이트"""
        cid = self.stats_complex_combo.currentData()
        if not cid: return
        
        snapshots = self.db.get_price_snapshots(cid)
        # 평형 목록 추출
        pyeongs = sorted(list(set(s[2] for s in snapshots)))
        
        self.stats_pyeong_combo.blockSignals(True)
        self.stats_pyeong_combo.clear()
        self.stats_pyeong_combo.addItem("전체")
        for p in pyeongs:
            self.stats_pyeong_combo.addItem(f"{p}평")
        self.stats_pyeong_combo.blockSignals(False)

    def _toggle_theme(self, theme=None):
        if theme in ("dark", "light"):
            new_theme = theme
        else:
            new_theme = "light" if self.current_theme == "dark" else "dark"
        self.current_theme = new_theme
        
        # 스타일시트 적용
        self.setStyleSheet(get_stylesheet(new_theme))
        
        # 개별 위젯 테마 업데이트
        if hasattr(self, "crawler_tab"):
            self.crawler_tab.set_theme(new_theme)
        if self.dashboard_widget is not None:
            self.dashboard_widget.set_theme(new_theme)
        if hasattr(self, 'favorites_tab'):
            self.favorites_tab.set_theme(new_theme)
        
        settings.set("theme", new_theme)
        self.show_toast(f"테마가 {new_theme} 모드로 변경되었습니다")
    
    def _show_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_settings()
    
    def _apply_settings(self):
        """설정 변경 후 적용"""
        # 테마 변경 체크
        new_theme = settings.get("theme", "dark")
        if new_theme != self.current_theme:
            self.current_theme = new_theme
            self.setStyleSheet(get_stylesheet(new_theme))
            
            # 개별 위젯 테마 업데이트 (안전하게)
            try:
                if hasattr(self, 'crawler_tab') and hasattr(self.crawler_tab, 'set_theme'):
                    self.crawler_tab.set_theme(new_theme)
            except Exception as e:
                ui_logger.debug(f"crawler_tab 테마 적용 실패 (무시): {e}")
            
            try:
                if self.dashboard_widget is not None and hasattr(self.dashboard_widget, 'set_theme'):
                    self.dashboard_widget.set_theme(new_theme)
            except Exception as e:
                ui_logger.debug(f"dashboard_widget 테마 적용 실패 (무시): {e}")
            
            try:
                if hasattr(self, 'favorites_tab') and hasattr(self.favorites_tab, 'set_theme'):
                    self.favorites_tab.set_theme(new_theme)
            except Exception as e:
                ui_logger.debug(f"favorites_tab 테마 적용 실패 (무시): {e}")
            
            # 메뉴 체크 상태 업데이트
            if hasattr(self, 'action_theme_dark'):
                self.action_theme_dark.setChecked(new_theme == "dark")
            if hasattr(self, 'action_theme_light'):
                self.action_theme_light.setChecked(new_theme == "light")
            
            self.show_toast(f"테마가 {new_theme} 모드로 변경되었습니다")
            
            # 위젯 테마 업데이트
            if hasattr(self, 'crawler_tab'):
                # CrawlerTab doesn't have explicit set_theme yet but standard widgets style updates automatically
                # If specialized manual update is needed, invoke here
                pass

        
        # 속도값 갱신은 슬라이더에서 처리됨
        # 알림 설정 등은 즉시 반영됨
        if self.retry_handler:
            self.retry_handler.max_retries = settings.get("max_retry_count", 3)
    
    def _save_preset(self):
        name, ok = QInputDialog.getText(self, "필터 저장", "프리셋 이름:")
        if ok and name:
            ct = self.crawler_tab
            config = {
                "trade": ct.check_trade.isChecked(),
                "jeonse": ct.check_jeonse.isChecked(),
                "monthly": ct.check_monthly.isChecked(),
                "area": {"enabled": ct.check_area_filter.isChecked(), "min": ct.spin_area_min.value(), "max": ct.spin_area_max.value()},
                "price": {
                    "enabled": ct.check_price_filter.isChecked(),
                    "trade_min": ct.spin_trade_min.value(), "trade_max": ct.spin_trade_max.value(),
                    "jeonse_min": ct.spin_jeonse_min.value(), "jeonse_max": ct.spin_jeonse_max.value(),
                    "monthly_min": ct.spin_monthly_min.value(), "monthly_max": ct.spin_monthly_max.value()
                }
            }
            if self.preset_manager.save_preset(name, config):
                self.show_toast(f"프리셋 '{name}' 저장 완료")
    
    def _load_preset(self):
        dialog = PresetDialog(self, self.preset_manager)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_preset:
            preset_name = dialog.selected_preset
            config = self.preset_manager.get(preset_name)
            if not config:
                self.show_toast(f"프리셋 '{preset_name}' 불러오기 실패")
                return
            ct = self.crawler_tab
            ct.check_trade.setChecked(config.get("trade", True))
            ct.check_jeonse.setChecked(config.get("jeonse", True))
            ct.check_monthly.setChecked(config.get("monthly", False))
            
            area = config.get("area", {})
            ct.check_area_filter.setChecked(area.get("enabled", False))
            ct.spin_area_min.setValue(area.get("min", 0))
            ct.spin_area_max.setValue(area.get("max", 200))
            
            p = config.get("price", {})
            ct.check_price_filter.setChecked(p.get("enabled", False))
            ct.spin_trade_min.setValue(p.get("trade_min", 0))
            ct.spin_trade_max.setValue(p.get("trade_max", 100000))
            ct.spin_jeonse_min.setValue(p.get("jeonse_min", 0))
            ct.spin_jeonse_max.setValue(p.get("jeonse_max", 50000))
            ct.spin_monthly_min.setValue(p.get("monthly_min", 0))
            ct.spin_monthly_max.setValue(p.get("monthly_max", 5000))
            self.show_toast("프리셋을 불러왔습니다")
    
    def _show_alert_settings(self):
        AlertSettingDialog(self, self.db).exec()
    
    def _show_shortcuts(self):
        ShortcutsDialog(self).exec()
    
    def _show_about(self):
        AboutDialog(self).exec()
    
    def _show_advanced_filter(self):
        # Legacy path retained for backward compatibility.
        # Advanced filtering is owned by CrawlerTab in the modular UI.
        ui_logger.warning("Deprecated app-level advanced filter entry invoked; ignoring.")
        self.status_bar.showMessage("고급 필터는 수집기 탭(CrawlerTab)에서만 지원됩니다.")

    def _apply_advanced_filter(self):
        self._show_advanced_filter()

    def _filter_results_advanced(self):
        ui_logger.warning("Deprecated app-level _filter_results_advanced invoked; ignoring.")
        self.status_bar.showMessage("고급 필터는 수집기 탭(CrawlerTab)에서만 지원됩니다.")

    def _render_results(self, data, render_only=True):
        ui_logger.warning("Deprecated app-level _render_results invoked; ignoring.")

    def _restore_summary(self):
        ui_logger.warning("Deprecated app-level _restore_summary invoked; ignoring.")

    def _is_default_advanced_filter(self, filters: dict) -> bool:
        defaults = {
            "price_min": 0,
            "price_max": 9999999,
            "area_min": 0,
            "area_max": 500,
            "floor_low": True,
            "floor_mid": True,
            "floor_high": True,
            "only_new": False,
            "only_price_down": False,
            "only_price_change": False,
        }
        for key, val in defaults.items():
            if filters.get(key) != val:
                return False
        if filters.get("include_keywords"):
            return False
        if filters.get("exclude_keywords"):
            return False
        return True

    def _refresh_favorite_keys(self):
        try:
            favorites = self.db.get_favorites()
            keys = set()
            for fav in favorites:
                aid = fav.get("article_id")
                cid = fav.get("complex_id")
                if aid and cid:
                    keys.add((aid, cid))
            self.favorite_keys = keys
        except Exception as e:
            ui_logger.debug(f"즐겨찾기 키 로드 실패 (무시): {e}")
            self.favorite_keys = set()

    def _on_favorite_toggled(self, article_id, complex_id, is_fav):
        if not article_id or not complex_id:
            return
        try:
            self.db.toggle_favorite(article_id, complex_id, is_fav)
        finally:
            key = (article_id, complex_id)
            if is_fav:
                self.favorite_keys.add(key)
            else:
                self.favorite_keys.discard(key)
            if hasattr(self, 'favorites_tab'):
                self.favorites_tab.refresh()
    
    def _check_advanced_filter(self, d):
        """단일 데이터에 대한 고급 필터 체크"""
        if not self.advanced_filters: return True
        
        f = self.advanced_filters

        # 가격 필터
        price_int = d.get("price_int")
        if price_int is None:
            price_text = d.get("매매가") or d.get("보증금") or ""
            price_int = PriceConverter.to_int(price_text)
        if price_int < f.get("price_min", 0) or price_int > f.get("price_max", 9999999):
            return False

        # 면적 필터 (평)
        area = d.get("면적(평)", 0) or 0
        if area < f.get("area_min", 0) or area > f.get("area_max", 9999999):
            return False

        # 층수 필터
        floor_text = d.get("층/방향", "")
        floor_category = None
        if "저층" in floor_text:
            floor_category = "low"
        elif "중층" in floor_text:
            floor_category = "mid"
        elif "고층" in floor_text or "탑" in floor_text:
            floor_category = "high"
        else:
            m = re.search(r'(\d+)\s*층', floor_text)
            if m:
                try:
                    floor_num = int(m.group(1))
                    if floor_num <= 3:
                        floor_category = "low"
                    elif floor_num <= 10:
                        floor_category = "mid"
                    else:
                        floor_category = "high"
                except ValueError:
                    floor_category = None

        if floor_category == "low" and not f.get("floor_low", True):
            return False
        if floor_category == "mid" and not f.get("floor_mid", True):
            return False
        if floor_category == "high" and not f.get("floor_high", True):
            return False

        # 신규/가격 변동 필터
        if f.get("only_new") and not d.get("is_new", False):
            return False

        price_change = d.get("price_change", 0)
        if isinstance(price_change, str):
            try:
                price_change = PriceConverter.to_int(price_change)
            except Exception:
                price_change = 0

        if f.get("only_price_down") and price_change >= 0:
            return False
        if f.get("only_price_change") and price_change == 0:
            return False

        # 키워드 필터
        text_blob = " ".join([
            str(d.get("단지명", "")),
            str(d.get("타입/특징", "")),
            str(d.get("층/방향", "")),
        ]).lower()

        include_keywords = [k.lower() for k in f.get("include_keywords", [])]
        exclude_keywords = [k.lower() for k in f.get("exclude_keywords", [])]

        if include_keywords and not any(k in text_blob for k in include_keywords):
            return False
        if exclude_keywords and any(k in text_blob for k in exclude_keywords):
            return False

        return True

    def _show_url_batch_dialog(self):
        # Legacy compatibility: delegate to active CrawlerTab.
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab._show_url_batch_dialog()
            return
        ui_logger.warning("CrawlerTab unavailable for URL batch dialog.")
    
    def _add_complexes_from_url(self, urls):
        if hasattr(self, "crawler_tab"):
            self.crawler_tab._add_complexes_from_url(urls)
            return
        ui_logger.warning("CrawlerTab unavailable for _add_complexes_from_url.")

    def _add_complexes_from_dialog(self, complexes):
        if hasattr(self, "crawler_tab"):
            for name, cid in complexes:
                self.crawler_tab.add_task(name, cid)
            if complexes:
                self.show_toast(f"{len(complexes)}개 단지 추가 완료")
            return
        ui_logger.warning("CrawlerTab unavailable for _add_complexes_from_dialog.")

    def _show_excel_template_dialog(self):
        current_template = settings.get("excel_template")
        dlg = ExcelTemplateDialog(self, current_template=current_template)
        dlg.template_saved.connect(self._save_excel_template)
        dlg.exec()

    def _save_excel_template(self, template):
        settings.set("excel_template", template)
        self.show_toast("엑셀 템플릿이 저장되었습니다")

    def _backup_db(self):
        path, _ = QFileDialog.getSaveFileName(self, "DB 백업", f"backup_{DateTimeHelper.file_timestamp()}.db", "Database (*.db)")
        if path:
            if self.db.backup_database(Path(path)):
                QMessageBox.information(self, "백업 완료", f"DB 백업 완료!\n{path}")
            else:
                QMessageBox.critical(self, "실패", "DB 백업에 실패했습니다.")

    def _restore_db(self):
        """DB 복원 - 안전한 UI 처리"""
        path, _ = QFileDialog.getOpenFileName(self, "DB 복원", "", "Database (*.db)")
        if not path:
            return
        
        # 확인 대화상자
        reply = QMessageBox.question(
            self, "DB 복원 확인",
            f"현재 DB를 선택한 파일로 교체합니다.\n\n"
            f"복원 파일: {path}\n\n"
            f"계속하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 진행 중 표시
        self.status_bar.showMessage("🔄 DB 복원 중...")
        QApplication.processEvents()
        
        try:
            ui_logger.info(f"DB 복원 시작: {path}")
            
            if self.db.restore_database(Path(path)):
                # 성공 시 모든 데이터 다시 로드
                ui_logger.info("DB 복원 성공, 데이터 다시 로드 중...")
                self._load_initial_data()
                self.status_bar.showMessage("✅ DB 복원 완료!")
                QMessageBox.information(self, "복원 완료", "DB 복원이 완료되었습니다!")
                ui_logger.info("DB 복원 완료")
            else:
                self.status_bar.showMessage("❌ DB 복원 실패")
                QMessageBox.critical(self, "복원 실패", "DB 복원에 실패했습니다.\n콘솔 로그를 확인하세요.")
                ui_logger.error("DB 복원 실패")
                
        except Exception as e:
            ui_logger.error(f"DB 복원 중 예외: {e}")
            import traceback
            traceback.print_exc()
            self.status_bar.showMessage("❌ DB 복원 중 오류 발생")
            QMessageBox.critical(self, "오류", f"DB 복원 중 오류가 발생했습니다:\n{e}")

    def _refresh_tab(self):
        current = self.tabs.currentWidget()
        if current is self.db_tab:
            self.db_tab.load_data()
        elif current is self.group_tab:
            self.group_tab.load_groups()
        elif current is self.history_tab:
            self._noncritical_loaded["history"] = True
            self._load_history()
        elif current is self.stats_tab:
            if not self._noncritical_loaded["stats"]:
                self._load_stats_complexes()
                self._noncritical_loaded["stats"] = True
            self._load_stats()
        elif current is self.dashboard_tab:
            self._ensure_dashboard_widget()
            self.dashboard_widget.refresh()
        elif current is self.favorites_tab:
            if not self._noncritical_loaded["favorites"]:
                self._refresh_favorite_keys()
                self._noncritical_loaded["favorites"] = True
            self.favorites_tab.refresh()


    def _focus_search(self):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            if hasattr(self.crawler_tab, "result_search"):
                self.crawler_tab.result_search.setFocus()

    def _minimize_to_tray(self):
        if not self.tray_icon:
            self.status_bar.showMessage("시스템 트레이를 사용할 수 없습니다.")
            return
        self.hide()
        self.tray_icon.showMessage("알림", "트레이로 최소화되었습니다.", QSystemTrayIcon.MessageIcon.Information, 2000)

    def _show_from_tray(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()

    def _shutdown(self):
        if self._is_shutting_down:
            return
        self._is_shutting_down = True
        if hasattr(self, 'crawler_tab'):
            self.crawler_tab.stop_crawling()
        if hasattr(self, 'schedule_timer') and self.schedule_timer:
            self.schedule_timer.stop()
        settings.set("window_geometry", [self.x(), self.y(), self.width(), self.height()])
        try:
            self.db.close()
        except Exception as e:
            ui_logger.debug(f"DB 종료 중 오류 (무시): {e}")
        if self.tray_icon:
            self.tray_icon.hide()

    def _quit_app(self, skip_confirm=False):
        if not skip_confirm and settings.get("confirm_before_close"):
            if QMessageBox.question(self, "종료", "정말 종료하시겠습니까?") != QMessageBox.StandardButton.Yes:
                return
        self._shutdown()
        QApplication.quit()

    def closeEvent(self, event):
        if self._is_shutting_down:
            event.accept()
            return

        if settings.get("minimize_to_tray", True) and self.tray_icon:
            event.ignore()
            self._minimize_to_tray()
            return

        if settings.get("confirm_before_close"):
            reply = QMessageBox.question(
                self,
                "종료",
                "정말 종료하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

        self._shutdown()
        event.accept()

    def show_toast(self, message, duration=3000):
        # 화면 우측 하단에 표시
        toast = ToastWidget(message, self)
        
        # 위치 계산 (쌓이도록)
        margin = 20
        y = self.height() - margin - toast.height()
        for t in self.toast_widgets:
            y -= (t.height() + 10)
        
        x = self.width() - margin - toast.width()
        toast.move(x, y)
        toast.show_toast(duration)
        
        self.toast_widgets.append(toast)
        # 종료 시 리스트에서 제거
        QTimer.singleShot(duration + 500, lambda: self.toast_widgets.remove(toast) if toast in self.toast_widgets else None)
        QTimer.singleShot(duration + 500, self._reposition_toasts)

    def _reposition_toasts(self):
        # 유효하지 않은 위젯 제거
        try:
            import sip
            self.toast_widgets = [t for t in self.toast_widgets if not sip.isdeleted(t)]
        except ImportError:
            # sip을 임포트할 수 없는 경우 (PySide6 등) 예외 처리
            pass
        except Exception:
            pass

        margin = 20
        y = self.height() - margin
        
        # 위치 재조정
        for t in reversed(self.toast_widgets):
            try:
                y -= t.height()
                t.move(self.width() - margin - t.width(), y)
                y -= 10
            except RuntimeError:
                continue







    def _toggle_view_mode(self):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab._toggle_view_mode()
            return
        ui_logger.warning("CrawlerTab unavailable for _toggle_view_mode.")
        
    def show_notification(self, title: str, message: str):
        """시스템 트레이 알림 표시"""
        if settings.get("show_notifications", True) and NOTIFICATION_AVAILABLE:
            try:
                notification.notify(
                    title=title,
                    message=message,
                    app_name=APP_TITLE,
                    app_icon=None,  # 아이콘 경로 설정 가능
                    timeout=5
                )
            except Exception as e:
                ui_logger.warning(f"알림 표시 실패: {e}")

    def _show_recently_viewed_dialog(self):
        """최근 본 매물 다이얼로그 (v13.0)"""
        dlg = QDialog(self)
        dlg.setWindowTitle("🕐 최근 본 매물")
        dlg.resize(900, 600)
        
        layout = QVBoxLayout(dlg)
        
        # 안내 문구
        info = QLabel("최근에 확인한 매물 목록입니다 (최대 50개).")
        info.setStyleSheet("color: #888; margin-bottom: 10px;")
        layout.addWidget(info)
        
        # 목록 (CardView 재사용)
        recent_items = self.recently_viewed.get_recent()
        
        if not recent_items:
            empty_lbl = QLabel("최근 본 매물이 없습니다.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty_lbl)
        else:
            card_view = CardViewWidget(is_dark=(self.current_theme=="dark"))
            card_view.set_data(recent_items)
            card_view.article_clicked.connect(lambda d: webbrowser.open(get_article_url(d.get("단지ID"), d.get("매물ID"))))
            card_view.favorite_toggled.connect(self._on_favorite_toggled)
            layout.addWidget(card_view)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)
        
        dlg.exec()
