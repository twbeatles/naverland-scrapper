from PyQt6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, QLineEdit, QSlider, QPushButton, QProgressBar, QFrame,
    QTableWidgetItem, QStyledItemDelegate
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QColor
import webbrowser
from src.utils.constants import CRAWL_SPEED_PRESETS, TRADE_COLORS
from src.ui.styles import COLORS


class EmptyStateWidget(QWidget):
    """재사용 가능한 빈 상태 위젯 (Fluent IconWidget 기반)"""
    action_clicked = pyqtSignal()

    _LEGACY_ICONS = {"📭": "DOCUMENT", "🔍": "SEARCH", "⭐": "HEART", "📁": "FOLDER", "ℹ": "INFO"}

    def __init__(self, icon=None, title: str = "데이터가 없습니다",
                 description: str = "", action_text: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("emptyStateWidget")
        from src.ui.fluent.design_tokens import SPACE_LG, SPACE_SM, SPACE_XL
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_LG, SPACE_XL, SPACE_LG, SPACE_XL)
        layout.setSpacing(SPACE_SM)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_widget = self._make_icon(icon)
        layout.addWidget(self.icon_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("emptyStateTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.desc_label = QLabel(description)
        self.desc_label.setObjectName("emptyStateDesc")
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.desc_label.setWordWrap(True)
        self.desc_label.setMinimumWidth(360)
        self.desc_label.setVisible(bool(description))
        layout.addWidget(self.desc_label)

        self.action_button = None
        if action_text:
            action_btn = QPushButton(action_text)
            action_btn.setObjectName("secondaryBtn")
            action_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            action_btn.clicked.connect(self.action_clicked.emit)
            action_btn.setMinimumWidth(140)
            layout.addWidget(action_btn, alignment=Qt.AlignmentFlag.AlignCenter)
            self.action_button = action_btn

    def set_text(self, title: str, description: str = "") -> None:
        self.title_label.setText(title)
        self.desc_label.setText(description)
        self.desc_label.setVisible(bool(description))

    @classmethod
    def _resolve_icon(cls, icon):
        """Accept a FluentIcon member; map legacy emoji strings for compatibility."""
        try:
            from qfluentwidgets import FluentIcon as FIF
        except Exception:
            return None
        if icon is None:
            return FIF.DOCUMENT
        name = cls._LEGACY_ICONS.get(icon, icon) if isinstance(icon, str) else icon
        if isinstance(name, str):
            return getattr(FIF, name, FIF.DOCUMENT)
        return name

    def _make_icon(self, icon):
        resolved = self._resolve_icon(icon)
        try:
            from qfluentwidgets import IconWidget

            widget = IconWidget(resolved)
            widget.setFixedSize(40, 40)
            return widget
        except Exception:
            fallback = QLabel("")
            fallback.setObjectName("emptyStateIcon")
            return fallback


class TokenLabelDelegate(QStyledItemDelegate):
    """셀 값(내부 토큰)은 그대로 두고 화면 표시만 쉬운 말로 바꾼다."""

    def __init__(self, mapper, parent=None):
        super().__init__(parent)
        self._mapper = mapper

    def displayText(self, value, locale):
        try:
            return str(self._mapper(value))
        except Exception:
            return str(value)


def install_token_labels(table, column: int, mapper) -> None:
    """``table``의 한 열에 토큰→표시 이름 delegate를 단다 (데이터는 불변)."""
    table.setItemDelegateForColumn(column, TokenLabelDelegate(mapper, table))


class SearchBar(QWidget):
    search_changed = pyqtSignal(str)

    def __init__(self, placeholder="검색...", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._uses_fluent = False
        try:
            from qfluentwidgets import SearchLineEdit

            self.input = SearchLineEdit(self)
            self.input.setPlaceholderText(placeholder)
            self.input.setClearButtonEnabled(True)
            self._uses_fluent = True
        except Exception:
            self.input = QLineEdit()
            self.input.setPlaceholderText(placeholder)
            self.input.setObjectName("searchInput")
            self.input.setClearButtonEnabled(True)

        self.input.textChanged.connect(lambda t: self.search_changed.emit(t))
        layout.addWidget(self.input, 1)

    def text(self):
        return self.input.text()

    def clear(self):
        self.input.clear()

    def setFocus(self, reason: Qt.FocusReason = Qt.FocusReason.OtherFocusReason):
        self.input.setFocus(reason)


class SpeedSlider(QWidget):
    speed_changed = pyqtSignal(str)
    SPEEDS = ["빠름", "보통", "느림", "매우 느림"]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        header = QHBoxLayout()
        header.setSpacing(8)
        self.label = QLabel("보통")
        self.label.setObjectName("speedLabel")
        self.label.setStyleSheet("font-weight: 600;")
        header.addWidget(self.label)
        self.desc_label = QLabel("")
        self.desc_label.setObjectName("fieldLabel")
        header.addWidget(self.desc_label)
        header.addStretch()
        layout.addLayout(header)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 3)
        self.slider.setPageStep(1)
        self.slider.setValue(1)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.valueChanged.connect(self._on_change)
        self.slider.setToolTip("천천히 수집할수록 네이버에서 접속이 막힐 위험이 줄어듭니다.")
        layout.addWidget(self.slider)
        self._refresh_text(self.SPEEDS[1])

    def _refresh_text(self, speed):
        self.label.setText(speed)
        desc = CRAWL_SPEED_PRESETS.get(speed, {}).get("desc", "")
        self.desc_label.setText(desc)

    def _on_change(self, val):
        speed = self.SPEEDS[val]
        self._refresh_text(speed)
        self.speed_changed.emit(speed)

    def current_speed(self): return self.SPEEDS[self.slider.value()]
    def set_speed(self, speed):
        if speed in self.SPEEDS: self.slider.setValue(self.SPEEDS.index(speed))

class ProgressWidget(QWidget):
    """진행 상태 위젯 - 예상 시간 표시"""
    IDLE_TEXT = "수집을 시작하면 진행 상황이 여기에 표시됩니다."

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # 상태 표시줄
        status_layout = QHBoxLayout()
        self.status_label = QLabel(self.IDLE_TEXT)
        self.status_label.setObjectName("progressStatus")
        self.status_label.setStyleSheet("font-weight: 600;")
        status_layout.addWidget(self.status_label)
        
        self.time_label = QLabel("")
        self.time_label.setObjectName("progressTime")
        self.time_label.setObjectName("fieldLabel")
        status_layout.addStretch()
        status_layout.addWidget(self.time_label)
        layout.addLayout(status_layout)
        
        # 프로그레스바
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(18)
        layout.addWidget(self.progress_bar)
    
    def update_progress(self, percent, current_name, remaining_seconds):
        self.progress_bar.setValue(percent)
        self.status_label.setText(str(current_name or "진행 중..."))
        
        if remaining_seconds > 0:
            mins, secs = divmod(remaining_seconds, 60)
            if mins > 0:
                self.time_label.setText(f"약 {mins}분 {secs}초 남음")
            else:
                self.time_label.setText(f"약 {secs}초 남음")
        else:
            self.time_label.setText("")
    
    def reset(self):
        self.progress_bar.setValue(0)
        self.status_label.setText(self.IDLE_TEXT)
        self.time_label.setText("")
    
    def complete(self):
        self.progress_bar.setValue(100)
        self.status_label.setText("수집을 마쳤습니다.")
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
    """결과 요약 카드 위젯 (v15.0 — QSS 토큰 연동)"""
    def __init__(self, parent=None, theme="dark"):
        super().__init__(parent)
        self.setObjectName("summaryCard")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        self._theme = theme
        layout = QHBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 8, 12, 8)

        c = COLORS[theme]

        self.total_widget = self._create_stat_widget("전체", "0건", c["accent"])
        layout.addWidget(self.total_widget)

        self.trade_widget = self._create_stat_widget("매매", "0건", c["trade_매매"])
        layout.addWidget(self.trade_widget)

        self.jeonse_widget = self._create_stat_widget("전세", "0건", c["trade_전세"])
        layout.addWidget(self.jeonse_widget)

        self.monthly_widget = self._create_stat_widget("월세", "0건", c["trade_월세"])
        layout.addWidget(self.monthly_widget)

        self.sep = QFrame()
        self.sep.setFrameShape(QFrame.Shape.VLine)
        self.sep.setFixedHeight(44)
        self.sep.setStyleSheet(f"color: {c['summary_separator']};")
        layout.addWidget(self.sep)

        self.new_widget = self._create_stat_widget("신규", "0건", c["warning"])
        layout.addWidget(self.new_widget)

        self.price_up_widget = self._create_stat_widget("가격 상승", "0건", c["error"])
        layout.addWidget(self.price_up_widget)

        self.price_down_widget = self._create_stat_widget("가격 하락", "0건", c["success"])
        layout.addWidget(self.price_down_widget)

        self.filtered_widget = self._create_stat_widget("조건 제외", "0건", c["text_secondary"])
        layout.addWidget(self.filtered_widget)

        layout.addStretch()

    def set_theme(self, theme):
        """테마 변경 시 호출"""
        self._theme = theme if theme in COLORS else "dark"
        c = COLORS[self._theme]
        self.sep.setStyleSheet(f"color: {c['summary_separator']};")
        self._update_title_colors()

    def _update_title_colors(self):
        """타이틀 레이블 색상 업데이트"""
        c = COLORS[self._theme]
        title_color = c["text_secondary"]
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
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(3)

        title_label = QLabel(title)
        title_color = COLORS[self._theme]["text_secondary"]
        title_label.setStyleSheet(f"color: {title_color}; font-size: 11px; font-weight: 500;")
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setObjectName("value")
        value_label.setStyleSheet(f"color: {color}; font-size: 18px; font-weight: 700; letter-spacing: -0.3px;")
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


def build_page_header(title: str, subtitle: str = "") -> QWidget:
    """모든 화면 상단에 같은 모양으로 쓰는 제목 + 한 줄 설명."""
    header = QWidget()
    box = QVBoxLayout(header)
    box.setContentsMargins(0, 0, 0, 4)
    box.setSpacing(2)
    title_label = QLabel(title)
    title_label.setObjectName("pageTitle")
    box.addWidget(title_label)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setObjectName("pageSubtitle")
        sub.setWordWrap(True)
        box.addWidget(sub)
    return header
