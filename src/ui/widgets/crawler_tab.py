from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QTableWidget, 
    QTableWidgetItem, QCheckBox, QAbstractItemView, QHeaderView, QTabWidget, 
    QGroupBox, QSplitter, QScrollArea, QFrame, QStackedWidget, QTextBrowser, 
    QDialog, QMessageBox, QFileDialog, QSizePolicy, QStyle, QApplication, QMenu,
    QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox
)


from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QTextCursor
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

class CrawlerTab(QWidget):
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
    COL_COLLECTED_AT = 10
    COL_LINK = 11
    COL_URL = 12
    COL_PRICE_SORT = 13
    
    # Signals
    data_collected = pyqtSignal(list)  # 수집 완료 시 데이터 전송
    crawling_started = pyqtSignal()
    crawling_stopped = pyqtSignal()
    status_message = pyqtSignal(str)
    alert_triggered = pyqtSignal(str, str, str, float, int)
    
    def __init__(self, db, history_manager=None, theme="dark", parent=None, maintenance_guard=None):
        super().__init__(parent)
        self.db = db
        self.history_manager = history_manager
        self.current_theme = theme
        self._maintenance_guard = maintenance_guard
        self.crawler_thread = None
        self.crawl_cache = None
        self.collected_data = []
        self.grouped_rows = {}
        self._pending_search_text = ""
        self._row_search_cache = []
        self._row_payload_cache = []
        self._row_hidden_state = {}
        self._advanced_filters = None
        self._append_chunk_size = 200
        self._compact_duplicates = bool(settings.get("compact_duplicate_listings", True))
        self._compact_items_by_key = {}
        self._compact_rows_data = []
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        try:
            debounce_ms = max(80, int(settings.get("result_filter_debounce_ms", 220)))
        except (TypeError, ValueError):
            debounce_ms = 220
        self._search_timer.setInterval(debounce_ms)
        self._search_timer.timeout.connect(self._apply_search_filter)
        
        # UI Setup
        self._init_ui()
        self._load_state()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left Panel (Controls)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMinimumWidth(380)
        scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        scroll_content = QWidget()
        left = QVBoxLayout(scroll_content)
        left.setSpacing(10)
        
        self._setup_options_group(left)
        self._setup_filter_group(left)
        self._setup_complex_list_group(left)
        self._setup_speed_group(left)
        self._setup_action_group(left)
        
        left.addStretch()
        scroll.setWidget(scroll_content)
        splitter.addWidget(scroll)
        
        # Right Panel (Results)
        right_w = QWidget()
        right = QVBoxLayout(right_w)
        right.setSpacing(8)
        
        self.summary_card = SummaryCard(theme=self.current_theme)
        right.addWidget(self.summary_card)
        
        self._setup_result_area(right)
        
        splitter.addWidget(right_w)
        splitter.setSizes([450, 900])
        layout.addWidget(splitter)

    def _setup_options_group(self, layout):
        # 1. 거래유형
        tg = QGroupBox("1️⃣ 거래 유형")
        tl = QHBoxLayout()
        self.check_trade = QCheckBox("매매")
        self.check_trade.setChecked(True)
        self.check_jeonse = QCheckBox("전세")
        self.check_jeonse.setChecked(True)
        self.check_monthly = QCheckBox("월세")
        tl.addWidget(self.check_trade)
        tl.addWidget(self.check_jeonse)
        tl.addWidget(self.check_monthly)
        tl.addStretch()
        tg.setLayout(tl)
        layout.addWidget(tg)

    def _setup_filter_group(self, layout):
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
        self.spin_area_max = QSpinBox()
        self.spin_area_max.setRange(0, 300)
        self.spin_area_max.setValue(200)
        self.spin_area_max.setEnabled(False)
        
        area_input.addWidget(QLabel("최소:"))
        area_input.addWidget(self.spin_area_min)
        area_input.addWidget(QLabel("㎡  ~  최대:"))
        area_input.addWidget(self.spin_area_max)
        area_input.addWidget(QLabel("㎡"))
        al.addLayout(area_input)
        ag.setLayout(al)
        layout.addWidget(ag)
        
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
        price_grid.addWidget(self.spin_trade_min, 0, 1)
        price_grid.addWidget(QLabel("~"), 0, 2)
        self.spin_trade_max = QSpinBox()
        self.spin_trade_max.setRange(0, 999999)
        self.spin_trade_max.setValue(100000)
        self.spin_trade_max.setSingleStep(1000)
        self.spin_trade_max.setEnabled(False)
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
        layout.addWidget(pg)

    def _setup_complex_list_group(self, layout):
        cg = QGroupBox("4️⃣ 단지 목록")
        cl = QVBoxLayout()
        
        # Load Buttons
        load_btn = QHBoxLayout()
        btn_db = QPushButton("💾 DB에서")
        btn_db.clicked.connect(self._show_db_load_dialog)
        btn_grp = QPushButton("📁 그룹에서")
        btn_grp.clicked.connect(self._show_group_load_dialog)
        load_btn.addWidget(btn_db)
        load_btn.addWidget(btn_grp)
        cl.addLayout(load_btn)
        
        # Input Area
        input_layout = QHBoxLayout()
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("단지명")
        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("단지 ID")
        btn_add = QPushButton("➕")
        btn_add.setMaximumWidth(45)
        btn_add.clicked.connect(self._add_complex)
        input_layout.addWidget(self.input_name, 2)
        input_layout.addWidget(self.input_id, 1)
        input_layout.addWidget(btn_add)
        cl.addLayout(input_layout)
        
        # History Button
        btn_hist = QPushButton("🕐 최근 검색 불러오기")
        btn_hist.clicked.connect(self._show_recent_search_dialog)
        cl.addWidget(btn_hist)
        
        # List Table
        self.table_list = QTableWidget()
        self.table_list.setColumnCount(2)
        self.table_list.setHorizontalHeaderLabels(["단지명", "ID"])
        self.table_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_list.setMinimumHeight(130)
        self.table_list.setAlternatingRowColors(True)
        self.table_list.doubleClicked.connect(self._open_complex_url)
        cl.addWidget(self.table_list)
        
        # Manage Buttons
        manage_btn = QHBoxLayout()
        btn_del = QPushButton("🗑️ 삭제")
        btn_del.clicked.connect(self._delete_complex)
        btn_clr = QPushButton("🧹 초기화")
        btn_clr.clicked.connect(self._clear_list)
        btn_sv = QPushButton("💾 DB저장")
        btn_sv.clicked.connect(self._save_to_db)
        btn_url = QPushButton("🔗 URL등록")
        btn_url.clicked.connect(self._show_url_batch_dialog)
        manage_btn.addWidget(btn_del)
        manage_btn.addWidget(btn_clr)
        manage_btn.addWidget(btn_sv)
        manage_btn.addWidget(btn_url)
        cl.addLayout(manage_btn)
        
        cg.setLayout(cl)
        layout.addWidget(cg)

    def _setup_speed_group(self, layout):
        spg = QGroupBox("5️⃣ 크롤링 속도")
        spl = QVBoxLayout()
        self.speed_slider = SpeedSlider()
        self.speed_slider.set_speed(settings.get("crawl_speed", "보통"))
        self.speed_slider.speed_changed.connect(self._on_speed_changed)
        spl.addWidget(self.speed_slider)
        spg.setLayout(spl)
        layout.addWidget(spg)

    def _setup_action_group(self, layout):
        eg = QGroupBox("6️⃣ 실행")
        el = QHBoxLayout()
        el.setSpacing(10)
        self.btn_start = QPushButton("▶️ 크롤링 시작")
        self.btn_start.setObjectName("startButton")
        self.btn_start.setMinimumHeight(48)
        self.btn_start.clicked.connect(self.start_crawling)
        
        self.btn_stop = QPushButton("⏹️ 중지")
        self.btn_stop.setObjectName("stopButton")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setMinimumHeight(42)
        self.btn_stop.clicked.connect(self.stop_crawling)
        
        self.btn_save = QPushButton("💾 저장")
        self.btn_save.setObjectName("saveButton")
        self.btn_save.setEnabled(False)
        self.btn_save.setMinimumHeight(42)
        self.btn_save.clicked.connect(self.show_save_menu)
        
        el.addWidget(self.btn_start, 2)
        el.addWidget(self.btn_stop, 1)
        el.addWidget(self.btn_save, 1)

        eg.setLayout(el)
        layout.addWidget(eg)

    def _setup_result_area(self, layout):
        # Search & Sort
        search_sort = QHBoxLayout()
        self.check_compact_duplicates = QCheckBox("동일 매물 묶기")
        self.check_compact_duplicates.setChecked(self._compact_duplicates)
        self.check_compact_duplicates.toggled.connect(self._toggle_compact_duplicates)
        search_sort.addWidget(self.check_compact_duplicates)

        self.result_search = SearchBar("결과 검색...")
        self.result_search.search_changed.connect(self._on_search_text_changed)
        search_sort.addWidget(self.result_search, 3)

        self.btn_advanced_filter = QPushButton("⚙️ 고급필터")
        self.btn_advanced_filter.clicked.connect(self.open_advanced_filter_dialog)
        search_sort.addWidget(self.btn_advanced_filter)

        self.btn_clear_advanced_filter = QPushButton("🧹 필터해제")
        self.btn_clear_advanced_filter.clicked.connect(self.clear_advanced_filters)
        self.btn_clear_advanced_filter.setEnabled(False)
        search_sort.addWidget(self.btn_clear_advanced_filter)
        
        search_sort.addWidget(QLabel("정렬:"))
        self.combo_sort = QComboBox()
        self.combo_sort.addItems(
            ["가격 ↑", "가격 ↓", "면적 ↑", "면적 ↓", "단지명 ↑", "단지명 ↓", "거래유형 ↑", "거래유형 ↓"]
        )
        self.combo_sort.currentTextChanged.connect(self._sort_results)
        search_sort.addWidget(self.combo_sort, 1)
        
        self.view_mode = settings.get("view_mode", "table")
        self.btn_view_mode = QPushButton("🃏 카드뷰" if self.view_mode != "card" else "📄 테이블")
        self.btn_view_mode.setCheckable(True)
        self.btn_view_mode.setChecked(self.view_mode == "card")
        self.btn_view_mode.clicked.connect(self._toggle_view_mode)
        search_sort.addWidget(self.btn_view_mode)
        layout.addLayout(search_sort)
        
        # Result Tabs
        result_tabs = QTabWidget()
        result_tab = QWidget()
        rl = QVBoxLayout(result_tab)
        rl.setContentsMargins(0, 5, 0, 0)
        
        # Table View
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(14)
        self.result_table.setHorizontalHeaderLabels([
            "단지명", "거래", "가격", "면적", "평당가", "층/방향", "특징", 
            "묶음", "🆕", "📊 변동", "시각", "링크", "URL", "가격(숫자)"
        ])
        self.result_table.setColumnHidden(self.COL_URL, True)
        self.result_table.setColumnHidden(self.COL_PRICE_SORT, True)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.doubleClicked.connect(self._open_article_url)
        
        # Card View
        self.view_stack = QStackedWidget()
        self.view_stack.addWidget(self.result_table)
        
        self.card_view = CardViewWidget(is_dark=(self.current_theme == "dark"))
        self.card_view.article_clicked.connect(lambda d: webbrowser.open(get_article_url(d.get("단지ID"), d.get("매물ID"))))
        self.card_view.favorite_toggled.connect(self.db.toggle_favorite)
        self.view_stack.addWidget(self.card_view)
        
        if self.view_mode == "card":
             self.view_stack.setCurrentWidget(self.card_view)
        
        rl.addWidget(self.view_stack)
        result_tabs.addTab(result_tab, "📊 결과")
        
        # Log Tab
        log_tab = QWidget()
        ll = QVBoxLayout(log_tab)
        ll.setContentsMargins(0, 5, 0, 0)
        self.log_browser = QTextBrowser()
        self.log_browser.setMinimumHeight(150)
        ll.addWidget(self.log_browser)
        result_tabs.addTab(log_tab, "📝 로그")
        
        layout.addWidget(result_tabs)
        
        # Progress
        self.progress_widget = ProgressWidget()
        layout.addWidget(self.progress_widget)

    def _load_state(self):
        # Load any persisted state if needed
        logger.debug("CrawlerTab 상태 로드 없음 (기본값 사용)")
        self.update_runtime_settings()

    def set_theme(self, theme):
        self.current_theme = theme
        if hasattr(self, 'summary_card'):
            self.summary_card.set_theme(theme)
        if hasattr(self, 'card_view'):
            self.card_view.is_dark = (theme == "dark")

    def _on_speed_changed(self, speed):
        settings.set("crawl_speed", speed)

    def _default_sort_criterion(self):
        column = str(settings.get("default_sort_column", "가격") or "가격")
        order = str(settings.get("default_sort_order", "asc") or "asc").lower()
        if column == "거래":
            column = "거래유형"
        if column not in {"가격", "면적", "단지명", "거래유형"}:
            column = "가격"
        arrow = "↑" if order == "asc" else "↓"
        return f"{column} {arrow}"

    def _apply_default_sort_settings(self):
        criterion = self._default_sort_criterion()
        idx = self.combo_sort.findText(criterion)
        if idx < 0:
            return
        self.combo_sort.blockSignals(True)
        self.combo_sort.setCurrentIndex(idx)
        self.combo_sort.blockSignals(False)
        if self.result_table.rowCount() > 0:
            self._sort_results(self.combo_sort.currentText())

    def update_runtime_settings(self):
        try:
            debounce_ms = max(80, int(settings.get("result_filter_debounce_ms", 220)))
        except (TypeError, ValueError):
            debounce_ms = 220
        self._search_timer.setInterval(debounce_ms)
        self.speed_slider.set_speed(settings.get("crawl_speed", "보통"))
        self._apply_default_sort_settings()

        compact = bool(settings.get("compact_duplicate_listings", True))
        self.check_compact_duplicates.setChecked(compact)
        
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

    def add_task(self, name, cid):
        row = self.table_list.rowCount()
        self.table_list.insertRow(row)
        self.table_list.setItem(row, 0, QTableWidgetItem(str(name)))
        self.table_list.setItem(row, 1, QTableWidgetItem(str(cid)))
        
    def _add_row(self, name, cid):
        self.add_task(name, cid)
    
    def clear_tasks(self):
        self.table_list.setRowCount(0)

    def _delete_complex(self):
        row = self.table_list.currentRow()
        if row >= 0:
            self.table_list.removeRow(row)
    
    def _clear_list(self):
        self.table_list.setRowCount(0)

    def _save_to_db(self):
        count = 0
        total = self.table_list.rowCount()
        for r in range(total):
            name = self.table_list.item(r, 0).text()
            cid = self.table_list.item(r, 1).text()
            if self.db.add_complex(name, cid):
                count += 1
        QMessageBox.information(self, "저장 완료", f"{count}개 단지가 DB에 저장되었습니다.")

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
                    self.add_task(name, cid)

    def _show_recent_search_dialog(self):
        if not self.history_manager:
            return
        
        try:
            dlg = RecentSearchDialog(self, self.history_manager)
            if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_search:
                search = dlg.selected_search
                self.clear_tasks()
                
                complexes = search.get('complexes', [])
                for item in complexes:
                    # Handle both [name, cid] list and dictionary just in case
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        name, cid = item[0], item[1]
                        self.add_task(name, cid)
                    elif isinstance(item, dict):
                        self.add_task(item.get('name', ''), item.get('cid', ''))
                        
                # 거래유형 복원
                types = search.get('trade_types', [])
                self.check_trade.setChecked("매매" in types)
                self.check_jeonse.setChecked("전세" in types)
                self.check_monthly.setChecked("월세" in types)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"최근 검색 기록을 불러오는 중 오류가 발생했습니다:\n{e}")
            logger.error(f"Recent search load failed: {e}")

    def _show_url_batch_dialog(self):
        dlg = URLBatchDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            selected = dlg.get_selected_complexes()
            if selected:
                for name, cid in selected:
                    self._add_row(name, cid)
                self.status_message.emit(f"{len(selected)}개 URL 등록 완료")
                return
            urls = dlg.get_urls()
            self._add_complexes_from_url(urls)

    def _add_complexes_from_url(self, urls):
        count = 0
        for url in urls:
            m = re.search(r'/complexes/(\d+)', url)
            if m:
                cid = m.group(1)
                self._add_row(f"단지_{cid}", cid)
                count += 1
        self.status_message.emit(f"{count}개 URL 등록 완료")

    def _open_complex_url(self):
        item = self.table_list.item(self.table_list.currentRow(), 1)
        if item:
            url = f"https://new.land.naver.com/complexes/{item.text()}"
            webbrowser.open(url)

    def _toggle_compact_duplicates(self, enabled):
        self._compact_duplicates = bool(enabled)
        settings.set("compact_duplicate_listings", self._compact_duplicates)
        self._rebuild_result_views_from_collected_data()

    @staticmethod
    def _area_float(value):
        try:
            return round(float(value or 0), 1)
        except (TypeError, ValueError):
            return 0.0

    def _extract_price_values(self, data):
        trade_type = str(data.get("거래유형", "") or "")
        if trade_type == "매매":
            price_text = str(data.get("매매가", "") or "")
            price_int = PriceConverter.to_int(price_text)
        else:
            deposit = str(data.get("보증금", "") or "")
            monthly = str(data.get("월세", "") or "")
            price_text = f"{deposit}/{monthly}" if monthly else deposit
            price_int = PriceConverter.to_int(deposit)
        return trade_type, price_text, int(price_int or 0)

    def _get_compact_key(self, data):
        trade_type, price_text, _ = self._extract_price_values(data)
        return (
            str(data.get("단지명", "") or ""),
            str(data.get("단지ID", "") or ""),
            trade_type,
            str(price_text),
            self._area_float(data.get("면적(평)", 0)),
            str(data.get("층/방향", "") or ""),
        )

    @staticmethod
    def _normalize_price_change(value):
        if isinstance(value, str):
            return PriceConverter.to_int(value)
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _merge_compact_item(self, existing, incoming):
        existing["duplicate_count"] = int(existing.get("duplicate_count", 1) or 1) + 1
        existing["수집시각"] = incoming.get("수집시각", existing.get("수집시각", ""))
        if bool(incoming.get("is_new") or incoming.get("신규여부")):
            existing["is_new"] = True
            existing["신규여부"] = True
        in_change = self._normalize_price_change(incoming.get("price_change", incoming.get("가격변동", 0)))
        ex_change = self._normalize_price_change(existing.get("price_change", existing.get("가격변동", 0)))
        if abs(in_change) > abs(ex_change):
            existing["price_change"] = in_change
            existing["가격변동"] = in_change

    def _reset_result_state(self):
        self.result_table.setRowCount(0)
        self._row_search_cache = []
        self._row_payload_cache = []
        self._row_hidden_state = {}
        self._compact_items_by_key = {}
        self._compact_rows_data = []

    def _rebuild_result_views_from_collected_data(self):
        self._reset_result_state()
        if not self.collected_data:
            self.card_view.set_data([])
            return

        if self._compact_duplicates:
            self._append_rows_compact_batch(self.collected_data)
            if self.view_mode == "card":
                self.card_view.set_data(list(self._compact_rows_data))
        else:
            self._append_rows_batch(self.collected_data)
            if self.view_mode == "card":
                self.card_view.set_data(self.collected_data)
        self._filter_results(self._pending_search_text)
            
    def _toggle_view_mode(self):
        if self.btn_view_mode.isChecked():
            self.view_mode = "card"
            self.btn_view_mode.setText("📄 테이블")
            self.view_stack.setCurrentWidget(self.card_view)
            if self.collected_data:
                if self._advanced_filters:
                    self.card_view.set_data(self._advanced_filtered_data_for_cards())
                    self.card_view.filter_cards(self._pending_search_text)
                elif self._compact_duplicates:
                    self.card_view.set_data(list(self._compact_rows_data))
                else:
                    self.card_view.set_data(self.collected_data)
        else:
            self.view_mode = "table"
            self.btn_view_mode.setText("🃏 카드뷰")
            self.view_stack.setCurrentWidget(self.result_table)
        settings.set("view_mode", self.view_mode)

    def start_crawling(self):
        if self.crawler_thread and self.crawler_thread.isRunning():
            self.append_log("⚠️ 이미 크롤링이 실행 중입니다.", 30)
            self.status_message.emit("이미 크롤링이 실행 중입니다.")
            return

        try:
            in_maintenance = bool(self._maintenance_guard()) if callable(self._maintenance_guard) else False
        except Exception:
            in_maintenance = False
        if in_maintenance:
            self.append_log("⛔ 유지보수 모드에서는 크롤링을 시작할 수 없습니다.", 30)
            self.status_message.emit("유지보수 모드에서는 크롤링이 차단됩니다.")
            return

        if self.table_list.rowCount() == 0:
            QMessageBox.warning(self, "경고", "크롤링할 단지를 추가해주세요.")
            return

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_save.setEnabled(False)
        self.log_browser.clear()
        self.progress_widget.reset()
        self.summary_card.reset()
        self.collected_data = []
        self.crawl_cache = None
        self._reset_result_state()
        self.card_view.set_data([])
        self.grouped_rows = {}
        
        target_list = []
        for r in range(self.table_list.rowCount()):
            name = self.table_list.item(r, 0).text()
            cid = self.table_list.item(r, 1).text()
            target_list.append((name, cid))
            
        trade_types = []
        if self.check_trade.isChecked(): trade_types.append("매매")
        if self.check_jeonse.isChecked(): trade_types.append("전세")
        if self.check_monthly.isChecked(): trade_types.append("월세")
        
        if not trade_types:
            QMessageBox.warning(self, "경고", "최소 하나의 거래 유형을 선택해주세요.")
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            return

        if self.history_manager:
            try:
                self.history_manager.add(
                    {
                        "complexes": [{"name": name, "cid": cid} for name, cid in target_list],
                        "trade_types": list(trade_types),
                    }
                )
            except Exception as e:
                logger.warning(f"최근 검색 기록 저장 실패: {e}")
            
        area_filter = {"enabled": self.check_area_filter.isChecked(), "min": self.spin_area_min.value(), "max": self.spin_area_max.value()}
        price_filter = {
            "enabled": self.check_price_filter.isChecked(),
            "매매": {"min": self.spin_trade_min.value(), "max": self.spin_trade_max.value()},
            "전세": {"min": self.spin_jeonse_min.value(), "max": self.spin_jeonse_max.value()},
            "월세": {"min": self.spin_monthly_min.value(), "max": self.spin_monthly_max.value()}
        }

        if settings.get("cache_enabled", True):
            self.crawl_cache = CrawlCache(
                ttl_minutes=settings.get("cache_ttl_minutes", 30),
                write_back_interval_sec=settings.get("cache_write_back_interval_sec", 2),
                max_entries=settings.get("cache_max_entries", 2000),
            )
        
        # Start Thread
        self.crawler_thread = CrawlerThread(
            target_list, trade_types, area_filter, price_filter, self.db,
            speed=self.speed_slider.current_speed(),
            cache=self.crawl_cache,
            ui_batch_interval_ms=settings.get("ui_batch_interval_ms", 120),
            ui_batch_size=settings.get("ui_batch_size", 30),
            max_retry_count=settings.get("max_retry_count", 3),
            show_new_badge=settings.get("show_new_badge", True),
            show_price_change=settings.get("show_price_change", True),
            price_change_threshold=settings.get("price_change_threshold", 0),
            track_disappeared=settings.get("track_disappeared", True),
            history_batch_size=settings.get("history_batch_size", 200),
        )
        self.crawler_thread.log_signal.connect(self.append_log)
        self.crawler_thread.progress_signal.connect(self.progress_widget.update_progress)
        self.crawler_thread.items_signal.connect(self._on_items_batch)
        self.crawler_thread.stats_signal.connect(self._update_stats_ui)
        self.crawler_thread.complex_finished_signal.connect(self._on_complex_finished)
        self.crawler_thread.alert_triggered_signal.connect(self._on_alert_triggered)
        self.crawler_thread.error_signal.connect(lambda msg: self.append_log(f"❌ 크롤링 오류: {msg}", 40))
        self.crawler_thread.finished_signal.connect(self._on_crawl_finished)
        self.crawler_thread.start()
        
        self.crawling_started.emit()

    def stop_crawling(self):
        if self.crawler_thread and self.crawler_thread.isRunning():
            self.crawler_thread.stop()
            self.append_log("🛑 중지 요청 중...", 30)
            self.btn_stop.setEnabled(False)

    def shutdown_crawl(self, timeout_ms: int = 8000) -> bool:
        thread = self.crawler_thread
        if not thread:
            return True
        if not thread.isRunning():
            self.crawler_thread = None
            return True

        thread.stop()
        try:
            wait_ms = max(100, int(timeout_ms))
        except (TypeError, ValueError):
            wait_ms = 8000
        finished = bool(thread.wait(wait_ms))
        if finished:
            self.crawler_thread = None
            return True
        self.append_log(f"⚠️ 크롤링 종료 대기 타임아웃 ({wait_ms}ms)", 30)
        return False

    def _on_crawl_finished(self, data):
        try:
            self.btn_save.setEnabled(True)
            self.progress_widget.complete()
            self.append_log(f"✅ 크롤링 완료: 총 {len(data)}건 수집")

            if self.crawl_cache:
                self.crawl_cache.flush()
            
            # DB Write
            try:
                self._save_price_snapshots()
            except Exception as e:
                self.append_log(f"⚠️ 가격 스냅샷 저장 실패: {e}", 30)

            if settings.get("play_sound_on_complete", True):
                try:
                    QApplication.beep()
                except Exception as e:
                    logger.debug(f"완료 알림음 재생 실패 (무시): {e}")
            
            self.data_collected.emit(data) # Notify App
            self.crawling_stopped.emit()
            
        except Exception as e:
            self.append_log(f"❌ 크롤링 마무리 중 오류: {e}", 40)
            logger.error(f"Crawl finish handler failed: {e}")
        finally:
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.crawler_thread = None

    def append_log(self, msg, level=20):
        theme_colors = COLORS[self.current_theme]
        color = theme_colors["text_primary"]
        
        if level >= 40: color = theme_colors["error"]
        elif level >= 30: color = theme_colors["warning"]
        elif level == 10: color = theme_colors["text_secondary"]
        
        self.log_browser.append(f'<span style="color:{color}">{msg}</span>')
        try:
            max_lines = max(200, int(settings.get("max_log_lines", 1500)))
        except (TypeError, ValueError):
            max_lines = 1500
        overflow = self.log_browser.document().blockCount() - max_lines
        if overflow > 0:
            cursor = self.log_browser.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            for _ in range(overflow):
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()
        # Scroll to bottom
        sb = self.log_browser.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_items_batch(self, items):
        if not items:
            return
        self.collected_data.extend(items)
        if self._compact_duplicates:
            self._append_rows_compact_batch(items)
            if self.view_mode == "card":
                self.card_view.set_data(list(self._compact_rows_data))
        else:
            self._append_rows_batch(items)
            if self.view_mode == "card":
                self.card_view.append_data(items)
        if self._advanced_filters:
            self._apply_card_filters(self._pending_search_text)

    def _sync_row_search_cache(self, row):
        values = []
        for col in range(self.result_table.columnCount()):
            item = self.result_table.item(row, col)
            if item:
                values.append(item.text())
        searchable = " ".join(values).lower()
        while len(self._row_search_cache) <= row:
            self._row_search_cache.append("")
        self._row_search_cache[row] = searchable
        return searchable

    def _build_row_payload_from_data(self, data, trade_type, price_int, area_val, price_change, is_new):
        payload = dict(data or {})
        payload["거래유형"] = trade_type
        payload["price_int"] = int(price_int or 0)
        payload["면적(평)"] = float(area_val or 0)
        payload["층/방향"] = str(data.get("층/방향", "") if isinstance(data, dict) else "")
        payload["타입/특징"] = str(data.get("타입/특징", "") if isinstance(data, dict) else "")
        payload["is_new"] = bool(is_new)
        payload["price_change"] = int(price_change or 0)
        return payload

    def _build_row_payload_from_table(self, row):
        def _text(col):
            item = self.result_table.item(row, col)
            return item.text().strip() if item else ""

        change_text = _text(self.COL_PRICE_CHANGE)
        sign = -1 if change_text.startswith("-") else 1
        change_value = PriceConverter.to_int(change_text.lstrip("+-"))
        price_int_text = _text(self.COL_PRICE_SORT)
        try:
            price_int = int(price_int_text.replace(",", "")) if price_int_text else 0
        except ValueError:
            price_int = 0
        area_val = self._area_float(_text(self.COL_AREA).replace("평", ""))
        payload = {
            "단지명": _text(self.COL_COMPLEX),
            "거래유형": _text(self.COL_TRADE),
            "price_int": int(price_int),
            "면적(평)": float(area_val),
            "층/방향": _text(self.COL_FLOOR),
            "타입/특징": _text(self.COL_FEATURE),
            "is_new": bool(_text(self.COL_NEW)),
            "price_change": int(sign * change_value),
        }
        return payload

    def _build_payload_lookup_by_url(self):
        if self._compact_duplicates:
            source = list(self._compact_rows_data)
        else:
            source = list(self.collected_data)
        lookup = {}
        for item in source:
            trade_type, _, price_int = self._extract_price_values(item)
            area_val = self._area_float(item.get("면적(평)", 0))
            price_change = self._normalize_price_change(item.get("price_change", item.get("가격변동", 0)))
            is_new = bool(item.get("is_new") or item.get("신규여부"))
            payload = self._build_row_payload_from_data(
                data=item,
                trade_type=trade_type,
                price_int=price_int,
                area_val=area_val,
                price_change=price_change,
                is_new=is_new,
            )
            url = get_article_url(item.get("단지ID", ""), item.get("매물ID", ""))
            if url:
                lookup[url] = payload
        return lookup

    def _apply_current_filter_to_row(self, row):
        text_lower = (self._pending_search_text or "").lower()
        searchable = self._row_search_cache[row] if row < len(self._row_search_cache) else ""
        hidden_by_text = bool(text_lower) and text_lower not in searchable
        hidden_by_advanced = False
        payload = self._row_payload_cache[row] if row < len(self._row_payload_cache) else None
        if self._advanced_filters and payload is not None:
            hidden_by_advanced = not self._check_advanced_filter(payload)
        hidden = hidden_by_text or hidden_by_advanced
        if self._row_hidden_state.get(row) != hidden:
            self.result_table.setRowHidden(row, hidden)
            self._row_hidden_state[row] = hidden

    def _set_result_row(self, row, data):
        trade_type, price_text, price_int = self._extract_price_values(data)
        area_val = self._area_float(data.get("면적(평)", 0))
        price_change = self._normalize_price_change(data.get("price_change", data.get("가격변동", 0)))

        show_new_badge = bool(settings.get("show_new_badge", True))
        show_price_change = bool(settings.get("show_price_change", True))
        try:
            price_change_threshold = max(0, int(settings.get("price_change_threshold", 0)))
        except (TypeError, ValueError):
            price_change_threshold = 0
        if price_change_threshold > 0 and abs(price_change) < price_change_threshold:
            price_change = 0

        self.result_table.setItem(row, self.COL_COMPLEX, QTableWidgetItem(str(data.get("단지명", ""))))
        self.result_table.setItem(row, self.COL_TRADE, QTableWidgetItem(trade_type))
        self.result_table.setItem(row, self.COL_PRICE, QTableWidgetItem(price_text))

        area_item = QTableWidgetItem(f"{area_val}평")
        area_item.setData(Qt.ItemDataRole.EditRole, float(area_val))
        self.result_table.setItem(row, self.COL_AREA, area_item)

        self.result_table.setItem(
            row, self.COL_PYEONG_PRICE, QTableWidgetItem(str(data.get("평당가_표시", "-")))
        )
        self.result_table.setItem(
            row, self.COL_FLOOR, QTableWidgetItem(str(data.get("층/방향", "")))
        )
        self.result_table.setItem(
            row, self.COL_FEATURE, QTableWidgetItem(str(data.get("타입/특징", "")))
        )

        dup_count = int(data.get("duplicate_count", 1) or 1)
        self.result_table.setItem(row, self.COL_DUP_COUNT, QTableWidgetItem(f"{dup_count}건"))

        is_new = bool(data.get("is_new") or data.get("신규여부"))
        new_badge_text = "N" if show_new_badge and is_new else ""
        self.result_table.setItem(row, self.COL_NEW, QTableWidgetItem(new_badge_text))

        if show_price_change and price_change != 0:
            change_text = PriceConverter.to_signed_string(price_change, zero_text="")
        else:
            change_text = ""
        self.result_table.setItem(row, self.COL_PRICE_CHANGE, QTableWidgetItem(change_text))

        collect_time = str(data.get("수집시각", ""))
        self.result_table.setItem(row, self.COL_COLLECTED_AT, QTableWidgetItem(collect_time))
        self.result_table.setItem(row, self.COL_LINK, QTableWidgetItem("🔗"))

        article_url = get_article_url(data.get("단지ID", ""), data.get("매물ID", ""))
        self.result_table.setItem(row, self.COL_URL, QTableWidgetItem(article_url))
        sort_item = QTableWidgetItem(str(price_int))
        sort_item.setData(Qt.ItemDataRole.EditRole, int(price_int))
        self.result_table.setItem(row, self.COL_PRICE_SORT, sort_item)
        payload = self._build_row_payload_from_data(
            data=data,
            trade_type=trade_type,
            price_int=price_int,
            area_val=area_val,
            price_change=price_change,
            is_new=is_new,
        )
        while len(self._row_payload_cache) <= row:
            self._row_payload_cache.append({})
        self._row_payload_cache[row] = payload

    def _append_rows_compact_batch(self, items):
        for item in items:
            key = self._get_compact_key(item)
            if key in self._compact_items_by_key:
                self._merge_compact_item(self._compact_items_by_key[key], item)
            else:
                compact_item = dict(item)
                compact_item["duplicate_count"] = 1
                self._compact_items_by_key[key] = compact_item
        self._render_compact_rows()

    def _sort_compact_rows(self, rows):
        criterion = self.combo_sort.currentText()
        key = criterion.split(" ")[0]
        is_asc = "↑" in criterion

        if key == "가격":
            rows.sort(key=lambda d: self._extract_price_values(d)[2], reverse=not is_asc)
        elif key == "면적":
            rows.sort(key=lambda d: self._area_float(d.get("면적(평)", 0)), reverse=not is_asc)
        elif key in ("거래", "거래유형"):
            rows.sort(key=lambda d: str(d.get("거래유형", "")), reverse=not is_asc)
        else:
            rows.sort(key=lambda d: str(d.get("단지명", "")), reverse=not is_asc)

    def _render_compact_rows(self):
        rows = list(self._compact_items_by_key.values())
        self._sort_compact_rows(rows)
        self._compact_rows_data = rows

        self.result_table.setUpdatesEnabled(False)
        self.result_table.setSortingEnabled(False)
        self.result_table.setRowCount(len(rows))
        self._row_search_cache = []
        self._row_payload_cache = []
        self._row_hidden_state = {}

        for row, data in enumerate(rows):
            self._set_result_row(row, data)
            self._sync_row_search_cache(row)
            self._apply_current_filter_to_row(row)

        self.result_table.setUpdatesEnabled(True)

    def _append_rows_batch(self, items):
        start_row = self.result_table.rowCount()
        row_count = len(items)
        if row_count == 0:
            return

        self.result_table.setSortingEnabled(False)
        self.result_table.setUpdatesEnabled(False)
        self.result_table.setRowCount(start_row + row_count)

        chunk_size = max(50, int(self._append_chunk_size))
        for start in range(0, row_count, chunk_size):
            end = min(row_count, start + chunk_size)
            for idx in range(start, end):
                row = start_row + idx
                data = dict(items[idx])
                data["duplicate_count"] = 1
                self._set_result_row(row, data)
                self._sync_row_search_cache(row)
                self._apply_current_filter_to_row(row)

        self.result_table.setUpdatesEnabled(True)

    def _on_complex_finished(self, name, cid, trade_types, count):
        try:
            self.db.add_crawl_history(name, cid, trade_types, int(count))
        except Exception as e:
            self.append_log(f"⚠️ 히스토리 저장 실패: {e}", 30)

    def _on_alert_triggered(self, complex_name, trade_type, price_text, area_pyeong, alert_id):
        self.append_log(
            f"🔔 알림 조건 충족: {complex_name} {trade_type} {price_text} ({area_pyeong:.1f}평)",
            30,
        )
        self.alert_triggered.emit(complex_name, trade_type, price_text, area_pyeong, int(alert_id or 0))

    def _update_stats_ui(self, stats):
        self.summary_card.update_stats(
            total=stats["total_found"],
            trade=stats["by_trade_type"].get("매매", 0),
            jeonse=stats["by_trade_type"].get("전세", 0),
            monthly=stats["by_trade_type"].get("월세", 0),
            filtered=stats["filtered_out"],
            new_count=stats.get("new_count", 0),
            price_up=stats.get("price_up", 0),
            price_down=stats.get("price_down", 0),
        )

    def _on_search_text_changed(self, text):
        self._pending_search_text = text
        self._search_timer.start()

    def _apply_search_filter(self):
        self._filter_results(self._pending_search_text)

    def _rebuild_row_search_cache_from_table(self):
        rows = self.result_table.rowCount()
        self._row_search_cache = []
        self._row_payload_cache = []
        self._row_hidden_state = {}
        payload_lookup = self._build_payload_lookup_by_url()
        for r in range(rows):
            values = []
            for c in range(self.result_table.columnCount()):
                item = self.result_table.item(r, c)
                if item:
                    values.append(item.text())
            self._row_search_cache.append(" ".join(values).lower())
            url_item = self.result_table.item(r, self.COL_URL)
            row_url = url_item.text().strip() if url_item else ""
            payload = payload_lookup.get(row_url) or self._build_row_payload_from_table(r)
            self._row_payload_cache.append(payload)

    @staticmethod
    def _is_default_advanced_filter(filters: dict) -> bool:
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

    @staticmethod
    def _floor_category(floor_text: str):
        text = str(floor_text or "")
        if "저층" in text:
            return "low"
        if "중층" in text:
            return "mid"
        if "고층" in text or "탑" in text:
            return "high"
        m = re.search(r"(\d+)\s*층", text)
        if not m:
            return None
        try:
            floor_num = int(m.group(1))
        except ValueError:
            return None
        if floor_num <= 3:
            return "low"
        if floor_num <= 10:
            return "mid"
        return "high"

    def _check_advanced_filter(self, d):
        if not self._advanced_filters:
            return True
        f = self._advanced_filters

        price_int = d.get("price_int")
        if price_int is None:
            price_text = d.get("매매가") or d.get("보증금") or ""
            price_int = PriceConverter.to_int(price_text)
        if price_int < f.get("price_min", 0) or price_int > f.get("price_max", 9999999):
            return False

        area = self._area_float(d.get("면적(평)", 0))
        if area < f.get("area_min", 0) or area > f.get("area_max", 9999999):
            return False

        floor_category = self._floor_category(d.get("층/방향", ""))
        if floor_category == "low" and not f.get("floor_low", True):
            return False
        if floor_category == "mid" and not f.get("floor_mid", True):
            return False
        if floor_category == "high" and not f.get("floor_high", True):
            return False

        if f.get("only_new") and not bool(d.get("is_new", False)):
            return False

        price_change = d.get("price_change", 0)
        if isinstance(price_change, str):
            try:
                sign = -1 if str(price_change).strip().startswith("-") else 1
                price_change = sign * PriceConverter.to_int(str(price_change).strip().lstrip("+-"))
            except Exception:
                price_change = 0

        if f.get("only_price_down") and price_change >= 0:
            return False
        if f.get("only_price_change") and price_change == 0:
            return False

        text_blob = " ".join(
            [
                str(d.get("단지명", "")),
                str(d.get("타입/특징", "")),
                str(d.get("층/방향", "")),
            ]
        ).lower()
        include_keywords = [k.lower() for k in f.get("include_keywords", [])]
        exclude_keywords = [k.lower() for k in f.get("exclude_keywords", [])]
        if include_keywords and not any(k in text_blob for k in include_keywords):
            return False
        if exclude_keywords and any(k in text_blob for k in exclude_keywords):
            return False
        return True

    def _advanced_filtered_data_for_cards(self):
        if self._compact_duplicates:
            base = list(self._compact_rows_data)
        else:
            base = list(self.collected_data)
        if not self._advanced_filters:
            return base
        filtered = []
        for item in base:
            trade_type, _, price_int = self._extract_price_values(item)
            area_val = self._area_float(item.get("면적(평)", 0))
            price_change = self._normalize_price_change(item.get("price_change", item.get("가격변동", 0)))
            is_new = bool(item.get("is_new") or item.get("신규여부"))
            payload = self._build_row_payload_from_data(
                data=item,
                trade_type=trade_type,
                price_int=price_int,
                area_val=area_val,
                price_change=price_change,
                is_new=is_new,
            )
            if self._check_advanced_filter(payload):
                filtered.append(item)
        return filtered

    def _apply_card_filters(self, text):
        if self._advanced_filters:
            self.card_view.set_data(self._advanced_filtered_data_for_cards())
        elif self._compact_duplicates:
            self.card_view.set_data(list(self._compact_rows_data))
        else:
            self.card_view.set_data(list(self.collected_data))
        self.card_view.filter_cards(text)

    def open_advanced_filter_dialog(self):
        dialog = AdvancedFilterDialog(self, current_filters=self._advanced_filters)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected = dialog.get_filters()
            if selected and not self._is_default_advanced_filter(selected):
                self._advanced_filters = selected
                self.status_message.emit("고급 필터가 적용되었습니다.")
            else:
                self._advanced_filters = None
                self.status_message.emit("고급 필터가 초기화되었습니다.")
            self.btn_clear_advanced_filter.setEnabled(self._advanced_filters is not None)
            self._filter_results(self._pending_search_text)

    def clear_advanced_filters(self):
        self._advanced_filters = None
        if hasattr(self, "btn_clear_advanced_filter"):
            self.btn_clear_advanced_filter.setEnabled(False)
        self.status_message.emit("고급 필터를 해제했습니다.")
        self._filter_results(self._pending_search_text)

    def _filter_results(self, text):
        self._pending_search_text = text or ""
        rows = self.result_table.rowCount()
        for r in range(rows):
            if r >= len(self._row_search_cache):
                values = []
                for c in range(self.result_table.columnCount()):
                    item = self.result_table.item(r, c)
                    if item:
                        values.append(item.text())
                self._row_search_cache.append(" ".join(values).lower())
            if r >= len(self._row_payload_cache):
                self._row_payload_cache.append(self._build_row_payload_from_table(r))
            self._apply_current_filter_to_row(r)
            
        # Card filtering
        self._apply_card_filters(self._pending_search_text)

    def _sort_results(self, criterion):
        col_map = {
            "단지명": self.COL_COMPLEX,
            "가격": self.COL_PRICE_SORT,
            "면적": self.COL_AREA,
            "거래유형": self.COL_TRADE,
            "거래": self.COL_TRADE,
        }
        is_asc = "↑" in criterion
        key = criterion.split(" ")[0]
        if self._compact_duplicates:
            self._render_compact_rows()
            self._apply_card_filters(self._pending_search_text)
            return

        col = col_map.get(key, self.COL_COMPLEX)
        order = Qt.SortOrder.AscendingOrder if is_asc else Qt.SortOrder.DescendingOrder
        self.result_table.sortItems(col, order)
        self._rebuild_row_search_cache_from_table()
        self._filter_results(self._pending_search_text)

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
        rows = []
        for (cid, ttype, pyeong), prices in grouped.items():
            if prices:
                min_price = min(prices)
                max_price = max(prices)
                avg_price = sum(prices) // len(prices)
                rows.append((cid, ttype, pyeong, min_price, max_price, avg_price, len(prices)))

        saved = self.db.add_price_snapshots_bulk(rows) if rows else 0
        self.append_log(f"📊 가격 스냅샷 {saved}건 저장", 10)


    def get_filter_state(self):
        """현재 필터 상태 반환"""
        return {
            "area": {
                "enabled": self.check_area_filter.isChecked(),
                "min": self.spin_area_min.value(),
                "max": self.spin_area_max.value()
            },
            "price": {
                "enabled": self.check_price_filter.isChecked(),
                "trade_min": self.spin_trade_min.value(),
                "trade_max": self.spin_trade_max.value(),
                # Add other price fields if needed, or simplify preset structure
                # The preset manager likely expects a specific structure.
                # Just mapping common fields.
            },
            # Add other settings...
        }

    def set_filter_state(self, state):
        """필터 상태 적용"""
        if "area" in state:
            area = state["area"]
            self.check_area_filter.setChecked(area.get("enabled", False))
            self.spin_area_min.setValue(area.get("min", 0))
            self.spin_area_max.setValue(area.get("max", 0))
        # Handle other fields...
        
    def show_save_menu(self):
        menu = QMenu(self)
        menu.addAction("📊 Excel로 저장", self.save_excel)
        menu.addAction("📄 CSV로 저장", self.save_csv)
        menu.addAction("📋 JSON으로 저장", self.save_json)
        menu.addSeparator()
        menu.addAction("⚙️ 엑셀 템플릿 설정", self._show_excel_template_dialog)
        menu.exec(self.btn_save.mapToGlobal(self.btn_save.rect().bottomLeft()))

    def save_excel(self):
        if not self.collected_data: return
        path, _ = QFileDialog.getSaveFileName(self, "Excel 저장", f"부동산_{DateTimeHelper.file_timestamp()}.xlsx", "Excel (*.xlsx)")
        if path:
            from pathlib import Path
            template = settings.get("excel_template")
            try:
                if DataExporter(self.collected_data).to_excel(Path(path), template):
                    QMessageBox.information(self, "저장 완료", f"Excel 파일 저장 완료!\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "저장 실패", f"Excel 저장 중 오류가 발생했습니다:\n{e}")
                logger.error(f"Excel Save Error: {e}")

    def save_csv(self):
        if not self.collected_data: return
        path, _ = QFileDialog.getSaveFileName(self, "CSV 저장", f"부동산_{DateTimeHelper.file_timestamp()}.csv", "CSV (*.csv)")
        if path:
            from pathlib import Path
            template = settings.get("excel_template")
            try:
                if DataExporter(self.collected_data).to_csv(Path(path), template):
                    QMessageBox.information(self, "저장 완료", f"CSV 파일 저장 완료!\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "저장 실패", f"CSV 저장 중 오류가 발생했습니다:\n{e}")
                logger.error(f"CSV Save Error: {e}")

    def save_json(self):
        if not self.collected_data: return
        path, _ = QFileDialog.getSaveFileName(self, "JSON 저장", f"부동산_{DateTimeHelper.file_timestamp()}.json", "JSON (*.json)")
        if path:
            from pathlib import Path
            try:
                if DataExporter(self.collected_data).to_json(Path(path)):
                    QMessageBox.information(self, "저장 완료", f"JSON 파일 저장 완료!\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "저장 실패", f"JSON 저장 중 오류가 발생했습니다:\n{e}")
                logger.error(f"JSON Save Error: {e}")

    def _show_excel_template_dialog(self):
        current_template = settings.get("excel_template")
        dlg = ExcelTemplateDialog(self, current_template=current_template)
        dlg.template_saved.connect(lambda t: settings.set("excel_template", t))
        dlg.exec()
        
    def _open_article_url(self):
        row = self.result_table.currentRow()
        if row < 0:
            return
        item = self.result_table.item(row, self.COL_URL)
        url = item.text() if item else ""
        if url:
            webbrowser.open(url)
