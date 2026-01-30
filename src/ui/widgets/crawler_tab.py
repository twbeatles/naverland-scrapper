from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, 
    QLineEdit, QComboBox, QSpinBox, QCheckBox, QTableWidget, QTableWidgetItem, 
    QGroupBox, QSplitter, QScrollArea, QFrame, QHeaderView, QTabWidget, 
    QStackedWidget, QTextBrowser, QDialog, QMessageBox, QFileDialog, QSizePolicy, QStyle, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
import webbrowser
import logging
import re

from src.utils.constants import SHORTCUTS, CRAWL_SPEED_PRESETS
from src.utils.helpers import PriceConverter, DateTimeHelper, get_article_url
from src.core.managers import SettingsManager
from src.core.crawler import CrawlerThread
from src.ui.widgets.components import (
    SearchBar, SpeedSlider, ProgressWidget, SummaryCard
)
from src.ui.widgets.dashboard import CardViewWidget
from src.ui.widgets.dialogs import MultiSelectDialog, URLBatchDialog, RecentSearchDialog
from src.ui.styles import COLORS
from src.utils.logger import get_logger

settings = SettingsManager()
logger = get_logger("CrawlerTab")

class CrawlerTab(QWidget):
    """크롤링 및 데이터 수집 탭"""
    
    # Signals
    data_collected = pyqtSignal(list)  # 수집 완료 시 데이터 전송
    crawling_started = pyqtSignal()
    crawling_stopped = pyqtSignal()
    status_message = pyqtSignal(str)
    
    def __init__(self, db, history_manager=None, theme="dark", parent=None):
        super().__init__(parent)
        self.db = db
        self.history_manager = history_manager
        self.current_theme = theme
        self.crawler_thread = None
        self.collected_data = []
        self.grouped_rows = {}
        
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
        spl.addWidget(self.speed_slider)
        spg.setLayout(spl)
        layout.addWidget(spg)

    def _setup_action_group(self, layout):
        eg = QGroupBox("6️⃣ 실행")
        el = QHBoxLayout()
        self.btn_start = QPushButton("▶️ 크롤링 시작")
        self.btn_start.setObjectName("startButton")
        self.btn_start.setMinimumHeight(45)
        self.btn_start.clicked.connect(self.start_crawling)
        
        self.btn_stop = QPushButton("⏹️ 중지")
        self.btn_stop.setObjectName("stopButton")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_crawling)
        
        # self.btn_save = QPushButton("💾 저장") # Save logic handled by App or separate Exporter
        # self.btn_save.setObjectName("saveButton")
        # self.btn_save.setEnabled(False)
        
        el.addWidget(self.btn_start, 2)
        el.addWidget(self.btn_stop, 1)
        # el.addWidget(self.btn_save, 1)
        eg.setLayout(el)
        layout.addWidget(eg)

    def _setup_result_area(self, layout):
        # Search & Sort
        search_sort = QHBoxLayout()
        self.result_search = SearchBar("결과 검색...")
        self.result_search.search_changed.connect(self._filter_results)
        search_sort.addWidget(self.result_search, 3)
        
        search_sort.addWidget(QLabel("정렬:"))
        self.combo_sort = QComboBox()
        self.combo_sort.addItems(["가격 ↑", "가격 ↓", "면적 ↑", "면적 ↓", "단지명 ↑", "단지명 ↓"])
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
        self.result_table.setColumnCount(13)
        self.result_table.setHorizontalHeaderLabels([
            "단지명", "거래", "가격", "면적", "평당가", "층/방향", "특징", 
            "🆕", "📊 변동", "시각", "링크", "URL", "가격(숫자)"
        ])
        self.result_table.setColumnHidden(11, True)
        self.result_table.setColumnHidden(12, True)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.doubleClicked.connect(self._open_article_url)
        
        # Card View
        self.view_stack = QStackedWidget()
        self.view_stack.addWidget(self.result_table)
        
        self.card_view = CardViewWidget(theme=self.current_theme)
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

    def set_theme(self, theme):
        self.current_theme = theme
        if hasattr(self, 'summary_card'):
            self.summary_card.set_theme(theme)
        if hasattr(self, 'card_view'):
            self.card_view.is_dark = (theme == "dark")
        
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
            
    def _toggle_view_mode(self):
        if self.btn_view_mode.isChecked():
            self.view_mode = "card"
            self.btn_view_mode.setText("📄 테이블")
            self.view_stack.setCurrentWidget(self.card_view)
            if self.collected_data:
                self.card_view.set_data(self.collected_data)
        else:
            self.view_mode = "table"
            self.btn_view_mode.setText("🃏 카드뷰")
            self.view_stack.setCurrentWidget(self.result_table)
        settings.set("view_mode", self.view_mode)

    def start_crawling(self):
        if self.table_list.rowCount() == 0:
            QMessageBox.warning(self, "경고", "크롤링할 단지를 추가해주세요.")
            return

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.log_browser.clear()
        self.progress_widget.reset()
        self.summary_card.reset()
        self.collected_data = []
        self.result_table.setRowCount(0)
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
            
        area_filter = {"enabled": self.check_area_filter.isChecked(), "min": self.spin_area_min.value(), "max": self.spin_area_max.value()}
        price_filter = {
            "enabled": self.check_price_filter.isChecked(),
            "매매": {"min": self.spin_trade_min.value(), "max": self.spin_trade_max.value()},
            "전세": {"min": self.spin_jeonse_min.value(), "max": self.spin_jeonse_max.value()},
            "월세": {"min": self.spin_monthly_min.value(), "max": self.spin_monthly_max.value()}
        }
        
        # Start Thread
        self.crawler_thread = CrawlerThread(
            target_list, trade_types, area_filter, price_filter, self.db,
            speed=self.speed_slider.current_speed()
        )
        self.crawler_thread.log_signal.connect(self.append_log)
        self.crawler_thread.progress_signal.connect(self.progress_widget.update_progress)
        self.crawler_thread.item_signal.connect(self._add_result)
        self.crawler_thread.stats_signal.connect(self._update_stats_ui)
        self.crawler_thread.finished_signal.connect(self._on_crawl_finished)
        self.crawler_thread.start()
        
        self.crawling_started.emit()

    def stop_crawling(self):
        if self.crawler_thread and self.crawler_thread.isRunning():
            self.crawler_thread.stop()
            self.append_log("🛑 중지 요청 중...", 30)
            self.btn_stop.setEnabled(False)

    def _on_crawl_finished(self, data):
        try:
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.progress_widget.complete()
            self.append_log(f"✅ 크롤링 완료: 총 {len(data)}건 수집")
            
            # DB Write
            try:
                self._save_price_snapshots()
            except Exception as e:
                self.append_log(f"⚠️ 가격 스냅샷 저장 실패: {e}", 30)
            
            self.data_collected.emit(data) # Notify App
            self.crawling_stopped.emit()
            
        except Exception as e:
            self.append_log(f"❌ 크롤링 마무리 중 오류: {e}", 40)
            logger.error(f"Crawl finish handler failed: {e}")
            # Ensure buttons are reset
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)

    def append_log(self, msg, level=20):
        theme_colors = COLORS[self.current_theme]
        color = theme_colors["text_primary"]
        
        if level >= 40: color = theme_colors["error"]
        elif level >= 30: color = theme_colors["warning"]
        elif level == 10: color = theme_colors["text_secondary"]
        
        self.log_browser.append(f'<span style="color:{color}">{msg}</span>')
        # Scroll to bottom
        sb = self.log_browser.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _add_result(self, data):
        self.collected_data.append(data)
        
        # Table Update
        row = self.result_table.rowCount()
        self.result_table.insertRow(row)
        
        self.result_table.setItem(row, 0, QTableWidgetItem(data['단지명']))
        self.result_table.setItem(row, 1, QTableWidgetItem(data['거래유형']))
        
        price_text = data['매매가'] if data['거래유형'] == '매매' else data['보증금']
        if data['월세']: price_text += f"/{data['월세']}"
        self.result_table.setItem(row, 2, QTableWidgetItem(price_text))
        
        self.result_table.setItem(row, 3, QTableWidgetItem(f"{data['면적(평)']}평"))
        self.result_table.setItem(row, 4, QTableWidgetItem(data['평당가_표시']))
        self.result_table.setItem(row, 5, QTableWidgetItem(data['층/방향']))
        self.result_table.setItem(row, 6, QTableWidgetItem(data['타입/특징']))
        self.result_table.setItem(row, 7, QTableWidgetItem("N" if data.get("신규여부") else ""))
        
        # Hidden columns
        self.result_table.setItem(row, 11, QTableWidgetItem(get_article_url(data['단지ID'], data['매물ID'])))
        
        # Card View Update (Optimize: don't reload all on every item)
        if self.view_mode == "card":
             # For performance, maybe update card view in batches or at end?
             # But user wants real-time.
             logger.debug("Card view 업데이트는 별도 신호/토글에서 처리됨")

    def _update_stats_ui(self, stats):
        self.summary_card.update_stats(
            total=stats["total_found"],
            trade=stats["by_trade_type"].get("매매", 0),
            jeonse=stats["by_trade_type"].get("전세", 0),
            monthly=stats["by_trade_type"].get("월세", 0),
            filtered=stats["filtered_out"]
        )

    def _filter_results(self, text):
        # Table filtering
        rows = self.result_table.rowCount()
        for r in range(rows):
            match = False
            for c in range(self.result_table.columnCount()):
                item = self.result_table.item(r, c)
                if item and text.lower() in item.text().lower():
                    match = True
                    break
            self.result_table.setRowHidden(r, not match)
            
        # Card filtering
        self.card_view.filter_cards(text)

    def _sort_results(self, criterion):
        col_map = {
            "단지명": 0, "가격": 12, "면적": 3
        }
        is_asc = "↑" in criterion
        key = criterion.split(" ")[0]
        col = col_map.get(key, 0)
        
        order = Qt.SortOrder.AscendingOrder if is_asc else Qt.SortOrder.DescendingOrder
        self.result_table.sortItems(col, order)

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
        
    def _open_article_url(self):
        row = self.result_table.currentRow()
        url = self.result_table.item(row, 11).text()
        if url: webbrowser.open(url)
