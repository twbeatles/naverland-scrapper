"""
UI 위젯 모듈 (v14.0 리팩토링)
향상된 UX와 애니메이션이 적용된 커스텀 위젯
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame, 
    QScrollArea, QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QInputDialog, QLineEdit, QSlider, QProgressBar,
    QGroupBox, QCheckBox, QComboBox, QDoubleSpinBox, QSpinBox, QDialogButtonBox, 
    QDialog, QGraphicsOpacityEffect, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QPoint, QSize
from PyQt6.QtGui import QColor, QFont, QCursor
import webbrowser
from typing import List, Dict, Tuple
import re

from ..utils.helpers import DateTimeHelper, PriceConverter
from ..utils.logger import get_logger
from ..utils.analytics import MarketAnalyzer
from ..config import TRADE_COLORS, CRAWL_SPEED_PRESETS
from .styles import DESIGN_TOKENS, get_token

# Matplotlib check
try:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class ToastWidget(QWidget):
    """v14.0: 향상된 Toast 알림 위젯 - 슬라이드 + 페이드 애니메이션"""
    
    closed = pyqtSignal()  # 닫힘 시그널 추가
    
    def __init__(self, message: str, toast_type: str = "info", parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.Tool | 
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        # 타입별 색상 설정 (그라디언트 적용)
        self.toast_colors = {
            "success": {
                "bg": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(34, 197, 94, 0.98), stop:1 rgba(22, 163, 74, 0.98))",
                "icon": "✅",
                "border": "rgba(74, 222, 128, 0.4)"
            },
            "error": {
                "bg": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(239, 68, 68, 0.98), stop:1 rgba(220, 38, 38, 0.98))",
                "icon": "❌",
                "border": "rgba(252, 165, 165, 0.4)"
            },
            "warning": {
                "bg": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(245, 158, 11, 0.98), stop:1 rgba(217, 119, 6, 0.98))",
                "icon": "⚠️",
                "border": "rgba(252, 211, 77, 0.4)"
            },
            "info": {
                "bg": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(59, 130, 246, 0.98), stop:1 rgba(37, 99, 235, 0.98))",
                "icon": "ℹ️",
                "border": "rgba(147, 197, 253, 0.4)"
            },
        }
        
        color_info = self.toast_colors.get(toast_type, self.toast_colors["info"])
        self._toast_type = toast_type
        
        # 레이아웃 설정
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)
        
        # 아이콘
        icon_label = QLabel(color_info["icon"])
        icon_label.setStyleSheet("font-size: 22px; background: transparent;")
        layout.addWidget(icon_label)
        
        # 메시지
        self.msg_label = QLabel(message)
        self.msg_label.setStyleSheet(
            "color: white; font-size: 14px; font-weight: 600; "
            "padding: 0; background: transparent;"
        )
        self.msg_label.setWordWrap(True)
        layout.addWidget(self.msg_label, 1)
        
        # 닫기 버튼
        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.2);
                border: none;
                border-radius: 12px;
                color: white;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.3);
            }
        """)
        close_btn.clicked.connect(self.fade_out)
        layout.addWidget(close_btn)
        
        # 스타일
        self.setStyleSheet(f"""
            ToastWidget {{
                background: {color_info["bg"]};
                border-radius: 14px;
                border: 1px solid {color_info["border"]};
            }}
        """)
        
        # 크기 조정
        self.setMinimumWidth(320)
        self.setMaximumWidth(480)
        self.adjustSize()
        
        # 타이머
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.fade_out)
        self.timer.setSingleShot(True)
        
        # 애니메이션 참조 저장
        self._fade_anim = None
        self._slide_anim = None
        
    def show_toast(self, duration: int = 3500):
        """Toast 표시 - 슬라이드 인 + 페이드 인 애니메이션"""
        if self.parent():
            parent_rect = self.parent().geometry()
            final_x = parent_rect.x() + parent_rect.width() - self.width() - 24
            final_y = parent_rect.y() + parent_rect.height() - self.height() - 60
            
            # 시작 위치 (오른쪽 바깥)
            start_x = parent_rect.x() + parent_rect.width() + 20
            start_y = final_y
            
            self.move(start_x, start_y)
            self.show()
            
            # 슬라이드 인 애니메이션
            self._slide_anim = QPropertyAnimation(self, b"pos")
            self._slide_anim.setDuration(400)
            self._slide_anim.setStartValue(QPoint(start_x, start_y))
            self._slide_anim.setEndValue(QPoint(final_x, final_y))
            self._slide_anim.setEasingCurve(QEasingCurve.Type.OutBack)
            self._slide_anim.start()
        else:
            self.show()
        
        self.timer.start(duration)
        
    def fade_out(self):
        """Toast 숨기기 - 슬라이드 아웃 + 페이드 아웃"""
        if self.timer.isActive():
            self.timer.stop()
        
        # 슬라이드 아웃
        current_pos = self.pos()
        end_pos = QPoint(current_pos.x() + 100, current_pos.y())
        
        # 페이드 아웃
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(300)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        
        # 슬라이드 아웃
        self._slide_anim = QPropertyAnimation(self, b"pos")
        self._slide_anim.setDuration(300)
        self._slide_anim.setStartValue(current_pos)
        self._slide_anim.setEndValue(end_pos)
        self._slide_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        
        self._fade_anim.finished.connect(self._on_close)
        self._fade_anim.start()
        self._slide_anim.start()
    
    def _on_close(self):
        """닫힘 처리"""
        self.closed.emit()
        self.close()


class DashboardWidget(QWidget):
    """통합 대시보드 (v13.0)"""
    
    def __init__(self, db, theme="dark", parent=None):
        super().__init__(parent)
        self.db = db
        self._theme = theme
        self._data = []
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 제목
        title = QLabel("📊 분석 대시보드")
        title.setStyleSheet("font-size: 20px; font-weight: bold; padding: 10px;")
        layout.addWidget(title)
        
        # 통계 카드 영역
        cards_layout = QHBoxLayout()
        
        self.total_card = self._create_stat_card("📦 총 매물", "0", "#3b82f6")
        self.new_card = self._create_stat_card("🆕 신규 (오늘)", "0", "#22c55e")
        self.up_card = self._create_stat_card("📈 가격 상승", "0", "#ef4444")
        self.down_card = self._create_stat_card("📉 가격 하락", "0", "#10b981")
        self.disappeared_card = self._create_stat_card("👻 소멸", "0", "#6b7280")
        
        cards_layout.addWidget(self.total_card)
        cards_layout.addWidget(self.new_card)
        cards_layout.addWidget(self.up_card)
        cards_layout.addWidget(self.down_card)
        cards_layout.addWidget(self.disappeared_card)
        layout.addLayout(cards_layout)
        
        # 차트 영역
        charts_layout = QHBoxLayout()
        
        # 거래유형별 파이 차트
        self.trade_chart_frame = QGroupBox("🏠 거래유형별 분포")
        trade_chart_layout = QVBoxLayout(self.trade_chart_frame)
        if MATPLOTLIB_AVAILABLE:
            self.trade_figure = Figure(figsize=(4, 3), facecolor='none')
            self.trade_canvas = FigureCanvas(self.trade_figure)
            trade_chart_layout.addWidget(self.trade_canvas)
        else:
            trade_chart_layout.addWidget(QLabel("Matplotlib 필요"))
        charts_layout.addWidget(self.trade_chart_frame)
        
        # 가격대별 히스토그램
        self.price_chart_frame = QGroupBox("💰 가격대별 분포")
        price_chart_layout = QVBoxLayout(self.price_chart_frame)
        if MATPLOTLIB_AVAILABLE:
            self.price_figure = Figure(figsize=(5, 3), facecolor='none')
            self.price_canvas = FigureCanvas(self.price_figure)
            price_chart_layout.addWidget(self.price_canvas)
        else:
            price_chart_layout.addWidget(QLabel("Matplotlib 필요"))
        charts_layout.addWidget(self.price_chart_frame)
        
        layout.addLayout(charts_layout)
        
        # 트렌드 정보 영역
        self.trend_frame = QGroupBox("📈 시세 트렌드")
        trend_layout = QVBoxLayout(self.trend_frame)
        self.trend_label = QLabel("데이터 수집 후 트렌드 정보가 표시됩니다.")
        self.trend_label.setWordWrap(True)
        trend_layout.addWidget(self.trend_label)
        layout.addWidget(self.trend_frame)
        
        layout.addStretch()
    
    def _create_stat_card(self, title: str, value: str, color: str) -> QFrame:
        """통계 카드 위젯 생성"""
        card = QFrame()
        card.setFrameStyle(QFrame.Shape.StyledPanel)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {color}20;
                border: 1px solid {color}40;
                border-radius: 12px;
                padding: 15px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(5)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 12px; color: #888;")
        layout.addWidget(title_label)
        
        value_label = QLabel(value)
        value_label.setObjectName("value")
        value_label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {color};")
        layout.addWidget(value_label)
        
        return card
    
    def set_data(self, data):
        self._data = data
        self.refresh()
    
    def refresh(self):
        """대시보드 새로고침"""
        if not self._data:
            return
        
        # 통계 계산
        total = len(self._data)
        trade_counts = {"매매": 0, "전세": 0, "월세": 0}
        new_count = 0
        price_up = 0
        price_down = 0
        
        # Trend Analysis Preparation
        unique_complexes = set()
        
        for item in self._data:
            trade_type = item.get("거래유형", "")
            if trade_type in trade_counts:
                trade_counts[trade_type] += 1
            if item.get("신규여부"):
                new_count += 1
            change = item.get("가격변동", 0)
            if change > 0:
                price_up += 1
            elif change < 0:
                price_down += 1
            
            if item.get("단지ID"):
                unique_complexes.add(item.get("단지ID"))
        
        # 카드 업데이트
        self.total_card.findChild(QLabel, "value").setText(str(total))
        self.new_card.findChild(QLabel, "value").setText(str(new_count))
        self.up_card.findChild(QLabel, "value").setText(str(price_up))
        self.down_card.findChild(QLabel, "value").setText(str(price_down))
        
        # 차트 업데이트
        if MATPLOTLIB_AVAILABLE:
            self._update_trade_chart(trade_counts)
            self._update_price_chart()
            
        # 트렌드 업데이트
        self._update_trend_info(list(unique_complexes))

    def _update_trade_chart(self, trade_counts: dict):
        """거래유형별 파이 차트 업데이트"""
        if not hasattr(self, 'trade_figure') or not hasattr(self, 'trade_canvas'):
            return
        
        self.trade_figure.clear()
        ax = self.trade_figure.add_subplot(111)
        
        labels = []
        sizes = []
        colors = ['#ef4444', '#22c55e', '#3b82f6']
        
        for i, (label, count) in enumerate(trade_counts.items()):
            if count > 0:
                labels.append(f"{label}\n({count})")
                sizes.append(count)
        
        if sizes:
            ax.pie(sizes, labels=labels, colors=colors[:len(sizes)], autopct='%1.1f%%', startangle=90)
            ax.axis('equal')
        
        self.trade_figure.tight_layout()
        self.trade_canvas.draw()
    
    def _update_price_chart(self):
        """가격대별 히스토그램 업데이트"""
        if not hasattr(self, 'price_figure') or not hasattr(self, 'price_canvas'):
            return
        
        self.price_figure.clear()
        ax = self.price_figure.add_subplot(111)
        
        prices = []
        for item in self._data:
            # 가격 추출 - 매매가 또는 보증금에서
            price_text = item.get("매매가", "") or item.get("보증금", "")
            if price_text:
                price = PriceConverter.to_int(price_text)
                if price > 0:
                    prices.append(price / 10000)  # 억 단위로 변환
        
        if prices:
            ax.hist(prices, bins=10, color='#3b82f6', alpha=0.7, edgecolor='white')
            ax.set_xlabel('가격 (억원)')
            ax.set_ylabel('매물 수')
        
        self.price_figure.tight_layout()
        self.price_canvas.draw()

    def _update_trend_info(self, complex_ids: List[str]):
        """트렌드 정보 업데이트 (v13.0)"""
        if not complex_ids:
            self.trend_label.setText("단지 정보가 없습니다.")
            return

        trends = []
        valid_count = 0
        
        for cid in complex_ids:
            # 매매 기준 트렌드 분석 (가장 대표성 있음)
            history = self.db.get_complex_price_history(cid, "매매")
            if history:
                # (date, trade_type, pyeong, min, max, avg) -> (date, avg)
                price_data = [(h[0], h[5]) for h in history]
                analysis = MarketAnalyzer.calculate_weekly_trend(price_data)
                if analysis["trend"] != "insufficient_data":
                    trends.append(analysis['trend'])
                    valid_count += 1
        
        if not trends:
            self.trend_label.setText("트렌드 분석을 위한 히스토리 데이터가 불충분합니다.\n(매일 꾸준히 수집하면 분석이 가능해집니다)")
            return
            
        up = trends.count("상승")
        down = trends.count("하락")
        flat = trends.count("보합")
        unknown = trends.count("unknown")
        
        msg = f"<b>[분석 결과]</b> {valid_count}개 단지 데이터 기반<br>"
        msg += f"상승: {up} | 하락: {down} | 보합: {flat}<br><br>"
        
        if up > down and up > flat:
            msg += "<font color='#ef4444'><b>📈 전반적인 상승세입니다.</b></font>"
        elif down > up and down > flat:
            msg += "<font color='#10b981'><b>📉 전반적인 하락세입니다.</b></font>"
        elif flat > up and flat > down:
            msg += "<font color='#fbbf24'><b>➡️ 전반적인 보합세입니다.</b></font>"
        else:
            msg += "혼조세를 보이고 있습니다."
            
        self.trend_label.setText(msg)


class ArticleCard(QFrame):
    """v14.0: 향상된 매물 카드 위젯 - 호버 효과 및 가격변동 표시"""
    clicked = pyqtSignal(dict)
    favorite_toggled = pyqtSignal(str, str, bool)
    
    def __init__(self, data: dict, is_dark: bool = True, parent=None):
        super().__init__(parent)
        self.data = data
        self.is_dark = is_dark
        self._is_hovered = False
        self._setup_ui()
        self._setup_shadow()
    
    def _setup_shadow(self):
        """그림자 효과 설정"""
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(15)
        self.shadow.setXOffset(0)
        self.shadow.setYOffset(4)
        self.shadow.setColor(QColor(0, 0, 0, 40))
        self.setGraphicsEffect(self.shadow)
    
    def _setup_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedSize(290, 195)
        
        # 거래유형별 색상
        trade_type = self.data.get("거래유형", "매매")
        colors = TRADE_COLORS.get(trade_type, TRADE_COLORS["매매"])
        self._bg_color = colors["dark_bg"] if self.is_dark else colors["bg"]
        self._fg_color = colors["dark_fg"] if self.is_dark else colors["fg"]
        self._hover_bg = self._lighten_color(self._bg_color) if self.is_dark else self._darken_color(self._bg_color)
        
        self._apply_style(False)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(14, 12, 14, 12)
        
        # 상단: 거래유형 + 배지 + 즐겨찾기
        top_layout = QHBoxLayout()
        
        # 거래유형 배지
        type_badge = QFrame()
        type_badge.setFixedHeight(26)
        type_badge_layout = QHBoxLayout(type_badge)
        type_badge_layout.setContentsMargins(8, 4, 8, 4)
        type_badge_layout.setSpacing(4)
        type_label = QLabel(f"🏠 {trade_type}")
        type_label.setStyleSheet(f"color: {self._fg_color}; font-weight: bold; font-size: 12px;")
        type_badge_layout.addWidget(type_label)
        type_badge.setStyleSheet(f"background: {self._fg_color}20; border-radius: 13px;")
        top_layout.addWidget(type_badge)
        
        top_layout.addStretch()
        
        # 가격 변동 표시
        price_change = self.data.get("가격변동", 0)
        if price_change:
            if price_change > 0:
                change_label = QLabel(f"📈 +{price_change:,}")
                change_label.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 11px;")
            else:
                change_label = QLabel(f"📉 {price_change:,}")
                change_label.setStyleSheet("color: #22c55e; font-weight: bold; font-size: 11px;")
            top_layout.addWidget(change_label)
        
        # 신규 배지
        if self.data.get("신규여부"):
            new_badge = QLabel("NEW")
            new_badge.setStyleSheet("""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #f97316);
                color: white; font-weight: bold; font-size: 10px;
                padding: 3px 8px; border-radius: 10px;
            """)
            top_layout.addWidget(new_badge)
        
        # 즐겨찾기 버튼
        self.fav_btn = QPushButton("⭐" if self.data.get("is_favorite") else "☆")
        self.fav_btn.setFixedSize(32, 32)
        self.fav_btn.setStyleSheet("""
            QPushButton {
                border: none; 
                font-size: 20px; 
                background: transparent;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 16px;
            }
        """)
        self.fav_btn.clicked.connect(self._toggle_favorite)
        top_layout.addWidget(self.fav_btn)
        
        layout.addLayout(top_layout)
        
        # 단지명
        name_label = QLabel(self.data.get("단지명", ""))
        name_label.setStyleSheet("font-size: 15px; font-weight: bold;")
        name_label.setWordWrap(True)
        name_label.setMaximumHeight(40)
        layout.addWidget(name_label)
        
        # 가격 (강조)
        price_text = self.data.get("매매가") or self.data.get("보증금") or ""
        if self.data.get("월세"):
            price_text += f" / {self.data.get('월세')}"
        price_label = QLabel(f"💰 {price_text}")
        price_label.setStyleSheet(f"color: {self._fg_color}; font-size: 17px; font-weight: bold;")
        layout.addWidget(price_label)
        
        # 정보 라인
        info_layout = QHBoxLayout()
        
        # 면적 + 층
        area = self.data.get("면적(평)", 0)
        floor = self.data.get("층/방향", "")
        info_label = QLabel(f"📐 {area}평  |  {floor}")
        info_label.setStyleSheet("font-size: 12px; color: #888;")
        info_layout.addWidget(info_label)
        
        info_layout.addStretch()
        
        # 평당가
        if self.data.get("평당가_표시"):
            pprice_label = QLabel(f"📊 {self.data.get('평당가_표시')}")
            pprice_label.setStyleSheet("font-size: 11px; color: #666;")
            info_layout.addWidget(pprice_label)
        
        layout.addLayout(info_layout)
        
        # 하단 구분선 + 등록일
        layout.addStretch()
        
        date_text = self.data.get("확인일자", "")
        if date_text:
            date_label = QLabel(f"📅 {date_text}")
            date_label.setStyleSheet("font-size: 10px; color: #666;")
            layout.addWidget(date_label)
    
    def _apply_style(self, hovered: bool):
        """스타일 적용"""
        bg = self._hover_bg if hovered else self._bg_color
        border_width = "2px" if hovered else "1px"
        self.setStyleSheet(f"""
            ArticleCard {{
                background-color: {bg};
                border: {border_width} solid {self._fg_color}50;
                border-radius: 14px;
            }}
        """)
    
    def _lighten_color(self, color: str) -> str:
        """색상 밝게"""
        # 간단한 처리: 투명도 증가
        if color.startswith("#"):
            return color + "30"
        return color
    
    def _darken_color(self, color: str) -> str:
        """색상 어둡게"""
        if color.startswith("#"):
            return color + "20"
        return color
    
    def enterEvent(self, event):
        """마우스 진입"""
        self._is_hovered = True
        self._apply_style(True)
        self.shadow.setBlurRadius(25)
        self.shadow.setYOffset(8)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """마우스 이탈"""
        self._is_hovered = False
        self._apply_style(False)
        self.shadow.setBlurRadius(15)
        self.shadow.setYOffset(4)
        super().leaveEvent(event)
    
    def _toggle_favorite(self):
        article_id = self.data.get("매물ID", "")
        complex_id = self.data.get("단지ID", "")
        is_fav = self.fav_btn.text() == "☆"
        self.fav_btn.setText("⭐" if is_fav else "☆")
        self.favorite_toggled.emit(article_id, complex_id, is_fav)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.data)
        super().mousePressEvent(event)


class CardViewWidget(QScrollArea):
    """카드 뷰 위젯 (v13.0)"""
    article_clicked = pyqtSignal(dict)
    favorite_toggled = pyqtSignal(str, str, bool)
    
    def __init__(self, is_dark: bool = True, parent=None):
        super().__init__(parent)
        self.is_dark = is_dark
        self._cards = []
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.container = QWidget()
        self.grid_layout = QGridLayout(self.container)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.setWidget(self.container)
    
    def set_data(self, articles: List[dict]):
        """매물 데이터를 카드로 표시"""
        # 기존 카드 제거
        for card in self._cards:
            card.deleteLater()
        self._cards.clear()
        
        # 새 카드 생성
        cols = 4  # 한 행에 4개
        for i, article in enumerate(articles):
            card = ArticleCard(article, self.is_dark)
            card.clicked.connect(self.article_clicked.emit)
            card.favorite_toggled.connect(self.favorite_toggled.emit)
            
            row, col = divmod(i, cols)
            self.grid_layout.addWidget(card, row, col)
            self._cards.append(card)
    
    def filter_cards(self, text: str):
        """카드 필터링"""
        text = text.lower()
        for card in self._cards:
            name = card.data.get("단지명", "").lower()
            features = card.data.get("타입/특징", "").lower()
            visible = text in name or text in features
            card.setVisible(visible)


class FavoritesTab(QWidget):
    """즐겨찾기 탭 (v13.0)"""
    
    def __init__(self, db, theme="dark", parent=None):
        super().__init__(parent)
        self.db = db
        self._theme = theme
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 헤더
        header = QHBoxLayout()
        title = QLabel("⭐ 즐겨찾기 매물")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        
        refresh_btn = QPushButton("🔄 새로고침")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)
        
        layout.addLayout(header)
        
        # 테이블
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "단지명", "거래유형", "가격", "면적", "층/방향", "메모", "추가일", "링크"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        
        # 하단 버튼
        btn_layout = QHBoxLayout()
        
        self.note_btn = QPushButton("📝 메모 편집")
        self.note_btn.clicked.connect(self._edit_note)
        btn_layout.addWidget(self.note_btn)
        
        self.remove_btn = QPushButton("❌ 즐겨찾기 해제")
        self.remove_btn.clicked.connect(self._remove_favorite)
        btn_layout.addWidget(self.remove_btn)
        
        btn_layout.addStretch()
        
        self.open_btn = QPushButton("🔗 매물 페이지 열기")
        self.open_btn.clicked.connect(self._open_article)
        btn_layout.addWidget(self.open_btn)
        
        layout.addLayout(btn_layout)
    
    def refresh(self):
        """즐겨찾기 목록 새로고침"""
        try:
            favorites = self.db.get_favorites()
            if favorites is None:
                favorites = []
        except Exception:
            favorites = []
        
        self.table.setRowCount(len(favorites))
        
        for row, fav in enumerate(favorites):
            self.table.setItem(row, 0, QTableWidgetItem(str(fav.get("complex_name", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(str(fav.get("trade_type", ""))))
            self.table.setItem(row, 2, QTableWidgetItem(str(fav.get("price_text", ""))))
            self.table.setItem(row, 3, QTableWidgetItem(f"{fav.get('area_pyeong', 0)}평"))
            self.table.setItem(row, 4, QTableWidgetItem(str(fav.get("floor_info", ""))))
            self.table.setItem(row, 5, QTableWidgetItem(str(fav.get("note", ""))))
            self.table.setItem(row, 6, QTableWidgetItem(str(fav.get("created_at", ""))[:10]))
            
            # 데이터 저장
            item = self.table.item(row, 0)
            if item:
                item.setData(Qt.ItemDataRole.UserRole, fav)
    
    def _edit_note(self):
        """메모 편집"""
        row = self.table.currentRow()
        if row < 0:
            return
        
        item = self.table.item(row, 0)
        if not item:
            return
        
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        note, ok = QInputDialog.getText(
            self, "메모 편집", "메모:", 
            text=data.get("note", "")
        )
        if ok:
            self.db.update_article_note(
                data.get("article_id", ""),
                data.get("complex_id", ""),
                note
            )
            self.refresh()
    
    def _remove_favorite(self):
        """즐겨찾기 해제"""
        row = self.table.currentRow()
        if row < 0:
            return
        
        item = self.table.item(row, 0)
        if not item:
            return
        
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        self.db.toggle_favorite(
            data.get("article_id", ""),
            data.get("complex_id", ""),
            False
        )
        self.refresh()
    
    def _open_article(self):
        """매물 페이지 열기"""
        row = self.table.currentRow()
        if row < 0:
            return
        
        item = self.table.item(row, 0)
        if not item:
            return
        
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            # Helper function needed to reconstruct URL or just store URL
            pass

class SortableTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other):
        t1 = self.text().replace(",", "")
        t2 = other.text().replace(",", "")
        v1, v2 = self._extract_number(t1), self._extract_number(t2)
        if v1 is not None and v2 is not None: return v1 < v2
        return t1 < t2
    
    def _extract_number(self, text):
        try:
            text = re.sub(r'\(\d+건\)', '', text).strip()
            if "평" in text: return float(text.replace("평", "").strip())
            if "/" in text: text = text.split("/")[0]
            if "억" in text or "만" in text: return float(PriceConverter.to_int(text))
            return None
        except (ValueError, TypeError, AttributeError):
            return None

class ColoredTableWidgetItem(QTableWidgetItem):
    def __init__(self, text, trade_type=None, is_dark=True):
        super().__init__(text)
        if trade_type in TRADE_COLORS:
            colors = TRADE_COLORS[trade_type]
            bg = colors["dark_bg"] if is_dark else colors["bg"]
            fg = colors["dark_fg"] if is_dark else colors["fg"]
            self.setBackground(QColor(bg))
            self.setForeground(QColor(fg))

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

class SearchBar(QWidget):
    search_changed = pyqtSignal(str)
    def __init__(self, placeholder="검색...", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("🔍"))
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
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

class SummaryCard(QFrame):
    """결과 요약 카드 위젿 (v7.3 확장)"""
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
                    background-color: rgba(40, 40, 60, 0.95); 
                    border-radius: 10px; 
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    padding: 10px;
                }
            """)
        else:
            self.setStyleSheet("""
                SummaryCard { 
                    background-color: #ffffff; 
                    border-radius: 10px; 
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
        self.total_widget.findChild(QLabel, "value").setText(f"{total}건")
        self.trade_widget.findChild(QLabel, "value").setText(f"{trade}건")
        self.jeonse_widget.findChild(QLabel, "value").setText(f"{jeonse}건")
        self.monthly_widget.findChild(QLabel, "value").setText(f"{monthly}건")
        self.filtered_widget.findChild(QLabel, "value").setText(f"{filtered}건")
        self.new_widget.findChild(QLabel, "value").setText(f"{new_count}건")
        self.price_up_widget.findChild(QLabel, "value").setText(f"{price_up}건")
        self.price_down_widget.findChild(QLabel, "value").setText(f"{price_down}건")
    
    def reset(self):
        self.update_stats(0, 0, 0, 0, 0, 0, 0, 0)


class ProgressWidget(QWidget):
    """v14.0: 향상된 진행 상태 위젯 - 부드러운 애니메이션"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_value = 0
        self._target_value = 0
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(8)
        
        # 상태 표시줄
        status_layout = QHBoxLayout()
        
        # 상태 아이콘 (애니메이션용)
        self.status_icon = QLabel("⏳")
        self.status_icon.setStyleSheet("font-size: 16px;")
        status_layout.addWidget(self.status_icon)
        
        self.status_label = QLabel("대기 중...")
        self.status_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        # 진행률 텍스트
        self.percent_label = QLabel("0%")
        self.percent_label.setStyleSheet("font-weight: bold; color: #4a9eff; font-size: 14px;")
        status_layout.addWidget(self.percent_label)
        
        self.time_label = QLabel("")
        self.time_label.setStyleSheet("color: #888; font-size: 12px; margin-left: 10px;")
        status_layout.addWidget(self.time_label)
        
        layout.addLayout(status_layout)
        
        # 프로그레스바 (텍스트 숨김 - 별도 표시)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMinimumHeight(12)
        self.progress_bar.setMaximumHeight(12)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 6px;
                background-color: rgba(100, 100, 140, 0.3);
            }
            QProgressBar::chunk {
                border-radius: 6px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a9eff, stop:0.5 #8b5cf6, stop:1 #22c55e);
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # 부드러운 진행 애니메이션용 타이머
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate_progress)
        self._anim_timer.setInterval(16)  # ~60fps
    
    def update_progress(self, percent, current_name, remaining_seconds):
        """진행 상태 업데이트"""
        self._target_value = percent
        
        # 부드러운 애니메이션 시작
        if not self._anim_timer.isActive():
            self._anim_timer.start()
        
        self.status_icon.setText("🔄")
        self.status_label.setText(current_name[:30] + "..." if len(current_name) > 30 else current_name)
        self.percent_label.setText(f"{percent}%")
        
        if remaining_seconds > 0:
            mins, secs = divmod(int(remaining_seconds), 60)
            if mins > 0:
                self.time_label.setText(f"⏱ {mins}분 {secs}초 남음")
            else:
                self.time_label.setText(f"⏱ {secs}초 남음")
        else:
            self.time_label.setText("")
    
    def _animate_progress(self):
        """부드러운 진행바 애니메이션"""
        diff = self._target_value - self._current_value
        if abs(diff) < 0.5:
            self._current_value = self._target_value
            self._anim_timer.stop()
        else:
            self._current_value += diff * 0.15  # 이징
        
        self.progress_bar.setValue(int(self._current_value))
    
    def reset(self):
        """초기화"""
        self._current_value = 0
        self._target_value = 0
        self._anim_timer.stop()
        self.progress_bar.setValue(0)
        self.status_icon.setText("⏳")
        self.status_label.setText("대기 중...")
        self.percent_label.setText("0%")
        self.time_label.setText("")
    
    def complete(self):
        """완료 상태"""
        self._target_value = 100
        self._current_value = 100
        self.progress_bar.setValue(100)
        self.status_icon.setText("✅")
        self.status_label.setText("크롤링 완료!")
        self.percent_label.setText("100%")
        self.percent_label.setStyleSheet("font-weight: bold; color: #22c55e; font-size: 14px;")
        self.time_label.setText("")


class ChartWidget(QWidget):
    """v10.0: Analytics Chart using Matplotlib (테마 지원 추가)"""
    def __init__(self, parent=None, theme="dark"):
        super().__init__(parent)
        self._theme = theme
        layout = QVBoxLayout(self)
        if MATPLOTLIB_AVAILABLE:
            self._setup_chart()
            layout.addWidget(self.canvas)
        else:
            layout.addWidget(QLabel("Matplotlib 라이브러리가 설치되지 않았습니다.\n(pip install matplotlib)"))
    
    def _setup_chart(self):
        bg_color = '#2b2b2b' if self._theme == "dark" else '#ffffff'
        # text_color = 'white' if self._theme == "dark" else 'black'
        
        self.figure = Figure(figsize=(5, 3), dpi=100, facecolor=bg_color)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self._apply_theme_to_axis()
    
    def _apply_theme_to_axis(self):
        bg_color = '#2b2b2b' if self._theme == "dark" else '#ffffff'
        text_color = 'white' if self._theme == "dark" else 'black'
        spine_color = '#555555' if self._theme == "dark" else '#cccccc'
        
        self.ax.set_facecolor(bg_color)
        self.ax.tick_params(colors=text_color)
        self.ax.xaxis.label.set_color(text_color)
        self.ax.yaxis.label.set_color(text_color)
        for spine in self.ax.spines.values():
            spine.set_color(spine_color)
    
    def set_theme(self, theme):
        """테마 변경 시 호출"""
        self._theme = theme
        if MATPLOTLIB_AVAILABLE:
            bg_color = '#2b2b2b' if theme == "dark" else '#ffffff'
            self.figure.set_facecolor(bg_color)
            self._apply_theme_to_axis()
            self.canvas.draw()

    def update_chart(self, data):
        if not MATPLOTLIB_AVAILABLE or not data: return
        self.ax.clear()
        self._apply_theme_to_axis()
        
        # Sort by date
        data.sort(key=lambda x: x[0])
        from datetime import datetime
        
        dates = [datetime.strptime(d[0], "%Y-%m-%d") for d in data]
        prices = [d[1] for d in data]
        
        text_color = 'white' if self._theme == "dark" else 'black'
        self.ax.plot(dates, prices, marker='o', linestyle='-', color='#3498db', linewidth=2)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        self.ax.grid(True, linestyle='--', alpha=0.3)
        self.ax.set_title("Price Trend", color=text_color)
        self.canvas.draw()
