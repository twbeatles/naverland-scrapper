<<<<<<< HEAD
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextBrowser, QPushButton, QTableWidget, 
    QHeaderView, QCheckBox, QTableWidgetItem, QHBoxLayout, QMessageBox, QApplication
)
from PyQt6.QtCore import pyqtSignal
from src.core.parser import NaverURLParser

class URLBatchDialog(QDialog):
    """URL 일괄 등록 다이얼로그 (v7.3)"""
    complexes_added = pyqtSignal(list)  # [(name, id), ...]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔗 URL 일괄 등록")
        self.setMinimumSize(600, 500)
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
        btn_parse = QPushButton("🔍 URL 분석")
        btn_parse.clicked.connect(self._parse_urls)
        layout.addWidget(btn_parse)
        
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
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        # 버튼
        btn_layout = QHBoxLayout()
        btn_select_all = QPushButton("전체 선택")
        btn_select_all.clicked.connect(self._select_all)
        btn_add = QPushButton("📥 선택 항목 추가")
        btn_add.clicked.connect(self._add_selected)
        btn_layout.addWidget(btn_select_all)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_add)
        layout.addLayout(btn_layout)
    
    def _parse_urls(self):
        text = self.input_text.toPlainText()
        if not text.strip():
            QMessageBox.warning(self, "입력 필요", "URL 또는 단지 ID를 입력하세요.")
            return
        
        self.result_table.setRowCount(0)
        results = NaverURLParser.extract_from_text(text)
        
        if not results:
            QMessageBox.warning(self, "파싱 실패", "유효한 URL이나 단지 ID를 찾지 못했습니다.")
            return
        
        self.status_label.setText(f"🔍 {len(results)}개 단지 발견, 이름 조회 중...")
        QApplication.processEvents()
        
        for source, cid in results:
            row = self.result_table.rowCount()
            self.result_table.insertRow(row)
            
            # 체크박스
            chk = QCheckBox()
            chk.setChecked(True)
            self.result_table.setCellWidget(row, 0, chk)
            
            # 단지 ID
            self.result_table.setItem(row, 1, QTableWidgetItem(cid))
            
            # 단지명 조회
            name = NaverURLParser.fetch_complex_name(cid)
            self.result_table.setItem(row, 2, QTableWidgetItem(name))
            
            # 상태
            status = "✅ 확인됨" if not name.startswith("단지_") else "⚠️ 이름 미확인"
            self.result_table.setItem(row, 3, QTableWidgetItem(status))
            
            QApplication.processEvents()
        
        self.status_label.setText(f"✅ {len(results)}개 단지 분석 완료")
    
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
                name = self.result_table.item(row, 2).text()
                selected.append((name, cid))
        
        if selected:
            self.complexes_added.emit(selected)
            self.accept()
        else:
            QMessageBox.warning(self, "선택 필요", "추가할 단지를 선택하세요.")
=======
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextBrowser, QPushButton, QTableWidget, 
    QHeaderView, QCheckBox, QTableWidgetItem, QHBoxLayout, QMessageBox, QApplication
)
from PyQt6.QtCore import pyqtSignal
from src.core.parser import NaverURLParser

class URLBatchDialog(QDialog):
    """URL 일괄 등록 다이얼로그 (v7.3)"""
    complexes_added = pyqtSignal(list)  # [(name, id), ...]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔗 URL 일괄 등록")
        self.setMinimumSize(600, 500)
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
        btn_parse = QPushButton("🔍 URL 분석")
        btn_parse.clicked.connect(self._parse_urls)
        layout.addWidget(btn_parse)
        
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
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        # 버튼
        btn_layout = QHBoxLayout()
        btn_select_all = QPushButton("전체 선택")
        btn_select_all.clicked.connect(self._select_all)
        btn_add = QPushButton("📥 선택 항목 추가")
        btn_add.clicked.connect(self._add_selected)
        btn_layout.addWidget(btn_select_all)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_add)
        layout.addLayout(btn_layout)
    
    def _parse_urls(self):
        text = self.input_text.toPlainText()
        if not text.strip():
            QMessageBox.warning(self, "입력 필요", "URL 또는 단지 ID를 입력하세요.")
            return
        
        self.result_table.setRowCount(0)
        results = NaverURLParser.extract_from_text(text)
        
        if not results:
            QMessageBox.warning(self, "파싱 실패", "유효한 URL이나 단지 ID를 찾지 못했습니다.")
            return
        
        self.status_label.setText(f"🔍 {len(results)}개 단지 발견, 이름 조회 중...")
        QApplication.processEvents()
        
        for source, cid in results:
            row = self.result_table.rowCount()
            self.result_table.insertRow(row)
            
            # 체크박스
            chk = QCheckBox()
            chk.setChecked(True)
            self.result_table.setCellWidget(row, 0, chk)
            
            # 단지 ID
            self.result_table.setItem(row, 1, QTableWidgetItem(cid))
            
            # 단지명 조회
            name = NaverURLParser.fetch_complex_name(cid)
            self.result_table.setItem(row, 2, QTableWidgetItem(name))
            
            # 상태
            status = "✅ 확인됨" if not name.startswith("단지_") else "⚠️ 이름 미확인"
            self.result_table.setItem(row, 3, QTableWidgetItem(status))
            
            QApplication.processEvents()
        
        self.status_label.setText(f"✅ {len(results)}개 단지 분석 완료")
    
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
                name = self.result_table.item(row, 2).text()
                selected.append((name, cid))
        
        if selected:
            self.complexes_added.emit(selected)
            self.accept()
        else:
            QMessageBox.warning(self, "선택 필요", "추가할 단지를 선택하세요.")
>>>>>>> d9c1bab01fe7f0174c099636906ac082e1c1c62b
