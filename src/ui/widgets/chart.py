from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
try:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
from datetime import datetime
from typing import List, Tuple

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

    def update_chart(self, data: List[Tuple[str, int]]):
        if not MATPLOTLIB_AVAILABLE or not data: return
        self.ax.clear()
        
        # Sort by date
        data.sort(key=lambda x: x[0])
        
        dates = [datetime.strptime(d[0], "%Y-%m-%d") for d in data]
        prices = [d[1] for d in data]
        
        self.ax.plot(dates, prices, marker='o', linestyle='-', color='#3498db', linewidth=2)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        self.ax.grid(True, linestyle='--', alpha=0.3)
        self.ax.set_title("Price Trend", color='white')
        self.canvas.draw()
