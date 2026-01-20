from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGroupBox, 
    QScrollArea, QGridLayout, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from openpyxl.styles import PatternFill # Unused here but kept for context if needed
# Try importing matplotlib for charts
try:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from src.utils.constants import TRADE_COLORS
from src.utils.helpers import PriceConverter

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
            # Make background transparent
            self.trade_figure.patch.set_alpha(0)
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
            self.price_figure.patch.set_alpha(0)
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
    
    def set_data(self, data: list):
        """대시보드 데이터 설정"""
        self._data = data
        self.refresh()
    
    def set_theme(self, theme: str):
        """테마 변경"""
        self._theme = theme
        # 차트 색상 업데이트
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
        
        # 카드 업데이트 (안전하게)
        def safe_set_text(card, name, text):
            child = card.findChild(QLabel, name)
            if child is not None:
                child.setText(text)
        
        safe_set_text(self.total_card, "value", str(total))
        safe_set_text(self.new_card, "value", str(new_count))
        safe_set_text(self.up_card, "value", str(price_up))
        safe_set_text(self.down_card, "value", str(price_down))
        
        # 차트 업데이트
        if MATPLOTLIB_AVAILABLE:
            try:
                self._update_trade_chart(trade_counts)
                self._update_price_chart()
            except Exception:
                pass  # 차트 업데이트 실패 무시
    
    def _update_trade_chart(self, trade_counts: dict):
        """거래유형별 파이 차트 업데이트"""
        if not hasattr(self, 'trade_figure') or not hasattr(self, 'trade_canvas'):
            return
        
        try:
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
                # Set text color based on theme - simplified logic
                text_color = 'white' if self._theme == 'dark' else 'black'
                
                wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors[:len(sizes)], autopct='%1.1f%%', startangle=90)
                ax.axis('equal')
                
                for text in texts + autotexts:
                    text.set_color(text_color)
            
            self.trade_figure.tight_layout()
            self.trade_canvas.draw()
        except Exception:
            pass  # 차트 그리기 실패 무시
    
    def _update_price_chart(self):
        """가격대별 히스토그램 업데이트"""
        if not hasattr(self, 'price_figure') or not hasattr(self, 'price_canvas'):
            return
        
        try:
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
                
                # Style update
                text_color = 'white' if self._theme == 'dark' else 'black'
                ax.tick_params(colors=text_color)
                ax.xaxis.label.set_color(text_color)
                ax.yaxis.label.set_color(text_color)
                for spine in ax.spines.values():
                    spine.set_color('#555555')
            
            self.price_figure.tight_layout()
            self.price_canvas.draw()
        except Exception:
            pass  # 차트 그리기 실패 무시


class ArticleCard(QFrame):
    """매물 카드 위젯 (v13.0)"""
    clicked = pyqtSignal(dict)
    favorite_toggled = pyqtSignal(str, str, bool)
    
    def __init__(self, data: dict, is_dark: bool = True, parent=None):
        super().__init__(parent)
        self.data = data
        self.is_dark = is_dark
        self._setup_ui()
    
    def _setup_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedSize(280, 180)
        
        # 거래유형별 색상
        trade_type = self.data.get("거래유형", "매매")
        colors = TRADE_COLORS.get(trade_type, TRADE_COLORS["매매"])
        bg_color = colors["dark_bg"] if self.is_dark else colors["bg"]
        fg_color = colors["dark_fg"] if self.is_dark else colors["fg"]
        
        self.setStyleSheet(f"""
            ArticleCard {{
                background-color: {bg_color};
                border: 1px solid {fg_color}40;
                border-radius: 12px;
                padding: 10px;
            }}
            ArticleCard:hover {{
                border: 2px solid {fg_color};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # 상단: 거래유형 + 즐겨찾기
        top_layout = QHBoxLayout()
        type_label = QLabel(f"🏠 {trade_type}")
        type_label.setStyleSheet(f"color: {fg_color}; font-weight: bold;")
        top_layout.addWidget(type_label)
        top_layout.addStretch()
        
        # 신규 배지
        if self.data.get("신규여부"):
            new_badge = QLabel("🆕 NEW")
            new_badge.setStyleSheet("color: #f59e0b; font-weight: bold;")
            top_layout.addWidget(new_badge)
        
        # 즐겨찾기 버튼
        self.fav_btn = QPushButton("⭐" if self.data.get("is_favorite") else "☆")
        self.fav_btn.setFixedSize(30, 30)
        self.fav_btn.setStyleSheet("border: none; font-size: 18px;")
        self.fav_btn.clicked.connect(self._toggle_favorite)
        top_layout.addWidget(self.fav_btn)
        
        layout.addLayout(top_layout)
        
        # 단지명
        name_label = QLabel(self.data.get("단지명", ""))
        name_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        name_label.setWordWrap(True)
        layout.addWidget(name_label)
        
        # 가격
        price_text = self.data.get("매매가") or self.data.get("보증금") or ""
        if self.data.get("월세"):
            price_text += f" / {self.data.get('월세')}"
        price_label = QLabel(f"💰 {price_text}")
        price_label.setStyleSheet(f"color: {fg_color}; font-size: 16px; font-weight: bold;")
        layout.addWidget(price_label)
        
        # 면적 + 층
        area = self.data.get("면적(평)", 0)
        floor = self.data.get("층/방향", "")
        info_label = QLabel(f"📐 {area}평 | {floor}")
        info_label.setStyleSheet("font-size: 12px; color: #888;")
        layout.addWidget(info_label)
        
        # 평당가
        if self.data.get("평당가_표시"):
            pprice_label = QLabel(f"📊 {self.data.get('평당가_표시')}")
            pprice_label.setStyleSheet("font-size: 11px; color: #888;")
            layout.addWidget(pprice_label)
        
        layout.addStretch()
    
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
    
    def set_data(self, articles: list):
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
