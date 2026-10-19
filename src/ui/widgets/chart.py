from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterable, Optional, Sequence, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    from matplotlib.ticker import FuncFormatter
    import matplotlib.dates as mdates

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    FigureCanvas = None
    Figure = None
    FuncFormatter = None
    mdates = None
    MATPLOTLIB_AVAILABLE = False

from src.utils.plot import sanitize_text_for_matplotlib, setup_korean_font

# 시리즈 색: 다크/라이트 양쪽 배경에서 읽히는 중간 채도 팔레트.
SERIES_COLORS: tuple[str, ...] = ("#3b82f6", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#ec4899")

_THEME_PALETTE = {
    "dark": {"bg": "#1e1e28", "text": "#e6e6ee", "muted": "#9a9ab0", "grid": "#3a3a4a", "spine": "#4a4a5a"},
    "light": {"bg": "#ffffff", "text": "#1f2937", "muted": "#64748b", "grid": "#e2e8f0", "spine": "#cbd5e1"},
}


def _resolve_theme(theme: str | None) -> str:
    name = str(theme or "dark").strip().lower()
    if name in _THEME_PALETTE:
        return name
    try:
        import darkdetect

        return "light" if darkdetect.theme() == "Light" else "dark"
    except Exception:
        return "dark"


def format_price_axis(value: float) -> str:
    """만원 단위 값을 축 눈금용 짧은 문자열로 (예: 85000 → 8.5억, 300 → 300만)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    if abs(v) >= 10000:
        text = f"{v / 10000:.2f}".rstrip("0").rstrip(".")
        return f"{text}억"
    return f"{v:,.0f}만"


def format_price_point(value: float) -> str:
    """마지막 점 라벨용 정확한 금액 (예: 107900 → 10억 7,900만)."""
    from src.utils.helpers import PriceConverter

    try:
        return PriceConverter.to_string(int(round(float(value))))
    except (TypeError, ValueError):
        return ""


@dataclass
class ChartSeries:
    label: str
    dates: Sequence[Any]
    avg: Sequence[Any]
    min_vals: Optional[Sequence[Any]] = None
    max_vals: Optional[Sequence[Any]] = None
    color: Optional[str] = None
    extra: dict = field(default_factory=dict)


class ChartWidget(QWidget):
    """시세 흐름 차트 (Matplotlib). 테마 대응 + 여러 시리즈 + 억/만 축."""

    def __init__(self, parent=None, theme: str = "dark"):
        super().__init__(parent)
        self._korean_font_ok = False
        self._theme = _resolve_theme(theme)
        self._last_render: Optional[Callable[[], None]] = None
        self.figure = None
        self.canvas = None
        self.ax = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.message_label = QLabel()
        self.message_label.setObjectName("listPlaceholder")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        if MATPLOTLIB_AVAILABLE and Figure is not None and FigureCanvas is not None:
            self._korean_font_ok = bool(setup_korean_font())
            self.figure = Figure(figsize=(5, 3), dpi=100)
            self.canvas = FigureCanvas(self.figure)
            self.ax = self.figure.add_subplot(111)
            layout.addWidget(self.canvas)
            self._apply_axes_style()
            self.clear("차트가 없습니다.")
        else:
            self.clear("Matplotlib 라이브러리가 설치되지 않았습니다.\n(pip install matplotlib)")

    # --- theme -----------------------------------------------------------
    @property
    def palette_colors(self) -> dict:
        return _THEME_PALETTE[self._theme]

    def set_theme(self, theme: str | None) -> None:
        self._theme = _resolve_theme(theme)
        self._apply_axes_style()
        if self._last_render is not None:
            self._last_render()
        elif self.canvas is not None:
            self.canvas.draw_idle()

    def _apply_axes_style(self) -> None:
        """``ax.clear()`` 가 눈금 색을 rcParams로 되돌리므로 그릴 때마다 다시 칠한다."""
        if self.figure is None or self.ax is None:
            return
        pal = self.palette_colors
        self.figure.set_facecolor(pal["bg"])
        self.ax.set_facecolor(pal["bg"])
        self.ax.tick_params(colors=pal["muted"], labelsize=9)
        self.ax.xaxis.label.set_color(pal["muted"])
        self.ax.yaxis.label.set_color(pal["muted"])
        self.ax.title.set_color(pal["text"])
        for name, spine in self.ax.spines.items():
            spine.set_color(pal["spine"])
            spine.set_visible(name in ("left", "bottom"))
        self.ax.grid(True, linestyle="--", alpha=0.6, color=pal["grid"])
        self.ax.set_axisbelow(True)

    # --- helpers ---------------------------------------------------------
    def _parse_date(self, value: str) -> Optional[datetime]:
        text = str(value or "")
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            try:
                return datetime.fromisoformat(text)
            except ValueError:
                return None

    def _title_text(self, title: str) -> str:
        title_text = str(title or "Price Trend")
        if not self._korean_font_ok:
            title_text = sanitize_text_for_matplotlib(title_text, fallback="Price Trend")
        return title_text

    def _apply_date_axis(self, xs: list[datetime]) -> None:
        if mdates is None or self.ax is None or not xs:
            return
        span_years = {x.year for x in xs}
        fmt = "%y.%m.%d" if len(span_years) > 1 else "%m.%d"
        locator = mdates.AutoDateLocator(minticks=3, maxticks=8)
        self.ax.xaxis.set_major_locator(locator)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt))
        if len({x.date() for x in xs}) == 1:
            # 하루치 기록이면 x축이 한 점으로 무너지므로 앞뒤로 여유를 준다.
            from datetime import timedelta

            self.ax.set_xlim(cast(Any, xs[0] - timedelta(days=3)), cast(Any, xs[0] + timedelta(days=3)))

    def _show_canvas(self) -> None:
        if self.canvas is None:
            return
        self.message_label.hide()
        self.canvas.show()
        try:
            self.figure.tight_layout()  # type: ignore[union-attr]
        except Exception:
            pass
        self.canvas.draw()

    def clear(self, message: str = "차트가 없습니다."):
        self._last_render = None
        self.message_label.setText(str(message or "차트가 없습니다."))
        self.message_label.show()
        if self.ax is not None:
            self.ax.clear()
            self._apply_axes_style()
        if self.canvas is not None:
            self.canvas.hide()
            self.canvas.draw_idle()

    # --- public render APIs ---------------------------------------------
    def update_series(
        self,
        series: Sequence[ChartSeries],
        title: str = "",
        *,
        value_formatter: Callable[[float], str] = format_price_axis,
        point_formatter: Optional[Callable[[float], str]] = None,
        show_band: bool = True,
    ) -> None:
        """여러 시세 시리즈를 그린다. 시리즈가 1개면 최저~최고 범위를 띠로 보여 준다."""
        if not MATPLOTLIB_AVAILABLE or self.ax is None or self.canvas is None:
            return
        prepared: list[tuple[ChartSeries, list[datetime], list[float], list[Optional[float]], list[Optional[float]]]] = []
        for s in series:
            rows = []
            mins = list(s.min_vals) if s.min_vals is not None else [None] * len(s.dates)
            maxs = list(s.max_vals) if s.max_vals is not None else [None] * len(s.dates)
            for d, a, mi, ma in zip(s.dates, s.avg, mins, maxs):
                parsed = self._parse_date(d)
                if parsed is None:
                    continue
                try:
                    avg_value = float(a)
                except (TypeError, ValueError):
                    continue
                if avg_value <= 0:
                    continue
                rows.append((parsed, avg_value, _as_float(mi), _as_float(ma)))
            rows.sort(key=lambda r: r[0])
            if rows:
                prepared.append(
                    (s, [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows], [r[3] for r in rows])
                )
        if not prepared:
            self.clear("차트에 그릴 가격 기록이 없습니다.")
            return

        def _render() -> None:
            ax = self.ax
            if ax is None:
                return
            pal = self.palette_colors
            ax.clear()
            self._apply_axes_style()
            single = len(prepared) == 1
            all_x: list[datetime] = []
            for idx, (s, xs, ys, mins, maxs) in enumerate(prepared):
                color = s.color or SERIES_COLORS[idx % len(SERIES_COLORS)]
                all_x.extend(xs)
                if single and show_band and all(v is not None for v in mins) and all(v is not None for v in maxs):
                    ax.fill_between(
                        cast(Any, xs), cast(Any, mins), cast(Any, maxs),
                        color=color, alpha=0.15, linewidth=0, label="최저~최고 범위",
                    )
                ax.plot(
                    cast(Any, xs), cast(Any, ys),
                    marker="o", markersize=4 if len(xs) > 1 else 6,
                    linestyle="-", color=color, linewidth=2, label=s.label,
                )
                if single:
                    ax.annotate(
                        (point_formatter or format_price_point)(ys[-1]),
                        xy=(cast(Any, xs[-1]), ys[-1]),
                        xytext=(6, 6), textcoords="offset points",
                        color=pal["text"], fontsize=9, fontweight="bold",
                    )
            if FuncFormatter is not None:
                ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _pos: value_formatter(v)))
            self._apply_date_axis(all_x)
            ax.set_title(self._title_text(title), color=pal["text"], fontsize=11, loc="left")
            if len(prepared) > 1 or (single and show_band):
                legend = ax.legend(loc="best", fontsize=8, frameon=False)
                if legend is not None:
                    for text in legend.get_texts():
                        text.set_color(pal["muted"])
            self._show_canvas()

        self._last_render = _render
        _render()

    def update_chart(
        self,
        dates: Iterable[str],
        avg: Optional[Iterable[float]] = None,
        min_vals: Optional[Iterable[float]] = None,
        max_vals: Optional[Iterable[float]] = None,
        title: str = "Price Trend",
    ):
        """단일 시리즈 호환 API. ``[(date, price), ...]`` 형태도 받는다."""
        if not MATPLOTLIB_AVAILABLE or self.ax is None or self.canvas is None:
            return
        dates_list = list(dates)
        if not dates_list:
            self.clear("차트가 없습니다.")
            return
        if avg is None and isinstance(dates_list[0], (list, tuple)):
            pairs = [p for p in dates_list if isinstance(p, (list, tuple)) and len(p) >= 2]
            series = ChartSeries(label="가격", dates=[p[0] for p in pairs], avg=[p[1] for p in pairs])
            self.update_series([series], title, show_band=False)
            return
        series = ChartSeries(
            label="평균",
            dates=dates_list,
            avg=list(avg) if avg is not None else [],
            min_vals=list(min_vals) if min_vals is not None else None,
            max_vals=list(max_vals) if max_vals is not None else None,
        )
        self.update_series([series], title, show_band=min_vals is not None and max_vals is not None)


def _as_float(value) -> Optional[float]:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None
