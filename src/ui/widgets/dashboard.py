from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGroupBox, 
    QScrollArea, QGridLayout, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from typing import Optional
import time
# Try importing matplotlib for charts
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    FigureCanvas = None
    Figure = None
    MATPLOTLIB_AVAILABLE = False

from src.utils.constants import TRADE_COLORS
from src.core.managers import SettingsManager
from src.utils.helpers import PriceConverter
from src.utils.logger import get_logger
from src.utils.plot import setup_korean_font, sanitize_text_for_matplotlib
from src.ui.styles import COLORS
from src.ui.widgets.components import EmptyStateWidget

logger = get_logger("Dashboard")
settings = SettingsManager()

class StatCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value_label: Optional[QLabel] = None

class DashboardWidget(QWidget):
    """통합 대시보드 (v13.0)"""
    warning_signal = pyqtSignal(str)
    
    def __init__(self, db, theme="dark", parent=None):
        super().__init__(parent)
        self.db = db
        self._theme = theme
        self._data = []
        self._data_revision = 0
        self._stat_cards = []
        self._stat_cols = None
        self._last_trade_chart_sig = None
        self._last_price_chart_sig = None
        self._stats_cache_revision = -1
        self._stats_cache = None
        self._disappeared_cache_value = 0
        self._disappeared_cache_revision = -1
        self._disappeared_cache_loaded_at = 0.0
        self._disappeared_cache_ttl = 10.0
        self._warning_cache = {}
        self._warning_throttle_seconds = 3.0
        self._korean_font_ok = bool(setup_korean_font()) if MATPLOTLIB_AVAILABLE else True
        self._trade_chart_layout = None
        self._price_chart_layout = None
        self._trade_placeholder = None
        self._price_placeholder = None
        self.trade_figure = None
        self.trade_canvas = None
        self.price_figure = None
        self.price_canvas = None
        self._setup_ui()

    def _emit_warning(self, message: str):
        text = str(message or "").strip()
        if not text:
            return
        now = time.monotonic()
        last = float(self._warning_cache.get(text, 0.0) or 0.0)
        if now - last < self._warning_throttle_seconds:
            return
        self._warning_cache[text] = now
        if len(self._warning_cache) > 32:
            oldest = sorted(self._warning_cache.items(), key=lambda x: x[1])[:8]
            for key, _ in oldest:
                self._warning_cache.pop(key, None)
        self.warning_signal.emit(text)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 제목
        title = QLabel("📊 분석 대시보드")
        title.setStyleSheet("font-size: 22px; font-weight: 800; padding: 10px 0; letter-spacing: 0.5px;")
        layout.addWidget(title)
        
        # 통계 카드 영역 (반응형 그리드)
        self.cards_container = QWidget()
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setSpacing(12)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        
        self.total_card = self._create_stat_card("📦 총 매물", "0", "#3b82f6")
        self.new_card = self._create_stat_card("🆕 신규 (오늘)", "0", "#22c55e")
        self.up_card = self._create_stat_card("📈 가격 상승", "0", "#ef4444")
        self.down_card = self._create_stat_card("📉 가격 하락", "0", "#10b981")
        self.disappeared_card = self._create_stat_card("👻 소멸", "0", "#6b7280")
        
        self._stat_cards = [
            self.total_card, self.new_card, self.up_card, self.down_card, self.disappeared_card
        ]
        self._relayout_stats()
        layout.addWidget(self.cards_container)
        
        # 차트 영역
        charts_layout = QHBoxLayout()
        
        # 거래유형별 파이 차트
        self.trade_chart_frame = QGroupBox("🏠 거래유형별 분포")
        self._trade_chart_layout = QVBoxLayout(self.trade_chart_frame)
        self._trade_placeholder = QLabel("데이터 수집 후 차트가 표시됩니다.")
        self._trade_chart_layout.addWidget(self._trade_placeholder)
        charts_layout.addWidget(self.trade_chart_frame)
        
        # 가격대별 히스토그램
        self.price_chart_frame = QGroupBox("💰 가격대별 분포")
        self._price_chart_layout = QVBoxLayout(self.price_chart_frame)
        self._price_placeholder = QLabel("데이터 수집 후 차트가 표시됩니다.")
        self._price_chart_layout.addWidget(self._price_placeholder)
        charts_layout.addWidget(self.price_chart_frame)
        
        layout.addLayout(charts_layout)
        
        # 트렌드 정보 영역
        self.trend_frame = QGroupBox("📈 시세 트렌드")
        trend_layout = QVBoxLayout(self.trend_frame)
        self.trend_label = QLabel("데이터 수집 후 트렌드 정보가 표시됩니다.")
        self.trend_label.setWordWrap(True)
        trend_layout.addWidget(self.trend_label)
        layout.addWidget(self.trend_frame)
        self.trend_frame.setVisible(bool(settings.get("show_trend_analysis", True)))

        # 빈 상태 안내
        self.empty_label = EmptyStateWidget(
            icon="📊",
            title="아직 수집된 데이터가 없습니다",
            description="크롤링을 실행한 후 다시 확인하세요."
        )
        layout.addWidget(self.empty_label)
        self.empty_label.hide()
        
        layout.addStretch()
    
    def _create_stat_card(self, title: str, value: str, color: str) -> StatCard:
        """통계 카드 위젯 생성"""
        c = COLORS[self._theme]
        card = StatCard()
        card.setObjectName("statCard")
        card.setFrameStyle(QFrame.Shape.StyledPanel)
        card.setMinimumWidth(180)
        card.setStyleSheet(f"""
            QFrame#statCard {{
                background-color: {color}20;
                border: 1px solid {color}40;
                border-radius: 14px;
                padding: 18px;
            }}
            QFrame#statCard:hover {{
                border: 1px solid {color}80;
                background-color: {color}28;
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("statCardTitle")
        title_label.setStyleSheet(f"font-size: 12px; color: {c['text_secondary']}; font-weight: 500;")
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setObjectName("value")
        value_label.setStyleSheet(f"font-size: 32px; font-weight: 800; color: {color}; letter-spacing: -0.5px;")
        layout.addWidget(value_label)
        card._value_label = value_label

        return card

    def _ensure_chart_canvases(self):
        if not MATPLOTLIB_AVAILABLE or Figure is None or FigureCanvas is None:
            if self._trade_placeholder is not None:
                self._trade_placeholder.setText("Matplotlib 필요")
            if self._price_placeholder is not None:
                self._price_placeholder.setText("Matplotlib 필요")
            return False
        if self.trade_canvas is not None and self.price_canvas is not None:
            return True

        if self._trade_placeholder is not None:
            self._trade_placeholder.deleteLater()
            self._trade_placeholder = None
        if self._price_placeholder is not None:
            self._price_placeholder.deleteLater()
            self._price_placeholder = None

        if self._trade_chart_layout is not None:
            self.trade_figure = Figure(figsize=(4, 3), facecolor="none")
            self.trade_canvas = FigureCanvas(self.trade_figure)
            self.trade_figure.patch.set_alpha(0)
            self._trade_chart_layout.addWidget(self.trade_canvas)

        if self._price_chart_layout is not None:
            self.price_figure = Figure(figsize=(5, 3), facecolor="none")
            self.price_canvas = FigureCanvas(self.price_figure)
            self.price_figure.patch.set_alpha(0)
            self._price_chart_layout.addWidget(self.price_canvas)

        return self.trade_canvas is not None and self.price_canvas is not None

    def _build_stats_snapshot(self):
        if self._stats_cache_revision == self._data_revision and self._stats_cache is not None:
            return self._stats_cache

        trade_counts = {"매매": 0, "전세": 0, "월세": 0}
        new_count = 0
        price_up = 0
        price_down = 0
        prices = []

        for item in self._data:
            trade_type = item.get("거래유형", "")
            if trade_type in trade_counts:
                trade_counts[trade_type] += 1

            if item.get("is_new") or item.get("신규여부"):
                new_count += 1

            change = item.get("price_change", item.get("가격변동", 0))
            if isinstance(change, str):
                try:
                    change = int(change.replace(",", "").replace("만", ""))
                except ValueError:
                    change = 0
            if change > 0:
                price_up += 1
            elif change < 0:
                price_down += 1

            price_text = item.get("매매가", "") or item.get("보증금", "")
            if price_text:
                price = PriceConverter.to_int(price_text)
                if price > 0:
                    prices.append(price / 10000)

        self._stats_cache = {
            "total": len(self._data),
            "trade_counts": trade_counts,
            "new_count": new_count,
            "price_up": price_up,
            "price_down": price_down,
            "prices": prices,
        }
        self._stats_cache_revision = self._data_revision
        return self._stats_cache

    def _get_disappeared_count(self) -> int:
        now = time.monotonic()
        if (
            self._disappeared_cache_revision == self._data_revision
            and (now - self._disappeared_cache_loaded_at) < self._disappeared_cache_ttl
        ):
            return self._disappeared_cache_value

        try:
            disappeared = int(self.db.count_disappeared_articles() or 0)
        except Exception as e:
            logger.debug(f"소멸 매물 개수 조회 실패 (무시): {e}")
            disappeared = 0
            self._emit_warning("대시보드 소멸 통계를 불러오지 못했습니다.")

        self._disappeared_cache_value = disappeared
        self._disappeared_cache_revision = self._data_revision
        self._disappeared_cache_loaded_at = now
        return disappeared
    
    def set_data(self, data: list):
        """대시보드 데이터 설정"""
        self._data = list(data) if data else []
        self._data_revision += 1
        self._stats_cache_revision = -1
        self._stats_cache = None
        self._disappeared_cache_revision = -1
        self.refresh()
    
    def set_theme(self, theme: str):
        """테마 변경"""
        self._theme = theme
        self._last_trade_chart_sig = None
        self._last_price_chart_sig = None
        # 차트 색상 업데이트
        self.refresh()

    @staticmethod
    def _set_card_value(card, text: str):
        child = getattr(card, "_value_label", None)
        if child is not None:
            child.setText(text)

    def _clear_chart(self, figure, canvas, placeholder, message: str):
        if placeholder is not None:
            placeholder.setText(message)
        if figure is None or canvas is None:
            return
        try:
            figure.clear()
            ax = figure.add_subplot(111)
            ax.axis("off")
            text_color = "white" if self._theme == "dark" else "black"
            ax.text(0.5, 0.5, message, ha="center", va="center", color=text_color)
            figure.tight_layout()
            canvas.draw()
        except Exception as e:
            logger.debug(f"대시보드 차트 초기화 실패 (무시): {e}")

    def _clear_dashboard(self):
        self._set_card_value(self.total_card, "0")
        self._set_card_value(self.new_card, "0")
        self._set_card_value(self.up_card, "0")
        self._set_card_value(self.down_card, "0")
        self._set_card_value(self.disappeared_card, "0")
        self._last_trade_chart_sig = None
        self._last_price_chart_sig = None
        self._clear_chart(self.trade_figure, self.trade_canvas, self._trade_placeholder, "데이터가 없습니다.")
        self._clear_chart(self.price_figure, self.price_canvas, self._price_placeholder, "데이터가 없습니다.")
        self.trend_label.setText("총 매물 0건\n신규 0건 · 상승 0건 · 하락 0건 · 소멸 0건\n최다 거래유형: 없음")

    @staticmethod
    def _dominant_trade_type(trade_counts: dict) -> str:
        dominant_label = ""
        dominant_count = 0
        for label, count in trade_counts.items():
            numeric_count = int(count or 0)
            if numeric_count > dominant_count:
                dominant_label = str(label)
                dominant_count = numeric_count
        if dominant_count <= 0:
            return "없음"
        return f"{dominant_label} ({dominant_count}건)"

    def _trend_summary_text(self, stats: dict, disappeared_count: int) -> str:
        return (
            f"총 매물 {int(stats.get('total', 0) or 0)}건\n"
            f"신규 {int(stats.get('new_count', 0) or 0)}건 · "
            f"상승 {int(stats.get('price_up', 0) or 0)}건 · "
            f"하락 {int(stats.get('price_down', 0) or 0)}건 · "
            f"소멸 {int(disappeared_count or 0)}건\n"
            f"최다 거래유형: {self._dominant_trade_type(stats.get('trade_counts', {}))}"
        )
    
    def refresh(self):
        """대시보드 새로고침"""
        show_trend = bool(settings.get("show_trend_analysis", True))
        self.trend_frame.setVisible(show_trend)
        if not self._data:
            self._clear_dashboard()
            self.empty_label.show()
            return
        self.empty_label.hide()

        stats = self._build_stats_snapshot()
        disappeared_count = self._get_disappeared_count()

        self._set_card_value(self.total_card, str(stats["total"]))
        self._set_card_value(self.new_card, str(stats["new_count"]))
        self._set_card_value(self.up_card, str(stats["price_up"]))
        self._set_card_value(self.down_card, str(stats["price_down"]))
        self._set_card_value(self.disappeared_card, str(disappeared_count))
        self.trend_label.setText(self._trend_summary_text(stats, disappeared_count))

        if self._ensure_chart_canvases():
            try:
                self._update_trade_chart(stats["trade_counts"])
                self._update_price_chart(stats["prices"])
            except Exception as e:
                logger.debug(f"차트 업데이트 실패 (무시): {e}")
                self._emit_warning("대시보드 차트 렌더링 중 오류가 발생했습니다.")

    def _calc_stat_columns(self) -> int:
        available = max(1, self.width() - 40)
        return max(1, available // 220)

    def _relayout_stats(self):
        cols = self._calc_stat_columns()
        if cols == self._stat_cols and self._stat_cards:
            return
        self._stat_cols = cols
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item is None:
                continue
            w = item.widget()
            if w:
                w.setParent(None)
        for i, card in enumerate(self._stat_cards):
            row, col = divmod(i, cols)
            self.cards_layout.addWidget(card, row, col)

    def resizeEvent(self, a0):
        super().resizeEvent(a0)
        self._relayout_stats()
    
    def _update_trade_chart(self, trade_counts: dict):
        """거래유형별 파이 차트 업데이트"""
        if self.trade_figure is None or self.trade_canvas is None:
            return
        signature = (
            self._data_revision,
            self._theme,
            tuple(sorted((k, int(v)) for k, v in trade_counts.items())),
        )
        if signature == self._last_trade_chart_sig:
            return
        
        try:
            self.trade_figure.clear()
            ax = self.trade_figure.add_subplot(111)
            
            labels = []
            sizes = []
            colors = ['#ef4444', '#22c55e', '#3b82f6']
            label_map = {"매매": "Sale", "전세": "Jeonse", "월세": "Monthly"}
            
            for i, (label, count) in enumerate(trade_counts.items()):
                if count > 0:
                    if self._korean_font_ok:
                        display = str(label)
                    else:
                        display = label_map.get(str(label), sanitize_text_for_matplotlib(str(label), fallback="Type"))
                    labels.append(f"{display}\n({count})")
                    sizes.append(count)
            
            if sizes:
                # Set text color based on theme - simplified logic
                text_color = 'white' if self._theme == 'dark' else 'black'
                
                pie_result = ax.pie(
                    sizes,
                    labels=labels,
                    colors=colors[:len(sizes)],
                    autopct='%1.1f%%',
                    startangle=90,
                )
                texts = pie_result[1]
                autotexts = pie_result[2] if len(pie_result) > 2 else []
                ax.axis('equal')
                
                for text in texts + autotexts:
                    text.set_color(text_color)
            
            self.trade_figure.tight_layout()
            self.trade_canvas.draw()
            self._last_trade_chart_sig = signature
        except Exception as e:
            logger.debug(f"거래유형 차트 그리기 실패 (무시): {e}")
            self._emit_warning("거래유형 차트 렌더링에 실패했습니다.")
    
    def _update_price_chart(self, prices: list[float]):
        """가격대별 히스토그램 업데이트"""
        if self.price_figure is None or self.price_canvas is None:
            return
        signature = (self._data_revision, self._theme)
        if signature == self._last_price_chart_sig:
            return
        
        try:
            self.price_figure.clear()
            ax = self.price_figure.add_subplot(111)

            if prices:
                ax.hist(prices, bins=10, color='#3b82f6', alpha=0.7, edgecolor='white')
                if self._korean_font_ok:
                    ax.set_xlabel('가격 (억원)')
                    ax.set_ylabel('매물 수')
                else:
                    ax.set_xlabel("Price (100M KRW)")
                    ax.set_ylabel("Listings")
                
                # Style update
                text_color = 'white' if self._theme == 'dark' else 'black'
                ax.tick_params(colors=text_color)
                ax.xaxis.label.set_color(text_color)
                ax.yaxis.label.set_color(text_color)
                for spine in ax.spines.values():
                    spine.set_color('#555555')
            
            self.price_figure.tight_layout()
            self.price_canvas.draw()
            self._last_price_chart_sig = signature
        except Exception as e:
            logger.debug(f"가격 차트 그리기 실패 (무시): {e}")
            self._emit_warning("가격대 차트 렌더링에 실패했습니다.")


class ArticleCard(QFrame):
    """매물 카드 위젯 (v13.0)"""
    clicked = pyqtSignal(dict)
    favorite_toggled = pyqtSignal(str, str, str, bool)
    
    def __init__(self, data: dict, is_dark: bool = True, parent=None):
        super().__init__(parent)
        self.data = data
        self.is_dark = is_dark
        self._setup_ui()
    
    def _setup_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedSize(280, 210)
        
        # 거래유형별 색상
        trade_type = self.data.get("거래유형", "매매")
        colors = TRADE_COLORS.get(trade_type, TRADE_COLORS["매매"])
        bg_color = colors["dark_bg"] if self.is_dark else colors["bg"]
        fg_color = colors["dark_fg"] if self.is_dark else colors["fg"]
        
        # 다크/라이트 모드에 따른 호버 배경
        hover_bg = f"{bg_color}" if self.is_dark else f"{fg_color}10"
        
        self.setStyleSheet(f"""
            ArticleCard {{
                background-color: {bg_color};
                border: 1px solid {fg_color}40;
                border-radius: 14px;
                padding: 14px;
            }}
            ArticleCard:hover {{
                border: 2px solid {fg_color};
                background-color: {hover_bg};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # 상단: 거래유형 칩 + 즐겨찾기
        top_layout = QHBoxLayout()
        type_label = QLabel(trade_type)
        type_label.setStyleSheet(
            f"color: {fg_color}; background-color: {fg_color}22; padding: 4px 10px; "
            "border-radius: 999px; font-weight: 700; font-size: 11px;"
        )
        top_layout.addWidget(type_label)
        top_layout.addStretch()
        
        # 신규/가격변동 배지
        duplicate_count = int(self.data.get("duplicate_count", 1) or 1)
        if duplicate_count > 1:
            dup_badge = QLabel(f"{duplicate_count}건")
            dup_badge.setStyleSheet("color: #06b6d4; font-weight: 700; font-size: 11px;")
            top_layout.addWidget(dup_badge)
        if self.data.get("is_new") or self.data.get("신규여부"):
            new_badge = QLabel("NEW")
            new_badge.setStyleSheet("color: #f59e0b; font-weight: 800; font-size: 11px;")
            top_layout.addWidget(new_badge)
        price_change = self.data.get("price_change", 0)
        if isinstance(price_change, str):
            try:
                price_change = int(price_change.replace(",", "").replace("만", ""))
            except ValueError:
                price_change = 0
        if price_change > 0:
            change_badge = QLabel("▲")
            change_badge.setStyleSheet("color: #ef4444; font-weight: 800;")
            top_layout.addWidget(change_badge)
        elif price_change < 0:
            change_badge = QLabel("▼")
            change_badge.setStyleSheet("color: #22c55e; font-weight: 800;")
            top_layout.addWidget(change_badge)
        
        # 즐겨찾기 버튼
        theme_key = "dark" if self.is_dark else "light"
        accent = COLORS[theme_key]["accent"]
        self.fav_btn = QPushButton("★" if self.data.get("is_favorite") else "☆")
        self.fav_btn.setFixedSize(30, 30)
        self.fav_btn.setStyleSheet(
            f"border: none; font-size: 18px; background: transparent; color: {accent};"
        )
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
        price_label = QLabel(price_text)
        price_label.setStyleSheet(f"color: {fg_color}; font-size: 18px; font-weight: 800;")
        layout.addWidget(price_label)

        # 가격 변동 텍스트
        if price_change != 0:
            sign = "+" if price_change > 0 else "-"
            change_text = PriceConverter.to_string(abs(price_change))
            change_label = QLabel(f"변동 {sign}{change_text}")
            change_color = "#ef4444" if price_change > 0 else "#22c55e"
            change_label.setStyleSheet(f"font-size: 11px; color: {change_color}; font-weight: 700;")
            layout.addWidget(change_label)
        
        # 면적 + 층/방향
        area = self.data.get("면적(평)", 0)
        floor = self.data.get("층/방향", "")
        info_label = QLabel(f"📐 {area}평  •  {floor}")
        info_label.setStyleSheet("font-size: 12px; color: #888;")
        layout.addWidget(info_label)
        
        # 평당가
        if self.data.get("평당가_표시"):
            pprice_label = QLabel(f"📊 {self.data.get('평당가_표시')}")
            pprice_label.setStyleSheet("font-size: 11px; color: #888;")
            layout.addWidget(pprice_label)

        # 특징 요약
        feature = self.data.get("타입/특징", "")
        if feature:
            feature_label = QLabel(feature[:30])
            feature_label.setStyleSheet("font-size: 11px; color: #9ca3af;")
            feature_label.setWordWrap(True)
            layout.addWidget(feature_label)
        
        layout.addStretch()
    
    def _toggle_favorite(self):
        article_id = self.data.get("매물ID", "")
        complex_id = self.data.get("단지ID", "")
        asset_type = str(self.data.get("자산유형", "APT") or "APT").strip().upper() or "APT"
        is_fav = self.fav_btn.text() == "☆"
        self.fav_btn.setText("★" if is_fav else "☆")
        self.favorite_toggled.emit(article_id, complex_id, asset_type, is_fav)
    
    def mousePressEvent(self, a0):
        if a0 is not None and a0.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.data)
        super().mousePressEvent(a0)


class CardViewWidget(QScrollArea):
    """카드 뷰 위젯 (v13.0)"""
    article_clicked = pyqtSignal(dict)
    favorite_toggled = pyqtSignal(str, str, str, bool)
    
    def __init__(self, is_dark: bool = True, parent=None):
        super().__init__(parent)
        self.is_dark = is_dark
        self._cards = []
        self._all_data = []
        self._search_text_cache = []
        self._filtered_data = []
        self._filter_text = ""
        self._card_width = 280
        self._card_spacing = 15
        self._page_size = 120
        self._render_cursor = 0
        self._last_columns = None
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.container = QWidget()
        self.grid_layout = QGridLayout(self.container)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.setWidget(self.container)

        self.empty_label = QLabel("조건에 맞는 매물이 없습니다.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #888; padding: 40px;")
        self.grid_layout.addWidget(self.empty_label, 0, 0)
        self.empty_label.hide()
        scroll_bar = self.verticalScrollBar()
        if scroll_bar is not None:
            scroll_bar.valueChanged.connect(self._on_scroll)

    @staticmethod
    def _build_search_text(article: dict) -> str:
        if not isinstance(article, dict):
            return ""
        return " ".join(
            [
                str(article.get("단지명", "")),
                str(article.get("타입/특징", "")),
                str(article.get("거래유형", "")),
                str(article.get("매매가", "")),
                str(article.get("보증금", "")),
                str(article.get("월세", "")),
            ]
        ).lower()
    
    def set_data(self, articles: list):
        """매물 데이터를 카드로 표시"""
        self._all_data = list(articles) if articles else []
        self._search_text_cache = [self._build_search_text(a) for a in self._all_data]
        self._apply_filter(reset_view=True)

    def append_data(self, articles: list):
        """기존 데이터에 매물 추가 (실시간 배치 업데이트용)"""
        if not articles:
            return
        new_items = list(articles)
        self._all_data.extend(new_items)
        self._search_text_cache.extend(self._build_search_text(a) for a in new_items)

        if self._filter_text:
            # 필터가 켜져 있으면 정확성을 위해 재적용
            self._apply_filter(reset_view=True)
            return

        had_count = len(self._filtered_data)
        self._filtered_data.extend(new_items)
        self.empty_label.setVisible(False)

        if self._render_cursor >= had_count:
            self._render_next_page()

    def _calc_columns(self) -> int:
        viewport = self.viewport()
        available = max(1, viewport.width() if viewport is not None else self.width())
        cols = max(1, available // (self._card_width + self._card_spacing))
        return cols

    def _clear_cards(self):
        for card in self._cards:
            card.deleteLater()
        self._cards.clear()
        self.grid_layout.setSpacing(self._card_spacing)
        self._render_cursor = 0
        self._last_columns = self._calc_columns()

    def _apply_filter(self, reset_view=False):
        text = (self._filter_text or "").lower()
        if text:
            self._filtered_data = [
                d for d, searchable in zip(self._all_data, self._search_text_cache)
                if text in searchable
            ]
        else:
            self._filtered_data = list(self._all_data)

        if reset_view:
            self._clear_cards()

        if not self._filtered_data:
            self._last_columns = None
            self.empty_label.show()
            return
        self.empty_label.hide()
        if reset_view:
            self._render_next_page()
        else:
            self._relayout_rendered_cards()

    def _on_scroll(self, value: int):
        scroll_bar = self.verticalScrollBar()
        if scroll_bar is None:
            return
        if scroll_bar.maximum() <= 0:
            return
        if value >= (scroll_bar.maximum() - 220):
            self._render_next_page()

    def _relayout_rendered_cards(self):
        cols = self._calc_columns()
        if not self._cards:
            self._last_columns = cols
            return
        for i, card in enumerate(self._cards):
            row, col = divmod(i, cols)
            self.grid_layout.addWidget(card, row, col)
        self._last_columns = cols

    def _render_next_page(self):
        if self._render_cursor >= len(self._filtered_data):
            return
        cols = self._calc_columns()
        end = min(len(self._filtered_data), self._render_cursor + self._page_size)
        for i in range(self._render_cursor, end):
            article = self._filtered_data[i]
            card = ArticleCard(article, self.is_dark)
            card.clicked.connect(self.article_clicked.emit)
            card.favorite_toggled.connect(self.favorite_toggled.emit)

            row, col = divmod(i, cols)
            self.grid_layout.addWidget(card, row, col)
            self._cards.append(card)
        self._render_cursor = end
        self._last_columns = cols

    def resizeEvent(self, a0):
        super().resizeEvent(a0)
        if self._filtered_data:
            cols = self._calc_columns()
            if cols != self._last_columns:
                self._relayout_rendered_cards()
    
    def filter_cards(self, text: str):
        """카드 필터링"""
        self._filter_text = text or ""
        self._apply_filter(reset_view=True)
