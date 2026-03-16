from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
)

from src.core.parser import NaverURLParser
from src.utils.retry_handler import RetryCancelledError


class _NameLookupWorker(QObject):
    progress = pyqtSignal(int, int, str, str, bool)
    finished = pyqtSignal(int, bool)

    def __init__(self, results):
        super().__init__()
        self._results = list(results)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    @pyqtSlot()
    def run(self):
        total = len(self._results)
        processed = 0
        for idx, (_source, cid) in enumerate(self._results):
            if self._cancelled:
                break

            try:
                name = NaverURLParser.fetch_complex_name(
                    cid,
                    cancel_checker=lambda: self._cancelled,
                )
            except RetryCancelledError:
                break
            except Exception:
                name = f"단지_{cid}"

            is_verified = not str(name).startswith("단지_")
            self.progress.emit(idx, total, str(cid), str(name), bool(is_verified))
            processed += 1

        self.finished.emit(processed, self._cancelled)


class URLBatchDialog(QDialog):
    """URL 일괄 등록 다이얼로그."""

    complexes_added = pyqtSignal(list)  # [(name, id), ...]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔗 URL 일괄 등록")
        self.setMinimumSize(600, 500)
        self._selected_complexes = []
        self._worker_thread = None
        self._worker = None
        self._parsing = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "네이버 부동산 URL 또는 단지 ID를 붙여넣으세요.\n"
            "여러 개를 한 번에 입력할 수 있습니다 (한 줄에 하나씩)."
        )
        info.setStyleSheet("color: #888; padding: 10px;")
        layout.addWidget(info)

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

        parse_row = QHBoxLayout()
        self.btn_parse = QPushButton("🔍 URL 분석")
        self.btn_parse.clicked.connect(self._parse_urls)
        self.btn_cancel = QPushButton("⏹ 취소")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_lookup)
        parse_row.addWidget(self.btn_parse)
        parse_row.addWidget(self.btn_cancel)
        parse_row.addStretch()
        layout.addLayout(parse_row)

        self.result_table = QTableWidget()
        self.result_table.setColumnCount(4)
        self.result_table.setHorizontalHeaderLabels(["✓", "단지 ID", "단지명", "상태"])
        batch_header = self.result_table.horizontalHeader()
        if batch_header is not None:
            batch_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.result_table.setColumnWidth(0, 30)
        self.result_table.setColumnWidth(1, 100)
        self.result_table.setColumnWidth(3, 120)
        layout.addWidget(self.result_table, 3)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        btn_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("전체 선택")
        self.btn_select_all.clicked.connect(self._select_all)
        self.btn_add = QPushButton("📥 선택 항목 추가")
        self.btn_add.clicked.connect(self._add_selected)
        btn_layout.addWidget(self.btn_select_all)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_add)
        layout.addLayout(btn_layout)

    def _set_parsing_state(self, parsing: bool):
        self._parsing = parsing
        self.btn_parse.setEnabled(not parsing)
        self.btn_cancel.setEnabled(parsing)
        self.btn_add.setEnabled(not parsing)
        self.btn_select_all.setEnabled(not parsing)

    def _prepare_rows(self, results):
        self.result_table.setRowCount(0)
        for _, cid in results:
            row = self.result_table.rowCount()
            self.result_table.insertRow(row)

            chk = QCheckBox()
            chk.setChecked(False)
            self.result_table.setCellWidget(row, 0, chk)
            self.result_table.setItem(row, 1, QTableWidgetItem(str(cid)))
            self.result_table.setItem(row, 2, QTableWidgetItem(f"단지_{cid}"))
            self.result_table.setItem(row, 3, QTableWidgetItem("조회 중..."))

    def _start_lookup_worker(self, results):
        self._cleanup_worker(wait=False)

        self._worker_thread = QThread(self)
        self._worker = _NameLookupWorker(results)
        self._worker.moveToThread(self._worker_thread)

        self._worker_thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_lookup_progress)
        self._worker.finished.connect(self._on_lookup_finished)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker_thread.finished.connect(self._worker.deleteLater)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)

        self._worker_thread.start()

    def _parse_urls(self):
        if self._parsing:
            return

        text = self.input_text.toPlainText()
        if not text.strip():
            QMessageBox.warning(self, "입력 필요", "URL 또는 단지 ID를 입력하세요.")
            return

        results = NaverURLParser.extract_from_text(text)
        if not results:
            QMessageBox.warning(self, "파싱 실패", "유효한 URL이나 단지 ID를 찾지 못했습니다.")
            return

        self._prepare_rows(results)
        self.status_label.setText(f"🔍 {len(results)}개 단지 발견, 이름 조회 시작")
        self._set_parsing_state(True)
        self._start_lookup_worker(results)

    def _cancel_lookup(self):
        if self._worker:
            self._worker.cancel()
        self.btn_cancel.setEnabled(False)
        self.status_label.setText("⏹ 취소 요청됨... 현재 조회를 마무리하는 중")

    @pyqtSlot(int, int, str, str, bool)
    def _on_lookup_progress(self, row, total, cid, name, is_verified):
        if row < 0 or row >= self.result_table.rowCount():
            return

        chk = self.result_table.cellWidget(row, 0)
        if isinstance(chk, QCheckBox):
            chk.setChecked(is_verified)
        self.result_table.setItem(row, 1, QTableWidgetItem(str(cid)))
        self.result_table.setItem(row, 2, QTableWidgetItem(str(name)))
        status = "✅ 확인됨" if is_verified else "⚠️ 이름 미확인"
        self.result_table.setItem(row, 3, QTableWidgetItem(status))
        self.status_label.setText(f"🔍 이름 조회 중... ({row + 1}/{total})")
        QApplication.processEvents()

    @pyqtSlot(int, bool)
    def _on_lookup_finished(self, processed, cancelled):
        self._set_parsing_state(False)
        total = self.result_table.rowCount()
        if cancelled:
            self.status_label.setText(f"⏹ 조회 취소됨 ({processed}/{total})")
        else:
            self.status_label.setText(f"✅ {processed}개 단지 분석 완료")
        self._cleanup_worker(wait=False)

    def _cleanup_worker(self, wait: bool):
        thread = self._worker_thread
        worker = self._worker
        self._worker_thread = None
        self._worker = None
        if worker:
            try:
                worker.cancel()
            except Exception:
                pass
        if thread:
            try:
                thread.quit()
                if wait:
                    thread.wait(2000)
            except Exception:
                pass

    def closeEvent(self, a0):
        event = a0
        if self._parsing:
            self._cancel_lookup()
            self._cleanup_worker(wait=True)
        super().closeEvent(event)

    def _select_all(self):
        for row in range(self.result_table.rowCount()):
            chk = self.result_table.cellWidget(row, 0)
            if isinstance(chk, QCheckBox):
                chk.setChecked(True)

    def _add_selected(self):
        selected = []
        for row in range(self.result_table.rowCount()):
            chk = self.result_table.cellWidget(row, 0)
            if isinstance(chk, QCheckBox) and chk.isChecked():
                cid_item = self.result_table.item(row, 1)
                name_item = self.result_table.item(row, 2)
                if not cid_item or not name_item:
                    continue
                selected.append((name_item.text(), cid_item.text()))

        if selected:
            self._selected_complexes = list(selected)
            self.complexes_added.emit(selected)
            self.accept()
        else:
            QMessageBox.warning(self, "선택 필요", "추가할 단지를 선택하세요.")

    def get_selected_complexes(self):
        return list(self._selected_complexes)

    def get_urls(self):
        return [f"https://new.land.naver.com/complexes/{cid}" for _, cid in self._selected_complexes]
