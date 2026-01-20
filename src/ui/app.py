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
from src.utils.helpers import PriceConverter, DateTimeHelper, get_complex_url, get_article_url
from src.core.database import ComplexDatabase
from src.core.crawler import CrawlerThread
from src.core.export import DataExporter
from src.core.managers import SettingsManager, FilterPresetManager, SearchHistoryManager, RecentlyViewedManager
from src.core.cache import CrawlCache
from src.utils.retry_handler import RetryHandler
from src.ui.styles import get_stylesheet
from src.ui.widgets.components import (
    SearchBar, SpeedSlider, LinkButton, ProgressWidget, ColoredTableWidgetItem, SummaryCard, SortableTableWidgetItem
)
from src.ui.widgets.dashboard import DashboardWidget, CardViewWidget
from src.ui.widgets.tabs import FavoritesTab
from src.ui.widgets.chart import ChartWidget
from src.ui.widgets.toast import ToastWidget
from src.ui.widgets.dialogs import (
    PresetDialog, AlertSettingDialog, AdvancedFilterDialog, URLBatchDialog,
    ExcelTemplateDialog, SettingsDialog, ShortcutsDialog, AboutDialog,
    RecentSearchDialog, MultiSelectDialog
)

settings = SettingsManager()

class RealEstateApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1400, 900)
        geo = settings.get("window_geometry")
        if geo: self.setGeometry(*geo)
        else: self.setGeometry(100, 100, 1500, 950)
        
        self.db = ComplexDatabase()
        self.preset_manager = FilterPresetManager()
        self.history_manager = SearchHistoryManager()
        self.crawler_thread = None
        self.collected_data = []
        self.grouped_rows = {}
        self.is_scheduled_run = False
        self.current_theme = settings.get("theme", "dark")
        self.tray_icon = None
        self.crawl_stats = {"매매": 0, "전세": 0, "월세": 0, "new": 0, "price_up": 0, "price_down": 0}
        self.advanced_filters = None  # v7.3: 고급 필터
        
        # v11.0: Toast 알림 시스템
        self.toast_widgets: List[ToastWidget] = []
        
        # v12.0: 크롤링 캐시
        self.crawl_cache = CrawlCache(ttl_minutes=settings.get("cache_ttl_minutes", 30))
        
        # v13.0: 신규 기능
        self.recently_viewed = RecentlyViewedManager()
        self.view_mode = settings.get("view_mode", "table")  # table | card
        self.retry_handler = RetryHandler(
            max_retries=settings.get("max_retry_count", 3)
        ) if settings.get("retry_on_error", True) else None
        
        self.setStyleSheet(get_stylesheet(self.current_theme))
        self._init_ui()
        self._init_menu()
        self._init_shortcuts()
        self._init_tray()
        self._init_timers()
        self._load_initial_data()
        self.status_bar.showMessage(f"✨ {APP_TITLE} 준비 완료")
    
    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self._setup_crawler_tab()
        self._setup_db_tab()
        self._setup_groups_tab()
        self._setup_schedule_tab()
        self._setup_history_tab()
        self._setup_stats_tab()
        self._setup_dashboard_tab()  # v13.0
        self._setup_favorites_tab()  # v13.0
        self._setup_guide_tab()
        self.status_bar = self.statusBar()
    
    def _setup_crawler_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - v11.0: 동적 크기 조정
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMinimumWidth(380)  # 최소 너비 감소
        scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        scroll_content = QWidget()
        left = QVBoxLayout(scroll_content)
        left.setSpacing(10)
        
        # 1. 거래유형
        tg = QGroupBox("1️⃣ 거래 유형")
        tl = QHBoxLayout()
        self.check_trade = QCheckBox("매매")
        self.check_trade.setChecked(True)
        self.check_trade.setToolTip("아파트 매매 매물을 검색합니다")
        self.check_jeonse = QCheckBox("전세")
        self.check_jeonse.setChecked(True)
        self.check_jeonse.setToolTip("전세 매물을 검색합니다")
        self.check_monthly = QCheckBox("월세")
        self.check_monthly.setToolTip("월세 매물을 검색합니다")
        tl.addWidget(self.check_trade)
        tl.addWidget(self.check_jeonse)
        tl.addWidget(self.check_monthly)
        tl.addStretch()
        tg.setLayout(tl)
        left.addWidget(tg)
        
        # 2. 면적 필터
        ag = QGroupBox("2️⃣ 면적 필터")
        al = QVBoxLayout()
        self.check_area_filter = QCheckBox("면적 필터 사용")
        self.check_area_filter.stateChanged.connect(self._toggle_area_filter)
        al.addWidget(self.check_area_filter)
        area_input = QHBoxLayout()
        self.spin_area_min = QSpinBox()
        self.spin_area_min.setRange(0, 300)
        self.spin_area_min.setEnabled(False)
        self.spin_area_min.setToolTip("최소 면적 (㎡)")
        self.spin_area_max = QSpinBox()
        self.spin_area_max.setRange(0, 300)
        self.spin_area_max.setValue(200)
        self.spin_area_max.setEnabled(False)
        self.spin_area_max.setToolTip("최대 면적 (㎡)")
        area_input.addWidget(QLabel("최소:"))
        area_input.addWidget(self.spin_area_min)
        area_input.addWidget(QLabel("㎡  ~  최대:"))
        area_input.addWidget(self.spin_area_max)
        area_input.addWidget(QLabel("㎡"))
        al.addLayout(area_input)
        ag.setLayout(al)
        left.addWidget(ag)
        
        # 3. 가격 필터
        pg = QGroupBox("3️⃣ 가격 필터")
        pl = QVBoxLayout()
        self.check_price_filter = QCheckBox("가격 필터 사용")
        self.check_price_filter.stateChanged.connect(self._toggle_price_filter)
        pl.addWidget(self.check_price_filter)
        
        price_grid = QGridLayout()
        # 매매
        price_grid.addWidget(QLabel("매매:"), 0, 0)
        self.spin_trade_min = QSpinBox()
        self.spin_trade_min.setRange(0, 999999)
        self.spin_trade_min.setSingleStep(1000)
        self.spin_trade_min.setEnabled(False)
        self.spin_trade_min.setToolTip("매매 최소 가격 (만원)")
        price_grid.addWidget(self.spin_trade_min, 0, 1)
        price_grid.addWidget(QLabel("~"), 0, 2)
        self.spin_trade_max = QSpinBox()
        self.spin_trade_max.setRange(0, 999999)
        self.spin_trade_max.setValue(100000)
        self.spin_trade_max.setSingleStep(1000)
        self.spin_trade_max.setEnabled(False)
        self.spin_trade_max.setToolTip("매매 최대 가격 (만원)")
        price_grid.addWidget(self.spin_trade_max, 0, 3)
        price_grid.addWidget(QLabel("만원"), 0, 4)
        
        # 전세
        price_grid.addWidget(QLabel("전세:"), 1, 0)
        self.spin_jeonse_min = QSpinBox()
        self.spin_jeonse_min.setRange(0, 999999)
        self.spin_jeonse_min.setSingleStep(1000)
        self.spin_jeonse_min.setEnabled(False)
        price_grid.addWidget(self.spin_jeonse_min, 1, 1)
        price_grid.addWidget(QLabel("~"), 1, 2)
        self.spin_jeonse_max = QSpinBox()
        self.spin_jeonse_max.setRange(0, 999999)
        self.spin_jeonse_max.setValue(50000)
        self.spin_jeonse_max.setSingleStep(1000)
        self.spin_jeonse_max.setEnabled(False)
        price_grid.addWidget(self.spin_jeonse_max, 1, 3)
        price_grid.addWidget(QLabel("만원"), 1, 4)
        
        # 월세
        price_grid.addWidget(QLabel("월세:"), 2, 0)
        self.spin_monthly_min = QSpinBox()
        self.spin_monthly_min.setRange(0, 999999)
        self.spin_monthly_min.setSingleStep(100)
        self.spin_monthly_min.setEnabled(False)
        price_grid.addWidget(self.spin_monthly_min, 2, 1)
        price_grid.addWidget(QLabel("~"), 2, 2)
        self.spin_monthly_max = QSpinBox()
        self.spin_monthly_max.setRange(0, 999999)
        self.spin_monthly_max.setValue(5000)
        self.spin_monthly_max.setSingleStep(100)
        self.spin_monthly_max.setEnabled(False)
        price_grid.addWidget(self.spin_monthly_max, 2, 3)
        price_grid.addWidget(QLabel("만원"), 2, 4)
        
        pl.addLayout(price_grid)
        pg.setLayout(pl)
        left.addWidget(pg)
        
        # 4. 단지 목록
        cg = QGroupBox("4️⃣ 단지 목록")
        cl = QVBoxLayout()
        load_btn = QHBoxLayout()
        btn_db = QPushButton("💾 DB에서")
        btn_db.setToolTip("저장된 단지 DB에서 불러오기")
        btn_db.clicked.connect(self._show_db_load_dialog)
        btn_grp = QPushButton("📁 그룹에서")
        btn_grp.setToolTip("저장된 그룹에서 불러오기")
        btn_grp.clicked.connect(self._show_group_load_dialog)
        btn_history = QPushButton("🕐 최근검색")
        btn_history.setToolTip("최근 검색 기록에서 불러오기")
        btn_history.clicked.connect(self._show_history_dialog)
        load_btn.addWidget(btn_db)
        load_btn.addWidget(btn_grp)
        load_btn.addWidget(btn_history)
        cl.addLayout(load_btn)
        
        input_layout = QHBoxLayout()
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("단지명")
        self.input_name.setToolTip("아파트 단지명을 입력하세요")
        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("단지 ID")
        self.input_id.setToolTip("네이버 부동산 URL에서 단지 ID를 확인할 수 있습니다")
        btn_add = QPushButton("➕")
        btn_add.setMaximumWidth(45)
        btn_add.setToolTip("단지 추가")
        btn_add.clicked.connect(self._add_complex)
        input_layout.addWidget(self.input_name, 2)
        input_layout.addWidget(self.input_id, 1)
        input_layout.addWidget(btn_add)
        cl.addLayout(input_layout)
        
        self.table_list = QTableWidget()
        self.table_list.setColumnCount(2)
        self.table_list.setHorizontalHeaderLabels(["단지명", "ID"])
        self.table_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_list.setMinimumHeight(130)
        self.table_list.setAlternatingRowColors(True)
        self.table_list.setToolTip("더블클릭하면 네이버 부동산 페이지를 엽니다")
        self.table_list.doubleClicked.connect(self._open_complex_url)
        cl.addWidget(self.table_list)
        
        manage_btn = QHBoxLayout()
        btn_del = QPushButton("🗑️ 삭제")
        btn_del.clicked.connect(self._delete_complex)
        btn_clr = QPushButton("🧹 초기화")
        btn_clr.clicked.connect(self._clear_list)
        btn_sv = QPushButton("💾 DB저장")
        btn_sv.clicked.connect(self._save_to_db)
        # v7.3: URL 일괄 등록
        btn_url = QPushButton("🔗 URL등록")
        btn_url.setToolTip("URL 또는 단지ID 일괄 등록")
        btn_url.clicked.connect(self._show_url_batch_dialog)
        manage_btn.addWidget(btn_del)
        manage_btn.addWidget(btn_clr)
        manage_btn.addWidget(btn_sv)
        manage_btn.addWidget(btn_url)
        cl.addLayout(manage_btn)
        cg.setLayout(cl)
        left.addWidget(cg)
        
        # 5. 속도
        spg = QGroupBox("5️⃣ 크롤링 속도")
        spl = QVBoxLayout()
        self.speed_slider = SpeedSlider()
        self.speed_slider.set_speed(settings.get("crawl_speed", "보통"))
        spl.addWidget(self.speed_slider)
        spg.setLayout(spl)
        left.addWidget(spg)
        
        # 6. 실행
        eg = QGroupBox("6️⃣ 실행")
        el = QHBoxLayout()
        self.btn_start = QPushButton("▶️ 크롤링 시작")
        self.btn_start.setObjectName("startButton")
        self.btn_start.setMinimumHeight(45)
        self.btn_start.setToolTip(f"크롤링 시작 ({SHORTCUTS['start_crawl']})")
        self.btn_start.clicked.connect(self._start_crawling)
        self.btn_stop = QPushButton("⏹️ 중지")
        self.btn_stop.setObjectName("stopButton")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setToolTip(f"크롤링 중지 ({SHORTCUTS['stop_crawl']})")
        self.btn_stop.clicked.connect(self._stop_crawling)
        self.btn_save = QPushButton("💾 저장")
        self.btn_save.setObjectName("saveButton")
        self.btn_save.setEnabled(False)
        self.btn_save.setToolTip("결과 저장 (Excel, CSV, JSON)")
        self.btn_save.clicked.connect(self._show_save_menu)
        el.addWidget(self.btn_start, 2)
        el.addWidget(self.btn_stop, 1)
        el.addWidget(self.btn_save, 1)
        eg.setLayout(el)
        left.addWidget(eg)
        
        left.addStretch()
        scroll.setWidget(scroll_content)
        splitter.addWidget(scroll)
        
        # Right panel
        right_w = QWidget()
        right = QVBoxLayout(right_w)
        right.setSpacing(8)
        
        # 요약 카드
        self.summary_card = SummaryCard(theme=self.current_theme)
        right.addWidget(self.summary_card)
        
        # 검색 및 정렬
        search_sort = QHBoxLayout()
        self.result_search = SearchBar("결과 검색...")
        self.result_search.search_changed.connect(self._filter_results)
        search_sort.addWidget(self.result_search, 3)
        
        # v7.3: 고급 필터 버튼
        btn_adv_filter = QPushButton("🔍 고급 필터")
        btn_adv_filter.setToolTip("가격, 면적, 층수 등 상세 필터")
        btn_adv_filter.clicked.connect(self._show_advanced_filter)
        search_sort.addWidget(btn_adv_filter)
        
        search_sort.addWidget(QLabel("정렬:"))
        self.combo_sort = QComboBox()
        self.combo_sort.addItems(["가격 ↑", "가격 ↓", "면적 ↑", "면적 ↓", "단지명 ↑", "단지명 ↓"])
        self.combo_sort.setToolTip("결과 정렬 기준")
        self.combo_sort.currentTextChanged.connect(self._sort_results)
        search_sort.addWidget(self.combo_sort, 1)
        
        # v13.0: 뷰 모드 전환 버튼
        self.btn_view_mode = QPushButton("🃏 카드뷰" if self.view_mode != "card" else "📄 테이블")
        self.btn_view_mode.setCheckable(True)
        self.btn_view_mode.setChecked(self.view_mode == "card")
        self.btn_view_mode.clicked.connect(self._toggle_view_mode)
        search_sort.addWidget(self.btn_view_mode)
        
        right.addLayout(search_sort)
        
        # 결과 탭
        result_tabs = QTabWidget()
        result_tab = QWidget()
        rl = QVBoxLayout(result_tab)
        rl.setContentsMargins(0, 5, 0, 0)
        
        # v12.0: 확장된 컬럼 (평당가, 신규, 변동 추가)
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(13)
        self.result_table.setHorizontalHeaderLabels([
            "단지명", "거래", "가격", "면적", "평당가", "층/방향", "특징", 
            "🆕", "📊 변동", "시각", "링크", "URL", "가격(숫자)"
        ])
        self.result_table.setColumnHidden(11, True)
        self.result_table.setColumnHidden(12, True)
        
        header = self.result_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        
        # DPI 스케일 적용된 컬럼 너비 설정
        dpi_scale = QApplication.primaryScreen().logicalDotsPerInch() / 96.0 if QApplication.primaryScreen() else 1.0
        
        col_widths = [150, 50, 80, 60, 90, 100, 150, 40, 80, 70, 80]
        for col, width in enumerate(col_widths):
            self.result_table.setColumnWidth(col, int(width * dpi_scale))
        
        self.result_table.setSortingEnabled(True)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.setToolTip("더블클릭하면 해당 매물 페이지를 엽니다")
        self.result_table.doubleClicked.connect(self._open_article_url)
        
        # v13.0: 카드 뷰 추가
        self.view_stack = QStackedWidget()
        self.view_stack.addWidget(self.result_table)
        
        self.card_view = CardViewWidget(is_dark=(self.current_theme=="dark"))
        self.card_view.article_clicked.connect(lambda d: webbrowser.open(get_article_url(d.get("단지ID"), d.get("매물ID"))))
        self.card_view.favorite_toggled.connect(self.db.toggle_favorite) # DB 연결
        self.view_stack.addWidget(self.card_view)
        
        # 초기 뷰 설정
        if self.view_mode == "card":
             self.view_stack.setCurrentWidget(self.card_view)
        
        rl.addWidget(self.view_stack)
        result_tabs.addTab(result_tab, "📊 결과")
        
        log_tab = QWidget()
        ll = QVBoxLayout(log_tab)
        ll.setContentsMargins(0, 5, 0, 0)
        self.log_browser = QTextBrowser()
        self.log_browser.setMinimumHeight(150)
        ll.addWidget(self.log_browser)
        result_tabs.addTab(log_tab, "📝 로그")
        right.addWidget(result_tabs)
        
        # 진행 상태
        self.progress_widget = ProgressWidget()
        right.addWidget(self.progress_widget)
        
        splitter.addWidget(right_w)
        splitter.setSizes([450, 900])
        layout.addWidget(splitter)
        self.tabs.addTab(tab, "🏘️ 데이터 수집")
    
    def _setup_db_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        bl = QHBoxLayout()
        btn_rf = QPushButton("🔄 새로고침")
        btn_rf.clicked.connect(self._load_db_complexes)
        btn_dl = QPushButton("🗑️ 선택 삭제")
        btn_dl.clicked.connect(self._delete_db_complex)
        btn_dlm = QPushButton("🗑️ 다중 삭제")
        btn_dlm.clicked.connect(self._delete_db_complexes_multi)
        btn_memo = QPushButton("✏️ 메모 수정")
        btn_memo.clicked.connect(self._edit_memo)
        bl.addWidget(btn_rf)
        bl.addWidget(btn_dl)
        bl.addWidget(btn_dlm)
        bl.addWidget(btn_memo)
        bl.addStretch()
        layout.addLayout(bl)
        self.db_search = SearchBar("단지 검색...")
        self.db_search.search_changed.connect(self._filter_db_table)
        layout.addWidget(self.db_search)
        self.db_table = QTableWidget()
        self.db_table.setColumnCount(4)
        self.db_table.setHorizontalHeaderLabels(["ID", "단지명", "단지ID", "메모"])
        self.db_table.setColumnHidden(0, True)
        self.db_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.db_table.setAlternatingRowColors(True)
        self.db_table.doubleClicked.connect(self._open_db_complex_url)
        layout.addWidget(self.db_table)
        self.tabs.addTab(tab, "💾 단지 DB")
    
    def _setup_groups_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 그룹 목록
        left_w = QWidget()
        left_l = QVBoxLayout(left_w)
        left_l.addWidget(QLabel("📁 그룹 목록"))
        gl = QHBoxLayout()
        btn_new = QPushButton("➕ 새 그룹")
        btn_new.clicked.connect(self._create_group)
        btn_del = QPushButton("🗑️ 삭제")
        btn_del.clicked.connect(self._delete_group)
        gl.addWidget(btn_new)
        gl.addWidget(btn_del)
        left_l.addLayout(gl)
        self.group_list = QListWidget()
        self.group_list.setAlternatingRowColors(True)
        self.group_list.itemClicked.connect(self._load_group_complexes)
        left_l.addWidget(self.group_list)
        splitter.addWidget(left_w)
        
        # 그룹 내 단지
        right_w = QWidget()
        right_l = QVBoxLayout(right_w)
        right_l.addWidget(QLabel("📋 그룹 내 단지"))
        rl = QHBoxLayout()
        btn_add = QPushButton("➕ 단지 추가")
        btn_add.clicked.connect(self._add_to_group)
        btn_add_multi = QPushButton("➕ 다중 추가")
        btn_add_multi.clicked.connect(self._add_to_group_multi)
        btn_rm = QPushButton("➖ 제거")
        btn_rm.clicked.connect(self._remove_from_group)
        rl.addWidget(btn_add)
        rl.addWidget(btn_add_multi)
        rl.addWidget(btn_rm)
        right_l.addLayout(rl)
        self.group_complex_table = QTableWidget()
        self.group_complex_table.setColumnCount(4)
        self.group_complex_table.setHorizontalHeaderLabels(["ID", "단지명", "단지ID", "메모"])
        self.group_complex_table.setColumnHidden(0, True)
        self.group_complex_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.group_complex_table.setAlternatingRowColors(True)
        right_l.addWidget(self.group_complex_table)
        splitter.addWidget(right_w)
        
        splitter.setSizes([300, 700])
        layout.addWidget(splitter)
        self.tabs.addTab(tab, "📁 그룹 관리")
    
    def _setup_schedule_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
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
        layout.addStretch()
        self.tabs.addTab(tab, "⏰ 예약 설정")
    
    def _setup_history_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
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
        self.tabs.addTab(tab, "📜 히스토리")
    
    def _setup_stats_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
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
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.stats_table)
        
        self.chart_widget = ChartWidget()
        splitter.addWidget(self.chart_widget)
        splitter.setSizes([300, 300])
        
        layout.addWidget(splitter)
        self.tabs.addTab(tab, "📈 통계/변동")
    
    def _setup_dashboard_tab(self):
        """v13.0: 분석 대시보드 탭"""
        self.dashboard_widget = DashboardWidget(self.db, theme=self.current_theme)
        self.tabs.addTab(self.dashboard_widget, "📊 대시보드")
    
    def _setup_favorites_tab(self):
        """v13.0: 즐겨찾기 탭"""
        self.favorites_tab = FavoritesTab(self.db, theme=self.current_theme)
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
        QShortcut(QKeySequence("Ctrl+R"), self, self._start_crawling)
        QShortcut(QKeySequence("Ctrl+Shift+R"), self, self._stop_crawling)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_excel)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, self._save_csv)
        QShortcut(QKeySequence("F5"), self, self._refresh_tab)
        QShortcut(QKeySequence("Ctrl+F"), self, self._focus_search)
        QShortcut(QKeySequence("Ctrl+T"), self, self._toggle_theme)
        QShortcut(QKeySequence("Ctrl+M"), self, self._minimize_to_tray)
        QShortcut(QKeySequence("Ctrl+Q"), self, self._quit_app)
    
    def _init_tray(self):
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
        self._load_db_complexes()
        self._load_all_groups()
        self._load_history()
        self._load_stats_complexes()
        self._load_schedule_groups()
        
        # Connect signals after loading
        self.stats_complex_combo.currentIndexChanged.connect(self._on_stats_complex_changed)
    
    # Event handlers
    def _toggle_area_filter(self, state):
        enabled = state == Qt.CheckState.Checked.value
        self.spin_area_min.setEnabled(enabled)
        self.spin_area_max.setEnabled(enabled)
    
    def _toggle_price_filter(self, state):
        enabled = state == Qt.CheckState.Checked.value
        for w in [self.spin_trade_min, self.spin_trade_max, self.spin_jeonse_min, 
                  self.spin_jeonse_max, self.spin_monthly_min, self.spin_monthly_max]:
            w.setEnabled(enabled)
    
    def _add_complex(self):
        name = self.input_name.text().strip()
        cid = self.input_id.text().strip()
        if name and cid:
            self._add_row(name, cid)
            self.input_name.clear()
            self.input_id.clear()
    
    def _add_row(self, name, cid):
        row = self.table_list.rowCount()
        self.table_list.insertRow(row)
        self.table_list.setItem(row, 0, QTableWidgetItem(name))
        self.table_list.setItem(row, 1, QTableWidgetItem(cid))
    
    def _delete_complex(self):
        row = self.table_list.currentRow()
        if row >= 0:
            self.table_list.removeRow(row)
    
    def _clear_list(self):
        self.table_list.setRowCount(0)
    
    def _save_to_db(self):
        """단지를 DB에 저장 - 디버깅 강화"""
        count = 0
        total = self.table_list.rowCount()
        print(f"[UI] DB 저장 시작: {total}개 단지")
        
        for r in range(total):
            name_item = self.table_list.item(r, 0)
            cid_item = self.table_list.item(r, 1)
            
            if not name_item or not cid_item:
                print(f"[UI WARN] 행 {r}: 데이터 없음")
                continue
            
            name = name_item.text().strip()
            cid = cid_item.text().strip()
            
            if not name or not cid:
                print(f"[UI WARN] 행 {r}: 빈 데이터")
                continue
            
            print(f"[UI] 저장 시도: {name} ({cid})")
            if self.db.add_complex(name, cid):
                count += 1
        
        print(f"[UI] DB 저장 완료: {count}/{total}개")
        QMessageBox.information(self, "저장 완료", f"{count}개 단지가 DB에 저장되었습니다.\n\nDB 경로: {self.db.db_path}")
        self._load_db_complexes()
        self._load_stats_complexes()  # 통계 탭도 갱신
    
    def _show_db_load_dialog(self):
        complexes = self.db.get_all_complexes()
        if not complexes:
            QMessageBox.information(self, "알림", "저장된 단지가 없습니다.")
            return
        items = [(f"{name} ({cid})", (name, cid)) for _, name, cid, _ in complexes]
        dlg = MultiSelectDialog("DB에서 불러오기", items, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            for name, cid in dlg.selected_items():
                self._add_row(name, cid)
    
    def _show_group_load_dialog(self):
        groups = self.db.get_all_groups()
        if not groups:
            QMessageBox.information(self, "알림", "저장된 그룹이 없습니다.")
            return
        items = [(name, gid) for gid, name, _ in groups]
        dlg = MultiSelectDialog("그룹에서 불러오기", items, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            for gid in dlg.selected_items():
                for _, name, cid, _ in self.db.get_complexes_in_group(gid):
                    self._add_row(name, cid)
    
    def _show_history_dialog(self):
        dlg = RecentSearchDialog(self, self.history_manager)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_search:
            search = dlg.selected_search
            self._clear_list()
            for name, cid in search.get('complexes', []):
                self._add_row(name, cid)
            # 거래유형 복원
            types = search.get('trade_types', [])
            self.check_trade.setChecked("매매" in types)
            self.check_jeonse.setChecked("전세" in types)
            self.check_monthly.setChecked("월세" in types)
    
    def _open_complex_url(self):
        row = self.table_list.currentRow()
        if row >= 0:
            cid = self.table_list.item(row, 1).text()
            webbrowser.open(get_complex_url(cid))
    
    def _open_db_complex_url(self):
        row = self.db_table.currentRow()
        if row >= 0:
            cid = self.db_table.item(row, 2).text()
            webbrowser.open(get_complex_url(cid))
    
    def _open_article_url(self):
        """결과 테이블에서 더블클릭 시 매물 URL 열기"""
        row = self.result_table.currentRow()
        if row >= 0:
            # v13.0: 최근 본 매물 저장
            item = self.result_table.item(row, 0)
            if item:
                data = item.data(Qt.ItemDataRole.UserRole)
                if data:
                    self.recently_viewed.add(data)

            # URL은 인덱스 11에 저장됨 (숨겨진 컬럼)
            url_item = self.result_table.item(row, 11)
            if url_item and url_item.text():
                webbrowser.open(url_item.text())
    
    def _filter_results(self, text):
        # 테이블 필터링
        for r in range(self.result_table.rowCount()):
            match = any(text.lower() in (self.result_table.item(r, c).text().lower() if self.result_table.item(r, c) else "") for c in range(7))
            self.result_table.setRowHidden(r, not match)
            
        # 카드 뷰 필터링
        if hasattr(self, 'card_view'):
            self.card_view.filter_cards(text)
    
    def _filter_db_table(self, text):
        for r in range(self.db_table.rowCount()):
            match = any(text.lower() in (self.db_table.item(r, c).text().lower() if self.db_table.item(r, c) else "") for c in range(4))
            self.db_table.setRowHidden(r, not match)
    
    def _sort_results(self, sort_text):
        col_map = {"가격": 2, "면적": 3, "단지명": 0}
        for key, col in col_map.items():
            if key in sort_text:
                order = Qt.SortOrder.AscendingOrder if "↑" in sort_text else Qt.SortOrder.DescendingOrder
                self.result_table.sortItems(col, order)
                break
    
    def _start_crawling(self):
        # 이전 크롤러 스레드가 실행 중이면 안전하게 종료
        if self.crawler_thread and self.crawler_thread.isRunning():
            get_logger('RealEstateApp').warning("이전 크롤러가 실행 중, 종료 대기...")
            self.crawler_thread.stop()
            self.crawler_thread.wait(3000)  # 최대 3초 대기
        
        tgs = [(self.table_list.item(r, 0).text(), self.table_list.item(r, 1).text()) for r in range(self.table_list.rowCount())]
        if not tgs:
            QMessageBox.warning(self, "알림", "단지를 추가해주세요.")
            return
        tts = []
        if self.check_trade.isChecked(): tts.append("매매")
        if self.check_jeonse.isChecked(): tts.append("전세")
        if self.check_monthly.isChecked(): tts.append("월세")
        if not tts:
            QMessageBox.warning(self, "알림", "거래유형을 선택해주세요.")
            return
        
        # 검색 기록 저장
        self.history_manager.add({
            'complexes': tgs,
            'trade_types': tts
        })
        
        af = {"enabled": self.check_area_filter.isChecked(), "min": self.spin_area_min.value(), "max": self.spin_area_max.value()}
        pf = {"enabled": self.check_price_filter.isChecked(), 
              "매매": {"min": self.spin_trade_min.value(), "max": self.spin_trade_max.value()}, 
              "전세": {"min": self.spin_jeonse_min.value(), "max": self.spin_jeonse_max.value()}, 
              "월세": {"min": self.spin_monthly_min.value(), "max": self.spin_monthly_max.value()}}
        
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_save.setEnabled(False)
        self.log_browser.clear()
        self.result_table.setRowCount(0)
        self.progress_widget.reset()
        self.summary_card.reset()
        self.grouped_rows.clear()
        self.collected_data.clear()
        self.crawl_stats = {"매매": 0, "전세": 0, "월세": 0, "new": 0, "price_up": 0, "price_down": 0}
        self.advanced_filters = None  # 필터 초기화
        
        self.crawler_thread = CrawlerThread(tgs, tts, af, pf, self.db, self.speed_slider.current_speed())
        self.crawler_thread.log_signal.connect(self._update_log)
        self.crawler_thread.progress_signal.connect(self._update_progress)
        self.crawler_thread.item_signal.connect(self._add_result)
        self.crawler_thread.stats_signal.connect(self._update_stats)
        self.crawler_thread.complex_finished_signal.connect(self._on_complex_done)
        self.crawler_thread.finished_signal.connect(self._crawling_done)
        self.crawler_thread.error_signal.connect(self._crawling_error)
        self.crawler_thread.start()
        self.status_bar.showMessage("🚀 크롤링 진행 중...")
    
    def _stop_crawling(self):
        if self.crawler_thread:
            self.crawler_thread.stop()
            self.log_browser.append("\n⏹️ 사용자에 의해 중지됨")
        self.btn_stop.setEnabled(False)
    
    def _update_log(self, msg, level=20):
        c = "#ff6b6b" if level >= 40 else "#f39c12" if level >= 30 else "#00ff00"
        self.log_browser.append(f"<span style='color: {c};'>{msg}</span>")
        self.log_browser.verticalScrollBar().setValue(self.log_browser.verticalScrollBar().maximum())
    
    def _update_progress(self, percent, current_name, remaining):
        self.progress_widget.update_progress(percent, current_name, remaining)
    
    def _add_result(self, d):
        tt = d["거래유형"]
        pv = d["매매가"] if tt == "매매" else d["보증금"] if tt == "전세" else f"{d['보증금']}/{d['월세']}"
        gk = (d["단지명"], tt, pv, d["면적(평)"])
        
        # 통계 업데이트
        self.crawl_stats[tt] = self.crawl_stats.get(tt, 0) + 1
        
        # v7.3: 신규/가격변동 체크
        is_new = False
        price_change = 0
        price_change_text = ""
        
        article_id = d.get("매물ID", "")
        complex_id = d.get("단지ID", "")
        
        # 가격을 숫자로 변환
        if tt == "매매":
            current_price = PriceConverter.to_int(d.get("매매가", "0"))
        else:
            current_price = PriceConverter.to_int(d.get("보증금", "0"))
        
        if article_id and complex_id:
            is_new, price_change, prev_price = self.db.check_article_history(
                article_id, complex_id, current_price
            )
            
            # 매물 히스토리 업데이트
            self.db.update_article_history(
                article_id, complex_id, d["단지명"], tt,
                current_price, pv, d["면적(평)"],
                d.get("층/방향", ""), d.get("타입/특징", "")
            )
            
            # 가격 변동 텍스트
            if price_change > 0:
                price_change_text = f"📈 +{PriceConverter.to_string(price_change)}"
                self.crawl_stats['price_up'] = self.crawl_stats.get('price_up', 0) + 1
            elif price_change < 0:
                price_change_text = f"📉 {PriceConverter.to_string(price_change)}"
                self.crawl_stats['price_down'] = self.crawl_stats.get('price_down', 0) + 1
            
            if is_new:
                self.crawl_stats['new'] = self.crawl_stats.get('new', 0) + 1
        
        # 데이터에 추가 정보 저장
        d['is_new'] = is_new
        d['price_change'] = price_change
        d['price_int'] = current_price
        
        if gk in self.grouped_rows:
            ri = self.grouped_rows[gk]
            cur = self.result_table.item(ri, 2).text()
            m = re.search(r'\((\d+)건\)', cur)
            cnt = int(m.group(1)) + 1 if m else 2
            self.result_table.setItem(ri, 2, SortableTableWidgetItem(f"{pv} ({cnt}건)"))
        else:
            row = self.result_table.rowCount()
            self.result_table.insertRow(row)
            self.result_table.setRowHeight(row, 32)  # 행 높이 고정
            self.grouped_rows[gk] = row
            
            is_dark = self.current_theme == "dark"
            
            # v13.0: 전체 데이터 저장 (UserRole)
            item_name = QTableWidgetItem(d["단지명"])
            item_name.setData(Qt.ItemDataRole.UserRole, d)
            self.result_table.setItem(row, 0, item_name)
            
            self.result_table.setItem(row, 1, ColoredTableWidgetItem(tt, tt, is_dark))
            self.result_table.setItem(row, 2, SortableTableWidgetItem(str(pv)))
            self.result_table.setItem(row, 3, SortableTableWidgetItem(f"{d['면적(평)']}평"))
            # v12.0: 평당가 컬럼 추가
            self.result_table.setItem(row, 4, SortableTableWidgetItem(d.get('평당가_표시', '-')))
            self.result_table.setItem(row, 5, QTableWidgetItem(d["층/방향"]))
            self.result_table.setItem(row, 6, QTableWidgetItem(d["타입/특징"]))
            
            # v7.3: 신규 배지
            new_item = QTableWidgetItem("🆕" if is_new else "")
            if is_new:
                new_item.setBackground(QColor("#f39c12") if is_dark else QColor("#ffeaa7"))
            self.result_table.setItem(row, 7, new_item)
            
            # v7.3: 가격 변동
            change_item = QTableWidgetItem(price_change_text)
            if price_change > 0:
                change_item.setForeground(QColor("#e74c3c"))
            elif price_change < 0:
                change_item.setForeground(QColor("#27ae60"))
            self.result_table.setItem(row, 8, change_item)
            
            # 시각
            self.result_table.setItem(row, 9, QTableWidgetItem(
                d["수집시각"].split()[1] if " " in d["수집시각"] else d["수집시각"]
            ))
            
            # 링크 버튼
            url = get_article_url(d["단지ID"], d.get("매물ID", "")) if d.get("매물ID") else get_complex_url(d["단지ID"])
            link_btn = LinkButton(url)
            self.result_table.setCellWidget(row, 10, link_btn)
            self.result_table.setItem(row, 11, QTableWidgetItem(url))
            
            # 가격 숫자 (정렬용)
            self.result_table.setItem(row, 12, SortableTableWidgetItem(str(current_price)))
        
        self.collected_data.append(d)
    
    def _update_stats(self, s):
        total = s.get('total_found', 0)
        filtered = s.get('filtered_out', 0)
        self.summary_card.update_stats(
            total, 
            self.crawl_stats.get("매매", 0),
            self.crawl_stats.get("전세", 0),
            self.crawl_stats.get("월세", 0),
            filtered,
            self.crawl_stats.get("new", 0),
            self.crawl_stats.get("price_up", 0),
            self.crawl_stats.get("price_down", 0)
        )
        self.status_bar.showMessage(f"📊 수집: {total}건 | 🆕 신규: {self.crawl_stats.get('new', 0)}건 | 필터 제외: {filtered}건")
    
    def _on_complex_done(self, n, c, t, cnt):
        self.db.add_crawl_history(n, c, t, cnt)
    
    def _crawling_done(self, data):
        # 시그널 연결 해제 (메모리 누수 방지)
        if self.crawler_thread:
            try:
                self.crawler_thread.log_signal.disconnect()
                self.crawler_thread.progress_signal.disconnect()
                self.crawler_thread.item_signal.disconnect()
                self.crawler_thread.stats_signal.disconnect()
                self.crawler_thread.complex_finished_signal.disconnect()
                self.crawler_thread.finished_signal.disconnect()
                self.crawler_thread.error_signal.disconnect()
            except (TypeError, RuntimeError):
                pass  # 이미 해제되었거나 연결되지 않은 경우
        
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_save.setEnabled(len(self.collected_data) > 0)
        self.progress_widget.complete()
        self.status_bar.showMessage(f"✅ 완료! 총 {len(self.collected_data)}건 수집")
        self._load_history()
        
        # 가격 스냅샷 저장 (통계용)
        self._save_price_snapshots()
        
        # v13.0: 대시보드 업데이트
        if hasattr(self, 'dashboard_widget') and self.collected_data:
            self.dashboard_widget.set_data(self.collected_data)
            
        # v13.0: 카드 뷰 업데이트
        if hasattr(self, 'card_view') and self.collected_data:
            self.card_view.set_data(self.collected_data)
        
        # v13.0: 즐겨찾기 탭 새로고침
        if hasattr(self, 'favorites_tab'):
            self.favorites_tab.refresh()
        
        # 완료 알림
        if settings.get("show_notifications") and NOTIFICATION_AVAILABLE:
            try:
                notification.notify(
                    title="크롤링 완료",
                    message=f"총 {len(self.collected_data)}건 수집 완료!",
                    timeout=5
                )
            except Exception as e:
                get_logger('RealEstateApp').debug(f"알림 표시 실패: {e}")
        
        # 완료 사운드
        if settings.get("play_sound_on_complete"):
            try:
                QApplication.beep()
            except Exception as e:
                get_logger('RealEstateApp').debug(f"완료 사운드 실패: {e}")
    
    def _save_price_snapshots(self):
        """크롤링 결과를 가격 스냅샷으로 저장"""
        if not self.collected_data:
            return
        
        # 단지별, 거래유형별, 평형별로 그룹화
        from collections import defaultdict
        grouped = defaultdict(list)
        
        for item in self.collected_data:
            cid = item.get("단지ID", "")
            ttype = item.get("거래유형", "")
            pyeong = item.get("면적(평)", 0)
            
            # 가격 추출
            if ttype == "매매":
                price = PriceConverter.to_int(item.get("매매가", "0"))
            else:
                price = PriceConverter.to_int(item.get("보증금", "0"))
            
            if cid and ttype and price > 0:
                # 평형 그룹화 (5평 단위)
                pyeong_group = round(pyeong / 5) * 5
                key = (cid, ttype, pyeong_group)
                grouped[key].append(price)
        
        # 스냅샷 저장
        saved = 0
        for (cid, ttype, pyeong), prices in grouped.items():
            if prices:
                min_price = min(prices)
                max_price = max(prices)
                avg_price = sum(prices) // len(prices)
                
                if self.db.add_price_snapshot(cid, ttype, pyeong, min_price, max_price, avg_price, len(prices)):
                    saved += 1
        
        print(f"[UI] 가격 스냅샷 저장: {saved}건")
    
    def _crawling_error(self, err):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        QMessageBox.critical(self, "오류", f"크롤링 중 오류 발생:\n{err}")
    
    def _show_save_menu(self):
        menu = QMenu(self)
        menu.addAction("📊 Excel로 저장", self._save_excel)
        menu.addAction("📄 CSV로 저장", self._save_csv)
        menu.addAction("📋 JSON으로 저장", self._save_json)
        menu.addSeparator()
        menu.addAction("⚙️ 엑셀 템플릿 설정", self._show_excel_template_dialog)
        menu.exec(self.btn_save.mapToGlobal(self.btn_save.rect().bottomLeft()))
    
    def _save_excel(self):
        if not self.collected_data: return
        path, _ = QFileDialog.getSaveFileName(self, "Excel 저장", f"부동산_{DateTimeHelper.file_timestamp()}.xlsx", "Excel (*.xlsx)")
        if path:
            # v7.3: 템플릿 적용
            template = settings.get("excel_template")
            if DataExporter(self.collected_data).to_excel(Path(path), template):
                QMessageBox.information(self, "저장 완료", f"Excel 파일 저장 완료!\n{path}")
    
    def _save_csv(self):
        if not self.collected_data: return
        path, _ = QFileDialog.getSaveFileName(self, "CSV 저장", f"부동산_{DateTimeHelper.file_timestamp()}.csv", "CSV (*.csv)")
        if path:
            if DataExporter(self.collected_data).to_csv(Path(path)):
                QMessageBox.information(self, "저장 완료", f"CSV 파일 저장 완료!\n{path}")
    
    def _save_json(self):
        if not self.collected_data: return
        path, _ = QFileDialog.getSaveFileName(self, "JSON 저장", f"부동산_{DateTimeHelper.file_timestamp()}.json", "JSON (*.json)")
        if path:
            if DataExporter(self.collected_data).to_json(Path(path)):
                QMessageBox.information(self, "저장 완료", f"JSON 파일 저장 완료!\n{path}")
    
    # DB Tab handlers
    def _load_db_complexes(self):
        """DB에서 단지 목록 로드 - 디버깅 강화"""
        print(f"[UI] DB 단지 로드 시작...")
        self.db_table.setRowCount(0)
        try:
            complexes = self.db.get_all_complexes()
            print(f"[UI] 로드된 단지: {len(complexes)}개")
            
            for db_id, name, cid, memo in complexes:
                row = self.db_table.rowCount()
                self.db_table.insertRow(row)
                self.db_table.setItem(row, 0, QTableWidgetItem(str(db_id)))
                self.db_table.setItem(row, 1, QTableWidgetItem(str(name)))
                self.db_table.setItem(row, 2, QTableWidgetItem(str(cid)))
                self.db_table.setItem(row, 3, QTableWidgetItem(str(memo) if memo else ""))
            
            print(f"[UI] DB 테이블 갱신 완료: {self.db_table.rowCount()}행")
        except Exception as e:
            print(f"[UI ERROR] DB 단지 로드 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def _delete_db_complex(self):
        row = self.db_table.currentRow()
        if row >= 0:
            db_id = int(self.db_table.item(row, 0).text())
            if self.db.delete_complex(db_id):
                self._load_db_complexes()
    
    def _delete_db_complexes_multi(self):
        rows = set(item.row() for item in self.db_table.selectedItems())
        if rows:
            ids = [int(self.db_table.item(r, 0).text()) for r in rows]
            cnt = self.db.delete_complexes_bulk(ids)
            QMessageBox.information(self, "삭제 완료", f"{cnt}개 단지 삭제됨")
            self._load_db_complexes()
    
    def _edit_memo(self):
        row = self.db_table.currentRow()
        if row >= 0:
            db_id = int(self.db_table.item(row, 0).text())
            old = self.db_table.item(row, 3).text()
            new, ok = QInputDialog.getText(self, "메모 수정", "메모:", text=old)
            if ok:
                self.db.update_complex_memo(db_id, new)
                self._load_db_complexes()
    
    # Group Tab handlers
    def _load_all_groups(self):
        self.group_list.clear()
        for gid, name, desc in self.db.get_all_groups():
            item = QListWidgetItem(f"{name} ({desc})" if desc else name)
            item.setData(Qt.ItemDataRole.UserRole, gid)
            self.group_list.addItem(item)
    
    def _create_group(self):
        name, ok = QInputDialog.getText(self, "새 그룹", "그룹 이름:")
        if ok and name:
            if self.db.create_group(name):
                self._load_all_groups()
                self._load_schedule_groups()
    
    def _delete_group(self):
        item = self.group_list.currentItem()
        if item:
            gid = item.data(Qt.ItemDataRole.UserRole)
            if self.db.delete_group(gid):
                self._load_all_groups()
                self._load_schedule_groups()
                self.group_complex_table.setRowCount(0)
    
    def _load_group_complexes(self, item):
        gid = item.data(Qt.ItemDataRole.UserRole)
        self.group_complex_table.setRowCount(0)
        for db_id, name, cid, memo in self.db.get_complexes_in_group(gid):
            row = self.group_complex_table.rowCount()
            self.group_complex_table.insertRow(row)
            self.group_complex_table.setItem(row, 0, QTableWidgetItem(str(db_id)))
            self.group_complex_table.setItem(row, 1, QTableWidgetItem(name))
            self.group_complex_table.setItem(row, 2, QTableWidgetItem(cid))
            self.group_complex_table.setItem(row, 3, QTableWidgetItem(memo or ""))
    
    def _add_to_group(self):
        group_item = self.group_list.currentItem()
        if not group_item:
            QMessageBox.warning(self, "알림", "그룹을 선택해주세요.")
            return
        gid = group_item.data(Qt.ItemDataRole.UserRole)
        complexes = self.db.get_all_complexes()
        if not complexes:
            QMessageBox.information(self, "알림", "DB에 저장된 단지가 없습니다.")
            return
        items = [(f"{name} ({cid})", db_id) for db_id, name, cid, _ in complexes]
        dlg = MultiSelectDialog("단지 추가", items, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.db.add_complexes_to_group(gid, dlg.selected_items())
            self._load_group_complexes(group_item)
    
    def _add_to_group_multi(self):
        self._add_to_group()  # 같은 기능
    
    def _remove_from_group(self):
        group_item = self.group_list.currentItem()
        if not group_item: return
        gid = group_item.data(Qt.ItemDataRole.UserRole)
        row = self.group_complex_table.currentRow()
        if row >= 0:
            db_id = int(self.group_complex_table.item(row, 0).text())
            self.db.remove_complex_from_group(gid, db_id)
            self._load_group_complexes(group_item)
    
    def _load_schedule_groups(self):
        self.schedule_group_combo.clear()
        for gid, name, _ in self.db.get_all_groups():
            self.schedule_group_combo.addItem(name, gid)
    
    def _check_schedule(self):
        if not self.check_schedule.isChecked(): return
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
            # 그룹 복원 로직
            self._clear_list()
            for _, name, cid, _ in self.db.get_complexes_in_group(gid):
                self._add_row(name, cid)
            self._start_crawling()
    
    # History Tab handlers
    def _load_history(self):
        self.history_table.setRowCount(0)
        history = self.db.get_crawl_history()
        for name, cid, ttype, cnt, date in history:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            self.history_table.setItem(row, 0, QTableWidgetItem(name))
            self.history_table.setItem(row, 1, QTableWidgetItem(cid))
            self.history_table.setItem(row, 2, QTableWidgetItem(ttype))
            self.history_table.setItem(row, 3, QTableWidgetItem(str(cnt)))
            self.history_table.setItem(row, 4, QTableWidgetItem(date))
    
    # Stats Tab handlers
    def _load_stats_complexes(self):
        self.stats_complex_combo.clear()
        complexes = self.db.get_all_complexes()
        for _, name, cid, _ in complexes:
            self.stats_complex_combo.addItem(f"{name}", cid)
    
    def _load_stats(self):
        cid = self.stats_complex_combo.currentData()
        ttype = self.stats_type_combo.currentText()
        if ttype == "전체": ttype = None
        
        # v10.0: 평형 필터
        pyeong_text = self.stats_pyeong_combo.currentText()
        pyeong = None
        if pyeong_text != "전체":
            pyeong = int(pyeong_text.replace("평", ""))
        
        snapshots = self.db.get_price_snapshots(cid, ttype)
        if pyeong:
            snapshots = [s for s in snapshots if s[2] == pyeong]
        
        self.stats_table.setRowCount(0)
        # 차트용 데이터 수집
        chart_data = {"date": [], "avg": [], "min": [], "max": []}
        
        for date, typ, py, min_p, max_p, avg_p, cnt in snapshots:
            row = self.stats_table.rowCount()
            self.stats_table.insertRow(row)
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
        
        # 차트 업데이트
        if chart_data["date"]:
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

    def _toggle_theme(self):
        new_theme = "light" if self.current_theme == "dark" else "dark"
        self.current_theme = new_theme
        
        # 스타일시트 적용
        self.setStyleSheet(get_stylesheet(new_theme))
        
        # 개별 위젯 테마 업데이트
        self.summary_card.set_theme(new_theme)
        if hasattr(self, 'dashboard_widget'):
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
                if hasattr(self, 'summary_card') and hasattr(self.summary_card, 'set_theme'):
                    self.summary_card.set_theme(new_theme)
            except Exception:
                pass
            
            try:
                if hasattr(self, 'dashboard_widget') and hasattr(self.dashboard_widget, 'set_theme'):
                    self.dashboard_widget.set_theme(new_theme)
            except Exception:
                pass
            
            try:
                if hasattr(self, 'favorites_tab') and hasattr(self.favorites_tab, 'set_theme'):
                    self.favorites_tab.set_theme(new_theme)
            except Exception:
                pass
            
            try:
                if hasattr(self, 'card_view'):
                    self.card_view.is_dark = (new_theme == "dark")
            except Exception:
                pass
            
            # 메뉴 체크 상태 업데이트
            if hasattr(self, 'action_theme_dark'):
                self.action_theme_dark.setChecked(new_theme == "dark")
            if hasattr(self, 'action_theme_light'):
                self.action_theme_light.setChecked(new_theme == "light")
            
            self.show_toast(f"테마가 {new_theme} 모드로 변경되었습니다")
        
        # 속도값 갱신은 슬라이더에서 처리됨
        # 알림 설정 등은 즉시 반영됨
        if self.retry_handler:
            self.retry_handler.max_retries = settings.get("max_retry_count", 3)
    
    def _save_preset(self):
        name, ok = QInputDialog.getText(self, "필터 저장", "프리셋 이름:")
        if ok and name:
            config = {
                "trade": self.check_trade.isChecked(),
                "jeonse": self.check_jeonse.isChecked(),
                "monthly": self.check_monthly.isChecked(),
                "area": {"enabled": self.check_area_filter.isChecked(), "min": self.spin_area_min.value(), "max": self.spin_area_max.value()},
                "price": {
                    "enabled": self.check_price_filter.isChecked(),
                    "trade_min": self.spin_trade_min.value(), "trade_max": self.spin_trade_max.value(),
                    "jeonse_min": self.spin_jeonse_min.value(), "jeonse_max": self.spin_jeonse_max.value(),
                    "monthly_min": self.spin_monthly_min.value(), "monthly_max": self.spin_monthly_max.value()
                }
            }
            if self.preset_manager.save_preset(name, config):
                self.show_toast(f"프리셋 '{name}' 저장 완료")
    
    def _load_preset(self):
        dialog = PresetDialog(self, self.preset_manager)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_preset:
            config = dialog.selected_preset
            self.check_trade.setChecked(config.get("trade", True))
            self.check_jeonse.setChecked(config.get("jeonse", True))
            self.check_monthly.setChecked(config.get("monthly", False))
            
            area = config.get("area", {})
            self.check_area_filter.setChecked(area.get("enabled", False))
            self.spin_area_min.setValue(area.get("min", 0))
            self.spin_area_max.setValue(area.get("max", 200))
            
            p = config.get("price", {})
            self.check_price_filter.setChecked(p.get("enabled", False))
            self.spin_trade_min.setValue(p.get("trade_min", 0))
            self.spin_trade_max.setValue(p.get("trade_max", 100000))
            self.spin_jeonse_min.setValue(p.get("jeonse_min", 0))
            self.spin_jeonse_max.setValue(p.get("jeonse_max", 50000))
            self.spin_monthly_min.setValue(p.get("monthly_min", 0))
            self.spin_monthly_max.setValue(p.get("monthly_max", 5000))
            self.show_toast("프리셋을 불러왔습니다")
    
    def _show_alert_settings(self):
        AlertSettingDialog(self).exec()
    
    def _show_shortcuts(self):
        ShortcutsDialog(self).exec()
    
    def _show_about(self):
        AboutDialog(self).exec()
    
    def _show_advanced_filter(self):
        dlg = AdvancedFilterDialog(self, self.advanced_filters)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.advanced_filters = dlg.get_filters()
            # 필터 버튼 스타일 변경으로 활성 상태 표시
            sender = self.sender()
            if sender and isinstance(sender, QPushButton):
                if self.advanced_filters:
                     sender.setStyleSheet("background-color: #e67e22; border: 1px solid #d35400;")
                else:
                     sender.setStyleSheet("") 
            self.show_toast("고급 필터가 적용되었습니다")
            
            # 이미 결과가 있다면 다시 필터링
            if self.collected_data:
                self._filter_results_advanced()

    def _apply_advanced_filter(self):
        self._show_advanced_filter()

    def _filter_results_advanced(self):
        """고급 필터를 수집된 데이터에 적용"""
        if not self.advanced_filters: return
        
        filtered_count = 0
        for r in range(self.result_table.rowCount()):
            # 로우에 해당하는 데이터 찾기 (result_table에는 원본 데이터 객체가 연결되어 있지 않음)
            # 수집된 데이터(collected_data)와 동기화가 필요하지만, 여기서는 화면 필터링만 수행
            # 하지만 화면 필터링만으로는 데이터 기반 필터(층수, 동 등)를 정확히 수행하기 어려움
            # 따라서 collected_data를 순회하며 조건에 안 맞는 행을 숨김
            
            # NOTE: result_table과 collected_data의 인덱스가 일치한다고 가정 (정렬하지 않았을 때)
            # 정렬 시에는 문제가 될 수 있으므로, 재구성이 필요함.
            # 여기서는 단순히 안내 메시지만 띄움 (구현 복잡도 때문에)
            pass
        
        # 실제 구현에서는 CrawlerThread 내에서 필터링하거나, 
        # collected_data를 다시 테이블에 렌더링하는 방식이 좋음.
        # 여기서는 재렌더링 방식 선택
        self.result_table.setRowCount(0)
        self.grouped_rows.clear()
        
        temp_data = []
        for d in self.collected_data:
            # 고급 필터 적용
            if self._check_advanced_filter(d):
                self._add_result(d)
            else:
                filtered_count += 1
        
        self.status_bar.showMessage(f"🔍 고급 필터 적용됨 (제외: {filtered_count}건)")
    
    def _check_advanced_filter(self, d):
        """단일 데이터에 대한 고급 필터 체크"""
        if not self.advanced_filters: return True
        
        f = self.advanced_filters
        
        # 층수 (저/중/고/탑)
        floor = d.get("층/방향", "").split("/")[0].strip()
        if f.get("exclude_low_floor") and (floor == "저" or floor == "1" or floor == "2" or floor == "3"):
            return False
        if f.get("exclude_top_floor") and (floor == "탑" or floor.endswith("탑")):
            return False
            
        # 동 (101동 등)
        dong = d.get("동", "") # 크롤러에서 동 정보를 수집해야 함
        target_dongs = f.get("dongs", [])
        if target_dongs and dong not in target_dongs:
            return False
            
        return True

    def _show_url_batch_dialog(self):
        dlg = URLBatchDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            urls = dlg.get_urls()
            self._add_complexes_from_url(urls)
    
    def _add_complexes_from_url(self, urls):
        count = 0
        for url in urls:
            # URL 파싱 로직 (utils/helpers.py 활용 가능)
            # 여기서는 간단히 ID 추출 예시
            m = re.search(r'/complexes/(\d+)', url)
            if m:
                cid = m.group(1)
                # 이름은 가져오기 어려우므로 "URL추가_ID" 임시 지정 후 사용자가 수정 권장
                # 또는 crawler가 ID로 이름 조회하는 기능 필요 (NaverURLParser 활용)
                self._add_row(f"단지_{cid}", cid)
                count += 1
        self.show_toast(f"{count}개 URL 등록 완료")

    def _show_excel_template_dialog(self):
        ExcelTemplateDialog(self).exec()

    def _save_excel_template(self):
        # Dialog에서 처리됨
        pass

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
            print(f"[UI] DB 복원 시작: {path}")
            
            if self.db.restore_database(Path(path)):
                # 성공 시 모든 데이터 다시 로드
                print("[UI] DB 복원 성공, 데이터 다시 로드 중...")
                self._load_initial_data()
                self.status_bar.showMessage("✅ DB 복원 완료!")
                QMessageBox.information(self, "복원 완료", "DB 복원이 완료되었습니다!")
                print("[UI] DB 복원 완료")
            else:
                self.status_bar.showMessage("❌ DB 복원 실패")
                QMessageBox.critical(self, "복원 실패", "DB 복원에 실패했습니다.\n콘솔 로그를 확인하세요.")
                print("[UI] DB 복원 실패")
                
        except Exception as e:
            print(f"[UI ERROR] DB 복원 중 예외: {e}")
            import traceback
            traceback.print_exc()
            self.status_bar.showMessage("❌ DB 복원 중 오류 발생")
            QMessageBox.critical(self, "오류", f"DB 복원 중 오류가 발생했습니다:\n{e}")

    def _refresh_tab(self):
        idx = self.tabs.currentIndex()
        if idx == 1: self._load_db_complexes()
        elif idx == 4: self._load_history()
        elif idx == 5: self._load_stats()
        elif idx == 6: 
             if hasattr(self, 'dashboard_widget'): self.dashboard_widget.refresh()
        elif idx == 7:
             if hasattr(self, 'favorites_tab'): self.favorites_tab.refresh()

    def _focus_search(self):
        self.result_search.setFocus()

    def _minimize_to_tray(self):
        if self.tray_icon:
            self.hide()
            self.tray_icon.showMessage("알림", "트레이로 최소화되었습니다.", QSystemTrayIcon.MessageIcon.Information, 2000)

    def _show_from_tray(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()

    def _quit_app(self):
        if settings.get("confirm_before_close"):
            if QMessageBox.question(self, "종료", "정말 종료하시겠습니까?") != QMessageBox.StandardButton.Yes:
                return
        
        # 스레드 안전 종료
        if self.crawler_thread and self.crawler_thread.isRunning():
            get_logger('RealEstateApp').info("크롤러 스레드 종료 중...")
            self.crawler_thread.stop()
            if not self.crawler_thread.wait(5000):  # 5초 대기
                get_logger('RealEstateApp').warning("크롤러 스레드 강제 종료")
        
        # 타이머 정리
        if hasattr(self, 'schedule_timer') and self.schedule_timer:
            self.schedule_timer.stop()
        
        # 설정 저장
        settings.set("window_geometry", [self.x(), self.y(), self.width(), self.height()])
        
        # DB 연결 종료
        self.db.close()
        
        QApplication.quit()

    def closeEvent(self, event):
        if settings.get("confirm_before_close"):
            reply = QMessageBox.question(self, "종료", "정말 종료하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self._quit_app()
                event.accept()
            else:
                event.ignore()
        else:
             self._quit_app()
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
        margin = 20
        y = self.height() - margin
        for t in reversed(self.toast_widgets):
            y -= t.height()
            t.move(self.width() - margin - t.width(), y)
            y -= 10







    def _toggle_view_mode(self):
        """테이블/카드 뷰 전환"""
        if self.btn_view_mode.isChecked():
            self.view_mode = "card"
            self.btn_view_mode.setText("📄 테이블")
            self.view_stack.setCurrentWidget(self.card_view)
            # 데이터 동기화 (필요시)
            if self.collected_data and not self.card_view._cards:
                self.card_view.set_data(self.collected_data)
        else:
            self.view_mode = "table"
            self.btn_view_mode.setText("🃏 카드뷰")
            self.view_stack.setCurrentWidget(self.result_table)
            
        settings.set("view_mode", self.view_mode)
        
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
                print(f"[WARN] 알림 표시 실패: {e}")

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
            card_view.favorite_toggled.connect(self.db.toggle_favorite)
            layout.addWidget(card_view)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)
        
        dlg.exec()
