from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    FigureCanvas = None
    Figure = None
    mdates = None
    MATPLOTLIB_AVAILABLE = False
from datetime import datetime
from typing import Optional, Iterable, Any, cast

from src.utils.plot import setup_korean_font, sanitize_text_for_matplotlib

class ChartWidget(QWidget):
    """v10.0: Analytics Chart using Matplotlib"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._korean_font_ok = False
        layout = QVBoxLayout(self)
        if MATPLOTLIB_AVAILABLE and Figure is not None and FigureCanvas is not None:
            self._korean_font_ok = bool(setup_korean_font())
            self.figure = Figure(figsize=(5, 3), dpi=100, facecolor='#2b2b2b')
            self.canvas = FigureCanvas(self.figure)
            self.ax = self.figure.add_subplot(111)
            self.ax.set_facecolor('#2b2b2b')
            self.ax.tick_params(colors='white')
            self.ax.xaxis.label.set_color('white')
            self.ax.yaxis.label.set_color('white')
            for spine in self.ax.spines.values():
                spine.set_color('#555555')
            layout.addWidget(self.canvas)
        else:
            layout.addWidget(QLabel("Matplotlib 라이브러리가 설치되지 않았습니다.\n(pip install matplotlib)"))

    def _parse_date(self, value: str) -> Optional[datetime]:
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None

    def update_chart(
        self,
        dates: Iterable[str],
        avg: Optional[Iterable[float]] = None,
        min_vals: Optional[Iterable[float]] = None,
        max_vals: Optional[Iterable[float]] = None,
        title: str = "Price Trend",
    ):
        if not MATPLOTLIB_AVAILABLE or mdates is None:
            return
        title_text = str(title or "Price Trend")
        if not self._korean_font_ok:
            title_text = sanitize_text_for_matplotlib(title_text, fallback="Price Trend")

        dates_list = list(dates)
        if not dates_list:
            return

        # Backward compatibility: list of (date, price) tuples.
        if avg is None and isinstance(dates_list[0], (list, tuple)):
            data = dates_list
            if not data:
                return
            data.sort(key=lambda x: x[0])
            parsed_points: list[tuple[datetime, float]] = []
            for raw_date, raw_price in data:
                parsed_date = self._parse_date(raw_date)
                if parsed_date is None:
                    continue
                try:
                    parsed_price = float(raw_price)
                except (TypeError, ValueError):
                    parsed_price = 0.0
                parsed_points.append((parsed_date, parsed_price))
            if not parsed_points:
                return
            x = [p[0] for p in parsed_points]
            y = [p[1] for p in parsed_points]
            self.ax.clear()
            self.ax.plot(cast(Any, x), cast(Any, y), marker='o', linestyle='-', color='#3498db', linewidth=2)
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
            self.ax.grid(True, linestyle='--', alpha=0.3)
            self.ax.set_title(title_text, color='white')
            self.canvas.draw()
            return

        avg_list = list(avg) if avg is not None else []
        min_list = list(min_vals) if min_vals is not None else None
        max_list = list(max_vals) if max_vals is not None else None

        parsed_series: list[tuple[datetime, float, float | None, float | None]] = []
        if min_list is None or max_list is None:
            merged = list(zip(dates_list, avg_list))
            merged.sort(key=lambda x: x[0])
            for d, a in merged:
                parsed_date = self._parse_date(d)
                if parsed_date is None:
                    continue
                try:
                    avg_value = float(a)
                except (TypeError, ValueError):
                    avg_value = 0.0
                parsed_series.append((parsed_date, avg_value, None, None))
        else:
            merged = list(zip(dates_list, avg_list, min_list, max_list))
            merged.sort(key=lambda x: x[0])
            for d, a, mi, ma in merged:
                parsed_date = self._parse_date(d)
                if parsed_date is None:
                    continue
                try:
                    avg_value = float(a)
                except (TypeError, ValueError):
                    avg_value = 0.0
                try:
                    min_value = float(mi)
                except (TypeError, ValueError):
                    min_value = None
                try:
                    max_value = float(ma)
                except (TypeError, ValueError):
                    max_value = None
                parsed_series.append((parsed_date, avg_value, min_value, max_value))

        if not parsed_series:
            return

        x = [p[0] for p in parsed_series]
        y_avg = [p[1] for p in parsed_series]
        y_min = [float(p[2]) for p in parsed_series if p[2] is not None] if min_list is not None else []
        y_max = [float(p[3]) for p in parsed_series if p[3] is not None] if max_list is not None else []

        self.ax.clear()
        if y_min and y_max and len(y_min) == len(x) and len(y_max) == len(x):
            self.ax.fill_between(cast(Any, x), cast(Any, y_min), cast(Any, y_max), color='#3498db', alpha=0.15)
        self.ax.plot(cast(Any, x), cast(Any, y_avg), marker='o', linestyle='-', color='#3498db', linewidth=2)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        self.ax.grid(True, linestyle='--', alpha=0.3)
        self.ax.set_title(title_text, color='white')
        self.canvas.draw()
