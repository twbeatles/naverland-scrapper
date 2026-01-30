from PyQt6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, QLineEdit, QSlider, QPushButton, QProgressBar, QFrame, QTableWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QColor
import webbrowser
from src.utils.constants import CRAWL_SPEED_PRESETS, TRADE_COLORS

class SearchBar(QWidget):
    search_changed = pyqtSignal(str)
    def __init__(self, placeholder="검색...", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("🔍"))
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.setObjectName("searchInput")
        self.input.setClearButtonEnabled(True)
        self.input.textChanged.connect(lambda t: self.search_changed.emit(t))
        layout.addWidget(self.input)
    def text(self): return self.input.text()
    def clear(self): self.input.clear()
    def setFocus(self): self.input.setFocus()

class SpeedSlider(QWidget):
    speed_changed = pyqtSignal(str)
    SPEEDS = ["빠름", "보통", "느림", "매우 느림"]
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        header.addWidget(QLabel("⚡ 속도:"))
        self.label = QLabel("보통")
        self.label.setStyleSheet("font-weight: bold; color: #4a9eff;")
        header.addWidget(self.label)
        self.desc_label = QLabel("(권장 속도)")
        self.desc_label.setStyleSheet("color: #888; font-size: 11px;")
        header.addWidget(self.desc_label)
        header.addStretch()
        layout.addLayout(header)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 3)
        self.slider.setValue(1)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.valueChanged.connect(self._on_change)
        self.slider.setToolTip("크롤링 속도를 조절합니다. 느릴수록 차단 위험이 낮습니다.")
        layout.addWidget(self.slider)
    def _on_change(self, val):
        speed = self.SPEEDS[val]
        self.label.setText(speed)
        desc = CRAWL_SPEED_PRESETS.get(speed, {}).get("desc", "")
        self.desc_label.setText(f"({desc})")
        self.speed_changed.emit(speed)
    def current_speed(self): return self.SPEEDS[self.slider.value()]
    def set_speed(self, speed):
        if speed in self.SPEEDS: self.slider.setValue(self.SPEEDS.index(speed))

class LinkButton(QPushButton):
    """클릭 가능한 링크 버튼"""
    def __init__(self, url, parent=None):
        super().__init__("🔗 보기", parent)
        self.url = url
        self.setObjectName("linkButton")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setToolTip(f"클릭하여 열기:\n{url[:50]}...")
        # 버튼 크기 고정
        self.setFixedHeight(26)
        self.setMaximumWidth(70)
        self.setMinimumWidth(60)
        self.setStyleSheet("""
            QPushButton {
                font-size: 11px;
                padding: 2px 6px;
                min-height: 22px;
                max-height: 24px;
            }
        """)
        self.clicked.connect(self._open_url)
    
    def _open_url(self):
        if self.url:
            webbrowser.open(self.url)

class ProgressWidget(QWidget):
    """진행 상태 위젯 - 예상 시간 표시"""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # 상태 표시줄
        status_layout = QHBoxLayout()
        self.status_label = QLabel("대기 중...")
        self.status_label.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(self.status_label)
        
        self.time_label = QLabel("")
        self.time_label.setStyleSheet("color: #888;")
        status_layout.addWidget(self.time_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # 프로그레스바
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMinimumHeight(25)
        layout.addWidget(self.progress_bar)
    
    def update_progress(self, percent, current_name, remaining_seconds):
        self.progress_bar.setValue(percent)
        self.status_label.setText(f"🔄 {current_name}")
        
        if remaining_seconds > 0:
            mins, secs = divmod(remaining_seconds, 60)
            if mins > 0:
                self.time_label.setText(f"예상 남은 시간: {mins}분 {secs}초")
            else:
                self.time_label.setText(f"예상 남은 시간: {secs}초")
        else:
            self.time_label.setText("")
    
    def reset(self):
        self.progress_bar.setValue(0)
        self.status_label.setText("대기 중...")
        self.time_label.setText("")
    
    def complete(self):
        self.progress_bar.setValue(100)
        self.status_label.setText("✅ 완료!")
        self.time_label.setText("")

class ColoredTableWidgetItem(QTableWidgetItem):
    def __init__(self, text, trade_type=None, is_dark=True):
        super().__init__(text)
        if trade_type in TRADE_COLORS:
            colors = TRADE_COLORS[trade_type]
            bg = colors["dark_bg"] if is_dark else colors["bg"]
            fg = colors["dark_fg"] if is_dark else colors["fg"]
            self.setBackground(QColor(bg))
            self.setForeground(QColor(fg))

class SummaryCard(QFrame):
    """결과 요약 카드 위젯 (v7.3 확장)"""
    def __init__(self, parent=None, theme="dark"):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self._theme = theme
        self._apply_theme()
        layout = QHBoxLayout(self)
        layout.setSpacing(15)
        
        # 총 수집
        self.total_widget = self._create_stat_widget("📊 총 수집", "0건", "#3498db")
        layout.addWidget(self.total_widget)
        
        # 매매
        self.trade_widget = self._create_stat_widget("🏠 매매", "0건", "#e74c3c")
        layout.addWidget(self.trade_widget)
        
        # 전세
        self.jeonse_widget = self._create_stat_widget("📋 전세", "0건", "#2ecc71")
        layout.addWidget(self.jeonse_widget)
        
        # 월세
        self.monthly_widget = self._create_stat_widget("💰 월세", "0건", "#9b59b6")
        layout.addWidget(self.monthly_widget)
        
        # 구분선
        self.sep = QFrame()
        self.sep.setFrameShape(QFrame.Shape.VLine)
        self._update_separator_style()
        layout.addWidget(self.sep)
        
        # v7.3 신규: 신규 매물
        self.new_widget = self._create_stat_widget("🆕 신규", "0건", "#f39c12")
        layout.addWidget(self.new_widget)
        
        # v7.3 신규: 가격 상승
        self.price_up_widget = self._create_stat_widget("📈 상승", "0건", "#e74c3c")
        layout.addWidget(self.price_up_widget)
        
        # v7.3 신규: 가격 하락
        self.price_down_widget = self._create_stat_widget("📉 하락", "0건", "#27ae60")
        layout.addWidget(self.price_down_widget)
        
        # 필터 제외
        self.filtered_widget = self._create_stat_widget("🚫 제외", "0건", "#95a5a6")
        layout.addWidget(self.filtered_widget)
        
        layout.addStretch()
    
    def _apply_theme(self):
        """테마에 따른 스타일 적용"""
        if self._theme == "dark":
            self.setStyleSheet("""
                SummaryCard { 
                    background-color: qlineargradient(
                        x1:0, y1:0, x2:1, y2:1,
                        stop:0 rgba(32, 36, 55, 0.95),
                        stop:1 rgba(24, 28, 45, 0.95)
                    );
                    border-radius: 12px; 
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    padding: 10px;
                }
            """)
        else:
            self.setStyleSheet("""
                SummaryCard { 
                    background-color: qlineargradient(
                        x1:0, y1:0, x2:1, y2:1,
                        stop:0 #ffffff,
                        stop:1 #f8fafc
                    );
                    border-radius: 12px; 
                    border: 1px solid #e2e8f0;
                    padding: 10px;
                }
            """)
    
    def _update_separator_style(self):
        """구분선 스타일 업데이트"""
        if self._theme == "dark":
            self.sep.setStyleSheet("color: rgba(255, 255, 255, 0.2);")
        else:
            self.sep.setStyleSheet("color: #e2e8f0;")
    
    def set_theme(self, theme):
        """테마 변경 시 호출"""
        self._theme = theme
        self._apply_theme()
        self._update_separator_style()
        self._update_title_colors()
    
    def _update_title_colors(self):
        """타이틀 레이블 색상 업데이트"""
        title_color = "#aaa" if self._theme == "dark" else "#64748b"
        for widget in [self.total_widget, self.trade_widget, self.jeonse_widget, 
                       self.monthly_widget, self.new_widget, self.price_up_widget,
                       self.price_down_widget, self.filtered_widget]:
            labels = widget.findChildren(QLabel)
            for label in labels:
                if label.objectName() != "value":
                    label.setStyleSheet(f"color: {title_color}; font-size: 11px;")
    
    def _create_stat_widget(self, title, value, color):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(2)
        
        title_label = QLabel(title)
        title_color = "#aaa" if self._theme == "dark" else "#64748b"
        title_label.setStyleSheet(f"color: {title_color}; font-size: 11px;")
        layout.addWidget(title_label)
        
        value_label = QLabel(value)
        value_label.setObjectName("value")
        value_label.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")
        layout.addWidget(value_label)
        
        return widget
    
    def update_stats(self, total=0, trade=0, jeonse=0, monthly=0, filtered=0, 
                     new_count=0, price_up=0, price_down=0):
        """통계 업데이트 (안전하게)"""
        def safe_set(widget, text):
            child = widget.findChild(QLabel, "value")
            if child is not None:
                child.setText(text)
        
        safe_set(self.total_widget, f"{total}건")
        safe_set(self.trade_widget, f"{trade}건")
        safe_set(self.jeonse_widget, f"{jeonse}건")
        safe_set(self.monthly_widget, f"{monthly}건")
        safe_set(self.filtered_widget, f"{filtered}건")
        safe_set(self.new_widget, f"{new_count}건")
        safe_set(self.price_up_widget, f"{price_up}건")
        safe_set(self.price_down_widget, f"{price_down}건")
    
    def reset(self):
        self.update_stats(0, 0, 0, 0, 0, 0, 0, 0)

class SortableTableWidgetItem(QTableWidgetItem):
    def __init__(self, text):
        super().__init__(text)
    
    def __lt__(self, other):
        try:
            # 숫자 비교 시도 (가격, 면적 등)
            val1 = float(self.text().replace(",", "").replace("만", "").replace("억", "").replace("평", "").split()[0])
            val2 = float(other.text().replace(",", "").replace("만", "").replace("억", "").replace("평", "").split()[0])
            return val1 < val2
        except (ValueError, IndexError):
            return super().__lt__(other)
