<<<<<<< HEAD
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    try:
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure
        import matplotlib.dates as mdates
        MATPLOTLIB_AVAILABLE = True
    except ImportError:
        MATPLOTLIB_AVAILABLE = False
from datetime import datetime
from typing import List, Tuple, Optional, Iterable

class ChartWidget(QWidget):
    """v10.0: Analytics Chart using Matplotlib"""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        if MATPLOTLIB_AVAILABLE:
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
        if not MATPLOTLIB_AVAILABLE:
            return

        dates_list = list(dates)
        if not dates_list:
            return

        # Backward compatibility: list of (date, price) tuples.
        if avg is None and isinstance(dates_list[0], (list, tuple)):
            data = dates_list
            if not data:
                return
            data.sort(key=lambda x: x[0])
            parsed = [(self._parse_date(d[0]), d[1]) for d in data]
            parsed = [p for p in parsed if p[0] is not None]
            if not parsed:
                return
            x = [p[0] for p in parsed]
            y = [p[1] for p in parsed]
            self.ax.clear()
            self.ax.plot(x, y, marker='o', linestyle='-', color='#3498db', linewidth=2)
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
            self.ax.grid(True, linestyle='--', alpha=0.3)
            self.ax.set_title(title, color='white')
            self.canvas.draw()
            return

        avg_list = list(avg) if avg is not None else []
        min_list = list(min_vals) if min_vals is not None else None
        max_list = list(max_vals) if max_vals is not None else None

        if min_list is None or max_list is None:
            merged = list(zip(dates_list, avg_list))
            merged.sort(key=lambda x: x[0])
            parsed = []
            for d, a in merged:
                parsed_date = self._parse_date(d)
                if parsed_date is None:
                    continue
                parsed.append((parsed_date, a, None, None))
        else:
            merged = list(zip(dates_list, avg_list, min_list, max_list))
            merged.sort(key=lambda x: x[0])
            parsed = []
            for d, a, mi, ma in merged:
                parsed_date = self._parse_date(d)
                if parsed_date is None:
                    continue
                parsed.append((parsed_date, a, mi, ma))

        if not parsed:
            return

        x = [p[0] for p in parsed]
        y_avg = [p[1] for p in parsed]
        y_min = [p[2] for p in parsed] if min_list is not None else []
        y_max = [p[3] for p in parsed] if max_list is not None else []

        self.ax.clear()
        if y_min and y_max:
            self.ax.fill_between(x, y_min, y_max, color='#3498db', alpha=0.15)
        self.ax.plot(x, y_avg, marker='o', linestyle='-', color='#3498db', linewidth=2)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        self.ax.grid(True, linestyle='--', alpha=0.3)
        self.ax.set_title(title, color='white')
        self.canvas.draw()
=======
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    try:
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure
        import matplotlib.dates as mdates
        MATPLOTLIB_AVAILABLE = True
    except ImportError:
        MATPLOTLIB_AVAILABLE = False
from datetime import datetime
from typing import List, Tuple, Optional, Iterable

class ChartWidget(QWidget):
    """v10.0: Analytics Chart using Matplotlib"""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        if MATPLOTLIB_AVAILABLE:
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
        if not MATPLOTLIB_AVAILABLE:
            return

        dates_list = list(dates)
        if not dates_list:
            return

        # Backward compatibility: list of (date, price) tuples.
        if avg is None and isinstance(dates_list[0], (list, tuple)):
            data = dates_list
            if not data:
                return
            data.sort(key=lambda x: x[0])
            parsed = [(self._parse_date(d[0]), d[1]) for d in data]
            parsed = [p for p in parsed if p[0] is not None]
            if not parsed:
                return
            x = [p[0] for p in parsed]
            y = [p[1] for p in parsed]
            self.ax.clear()
            self.ax.plot(x, y, marker='o', linestyle='-', color='#3498db', linewidth=2)
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
            self.ax.grid(True, linestyle='--', alpha=0.3)
            self.ax.set_title(title, color='white')
            self.canvas.draw()
            return

        avg_list = list(avg) if avg is not None else []
        min_list = list(min_vals) if min_vals is not None else None
        max_list = list(max_vals) if max_vals is not None else None

        if min_list is None or max_list is None:
            merged = list(zip(dates_list, avg_list))
            merged.sort(key=lambda x: x[0])
            parsed = []
            for d, a in merged:
                parsed_date = self._parse_date(d)
                if parsed_date is None:
                    continue
                parsed.append((parsed_date, a, None, None))
        else:
            merged = list(zip(dates_list, avg_list, min_list, max_list))
            merged.sort(key=lambda x: x[0])
            parsed = []
            for d, a, mi, ma in merged:
                parsed_date = self._parse_date(d)
                if parsed_date is None:
                    continue
                parsed.append((parsed_date, a, mi, ma))

        if not parsed:
            return

        x = [p[0] for p in parsed]
        y_avg = [p[1] for p in parsed]
        y_min = [p[2] for p in parsed] if min_list is not None else []
        y_max = [p[3] for p in parsed] if max_list is not None else []

        self.ax.clear()
        if y_min and y_max:
            self.ax.fill_between(x, y_min, y_max, color='#3498db', alpha=0.15)
        self.ax.plot(x, y_avg, marker='o', linestyle='-', color='#3498db', linewidth=2)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        self.ax.grid(True, linestyle='--', alpha=0.3)
        self.ax.set_title(title, color='white')
        self.canvas.draw()
>>>>>>> 39500298f217e86700ed82ba5199a76ef9100859
