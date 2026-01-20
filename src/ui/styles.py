"""
UI 스타일시트 모듈 (v14.0)
- Dark/Light 테마 완전 지원
- Glassmorphism 효과
- 마이크로 애니메이션
"""

# ===== 색상 팔레트 =====
COLORS = {
    "dark": {
        "bg_primary": "#0f0f1a",
        "bg_secondary": "#1a1a2e",
        "bg_card": "rgba(30, 30, 40, 0.85)",
        "bg_input": "#1e1e2e",
        "border": "rgba(255, 255, 255, 0.1)",
        "border_focus": "#f59e0b",  # Warm amber
        "text_primary": "#f0f0f0",
        "text_secondary": "#a0a0b0",
        "accent": "#f59e0b",  # Warm amber
        "accent_hover": "#d97706",  # Darker amber
        "success": "#22c55e",
        "warning": "#f59e0b",
        "error": "#ef4444",
        "trade_매매": "#ef4444",
        "trade_전세": "#22c55e",
        "trade_월세": "#3b82f6",
    },
    "light": {
        "bg_primary": "#f8fafc",
        "bg_secondary": "#ffffff",
        "bg_card": "rgba(255, 255, 255, 0.9)",
        "bg_input": "#f1f5f9",
        "border": "#e2e8f0",
        "border_focus": "#ea580c",  # Warm orange
        "text_primary": "#1e293b",
        "text_secondary": "#64748b",
        "accent": "#ea580c",  # Warm orange
        "accent_hover": "#c2410c",  # Darker orange
        "success": "#16a34a",
        "warning": "#d97706",
        "error": "#dc2626",
        "trade_매매": "#dc2626",
        "trade_전세": "#16a34a",
        "trade_월세": "#2563eb",
    }
}


def get_dark_stylesheet():
    """다크 테마 스타일시트 (v14.0 - Glassmorphism with Warm Colors)"""
    return """
/* ========================================
   v14.0 Enhanced Dark Theme - Warm Glassmorphism
   ======================================== */

/* === Base === */
QMainWindow, QWidget { 
    background-color: #0f0f1a; 
    color: #f0f0f0; 
    font-family: 'Malgun Gothic', 'Segoe UI', -apple-system, sans-serif;
    font-size: 13px;
}

/* === Glassmorphism Card (GroupBox) === */
QGroupBox { 
    background-color: rgba(30, 30, 40, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px; 
    margin-top: 1.2em; 
    padding: 18px;
    padding-top: 28px;
    font-weight: 600;
    font-size: 14px;
}
QGroupBox::title { 
    subcontrol-origin: margin; 
    subcontrol-position: top left; 
    padding: 6px 14px; 
    color: #f59e0b;
    background: transparent;
    font-weight: 700;
}

/* === Buttons with Transitions === */
QPushButton { 
    background-color: rgba(245, 158, 11, 0.15);
    color: #f59e0b; 
    border: 1px solid rgba(245, 158, 11, 0.3);
    padding: 10px 20px; 
    border-radius: 8px; 
    font-weight: 600;
    min-height: 28px;
}
QPushButton:hover { 
    background-color: rgba(245, 158, 11, 0.25);
    border-color: #f59e0b;
}
QPushButton:pressed { 
    background-color: rgba(245, 158, 11, 0.35);
}
QPushButton:disabled { 
    background-color: rgba(50, 50, 70, 0.5);
    color: #555; 
    border-color: rgba(255, 255, 255, 0.05);
}

/* Primary Action Button */
QPushButton#startButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f59e0b, stop:1 #d97706);
    color: #0f0f1a;
    font-size: 15px;
    font-weight: 700;
    padding: 12px 24px;
    border: none;
}
QPushButton#startButton:hover { 
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fbbf24, stop:1 #f59e0b);
}
QPushButton#startButton:pressed { 
    background: #b45309;
}

/* Stop Button */
QPushButton#stopButton {
    background-color: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.3);
}
QPushButton#stopButton:hover { 
    background-color: rgba(239, 68, 68, 0.25);
    border-color: #ef4444;
}

/* Save Button */
QPushButton#saveButton {
    background-color: rgba(34, 197, 94, 0.15);
    color: #22c55e;
    border: 1px solid rgba(34, 197, 94, 0.3);
}
QPushButton#saveButton:hover { 
    background-color: rgba(34, 197, 94, 0.25);
    border-color: #22c55e;
}

/* === Input Fields === */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTimeEdit { 
    padding: 10px 14px; 
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    background-color: rgba(30, 30, 46, 0.8);
    color: #f0f0f0;
    selection-background-color: #f59e0b;
    selection-color: #0f0f1a;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { 
    border: 1px solid #f59e0b;
    background-color: rgba(30, 30, 46, 1);
}
QComboBox::drop-down {
    border: none;
    padding-right: 10px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #f59e0b;
    margin-right: 8px;
}

/* === Table === */
QTableWidget { 
    background-color: rgba(30, 30, 46, 0.6);
    gridline-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    selection-background-color: rgba(245, 158, 11, 0.2);
    selection-color: #ffffff;
    alternate-background-color: rgba(40, 40, 60, 0.5);
}
QHeaderView::section { 
    background-color: rgba(50, 50, 70, 0.9);
    padding: 10px 8px;
    border: none;
    color: #f59e0b;
    font-weight: 700;
    font-size: 12px;
    border-bottom: 2px solid rgba(245, 158, 11, 0.3);
}
QTableWidget::item { 
    padding: 8px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}
QTableWidget::item:selected {
    background-color: rgba(245, 158, 11, 0.15);
}

/* === Scrollbars === */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 8px;
    margin: 4px 2px;
}
QScrollBar::handle:vertical {
    background: rgba(245, 158, 11, 0.3);
    min-height: 30px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(245, 158, 11, 0.5);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 8px;
    margin: 2px 4px;
}
QScrollBar::handle:horizontal {
    background: rgba(245, 158, 11, 0.3);
    min-width: 30px;
    border-radius: 4px;
}

/* === Tab Widget === */
QTabWidget::pane { 
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    background-color: rgba(20, 20, 35, 0.5);
    margin-top: -1px;
}
QTabBar::tab {
    background: transparent;
    color: #888;
    padding: 12px 24px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    margin-right: 4px;
    font-weight: 500;
}
QTabBar::tab:selected {
    background: rgba(245, 158, 11, 0.15);
    color: #f59e0b;
    font-weight: 700;
    border-bottom: 2px solid #f59e0b;
}
QTabBar::tab:hover:!selected {
    background: rgba(255, 255, 255, 0.05);
    color: #aaa;
}

/* === Progress Bar === */
QProgressBar {
    border: none;
    border-radius: 6px;
    text-align: center;
    background-color: rgba(40, 50, 80, 0.6);
    color: #fff;
    font-weight: 600;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #d97706);
    border-radius: 5px;
}

/* === Checkbox === */
QCheckBox {
    spacing: 8px;
    color: #f0f0f0;
}
QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 4px;
    border: 2px solid rgba(255, 255, 255, 0.2);
    background: transparent;
}
QCheckBox::indicator:checked {
    background-color: #f59e0b;
    border-color: #f59e0b;
}
QCheckBox::indicator:hover {
    border-color: #f59e0b;
}

/* === List Widget === */
QListWidget {
    background-color: rgba(30, 30, 46, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 5px;
}
QListWidget::item {
    padding: 10px;
    border-radius: 6px;
    margin: 2px;
}
QListWidget::item:selected {
    background-color: rgba(245, 158, 11, 0.2);
}
QListWidget::item:hover {
    background-color: rgba(255, 255, 255, 0.05);
}

/* === Tooltips === */
QToolTip { 
    color: #f0f0f0;
    background-color: rgba(30, 30, 50, 0.95);
    border: 1px solid #f59e0b;
    border-radius: 6px;
    padding: 8px 12px;
}

/* === Menu === */
QMenuBar {
    background-color: transparent;
    color: #f0f0f0;
}
QMenuBar::item:selected {
    background-color: rgba(245, 158, 11, 0.15);
}
QMenu {
    background-color: rgba(30, 30, 50, 0.98);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 5px;
}
QMenu::item {
    padding: 8px 25px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: rgba(245, 158, 11, 0.2);
}

/* === Status Bar === */
QStatusBar {
    background-color: rgba(15, 15, 26, 0.9);
    color: #888;
}

/* === Splitter === */
QSplitter::handle {
    background-color: rgba(245, 158, 11, 0.1);
}
QSplitter::handle:hover {
    background-color: rgba(245, 158, 11, 0.3);
}

/* === Text Browser === */
QTextBrowser {
    background-color: rgba(30, 30, 46, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 10px;
    color: #f0f0f0;
}
"""


def get_light_stylesheet():
    """라이트 테마 스타일시트 (v14.0 - Clean & Modern)"""
    return """
/* ========================================
   v14.0 Light Theme - Clean & Modern
   ======================================== */

/* === Base === */
QMainWindow, QWidget { 
    background-color: #f8fafc;
    color: #1e293b;
    font-family: 'Malgun Gothic', 'Segoe UI', -apple-system, sans-serif;
    font-size: 13px;
}

/* === Card Style (GroupBox) === */
QGroupBox { 
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 16px; 
    margin-top: 1.2em; 
    padding: 18px;
    padding-top: 28px;
    font-weight: 600;
    font-size: 14px;
}
QGroupBox::title { 
    subcontrol-origin: margin; 
    subcontrol-position: top left; 
    padding: 6px 14px; 
    color: #0ea5e9;
    background: transparent;
    font-weight: 700;
}

/* === Buttons === */
QPushButton { 
    background-color: #f1f5f9;
    color: #0ea5e9;
    border: 1px solid #e2e8f0;
    padding: 10px 20px; 
    border-radius: 8px; 
    font-weight: 600;
    min-height: 28px;
}
QPushButton:hover { 
    background-color: #e2e8f0;
    border-color: #0ea5e9;
}
QPushButton:pressed { 
    background-color: #cbd5e1;
}
QPushButton:disabled { 
    background-color: #f1f5f9;
    color: #94a3b8;
    border-color: #e2e8f0;
}

/* Primary Action Button */
QPushButton#startButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0ea5e9, stop:1 #0284c7);
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
    padding: 12px 24px;
    border: none;
}
QPushButton#startButton:hover { 
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #38bdf8, stop:1 #0ea5e9);
}

/* Stop Button */
QPushButton#stopButton {
    background-color: #fef2f2;
    color: #dc2626;
    border: 1px solid #fecaca;
}
QPushButton#stopButton:hover { 
    background-color: #fee2e2;
    border-color: #dc2626;
}

/* Save Button */
QPushButton#saveButton {
    background-color: #f0fdf4;
    color: #16a34a;
    border: 1px solid #bbf7d0;
}
QPushButton#saveButton:hover { 
    background-color: #dcfce7;
    border-color: #16a34a;
}

/* === Input Fields === */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTimeEdit { 
    padding: 10px 14px; 
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background-color: #ffffff;
    color: #1e293b;
    selection-background-color: #0ea5e9;
    selection-color: #ffffff;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { 
    border: 2px solid #0ea5e9;
}
QComboBox::drop-down {
    border: none;
    padding-right: 10px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #0ea5e9;
    margin-right: 8px;
}

/* === Table === */
QTableWidget { 
    background-color: #ffffff;
    gridline-color: #f1f5f9;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    selection-background-color: #e0f2fe;
    selection-color: #0c4a6e;
    alternate-background-color: #f8fafc;
}
QHeaderView::section { 
    background-color: #f1f5f9;
    padding: 10px 8px;
    border: none;
    color: #0ea5e9;
    font-weight: 700;
    font-size: 12px;
    border-bottom: 2px solid #e2e8f0;
}
QTableWidget::item { 
    padding: 8px;
    border-bottom: 1px solid #f1f5f9;
}
QTableWidget::item:selected {
    background-color: #e0f2fe;
}

/* === Scrollbars === */
QScrollBar:vertical {
    border: none;
    background: #f1f5f9;
    width: 8px;
    margin: 4px 2px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #cbd5e1;
    min-height: 30px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #94a3b8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    border: none;
    background: #f1f5f9;
    height: 8px;
    margin: 2px 4px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #cbd5e1;
    min-width: 30px;
    border-radius: 4px;
}

/* === Tab Widget === */
QTabWidget::pane { 
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    background-color: #ffffff;
    margin-top: -1px;
}
QTabBar::tab {
    background: transparent;
    color: #64748b;
    padding: 12px 24px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    margin-right: 4px;
    font-weight: 500;
}
QTabBar::tab:selected {
    background: #e0f2fe;
    color: #0ea5e9;
    font-weight: 700;
    border-bottom: 2px solid #0ea5e9;
}
QTabBar::tab:hover:!selected {
    background: #f1f5f9;
    color: #475569;
}

/* === Progress Bar === */
QProgressBar {
    border: none;
    border-radius: 6px;
    text-align: center;
    background-color: #e2e8f0;
    color: #1e293b;
    font-weight: 600;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0ea5e9, stop:1 #38bdf8);
    border-radius: 5px;
}

/* === Checkbox === */
QCheckBox {
    spacing: 8px;
    color: #1e293b;
}
QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 4px;
    border: 2px solid #cbd5e1;
    background: #ffffff;
}
QCheckBox::indicator:checked {
    background-color: #0ea5e9;
    border-color: #0ea5e9;
}
QCheckBox::indicator:hover {
    border-color: #0ea5e9;
}

/* === List Widget === */
QListWidget {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 5px;
}
QListWidget::item {
    padding: 10px;
    border-radius: 6px;
    margin: 2px;
}
QListWidget::item:selected {
    background-color: #e0f2fe;
    color: #0c4a6e;
}
QListWidget::item:hover {
    background-color: #f1f5f9;
}

/* === Tooltips === */
QToolTip { 
    color: #1e293b;
    background-color: #ffffff;
    border: 1px solid #0ea5e9;
    border-radius: 6px;
    padding: 8px 12px;
}

/* === Menu === */
QMenuBar {
    background-color: #f8fafc;
    color: #1e293b;
}
QMenuBar::item:selected {
    background-color: #e0f2fe;
    border-radius: 4px;
}
QMenu {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 5px;
}
QMenu::item {
    padding: 8px 25px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #e0f2fe;
}

/* === Status Bar === */
QStatusBar {
    background-color: #f1f5f9;
    color: #64748b;
}

/* === Splitter === */
QSplitter::handle {
    background-color: #e2e8f0;
}
QSplitter::handle:hover {
    background-color: #0ea5e9;
}

/* === Text Browser === */
QTextBrowser {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 10px;
    color: #1e293b;
}
"""


def get_stylesheet(theme="dark"):
    """테마에 따른 스타일시트 반환"""
    if theme == "dark":
        return get_dark_stylesheet()
    else:
        return get_light_stylesheet()
