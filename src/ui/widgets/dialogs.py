<<<<<<< HEAD
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, 
    QComboBox, QDoubleSpinBox, QSpinBox, QGroupBox, QGridLayout, QTableWidget, 
    QHeaderView, QCheckBox, QTableWidgetItem, QDialogButtonBox, QTextBrowser, 
    QMessageBox, QListWidgetItem, QAbstractItemView, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from src.core.managers import SettingsManager
from src.core.parser import NaverURLParser
from src.core.export import ExcelTemplate
from src.utils.constants import APP_TITLE, APP_VERSION, SHORTCUTS, CRAWL_SPEED_PRESETS
from PyQt6.QtWidgets import QApplication

class PresetDialog(QDialog):
    def __init__(self, parent=None, preset_manager=None):
        super().__init__(parent)
        self.preset_manager = preset_manager
        self.selected_preset = None
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle("📁 필터 프리셋")
        self.setMinimumSize(400, 350)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("저장된 프리셋:"))
        self.list = QListWidget()
        self.list.setAlternatingRowColors(True)
        self.list.itemDoubleClicked.connect(self._load)
        layout.addWidget(self.list)
        btn_layout = QHBoxLayout()
        btn_load = QPushButton("📂 불러오기")
        btn_load.clicked.connect(self._load)
        btn_del = QPushButton("🗑️ 삭제")
        btn_del.clicked.connect(self._delete)
        btn_layout.addWidget(btn_load)
        btn_layout.addWidget(btn_del)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        self._refresh()
    
    def _refresh(self):
        self.list.clear()
        if self.preset_manager:
            for name in self.preset_manager.get_all_names():
                self.list.addItem(name)
    
    def _load(self):
        if item := self.list.currentItem():
            self.selected_preset = item.text()
            self.accept()
    
    def _delete(self):
        if (item := self.list.currentItem()) and self.preset_manager:
            self.preset_manager.delete(item.text())
            self._refresh()

class AlertSettingDialog(QDialog):
    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        self.db = db
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle("🔔 알림 설정")
        self.setMinimumSize(650, 550)
        layout = QVBoxLayout(self)
        
        # 추가 폼
        add_g = QGroupBox("새 알림 추가")
        add_l = QGridLayout()
        add_l.addWidget(QLabel("단지:"), 0, 0)
        self.combo_complex = QComboBox()
        for _, name, cid, _ in (self.db.get_all_complexes() if self.db else []):
            self.combo_complex.addItem(f"{name} ({cid})", (cid, name))
        add_l.addWidget(self.combo_complex, 0, 1, 1, 3)
        
        add_l.addWidget(QLabel("유형:"), 1, 0)
        self.combo_type = QComboBox()
        self.combo_type.addItems(["매매", "전세", "월세"])
        add_l.addWidget(self.combo_type, 1, 1)
        
        add_l.addWidget(QLabel("면적(평):"), 2, 0)
        self.spin_area_min = QDoubleSpinBox()
        self.spin_area_min.setRange(0, 200)
        add_l.addWidget(self.spin_area_min, 2, 1)
        add_l.addWidget(QLabel("~"), 2, 2)
        self.spin_area_max = QDoubleSpinBox()
        self.spin_area_max.setRange(0, 200)
        self.spin_area_max.setValue(100)
        add_l.addWidget(self.spin_area_max, 2, 3)
        
        add_l.addWidget(QLabel("가격(만원):"), 3, 0)
        self.spin_price_min = QSpinBox()
        self.spin_price_min.setRange(0, 999999)
        self.spin_price_min.setSingleStep(1000)
        add_l.addWidget(self.spin_price_min, 3, 1)
        add_l.addWidget(QLabel("~"), 3, 2)
        self.spin_price_max = QSpinBox()
        self.spin_price_max.setRange(0, 999999)
        self.spin_price_max.setValue(100000)
        self.spin_price_max.setSingleStep(1000)
        add_l.addWidget(self.spin_price_max, 3, 3)
        
        btn_add = QPushButton("➕ 추가")
        btn_add.clicked.connect(self._add)
        add_l.addWidget(btn_add, 4, 0, 1, 4)
        add_g.setLayout(add_l)
        layout.addWidget(add_g)
        
        layout.addWidget(QLabel("설정된 알림:"))
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["단지", "유형", "면적", "가격", "활성", "삭제"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
        self._load()
    
    def _add(self):
        if self.combo_complex.count() == 0: return
        data = self.combo_complex.currentData()
        if not data: return
        cid, name = data
        if self.db.add_alert_setting(cid, name, self.combo_type.currentText(),
            self.spin_area_min.value(), self.spin_area_max.value(),
            self.spin_price_min.value(), self.spin_price_max.value()):
            self._load()
    
    def _load(self):
        self.table.setRowCount(0)
        if not self.db: return
        for aid, cid, name, tt, amin, amax, pmin, pmax, enabled in self.db.get_all_alert_settings():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(name or cid))
            self.table.setItem(row, 1, QTableWidgetItem(tt))
            self.table.setItem(row, 2, QTableWidgetItem(f"{amin}~{amax}평"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{pmin:,}~{pmax:,}만"))
            check = QCheckBox()
            check.setChecked(enabled == 1)
            check.stateChanged.connect(lambda s, a=aid: self.db.toggle_alert_setting(a, s == Qt.CheckState.Checked.value))
            self.table.setCellWidget(row, 4, check)
            btn = QPushButton("🗑️")
            btn.clicked.connect(lambda _, a=aid: self._delete(a))
            self.table.setCellWidget(row, 5, btn)
    
    def _delete(self, aid):
        self.db.delete_alert_setting(aid)
        self._load()

class AdvancedFilterDialog(QDialog):
    """고급 결과 필터 다이얼로그 (v7.3)"""
    filter_applied = pyqtSignal(dict)
    
    def __init__(self, parent=None, current_filters=None):
        super().__init__(parent)
        self.setWindowTitle("🔍 고급 필터")
        self.setMinimumWidth(450)
        self._filters = None
        self._setup_ui()
        if current_filters:
            self._apply_filters_to_ui(current_filters)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 가격 필터
        price_group = QGroupBox("💰 가격 필터")
        pg = QGridLayout(price_group)
        pg.addWidget(QLabel("최소 가격:"), 0, 0)
        self.price_min = QSpinBox()
        self.price_min.setRange(0, 9999999)
        self.price_min.setSuffix(" 만원")
        self.price_min.setSpecialValueText("제한 없음")
        pg.addWidget(self.price_min, 0, 1)
        pg.addWidget(QLabel("최대 가격:"), 0, 2)
        self.price_max = QSpinBox()
        self.price_max.setRange(0, 9999999)
        self.price_max.setValue(9999999)
        self.price_max.setSuffix(" 만원")
        self.price_max.setSpecialValueText("제한 없음")
        pg.addWidget(self.price_max, 0, 3)
        layout.addWidget(price_group)
        
        # 면적 필터
        area_group = QGroupBox("📐 면적 필터")
        ag = QGridLayout(area_group)
        ag.addWidget(QLabel("최소 면적:"), 0, 0)
        self.area_min = QDoubleSpinBox()
        self.area_min.setRange(0, 500)
        self.area_min.setSuffix(" 평")
        self.area_min.setSpecialValueText("제한 없음")
        ag.addWidget(self.area_min, 0, 1)
        ag.addWidget(QLabel("최대 면적:"), 0, 2)
        self.area_max = QDoubleSpinBox()
        self.area_max.setRange(0, 500)
        self.area_max.setValue(500)
        self.area_max.setSuffix(" 평")
        ag.addWidget(self.area_max, 0, 3)
        layout.addWidget(area_group)
        
        # 층수 필터
        floor_group = QGroupBox("🏢 층수 필터")
        fg = QHBoxLayout(floor_group)
        self.floor_low = QCheckBox("저층")
        self.floor_mid = QCheckBox("중층")
        self.floor_high = QCheckBox("고층")
        self.floor_low.setChecked(True)
        self.floor_mid.setChecked(True)
        self.floor_high.setChecked(True)
        fg.addWidget(self.floor_low)
        fg.addWidget(self.floor_mid)
        fg.addWidget(self.floor_high)
        fg.addStretch()
        layout.addWidget(floor_group)
        
        # 특수 필터
        special_group = QGroupBox("⭐ 특수 필터")
        sg = QHBoxLayout(special_group)
        self.only_new = QCheckBox("🆕 신규 매물만")
        self.only_price_down = QCheckBox("📉 가격 하락만")
        self.only_price_change = QCheckBox("📊 가격 변동만")
        sg.addWidget(self.only_new)
        sg.addWidget(self.only_price_down)
        sg.addWidget(self.only_price_change)
        sg.addStretch()
        layout.addWidget(special_group)
        
        # 키워드 필터
        keyword_group = QGroupBox("🔤 키워드 필터")
        kg = QVBoxLayout(keyword_group)
        kg.addWidget(QLabel("포함 키워드 (쉼표로 구분):"))
        self.include_keywords = QLineEdit()
        self.include_keywords.setPlaceholderText("예: 급매, 역세권, 올수리")
        kg.addWidget(self.include_keywords)
        kg.addWidget(QLabel("제외 키워드 (쉼표로 구분):"))
        self.exclude_keywords = QLineEdit()
        self.exclude_keywords.setPlaceholderText("예: 반지하, 탑층")
        kg.addWidget(self.exclude_keywords)
        layout.addWidget(keyword_group)
        
        # 버튼
        btn_layout = QHBoxLayout()
        btn_reset = QPushButton("초기화")
        btn_reset.clicked.connect(self._reset)
        btn_apply = QPushButton("적용")
        btn_apply.clicked.connect(self._apply)
        btn_apply.setDefault(True)
        btn_layout.addWidget(btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_apply)
        layout.addLayout(btn_layout)
    
    def _reset(self):
        self.price_min.setValue(0)
        self.price_max.setValue(9999999)
        self.area_min.setValue(0)
        self.area_max.setValue(500)
        self.floor_low.setChecked(True)
        self.floor_mid.setChecked(True)
        self.floor_high.setChecked(True)
        self.only_new.setChecked(False)
        self.only_price_down.setChecked(False)
        self.only_price_change.setChecked(False)
        self.include_keywords.clear()
        self.exclude_keywords.clear()
        self._filters = None
    
    def _apply(self):
        filters = {
            'price_min': self.price_min.value(),
            'price_max': self.price_max.value(),
            'area_min': self.area_min.value(),
            'area_max': self.area_max.value(),
            'floor_low': self.floor_low.isChecked(),
            'floor_mid': self.floor_mid.isChecked(),
            'floor_high': self.floor_high.isChecked(),
            'only_new': self.only_new.isChecked(),
            'only_price_down': self.only_price_down.isChecked(),
            'only_price_change': self.only_price_change.isChecked(),
            'include_keywords': [k.strip() for k in self.include_keywords.text().split(',') if k.strip()],
            'exclude_keywords': [k.strip() for k in self.exclude_keywords.text().split(',') if k.strip()],
        }
        self._filters = filters
        self.filter_applied.emit(filters)
        self.accept()

    def _apply_filters_to_ui(self, filters: dict):
        try:
            self.price_min.setValue(int(filters.get("price_min", self.price_min.value())))
            self.price_max.setValue(int(filters.get("price_max", self.price_max.value())))
            self.area_min.setValue(float(filters.get("area_min", self.area_min.value())))
            self.area_max.setValue(float(filters.get("area_max", self.area_max.value())))
            self.floor_low.setChecked(bool(filters.get("floor_low", True)))
            self.floor_mid.setChecked(bool(filters.get("floor_mid", True)))
            self.floor_high.setChecked(bool(filters.get("floor_high", True)))
            self.only_new.setChecked(bool(filters.get("only_new", False)))
            self.only_price_down.setChecked(bool(filters.get("only_price_down", False)))
            self.only_price_change.setChecked(bool(filters.get("only_price_change", False)))
            self.include_keywords.setText(", ".join(filters.get("include_keywords", [])))
            self.exclude_keywords.setText(", ".join(filters.get("exclude_keywords", [])))
        except Exception:
            pass

    def get_filters(self):
        return self._filters

class URLParsingWorker(QThread):
    """URL 파싱 및 단지명 조회를 위한 워커 스레드 (v7.3)"""
    ids_extracted = pyqtSignal(list)      # [(source, cid), ...]
    name_fetched = pyqtSignal(int, str, str) # row, name, status
    progress = pyqtSignal(int, int)       # current, total
    finished = pyqtSignal()

    def __init__(self, text):
        super().__init__()
        self.text = text
        self.is_running = True

    def run(self):
        # 1. ID 추출 (빠름)
        results = NaverURLParser.extract_from_text(self.text)
        self.ids_extracted.emit(results)
        
        total = len(results)
        if total == 0:
            self.finished.emit()
            return
            
        # 2. 단지명 조회 (느림 - 네트워크 통신)
        for i, (source, cid) in enumerate(results):
            if not self.is_running: break
            
            # 단지명 조회 (블로킹)
            name = NaverURLParser.fetch_complex_name(cid)
            status = "✅ 확인됨" if not name.startswith("단지_") else "⚠️ 이름 미확인"
            
            self.name_fetched.emit(i, name, status)
            self.progress.emit(i + 1, total)
            
        self.finished.emit()

    def stop(self):
        self.is_running = False


class URLBatchDialog(QDialog):
    """URL 일괄 등록 다이얼로그 (v7.3)"""
    complexes_added = pyqtSignal(list)  # [(name, id), ...]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔗 URL 일괄 등록")
        self.setMinimumSize(600, 500)
        self.worker = None
        self._selected_complexes = []
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 안내
        info = QLabel(
            "네이버 부동산 URL 또는 단지 ID를 붙여넣으세요.\n"
            "여러 개를 한 번에 입력할 수 있습니다 (한 줄에 하나씩)."
        )
        info.setStyleSheet("color: #888; padding: 10px;")
        layout.addWidget(info)
        
        # 입력 영역
        self.input_text = QTextBrowser()
        self.input_text.setReadOnly(False)
        self.input_text.setPlaceholderText(
            "예시:\n"
            "https://new.land.naver.com/complexes/102378\n"
            "https://land.naver.com/complex?complexNo=123456\n"
            "123456\n"
            "789012"
        )
        self.input_text.setAcceptRichText(False)
        layout.addWidget(self.input_text, 2)
        
        # 파싱 버튼
        self.btn_parse = QPushButton("🔍 URL 분석")
        self.btn_parse.clicked.connect(self._parse_urls)
        layout.addWidget(self.btn_parse)
        
        # 결과 테이블
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(4)
        self.result_table.setHorizontalHeaderLabels(["✓", "단지 ID", "단지명", "상태"])
        self.result_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.result_table.setColumnWidth(0, 30)
        self.result_table.setColumnWidth(1, 100)
        self.result_table.setColumnWidth(3, 100)
        layout.addWidget(self.result_table, 3)
        
        # 진행 상태
        self.status_bar = QProgressBar()
        self.status_bar.setRange(0, 100)
        self.status_bar.setValue(0)
        self.status_bar.setVisible(False)
        layout.addWidget(self.status_bar)
        
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        # 버튼
        btn_layout = QHBoxLayout()
        btn_select_all = QPushButton("전체 선택")
        btn_select_all.clicked.connect(self._select_all)
        self.btn_add = QPushButton("📥 선택 항목 추가")
        self.btn_add.clicked.connect(self._add_selected)
        btn_layout.addWidget(btn_select_all)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_add)
        layout.addLayout(btn_layout)
    
    def _parse_urls(self):
        text = self.input_text.toPlainText()
        if not text.strip():
            QMessageBox.warning(self, "입력 필요", "URL 또는 단지 ID를 입력하세요.")
            return
        
        self.btn_parse.setEnabled(False)
        self.btn_add.setEnabled(False)
        self.result_table.setRowCount(0)
        self.status_bar.setVisible(True)
        self.status_bar.setValue(0)
        self.status_label.setText("🔍 분석 중...")
        
        self.worker = URLParsingWorker(text)
        self.worker.ids_extracted.connect(self._on_ids_extracted)
        self.worker.name_fetched.connect(self._on_name_fetched)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()
        
    def _on_ids_extracted(self, results):
        if not results:
            QMessageBox.warning(self, "파싱 실패", "유효한 URL이나 단지 ID를 찾지 못했습니다.")
            self.status_label.setText("결과 없음")
            return

        self.status_label.setText(f"🔍 {len(results)}개 단지 발견, 이름 조회 중...")
        self.status_bar.setRange(0, len(results))
        
        for source, cid in results:
            row = self.result_table.rowCount()
            self.result_table.insertRow(row)
            
            # 체크박스
            chk = QCheckBox()
            chk.setChecked(True)
            self.result_table.setCellWidget(row, 0, chk)
            
            # 단지 ID
            self.result_table.setItem(row, 1, QTableWidgetItem(cid))
            
            # 단지명 (로딩 중)
            self.result_table.setItem(row, 2, QTableWidgetItem("⌛ 조회 중..."))
            
            # 상태
            self.result_table.setItem(row, 3, QTableWidgetItem("-"))
            
    def _on_name_fetched(self, row, name, status):
        if row < self.result_table.rowCount():
             self.result_table.setItem(row, 2, QTableWidgetItem(name))
             self.result_table.setItem(row, 3, QTableWidgetItem(status))
    
    def _on_progress(self, current, total):
        self.status_bar.setValue(current)
        self.status_label.setText(f"진행 중: {current}/{total}")

    def _on_finished(self):
        self.btn_parse.setEnabled(True)
        self.btn_add.setEnabled(True)
        self.status_bar.setVisible(False)
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        
        if self.result_table.rowCount() > 0:
            self.status_label.setText(f"✅ {self.result_table.rowCount()}개 단지 분석 완료")
        else:
            self.status_label.setText("대기 중")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(2000)
        event.accept()

    def _select_all(self):
        for row in range(self.result_table.rowCount()):
            chk = self.result_table.cellWidget(row, 0)
            if chk:
                chk.setChecked(True)
    
    def _add_selected(self):
        selected = []
        for row in range(self.result_table.rowCount()):
            chk = self.result_table.cellWidget(row, 0)
            if chk and chk.isChecked():
                cid = self.result_table.item(row, 1).text()
                name_item = self.result_table.item(row, 2)
                name = name_item.text() if name_item else f"단지_{cid}"
                if name == "⌛ 조회 중...": name = f"단지_{cid}" # 미처 조회 안 된 경우
                selected.append((name, cid))
        
        if selected:
            self._selected_complexes = selected
            self.complexes_added.emit(selected)
            self.accept()
        else:
            QMessageBox.warning(self, "선택 필요", "추가할 단지를 선택하세요.")

    def get_urls(self):
        """호환용: 선택된 단지의 URL 목록 반환"""
        return [f"https://new.land.naver.com/complexes/{cid}" for _, cid in self._selected_complexes]

    def get_selected_complexes(self):
        """선택된 (이름, ID) 목록 반환"""
        return list(self._selected_complexes)

class ExcelTemplateDialog(QDialog):
    """엑셀 내보내기 템플릿 설정 (v7.3)"""
    template_saved = pyqtSignal(dict)
    
    def __init__(self, parent=None, current_template=None):
        super().__init__(parent)
        self.setWindowTitle("📊 엑셀 템플릿 설정")
        self.setMinimumSize(400, 500)
        self._columns, self._order = self._normalize_template(current_template)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        info = QLabel("내보낼 컬럼을 선택하고 순서를 조정하세요:")
        layout.addWidget(info)
        
        # 컬럼 목록
        self.column_list = QListWidget()
        self.column_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        
        for col_name in self._order:
            item = QListWidgetItem(col_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if self._columns.get(col_name, True) else Qt.CheckState.Unchecked)
            self.column_list.addItem(item)
        
        layout.addWidget(self.column_list)
        
        # 순서 조정 버튼
        order_layout = QHBoxLayout()
        btn_up = QPushButton("⬆️ 위로")
        btn_up.clicked.connect(self._move_up)
        btn_down = QPushButton("⬇️ 아래로")
        btn_down.clicked.connect(self._move_down)
        order_layout.addWidget(btn_up)
        order_layout.addWidget(btn_down)
        order_layout.addStretch()
        layout.addLayout(order_layout)
        
        # 전체 선택/해제
        select_layout = QHBoxLayout()
        btn_all = QPushButton("전체 선택")
        btn_all.clicked.connect(lambda: self._set_all(True))
        btn_none = QPushButton("전체 해제")
        btn_none.clicked.connect(lambda: self._set_all(False))
        btn_reset = QPushButton("기본값")
        btn_reset.clicked.connect(self._reset)
        select_layout.addWidget(btn_all)
        select_layout.addWidget(btn_none)
        select_layout.addWidget(btn_reset)
        select_layout.addStretch()
        layout.addLayout(select_layout)
        
        # 저장 버튼
        btn_save = QPushButton("💾 저장")
        btn_save.clicked.connect(self._save)
        layout.addWidget(btn_save)
    
    def _move_up(self):
        row = self.column_list.currentRow()
        if row > 0:
            item = self.column_list.takeItem(row)
            self.column_list.insertItem(row - 1, item)
            self.column_list.setCurrentRow(row - 1)
    
    def _move_down(self):
        row = self.column_list.currentRow()
        if row < self.column_list.count() - 1:
            item = self.column_list.takeItem(row)
            self.column_list.insertItem(row + 1, item)
            self.column_list.setCurrentRow(row + 1)
    
    def _set_all(self, checked):
        for i in range(self.column_list.count()):
            self.column_list.item(i).setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
    
    def _reset(self):
        self.column_list.clear()
        default = ExcelTemplate.get_default_template()
        for col_name in ExcelTemplate.get_column_order():
            item = QListWidgetItem(col_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if default.get(col_name, True) else Qt.CheckState.Unchecked)
            self.column_list.addItem(item)
    
    def _save(self):
        template = {}
        column_order = []
        for i in range(self.column_list.count()):
            item = self.column_list.item(i)
            name = item.text()
            enabled = item.checkState() == Qt.CheckState.Checked
            template[name] = enabled
            column_order.append(name)
        
        result = {'columns': template, 'order': column_order}
        self.template_saved.emit(result)
        self.accept()

    def _normalize_template(self, current_template):
        columns = None
        order = None

        if isinstance(current_template, dict):
            if "columns" in current_template:
                columns = current_template.get("columns", {})
                order = current_template.get("order", [])
            else:
                columns = current_template

        if not order:
            order = list(ExcelTemplate.get_column_order())

        # Ensure order includes all known columns
        for col in ExcelTemplate.get_column_order():
            if col not in order:
                order.append(col)

        if columns is None:
            columns = ExcelTemplate.get_default_template()
        else:
            default = ExcelTemplate.get_default_template()
            for col in default:
                if col not in columns:
                    columns[col] = default[col]

        return columns, order

class SettingsDialog(QDialog):
    settings_changed = pyqtSignal(dict)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_manager = SettingsManager()
        self._setup_ui()
        self._load()
    
    def _setup_ui(self):
        self.setWindowTitle("⚙️ 설정")
        self.setMinimumSize(450, 450)
        layout = QVBoxLayout(self)
        
        # 테마
        tg = QGroupBox("🎨 테마")
        tl = QHBoxLayout()
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["dark", "light"])
        tl.addWidget(QLabel("테마:"))
        tl.addWidget(self.combo_theme)
        tl.addStretch()
        tg.setLayout(tl)
        layout.addWidget(tg)
        
        # 시스템
        sg = QGroupBox("🖥️ 시스템")
        sl = QVBoxLayout()
        self.check_tray = QCheckBox("닫기 시 트레이로 최소화")
        self.check_notify = QCheckBox("데스크톱 알림 표시")
        self.check_confirm = QCheckBox("종료 전 확인")
        self.check_sound = QCheckBox("크롤링 완료 시 알림음 재생")
        sl.addWidget(self.check_tray)
        sl.addWidget(self.check_notify)
        sl.addWidget(self.check_confirm)
        sl.addWidget(self.check_sound)
        sg.setLayout(sl)
        layout.addWidget(sg)
        
        # 크롤링
        cg = QGroupBox("🔄 크롤링")
        cl = QHBoxLayout()
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(list(CRAWL_SPEED_PRESETS.keys()))
        cl.addWidget(QLabel("기본 속도:"))
        cl.addWidget(self.combo_speed)
        cl.addStretch()
        cg.setLayout(cl)
        layout.addWidget(cg)
        
        # 정렬
        og = QGroupBox("📊 결과 정렬")
        ol = QHBoxLayout()
        self.combo_sort_col = QComboBox()
        self.combo_sort_col.addItems(["가격", "면적", "단지명", "거래유형"])
        ol.addWidget(QLabel("기준:"))
        ol.addWidget(self.combo_sort_col)
        self.combo_sort_order = QComboBox()
        self.combo_sort_order.addItems(["오름차순", "내림차순"])
        ol.addWidget(self.combo_sort_order)
        ol.addStretch()
        og.setLayout(ol)
        layout.addWidget(og)
        
        layout.addStretch()
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _load(self):
        self.combo_theme.setCurrentText(self.settings_manager.get("theme", "dark"))
        self.check_tray.setChecked(self.settings_manager.get("minimize_to_tray", True))
        self.check_notify.setChecked(self.settings_manager.get("show_notifications", True))
        self.check_confirm.setChecked(self.settings_manager.get("confirm_before_close", True))
        self.check_sound.setChecked(self.settings_manager.get("play_sound_on_complete", True))
        self.combo_speed.setCurrentText(self.settings_manager.get("crawl_speed", "보통"))
        self.combo_sort_col.setCurrentText(self.settings_manager.get("default_sort_column", "가격"))
        self.combo_sort_order.setCurrentText("오름차순" if self.settings_manager.get("default_sort_order", "asc") == "asc" else "내림차순")
    
    def _save(self):
        new = {
            "theme": self.combo_theme.currentText(),
            "minimize_to_tray": self.check_tray.isChecked(),
            "show_notifications": self.check_notify.isChecked(),
            "confirm_before_close": self.check_confirm.isChecked(),
            "play_sound_on_complete": self.check_sound.isChecked(),
            "crawl_speed": self.combo_speed.currentText(),
            "default_sort_column": self.combo_sort_col.currentText(),
            "default_sort_order": "asc" if self.combo_sort_order.currentText() == "오름차순" else "desc"
        }
        self.settings_manager.update(new)
        self.settings_changed.emit(new)
        self.accept()

class ShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⌨️ 단축키")
        self.setMinimumSize(400, 350)
        layout = QVBoxLayout(self)
        tbl = QTableWidget()
        tbl.setColumnCount(2)
        tbl.setHorizontalHeaderLabels(["기능", "단축키"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tbl.setAlternatingRowColors(True)
        shortcuts_list = [
            ("🚀 크롤링 시작", SHORTCUTS["start_crawl"]),
            ("⏹️ 크롤링 중지", SHORTCUTS["stop_crawl"]),
            ("💾 Excel 저장", SHORTCUTS["save_excel"]),
            ("📄 CSV 저장", SHORTCUTS["save_csv"]),
            ("🔄 새로고침", SHORTCUTS["refresh"]),
            ("🔍 검색", SHORTCUTS["search"]),
            ("🎨 테마 변경", SHORTCUTS["toggle_theme"]),
            ("📥 트레이 최소화", SHORTCUTS["minimize_tray"]),
            ("❌ 종료", SHORTCUTS["quit"])
        ]
        tbl.setRowCount(len(shortcuts_list))
        for i, (d, k) in enumerate(shortcuts_list):
            tbl.setItem(i, 0, QTableWidgetItem(d))
            tbl.setItem(i, 1, QTableWidgetItem(k))
        layout.addWidget(tbl)
        btn = QPushButton("닫기")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ℹ️ 정보")
        self.setMinimumSize(500, 500)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(f"""
        <div style="text-align: center; padding: 20px;">
            <h1 style="color: #3b82f6; margin-bottom: 5px;">🏠 {APP_TITLE}</h1>
            <h2 style="margin-top: 0;">{APP_VERSION}</h2>
            <p style="color: #64748b; font-size: 14px;">Analytics & Stability 업데이트</p>
        </div>
        
        <h3 style="color: #3b82f6; border-bottom: 2px solid #3b82f6; padding-bottom: 5px;">🆕 {APP_VERSION} 업데이트</h3>
        <ul>
            <li>📊 <b>시세 분석 대시보드</b> - 통계 카드, 차트, 트렌드 분석</li>
            <li>🃏 <b>카드 뷰 모드</b> - 시각적인 매물 카드 형태 조회</li>
            <li>⭐ <b>즐겨찾기 탭</b> - 관심 매물 별도 관리</li>
            <li>🔄 <b>안정성 강화</b> - 자동 재시도, Rate Limit 감지</li>
            <li>🕐 <b>최근 본 매물</b> - 조회 히스토리 자동 저장</li>
        </ul>
        
        <p style="color: #64748b; margin-top: 20px; text-align: center; font-size: 12px;">
            Made with ❤️ using Claude & Gemini AI
        </p>
        """)
        layout.addWidget(browser)
        btn = QPushButton("닫기")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

class RecentSearchDialog(QDialog):
    """최근 검색 기록 다이얼로그"""
    def __init__(self, parent=None, history_manager=None):
        super().__init__(parent)
        self.history_manager = history_manager
        self.selected_search = None
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle("🕐 최근 검색 기록")
        self.setMinimumSize(500, 400)
        layout = QVBoxLayout(self)
        
        self.list = QListWidget()
        self.list.setAlternatingRowColors(True)
        self.list.itemDoubleClicked.connect(self._load)
        layout.addWidget(self.list)
        
        btn_layout = QHBoxLayout()
        btn_load = QPushButton("📂 불러오기")
        btn_load.clicked.connect(self._load)
        btn_clear = QPushButton("🗑️ 기록 지우기")
        btn_clear.clicked.connect(self._clear)
        btn_layout.addWidget(btn_load)
        btn_layout.addWidget(btn_clear)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self._refresh()
    
    def _refresh(self):
        self.list.clear()
        if self.history_manager:
            for h in self.history_manager.get_recent():
                complexes = h.get('complexes', [])
                types = h.get('trade_types', [])
                timestamp = h.get('timestamp', '')
                text = f"[{timestamp}] {len(complexes)}개 단지 - {', '.join(types)}"
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, h)
                self.list.addItem(item)
    
    def _load(self):
        if item := self.list.currentItem():
            self.selected_search = item.data(Qt.ItemDataRole.UserRole)
            self.accept()
    
    def _clear(self):
        if self.history_manager:
            self.history_manager.clear()
            self._refresh()

class MultiSelectDialog(QDialog):
    def __init__(self, title, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(450, 550)
        self._selected = []
        self._setup_ui(items)
    
    def _setup_ui(self, items):
        layout = QVBoxLayout(self)
        
        # 상단 버튼
        btn_layout = QHBoxLayout()
        btn_all = QPushButton("✅ 전체 선택")
        btn_all.clicked.connect(self._select_all)
        btn_none = QPushButton("⬜ 전체 해제")
        btn_none.clicked.connect(self._deselect_all)
        btn_layout.addWidget(btn_all)
        btn_layout.addWidget(btn_none)
        layout.addLayout(btn_layout)
        
        # 리스트
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        for item_data in items:
            text, data = (item_data if isinstance(item_data, tuple) else (str(item_data), item_data))
            item = QListWidgetItem()
            checkbox = QCheckBox(text)
            checkbox.setProperty("data", data)
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, checkbox)
        layout.addWidget(self.list_widget)
        
        # 카운트
        self.count_label = QLabel("선택: 0개")
        self.count_label.setStyleSheet("font-weight: bold; color: #4a9eff;")
        layout.addWidget(self.count_label)
        
        # 버튼
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        for i in range(self.list_widget.count()):
            cb = self.list_widget.itemWidget(self.list_widget.item(i))
            if isinstance(cb, QCheckBox):
                cb.stateChanged.connect(self._update_count)
    
    def _update_count(self):
        count = sum(1 for i in range(self.list_widget.count())
                   if isinstance(w := self.list_widget.itemWidget(self.list_widget.item(i)), QCheckBox) and w.isChecked())
        self.count_label.setText(f"선택: {count}개")
    
    def _select_all(self):
        for i in range(self.list_widget.count()):
            if isinstance(cb := self.list_widget.itemWidget(self.list_widget.item(i)), QCheckBox):
                cb.setChecked(True)
    
    def _deselect_all(self):
        for i in range(self.list_widget.count()):
            if isinstance(cb := self.list_widget.itemWidget(self.list_widget.item(i)), QCheckBox):
                cb.setChecked(False)
    
    def _on_accept(self):
        self._selected = []
        for i in range(self.list_widget.count()):
            if isinstance(cb := self.list_widget.itemWidget(self.list_widget.item(i)), QCheckBox) and cb.isChecked():
                self._selected.append(cb.property("data"))
        self.accept()
    
    def selected_items(self): return self._selected
=======
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, 
    QComboBox, QDoubleSpinBox, QSpinBox, QGroupBox, QGridLayout, QTableWidget, 
    QHeaderView, QCheckBox, QTableWidgetItem, QDialogButtonBox, QTextBrowser, 
    QMessageBox, QListWidgetItem, QAbstractItemView, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from src.core.managers import SettingsManager
from src.core.parser import NaverURLParser
from src.core.export import ExcelTemplate
from src.utils.constants import APP_TITLE, APP_VERSION, SHORTCUTS, CRAWL_SPEED_PRESETS
from PyQt6.QtWidgets import QApplication

class PresetDialog(QDialog):
    def __init__(self, parent=None, preset_manager=None):
        super().__init__(parent)
        self.preset_manager = preset_manager
        self.selected_preset = None
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle("📁 필터 프리셋")
        self.setMinimumSize(400, 350)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("저장된 프리셋:"))
        self.list = QListWidget()
        self.list.setAlternatingRowColors(True)
        self.list.itemDoubleClicked.connect(self._load)
        layout.addWidget(self.list)
        btn_layout = QHBoxLayout()
        btn_load = QPushButton("📂 불러오기")
        btn_load.clicked.connect(self._load)
        btn_del = QPushButton("🗑️ 삭제")
        btn_del.clicked.connect(self._delete)
        btn_layout.addWidget(btn_load)
        btn_layout.addWidget(btn_del)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        self._refresh()
    
    def _refresh(self):
        self.list.clear()
        if self.preset_manager:
            for name in self.preset_manager.get_all_names():
                self.list.addItem(name)
    
    def _load(self):
        if item := self.list.currentItem():
            self.selected_preset = item.text()
            self.accept()
    
    def _delete(self):
        if (item := self.list.currentItem()) and self.preset_manager:
            self.preset_manager.delete(item.text())
            self._refresh()

class AlertSettingDialog(QDialog):
    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        self.db = db
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle("🔔 알림 설정")
        self.setMinimumSize(650, 550)
        layout = QVBoxLayout(self)
        
        # 추가 폼
        add_g = QGroupBox("새 알림 추가")
        add_l = QGridLayout()
        add_l.addWidget(QLabel("단지:"), 0, 0)
        self.combo_complex = QComboBox()
        for _, name, cid, _ in (self.db.get_all_complexes() if self.db else []):
            self.combo_complex.addItem(f"{name} ({cid})", (cid, name))
        add_l.addWidget(self.combo_complex, 0, 1, 1, 3)
        
        add_l.addWidget(QLabel("유형:"), 1, 0)
        self.combo_type = QComboBox()
        self.combo_type.addItems(["매매", "전세", "월세"])
        add_l.addWidget(self.combo_type, 1, 1)
        
        add_l.addWidget(QLabel("면적(평):"), 2, 0)
        self.spin_area_min = QDoubleSpinBox()
        self.spin_area_min.setRange(0, 200)
        add_l.addWidget(self.spin_area_min, 2, 1)
        add_l.addWidget(QLabel("~"), 2, 2)
        self.spin_area_max = QDoubleSpinBox()
        self.spin_area_max.setRange(0, 200)
        self.spin_area_max.setValue(100)
        add_l.addWidget(self.spin_area_max, 2, 3)
        
        add_l.addWidget(QLabel("가격(만원):"), 3, 0)
        self.spin_price_min = QSpinBox()
        self.spin_price_min.setRange(0, 999999)
        self.spin_price_min.setSingleStep(1000)
        add_l.addWidget(self.spin_price_min, 3, 1)
        add_l.addWidget(QLabel("~"), 3, 2)
        self.spin_price_max = QSpinBox()
        self.spin_price_max.setRange(0, 999999)
        self.spin_price_max.setValue(100000)
        self.spin_price_max.setSingleStep(1000)
        add_l.addWidget(self.spin_price_max, 3, 3)
        
        btn_add = QPushButton("➕ 추가")
        btn_add.clicked.connect(self._add)
        add_l.addWidget(btn_add, 4, 0, 1, 4)
        add_g.setLayout(add_l)
        layout.addWidget(add_g)
        
        layout.addWidget(QLabel("설정된 알림:"))
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["단지", "유형", "면적", "가격", "활성", "삭제"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
        self._load()
    
    def _add(self):
        if self.combo_complex.count() == 0: return
        data = self.combo_complex.currentData()
        if not data: return
        cid, name = data
        if self.db.add_alert_setting(cid, name, self.combo_type.currentText(),
            self.spin_area_min.value(), self.spin_area_max.value(),
            self.spin_price_min.value(), self.spin_price_max.value()):
            self._load()
    
    def _load(self):
        self.table.setRowCount(0)
        if not self.db: return
        for aid, cid, name, tt, amin, amax, pmin, pmax, enabled in self.db.get_all_alert_settings():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(name or cid))
            self.table.setItem(row, 1, QTableWidgetItem(tt))
            self.table.setItem(row, 2, QTableWidgetItem(f"{amin}~{amax}평"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{pmin:,}~{pmax:,}만"))
            check = QCheckBox()
            check.setChecked(enabled == 1)
            check.stateChanged.connect(lambda s, a=aid: self.db.toggle_alert_setting(a, s == Qt.CheckState.Checked.value))
            self.table.setCellWidget(row, 4, check)
            btn = QPushButton("🗑️")
            btn.clicked.connect(lambda _, a=aid: self._delete(a))
            self.table.setCellWidget(row, 5, btn)
    
    def _delete(self, aid):
        self.db.delete_alert_setting(aid)
        self._load()

class AdvancedFilterDialog(QDialog):
    """고급 결과 필터 다이얼로그 (v7.3)"""
    filter_applied = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔍 고급 필터")
        self.setMinimumWidth(450)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 가격 필터
        price_group = QGroupBox("💰 가격 필터")
        pg = QGridLayout(price_group)
        pg.addWidget(QLabel("최소 가격:"), 0, 0)
        self.price_min = QSpinBox()
        self.price_min.setRange(0, 9999999)
        self.price_min.setSuffix(" 만원")
        self.price_min.setSpecialValueText("제한 없음")
        pg.addWidget(self.price_min, 0, 1)
        pg.addWidget(QLabel("최대 가격:"), 0, 2)
        self.price_max = QSpinBox()
        self.price_max.setRange(0, 9999999)
        self.price_max.setValue(9999999)
        self.price_max.setSuffix(" 만원")
        self.price_max.setSpecialValueText("제한 없음")
        pg.addWidget(self.price_max, 0, 3)
        layout.addWidget(price_group)
        
        # 면적 필터
        area_group = QGroupBox("📐 면적 필터")
        ag = QGridLayout(area_group)
        ag.addWidget(QLabel("최소 면적:"), 0, 0)
        self.area_min = QDoubleSpinBox()
        self.area_min.setRange(0, 500)
        self.area_min.setSuffix(" 평")
        self.area_min.setSpecialValueText("제한 없음")
        ag.addWidget(self.area_min, 0, 1)
        ag.addWidget(QLabel("최대 면적:"), 0, 2)
        self.area_max = QDoubleSpinBox()
        self.area_max.setRange(0, 500)
        self.area_max.setValue(500)
        self.area_max.setSuffix(" 평")
        ag.addWidget(self.area_max, 0, 3)
        layout.addWidget(area_group)
        
        # 층수 필터
        floor_group = QGroupBox("🏢 층수 필터")
        fg = QHBoxLayout(floor_group)
        self.floor_low = QCheckBox("저층")
        self.floor_mid = QCheckBox("중층")
        self.floor_high = QCheckBox("고층")
        self.floor_low.setChecked(True)
        self.floor_mid.setChecked(True)
        self.floor_high.setChecked(True)
        fg.addWidget(self.floor_low)
        fg.addWidget(self.floor_mid)
        fg.addWidget(self.floor_high)
        fg.addStretch()
        layout.addWidget(floor_group)
        
        # 특수 필터
        special_group = QGroupBox("⭐ 특수 필터")
        sg = QHBoxLayout(special_group)
        self.only_new = QCheckBox("🆕 신규 매물만")
        self.only_price_down = QCheckBox("📉 가격 하락만")
        self.only_price_change = QCheckBox("📊 가격 변동만")
        sg.addWidget(self.only_new)
        sg.addWidget(self.only_price_down)
        sg.addWidget(self.only_price_change)
        sg.addStretch()
        layout.addWidget(special_group)
        
        # 키워드 필터
        keyword_group = QGroupBox("🔤 키워드 필터")
        kg = QVBoxLayout(keyword_group)
        kg.addWidget(QLabel("포함 키워드 (쉼표로 구분):"))
        self.include_keywords = QLineEdit()
        self.include_keywords.setPlaceholderText("예: 급매, 역세권, 올수리")
        kg.addWidget(self.include_keywords)
        kg.addWidget(QLabel("제외 키워드 (쉼표로 구분):"))
        self.exclude_keywords = QLineEdit()
        self.exclude_keywords.setPlaceholderText("예: 반지하, 탑층")
        kg.addWidget(self.exclude_keywords)
        layout.addWidget(keyword_group)
        
        # 버튼
        btn_layout = QHBoxLayout()
        btn_reset = QPushButton("초기화")
        btn_reset.clicked.connect(self._reset)
        btn_apply = QPushButton("적용")
        btn_apply.clicked.connect(self._apply)
        btn_apply.setDefault(True)
        btn_layout.addWidget(btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_apply)
        layout.addLayout(btn_layout)
    
    def _reset(self):
        self.price_min.setValue(0)
        self.price_max.setValue(9999999)
        self.area_min.setValue(0)
        self.area_max.setValue(500)
        self.floor_low.setChecked(True)
        self.floor_mid.setChecked(True)
        self.floor_high.setChecked(True)
        self.only_new.setChecked(False)
        self.only_price_down.setChecked(False)
        self.only_price_change.setChecked(False)
        self.include_keywords.clear()
        self.exclude_keywords.clear()
    
    def _apply(self):
        filters = {
            'price_min': self.price_min.value(),
            'price_max': self.price_max.value(),
            'area_min': self.area_min.value(),
            'area_max': self.area_max.value(),
            'floor_low': self.floor_low.isChecked(),
            'floor_mid': self.floor_mid.isChecked(),
            'floor_high': self.floor_high.isChecked(),
            'only_new': self.only_new.isChecked(),
            'only_price_down': self.only_price_down.isChecked(),
            'only_price_change': self.only_price_change.isChecked(),
            'include_keywords': [k.strip() for k in self.include_keywords.text().split(',') if k.strip()],
            'exclude_keywords': [k.strip() for k in self.exclude_keywords.text().split(',') if k.strip()],
        }
        self.filter_applied.emit(filters)
        self.accept()

class URLParsingWorker(QThread):
    """URL 파싱 및 단지명 조회를 위한 워커 스레드 (v7.3)"""
    ids_extracted = pyqtSignal(list)      # [(source, cid), ...]
    name_fetched = pyqtSignal(int, str, str) # row, name, status
    progress = pyqtSignal(int, int)       # current, total
    finished = pyqtSignal()

    def __init__(self, text):
        super().__init__()
        self.text = text
        self.is_running = True

    def run(self):
        # 1. ID 추출 (빠름)
        results = NaverURLParser.extract_from_text(self.text)
        self.ids_extracted.emit(results)
        
        total = len(results)
        if total == 0:
            self.finished.emit()
            return
            
        # 2. 단지명 조회 (느림 - 네트워크 통신)
        for i, (source, cid) in enumerate(results):
            if not self.is_running: break
            
            # 단지명 조회 (블로킹)
            name = NaverURLParser.fetch_complex_name(cid)
            status = "✅ 확인됨" if not name.startswith("단지_") else "⚠️ 이름 미확인"
            
            self.name_fetched.emit(i, name, status)
            self.progress.emit(i + 1, total)
            
        self.finished.emit()

    def stop(self):
        self.is_running = False


class URLBatchDialog(QDialog):
    """URL 일괄 등록 다이얼로그 (v7.3)"""
    complexes_added = pyqtSignal(list)  # [(name, id), ...]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔗 URL 일괄 등록")
        self.setMinimumSize(600, 500)
        self.worker = None
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 안내
        info = QLabel(
            "네이버 부동산 URL 또는 단지 ID를 붙여넣으세요.\n"
            "여러 개를 한 번에 입력할 수 있습니다 (한 줄에 하나씩)."
        )
        info.setStyleSheet("color: #888; padding: 10px;")
        layout.addWidget(info)
        
        # 입력 영역
        self.input_text = QTextBrowser()
        self.input_text.setReadOnly(False)
        self.input_text.setPlaceholderText(
            "예시:\n"
            "https://new.land.naver.com/complexes/102378\n"
            "https://land.naver.com/complex?complexNo=123456\n"
            "123456\n"
            "789012"
        )
        self.input_text.setAcceptRichText(False)
        layout.addWidget(self.input_text, 2)
        
        # 파싱 버튼
        self.btn_parse = QPushButton("🔍 URL 분석")
        self.btn_parse.clicked.connect(self._parse_urls)
        layout.addWidget(self.btn_parse)
        
        # 결과 테이블
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(4)
        self.result_table.setHorizontalHeaderLabels(["✓", "단지 ID", "단지명", "상태"])
        self.result_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.result_table.setColumnWidth(0, 30)
        self.result_table.setColumnWidth(1, 100)
        self.result_table.setColumnWidth(3, 100)
        layout.addWidget(self.result_table, 3)
        
        # 진행 상태
        self.status_bar = QProgressBar()
        self.status_bar.setRange(0, 100)
        self.status_bar.setValue(0)
        self.status_bar.setVisible(False)
        layout.addWidget(self.status_bar)
        
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        # 버튼
        btn_layout = QHBoxLayout()
        btn_select_all = QPushButton("전체 선택")
        btn_select_all.clicked.connect(self._select_all)
        self.btn_add = QPushButton("📥 선택 항목 추가")
        self.btn_add.clicked.connect(self._add_selected)
        btn_layout.addWidget(btn_select_all)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_add)
        layout.addLayout(btn_layout)
    
    def _parse_urls(self):
        text = self.input_text.toPlainText()
        if not text.strip():
            QMessageBox.warning(self, "입력 필요", "URL 또는 단지 ID를 입력하세요.")
            return
        
        self.btn_parse.setEnabled(False)
        self.btn_add.setEnabled(False)
        self.result_table.setRowCount(0)
        self.status_bar.setVisible(True)
        self.status_bar.setValue(0)
        self.status_label.setText("🔍 분석 중...")
        
        self.worker = URLParsingWorker(text)
        self.worker.ids_extracted.connect(self._on_ids_extracted)
        self.worker.name_fetched.connect(self._on_name_fetched)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()
        
    def _on_ids_extracted(self, results):
        if not results:
            QMessageBox.warning(self, "파싱 실패", "유효한 URL이나 단지 ID를 찾지 못했습니다.")
            self.status_label.setText("결과 없음")
            return

        self.status_label.setText(f"🔍 {len(results)}개 단지 발견, 이름 조회 중...")
        self.status_bar.setRange(0, len(results))
        
        for source, cid in results:
            row = self.result_table.rowCount()
            self.result_table.insertRow(row)
            
            # 체크박스
            chk = QCheckBox()
            chk.setChecked(True)
            self.result_table.setCellWidget(row, 0, chk)
            
            # 단지 ID
            self.result_table.setItem(row, 1, QTableWidgetItem(cid))
            
            # 단지명 (로딩 중)
            self.result_table.setItem(row, 2, QTableWidgetItem("⌛ 조회 중..."))
            
            # 상태
            self.result_table.setItem(row, 3, QTableWidgetItem("-"))
            
    def _on_name_fetched(self, row, name, status):
        if row < self.result_table.rowCount():
             self.result_table.setItem(row, 2, QTableWidgetItem(name))
             self.result_table.setItem(row, 3, QTableWidgetItem(status))
    
    def _on_progress(self, current, total):
        self.status_bar.setValue(current)
        self.status_label.setText(f"진행 중: {current}/{total}")

    def _on_finished(self):
        self.btn_parse.setEnabled(True)
        self.btn_add.setEnabled(True)
        self.status_bar.setVisible(False)
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        
        if self.result_table.rowCount() > 0:
            self.status_label.setText(f"✅ {self.result_table.rowCount()}개 단지 분석 완료")
        else:
            self.status_label.setText("대기 중")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(2000)
        event.accept()

    def _select_all(self):
        for row in range(self.result_table.rowCount()):
            chk = self.result_table.cellWidget(row, 0)
            if chk:
                chk.setChecked(True)
    
    def _add_selected(self):
        selected = []
        for row in range(self.result_table.rowCount()):
            chk = self.result_table.cellWidget(row, 0)
            if chk and chk.isChecked():
                cid = self.result_table.item(row, 1).text()
                name_item = self.result_table.item(row, 2)
                name = name_item.text() if name_item else f"단지_{cid}"
                if name == "⌛ 조회 중...": name = f"단지_{cid}" # 미처 조회 안 된 경우
                selected.append((name, cid))
        
        if selected:
            self.complexes_added.emit(selected)
            self.accept()
        else:
            QMessageBox.warning(self, "선택 필요", "추가할 단지를 선택하세요.")

class ExcelTemplateDialog(QDialog):
    """엑셀 내보내기 템플릿 설정 (v7.3)"""
    template_saved = pyqtSignal(dict)
    
    def __init__(self, parent=None, current_template=None):
        super().__init__(parent)
        self.setWindowTitle("📊 엑셀 템플릿 설정")
        self.setMinimumSize(400, 500)
        self.current_template = current_template or ExcelTemplate.get_default_template()
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        info = QLabel("내보낼 컬럼을 선택하고 순서를 조정하세요:")
        layout.addWidget(info)
        
        # 컬럼 목록
        self.column_list = QListWidget()
        self.column_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        
        for col_name in ExcelTemplate.get_column_order():
            item = QListWidgetItem(col_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if self.current_template.get(col_name, True) else Qt.CheckState.Unchecked)
            self.column_list.addItem(item)
        
        layout.addWidget(self.column_list)
        
        # 순서 조정 버튼
        order_layout = QHBoxLayout()
        btn_up = QPushButton("⬆️ 위로")
        btn_up.clicked.connect(self._move_up)
        btn_down = QPushButton("⬇️ 아래로")
        btn_down.clicked.connect(self._move_down)
        order_layout.addWidget(btn_up)
        order_layout.addWidget(btn_down)
        order_layout.addStretch()
        layout.addLayout(order_layout)
        
        # 전체 선택/해제
        select_layout = QHBoxLayout()
        btn_all = QPushButton("전체 선택")
        btn_all.clicked.connect(lambda: self._set_all(True))
        btn_none = QPushButton("전체 해제")
        btn_none.clicked.connect(lambda: self._set_all(False))
        btn_reset = QPushButton("기본값")
        btn_reset.clicked.connect(self._reset)
        select_layout.addWidget(btn_all)
        select_layout.addWidget(btn_none)
        select_layout.addWidget(btn_reset)
        select_layout.addStretch()
        layout.addLayout(select_layout)
        
        # 저장 버튼
        btn_save = QPushButton("💾 저장")
        btn_save.clicked.connect(self._save)
        layout.addWidget(btn_save)
    
    def _move_up(self):
        row = self.column_list.currentRow()
        if row > 0:
            item = self.column_list.takeItem(row)
            self.column_list.insertItem(row - 1, item)
            self.column_list.setCurrentRow(row - 1)
    
    def _move_down(self):
        row = self.column_list.currentRow()
        if row < self.column_list.count() - 1:
            item = self.column_list.takeItem(row)
            self.column_list.insertItem(row + 1, item)
            self.column_list.setCurrentRow(row + 1)
    
    def _set_all(self, checked):
        for i in range(self.column_list.count()):
            self.column_list.item(i).setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
    
    def _reset(self):
        self.column_list.clear()
        default = ExcelTemplate.get_default_template()
        for col_name in ExcelTemplate.get_column_order():
            item = QListWidgetItem(col_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if default.get(col_name, True) else Qt.CheckState.Unchecked)
            self.column_list.addItem(item)
    
    def _save(self):
        template = {}
        column_order = []
        for i in range(self.column_list.count()):
            item = self.column_list.item(i)
            name = item.text()
            enabled = item.checkState() == Qt.CheckState.Checked
            template[name] = enabled
            column_order.append(name)
        
        result = {'columns': template, 'order': column_order}
        self.template_saved.emit(result)
        self.accept()

class SettingsDialog(QDialog):
    settings_changed = pyqtSignal(dict)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_manager = SettingsManager()
        self._setup_ui()
        self._load()
    
    def _setup_ui(self):
        self.setWindowTitle("⚙️ 설정")
        self.setMinimumSize(450, 450)
        layout = QVBoxLayout(self)
        
        # 테마
        tg = QGroupBox("🎨 테마")
        tl = QHBoxLayout()
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["dark", "light"])
        tl.addWidget(QLabel("테마:"))
        tl.addWidget(self.combo_theme)
        tl.addStretch()
        tg.setLayout(tl)
        layout.addWidget(tg)
        
        # 시스템
        sg = QGroupBox("🖥️ 시스템")
        sl = QVBoxLayout()
        self.check_tray = QCheckBox("닫기 시 트레이로 최소화")
        self.check_notify = QCheckBox("데스크톱 알림 표시")
        self.check_confirm = QCheckBox("종료 전 확인")
        self.check_sound = QCheckBox("크롤링 완료 시 알림음 재생")
        sl.addWidget(self.check_tray)
        sl.addWidget(self.check_notify)
        sl.addWidget(self.check_confirm)
        sl.addWidget(self.check_sound)
        sg.setLayout(sl)
        layout.addWidget(sg)
        
        # 크롤링
        cg = QGroupBox("🔄 크롤링")
        cl = QHBoxLayout()
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(list(CRAWL_SPEED_PRESETS.keys()))
        cl.addWidget(QLabel("기본 속도:"))
        cl.addWidget(self.combo_speed)
        cl.addStretch()
        cg.setLayout(cl)
        layout.addWidget(cg)
        
        # 정렬
        og = QGroupBox("📊 결과 정렬")
        ol = QHBoxLayout()
        self.combo_sort_col = QComboBox()
        self.combo_sort_col.addItems(["가격", "면적", "단지명", "거래유형"])
        ol.addWidget(QLabel("기준:"))
        ol.addWidget(self.combo_sort_col)
        self.combo_sort_order = QComboBox()
        self.combo_sort_order.addItems(["오름차순", "내림차순"])
        ol.addWidget(self.combo_sort_order)
        ol.addStretch()
        og.setLayout(ol)
        layout.addWidget(og)
        
        layout.addStretch()
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _load(self):
        self.combo_theme.setCurrentText(self.settings_manager.get("theme", "dark"))
        self.check_tray.setChecked(self.settings_manager.get("minimize_to_tray", True))
        self.check_notify.setChecked(self.settings_manager.get("show_notifications", True))
        self.check_confirm.setChecked(self.settings_manager.get("confirm_before_close", True))
        self.check_sound.setChecked(self.settings_manager.get("play_sound_on_complete", True))
        self.combo_speed.setCurrentText(self.settings_manager.get("crawl_speed", "보통"))
        self.combo_sort_col.setCurrentText(self.settings_manager.get("default_sort_column", "가격"))
        self.combo_sort_order.setCurrentText("오름차순" if self.settings_manager.get("default_sort_order", "asc") == "asc" else "내림차순")
    
    def _save(self):
        new = {
            "theme": self.combo_theme.currentText(),
            "minimize_to_tray": self.check_tray.isChecked(),
            "show_notifications": self.check_notify.isChecked(),
            "confirm_before_close": self.check_confirm.isChecked(),
            "play_sound_on_complete": self.check_sound.isChecked(),
            "crawl_speed": self.combo_speed.currentText(),
            "default_sort_column": self.combo_sort_col.currentText(),
            "default_sort_order": "asc" if self.combo_sort_order.currentText() == "오름차순" else "desc"
        }
        self.settings_manager.update(new)
        self.settings_changed.emit(new)
        self.accept()

class ShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⌨️ 단축키")
        self.setMinimumSize(400, 350)
        layout = QVBoxLayout(self)
        tbl = QTableWidget()
        tbl.setColumnCount(2)
        tbl.setHorizontalHeaderLabels(["기능", "단축키"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tbl.setAlternatingRowColors(True)
        shortcuts_list = [
            ("🚀 크롤링 시작", SHORTCUTS["start_crawl"]),
            ("⏹️ 크롤링 중지", SHORTCUTS["stop_crawl"]),
            ("💾 Excel 저장", SHORTCUTS["save_excel"]),
            ("📄 CSV 저장", SHORTCUTS["save_csv"]),
            ("🔄 새로고침", SHORTCUTS["refresh"]),
            ("🔍 검색", SHORTCUTS["search"]),
            ("🎨 테마 변경", SHORTCUTS["toggle_theme"]),
            ("📥 트레이 최소화", SHORTCUTS["minimize_tray"]),
            ("❌ 종료", SHORTCUTS["quit"])
        ]
        tbl.setRowCount(len(shortcuts_list))
        for i, (d, k) in enumerate(shortcuts_list):
            tbl.setItem(i, 0, QTableWidgetItem(d))
            tbl.setItem(i, 1, QTableWidgetItem(k))
        layout.addWidget(tbl)
        btn = QPushButton("닫기")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ℹ️ 정보")
        self.setMinimumSize(500, 500)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(f"""
        <div style="text-align: center; padding: 20px;">
            <h1 style="color: #3b82f6; margin-bottom: 5px;">🏠 {APP_TITLE}</h1>
            <h2 style="margin-top: 0;">{APP_VERSION}</h2>
            <p style="color: #64748b; font-size: 14px;">Analytics & Stability 업데이트</p>
        </div>
        
        <h3 style="color: #3b82f6; border-bottom: 2px solid #3b82f6; padding-bottom: 5px;">🆕 v13.0 업데이트</h3>
        <ul>
            <li>📊 <b>시세 분석 대시보드</b> - 통계 카드, 차트, 트렌드 분석</li>
            <li>🃏 <b>카드 뷰 모드</b> - 시각적인 매물 카드 형태 조회</li>
            <li>⭐ <b>즐겨찾기 탭</b> - 관심 매물 별도 관리</li>
            <li>🔄 <b>안정성 강화</b> - 자동 재시도, Rate Limit 감지</li>
            <li>🕐 <b>최근 본 매물</b> - 조회 히스토리 자동 저장</li>
        </ul>
        
        <p style="color: #64748b; margin-top: 20px; text-align: center; font-size: 12px;">
            Made with ❤️ using Claude & Gemini AI
        </p>
        """)
        layout.addWidget(browser)
        btn = QPushButton("닫기")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

class RecentSearchDialog(QDialog):
    """최근 검색 기록 다이얼로그"""
    def __init__(self, parent=None, history_manager=None):
        super().__init__(parent)
        self.history_manager = history_manager
        self.selected_search = None
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle("🕐 최근 검색 기록")
        self.setMinimumSize(500, 400)
        layout = QVBoxLayout(self)
        
        self.list = QListWidget()
        self.list.setAlternatingRowColors(True)
        self.list.itemDoubleClicked.connect(self._load)
        layout.addWidget(self.list)
        
        btn_layout = QHBoxLayout()
        btn_load = QPushButton("📂 불러오기")
        btn_load.clicked.connect(self._load)
        btn_clear = QPushButton("🗑️ 기록 지우기")
        btn_clear.clicked.connect(self._clear)
        btn_layout.addWidget(btn_load)
        btn_layout.addWidget(btn_clear)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self._refresh()
    
    def _refresh(self):
        self.list.clear()
        if self.history_manager:
            for h in self.history_manager.get_recent():
                complexes = h.get('complexes', [])
                types = h.get('trade_types', [])
                timestamp = h.get('timestamp', '')
                text = f"[{timestamp}] {len(complexes)}개 단지 - {', '.join(types)}"
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, h)
                self.list.addItem(item)
    
    def _load(self):
        if item := self.list.currentItem():
            self.selected_search = item.data(Qt.ItemDataRole.UserRole)
            self.accept()
    
    def _clear(self):
        if self.history_manager:
            self.history_manager.clear()
            self._refresh()

class MultiSelectDialog(QDialog):
    def __init__(self, title, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(450, 550)
        self._selected = []
        self._setup_ui(items)
    
    def _setup_ui(self, items):
        layout = QVBoxLayout(self)
        
        # 상단 버튼
        btn_layout = QHBoxLayout()
        btn_all = QPushButton("✅ 전체 선택")
        btn_all.clicked.connect(self._select_all)
        btn_none = QPushButton("⬜ 전체 해제")
        btn_none.clicked.connect(self._deselect_all)
        btn_layout.addWidget(btn_all)
        btn_layout.addWidget(btn_none)
        layout.addLayout(btn_layout)
        
        # 리스트
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        for item_data in items:
            text, data = (item_data if isinstance(item_data, tuple) else (str(item_data), item_data))
            item = QListWidgetItem()
            checkbox = QCheckBox(text)
            checkbox.setProperty("data", data)
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, checkbox)
        layout.addWidget(self.list_widget)
        
        # 카운트
        self.count_label = QLabel("선택: 0개")
        self.count_label.setStyleSheet("font-weight: bold; color: #4a9eff;")
        layout.addWidget(self.count_label)
        
        # 버튼
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        for i in range(self.list_widget.count()):
            cb = self.list_widget.itemWidget(self.list_widget.item(i))
            if isinstance(cb, QCheckBox):
                cb.stateChanged.connect(self._update_count)
    
    def _update_count(self):
        count = sum(1 for i in range(self.list_widget.count())
                   if isinstance(w := self.list_widget.itemWidget(self.list_widget.item(i)), QCheckBox) and w.isChecked())
        self.count_label.setText(f"선택: {count}개")
    
    def _select_all(self):
        for i in range(self.list_widget.count()):
            if isinstance(cb := self.list_widget.itemWidget(self.list_widget.item(i)), QCheckBox):
                cb.setChecked(True)
    
    def _deselect_all(self):
        for i in range(self.list_widget.count()):
            if isinstance(cb := self.list_widget.itemWidget(self.list_widget.item(i)), QCheckBox):
                cb.setChecked(False)
    
    def _on_accept(self):
        self._selected = []
        for i in range(self.list_widget.count()):
            if isinstance(cb := self.list_widget.itemWidget(self.list_widget.item(i)), QCheckBox) and cb.isChecked():
                self._selected.append(cb.property("data"))
        self.accept()
    
    def selected_items(self): return self._selected
>>>>>>> d9c1bab01fe7f0174c099636906ac082e1c1c62b
