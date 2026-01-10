"""
UI 스타일시트 - 디자인 토큰 시스템 기반 (v14.0 리팩토링)
Modern Dark/Light Theme with Enhanced UX
"""

# ============ 디자인 토큰 ============
DESIGN_TOKENS = {
    "dark": {
        # 배경색
        "bg_primary": "#0f0f1a",
        "bg_secondary": "#1a1a2e",
        "bg_card": "#252540",
        "bg_elevated": "#2f2f4a",
        "bg_input": "rgba(255, 255, 255, 0.08)",
        "bg_hover": "rgba(255, 255, 255, 0.12)",
        
        # 텍스트
        "text_primary": "#ffffff",
        "text_secondary": "#a0a0b0",
        "text_muted": "#666677",
        
        # 액센트
        "accent_blue": "#4a9eff",
        "accent_blue_hover": "#60a5fa",
        "accent_green": "#22c55e",
        "accent_green_hover": "#4ade80",
        "accent_red": "#ef4444",
        "accent_red_hover": "#f87171",
        "accent_purple": "#8b5cf6",
        "accent_yellow": "#f59e0b",
        
        # 테두리
        "border_subtle": "rgba(255, 255, 255, 0.1)",
        "border_medium": "rgba(255, 255, 255, 0.2)",
        "border_focus": "#4a9eff",
        
        # 그림자
        "shadow_sm": "rgba(0, 0, 0, 0.2)",
        "shadow_md": "rgba(0, 0, 0, 0.3)",
        "shadow_lg": "rgba(0, 0, 0, 0.5)",
        
        # 차트 색상
        "chart_1": "#ef4444",
        "chart_2": "#22c55e",
        "chart_3": "#3b82f6",
    },
    "light": {
        # 배경색
        "bg_primary": "#f8fafc",
        "bg_secondary": "#ffffff",
        "bg_card": "#ffffff",
        "bg_elevated": "#ffffff",
        "bg_input": "#ffffff",
        "bg_hover": "#e2e8f0",
        
        # 텍스트
        "text_primary": "#1e293b",
        "text_secondary": "#475569",
        "text_muted": "#94a3b8",
        
        # 액센트
        "accent_blue": "#3b82f6",
        "accent_blue_hover": "#60a5fa",
        "accent_green": "#16a34a",
        "accent_green_hover": "#22c55e",
        "accent_red": "#dc2626",
        "accent_red_hover": "#ef4444",
        "accent_purple": "#7c3aed",
        "accent_yellow": "#d97706",
        
        # 테두리
        "border_subtle": "#e2e8f0",
        "border_medium": "#cbd5e1",
        "border_focus": "#3b82f6",
        
        # 그림자
        "shadow_sm": "rgba(0, 0, 0, 0.05)",
        "shadow_md": "rgba(0, 0, 0, 0.1)",
        "shadow_lg": "rgba(0, 0, 0, 0.15)",
        
        # 차트 색상
        "chart_1": "#ef4444",
        "chart_2": "#22c55e",
        "chart_3": "#3b82f6",
    }
}

# 공통 값
RADIUS = {
    "sm": "6px",
    "md": "10px",
    "lg": "14px",
    "xl": "20px",
    "full": "9999px"
}

SPACING = {
    "xs": "4px",
    "sm": "8px",
    "md": "12px",
    "lg": "16px",
    "xl": "24px"
}

FONT_SIZE = {
    "xs": "11px",
    "sm": "12px",
    "md": "13px",
    "lg": "14px",
    "xl": "16px",
    "2xl": "20px",
    "3xl": "24px"
}

TRANSITION = "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)"


def get_dark_stylesheet():
    t = DESIGN_TOKENS["dark"]
    return f"""
/* === v14.0 Enhanced Dark Theme with Design Tokens === */

/* Main Window & Base */
QMainWindow, QWidget {{ 
    background-color: {t["bg_secondary"]}; 
    color: {t["text_primary"]}; 
    font-family: 'Malgun Gothic', 'Segoe UI', -apple-system, sans-serif;
    font-size: {FONT_SIZE["md"]};
}}

/* GroupBox - Modern Card Style */
QGroupBox {{ 
    border: 1px solid {t["border_subtle"]}; 
    border-radius: {RADIUS["lg"]}; 
    margin-top: 1.5em; 
    padding: {SPACING["lg"]};
    padding-top: {SPACING["xl"]};
    font-weight: 600;
    font-size: {FONT_SIZE["lg"]};
    background-color: {t["bg_card"]};
}}
QGroupBox::title {{ 
    subcontrol-origin: margin; 
    left: {SPACING["lg"]}; 
    padding: 0 {SPACING["md"]};
    color: {t["accent_blue"]};
    font-weight: bold;
}}

/* Input Fields - Glassmorphism */
QLineEdit, QSpinBox, QTimeEdit, QDoubleSpinBox, QComboBox {{ 
    background-color: {t["bg_input"]}; 
    border: 1px solid {t["border_subtle"]}; 
    border-radius: {RADIUS["md"]}; 
    padding: {SPACING["sm"]} {SPACING["md"]}; 
    color: {t["text_primary"]}; 
    min-height: 34px;
    selection-background-color: {t["accent_blue"]};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ 
    border: 2px solid {t["accent_blue"]};
    background-color: {t["bg_hover"]};
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{ 
    border-color: {t["border_medium"]};
    background-color: {t["bg_hover"]};
}}
QComboBox::drop-down {{
    border: none;
    padding-right: {SPACING["sm"]};
}}
QComboBox QAbstractItemView {{
    background-color: {t["bg_elevated"]};
    border: 1px solid {t["border_medium"]};
    border-radius: {RADIUS["md"]};
    selection-background-color: {t["accent_blue"]};
    padding: {SPACING["xs"]};
}}

/* Table Widget - Enhanced */
QTableWidget {{ 
    background-color: {t["bg_primary"]}; 
    gridline-color: {t["border_subtle"]}; 
    border: 1px solid {t["border_subtle"]}; 
    border-radius: {RADIUS["lg"]}; 
    color: {t["text_primary"]}; 
    alternate-background-color: {t["bg_card"]};
    outline: none;
}}
QTableWidget::item {{
    border-bottom: 1px solid {t["border_subtle"]};
    padding: 6px {SPACING["sm"]};
}}
QTableWidget::item:selected {{ 
    background-color: {t["accent_blue"]}; 
    color: {t["text_primary"]};
}}
QTableWidget::item:hover {{ 
    background-color: {t["bg_hover"]}; 
}}
QHeaderView::section {{ 
    background-color: {t["bg_elevated"]}; 
    padding: {SPACING["md"]}; 
    border: none;
    border-bottom: 2px solid {t["accent_blue"]};
    color: {t["text_primary"]}; 
    font-weight: bold;
    font-size: {FONT_SIZE["sm"]};
}}
QHeaderView::section:first {{
    border-top-left-radius: {RADIUS["md"]};
}}
QHeaderView::section:last {{
    border-top-right-radius: {RADIUS["md"]};
}}

/* Text Browser / Log */
QTextBrowser {{ 
    background-color: {t["bg_primary"]}; 
    color: {t["accent_green"]}; 
    border: 1px solid {t["border_subtle"]}; 
    border-radius: {RADIUS["lg"]}; 
    font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace; 
    font-size: {FONT_SIZE["sm"]};
    padding: {SPACING["md"]};
    line-height: 1.5;
}}

/* Buttons - Enhanced with Gradients & Transitions */
QPushButton {{ 
    background-color: {t["bg_elevated"]};
    border: 1px solid {t["border_subtle"]}; 
    border-radius: {RADIUS["md"]}; 
    padding: {SPACING["md"]} {SPACING["xl"]}; 
    color: {t["text_primary"]}; 
    font-weight: 600; 
    min-height: 38px;
}}
QPushButton:hover {{ 
    background-color: {t["bg_hover"]};
    border-color: {t["border_medium"]};
}}
QPushButton:pressed {{ 
    background-color: {t["bg_card"]};
    transform: scale(0.98);
}}
QPushButton:disabled {{ 
    background-color: {t["bg_primary"]}; 
    color: {t["text_muted"]}; 
    border-color: {t["border_subtle"]};
}}

/* Start Button - Green Gradient */
QPushButton#startButton {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 {t["accent_green_hover"]}, stop:1 {t["accent_green"]});
    border: none;
    color: #fff;
    font-size: {FONT_SIZE["xl"]};
    font-weight: bold;
}}
QPushButton#startButton:hover {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 #6ee7b7, stop:1 {t["accent_green_hover"]});
}}
QPushButton#startButton:disabled {{
    background: rgba(34, 197, 94, 0.3);
    color: rgba(255, 255, 255, 0.5);
}}

/* Stop Button - Red Gradient */
QPushButton#stopButton {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 {t["accent_red_hover"]}, stop:1 {t["accent_red"]});
    border: none;
    color: #fff;
    font-weight: bold;
}}
QPushButton#stopButton:hover {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 #fca5a5, stop:1 {t["accent_red_hover"]});
}}

/* Save Button - Blue Gradient */
QPushButton#saveButton {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 {t["accent_blue_hover"]}, stop:1 {t["accent_blue"]});
    border: none;
    color: #fff;
    font-weight: bold;
}}
QPushButton#saveButton:hover {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 #93c5fd, stop:1 {t["accent_blue_hover"]});
}}

/* Link Button - Purple */
QPushButton#linkButton {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 #a78bfa, stop:1 {t["accent_purple"]});
    border: none;
    min-width: 65px; 
    padding: 6px {SPACING["md"]}; 
    min-height: 28px;
    font-size: {FONT_SIZE["sm"]};
    color: #fff;
}}
QPushButton#linkButton:hover {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 #c4b5fd, stop:1 #a78bfa);
}}

/* Progress Bar - Animated Gradient */
QProgressBar {{ 
    border: none;
    border-radius: {RADIUS["lg"]}; 
    text-align: center; 
    background-color: {t["bg_primary"]}; 
    color: {t["text_primary"]}; 
    min-height: 28px;
    font-weight: bold;
}}
QProgressBar::chunk {{ 
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 {t["accent_blue"]}, stop:0.5 {t["accent_purple"]}, stop:1 {t["accent_green"]});
    border-radius: {RADIUS["md"]};
}}

/* Checkbox & Radio */
QCheckBox, QRadioButton {{ 
    color: {t["text_primary"]}; 
    spacing: {SPACING["md"]};
    font-size: {FONT_SIZE["md"]};
}}
QCheckBox::indicator {{ 
    width: 22px; 
    height: 22px; 
    border-radius: {RADIUS["sm"]}; 
    border: 2px solid {t["border_medium"]}; 
    background-color: {t["bg_input"]};
}}
QCheckBox::indicator:hover {{
    border-color: {t["accent_blue"]};
    background-color: {t["bg_hover"]};
}}
QCheckBox::indicator:checked {{ 
    background-color: {t["accent_blue"]}; 
    border-color: {t["accent_blue_hover"]};
}}

/* Tab Widget - Modern */
QTabWidget::pane {{ 
    border: 1px solid {t["border_subtle"]}; 
    border-radius: {RADIUS["lg"]}; 
    background-color: {t["bg_card"]};
    margin-top: -1px;
}}
QTabBar::tab {{ 
    background-color: {t["bg_elevated"]};
    color: {t["text_secondary"]}; 
    padding: {SPACING["md"]} {SPACING["xl"]}; 
    margin-right: 4px; 
    border-top-left-radius: {RADIUS["md"]}; 
    border-top-right-radius: {RADIUS["md"]};
    font-size: {FONT_SIZE["md"]};
    font-weight: 500;
}}
QTabBar::tab:selected {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 {t["accent_blue"]}, stop:1 #3b5998);
    color: {t["text_primary"]};
    font-weight: bold;
}}
QTabBar::tab:hover:!selected {{ 
    background-color: {t["bg_hover"]};
    color: {t["text_primary"]};
}}

/* Scroll Bars - Minimal */
QScrollBar:vertical {{ 
    background-color: transparent; 
    width: 12px; 
    border-radius: 6px;
    margin: 3px;
}}
QScrollBar::handle:vertical {{ 
    background-color: {t["border_medium"]}; 
    border-radius: 5px; 
    min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{ 
    background-color: {t["text_muted"]};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ 
    height: 0px;
}}
QScrollBar:horizontal {{
    background-color: transparent;
    height: 12px;
    border-radius: 6px;
    margin: 3px;
}}
QScrollBar::handle:horizontal {{
    background-color: {t["border_medium"]};
    border-radius: 5px;
    min-width: 40px;
}}

/* Menu - Modern Dropdown */
QMenu {{ 
    background-color: {t["bg_elevated"]};
    border: 1px solid {t["border_medium"]}; 
    border-radius: {RADIUS["lg"]};
    color: {t["text_primary"]}; 
    padding: {SPACING["sm"]};
}}
QMenu::item {{ 
    padding: {SPACING["md"]} {SPACING["xl"]};
    border-radius: {RADIUS["sm"]};
    margin: 2px;
}}
QMenu::item:selected {{ 
    background-color: {t["accent_blue"]};
}}
QMenu::separator {{
    height: 1px;
    background-color: {t["border_subtle"]};
    margin: {SPACING["sm"]} {SPACING["md"]};
}}

/* Slider - Modern */
QSlider::groove:horizontal {{ 
    height: 8px; 
    background: {t["bg_primary"]};
    border-radius: 4px;
}}
QSlider::handle:horizontal {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 {t["accent_blue_hover"]}, stop:1 {t["accent_blue"]});
    width: 20px; 
    height: 20px;
    margin: -6px 0; 
    border-radius: 10px;
}}
QSlider::handle:horizontal:hover {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 #93c5fd, stop:1 {t["accent_blue_hover"]});
}}
QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 {t["accent_blue"]}, stop:1 {t["accent_blue_hover"]});
    border-radius: 4px;
}}

/* Tooltip - Modern */
QToolTip {{ 
    background-color: {t["bg_elevated"]};
    color: {t["text_primary"]}; 
    border: 1px solid {t["border_medium"]};
    border-radius: {RADIUS["md"]}; 
    padding: {SPACING["sm"]} {SPACING["md"]};
    font-size: {FONT_SIZE["sm"]};
}}

/* List Widget */
QListWidget {{
    background-color: {t["bg_primary"]};
    border: 1px solid {t["border_subtle"]};
    border-radius: {RADIUS["lg"]};
    alternate-background-color: {t["bg_card"]};
    outline: none;
}}
QListWidget::item {{
    padding: {SPACING["md"]};
    border-radius: {RADIUS["sm"]};
    margin: 2px;
}}
QListWidget::item:selected {{
    background-color: {t["accent_blue"]};
}}
QListWidget::item:hover:!selected {{
    background-color: {t["bg_hover"]};
}}

/* Status Bar */
QStatusBar {{
    background-color: {t["bg_primary"]};
    color: {t["text_secondary"]};
    border-top: 1px solid {t["border_subtle"]};
    padding: {SPACING["xs"]};
}}

/* Menu Bar */
QMenuBar {{
    background-color: {t["bg_primary"]};
    color: {t["text_primary"]};
    padding: {SPACING["xs"]};
    border-bottom: 1px solid {t["border_subtle"]};
}}
QMenuBar::item {{
    padding: {SPACING["sm"]} {SPACING["lg"]};
    border-radius: {RADIUS["sm"]};
}}
QMenuBar::item:selected {{
    background-color: {t["accent_blue"]};
}}

/* Dialog Styles */
QDialog {{
    background-color: {t["bg_secondary"]};
    border-radius: {RADIUS["xl"]};
}}

/* Frame Styles */
QFrame[frameShape="4"] {{ /* HLine */
    background-color: {t["border_subtle"]};
    max-height: 1px;
}}
QFrame[frameShape="5"] {{ /* VLine */
    background-color: {t["border_subtle"]};
    max-width: 1px;
}}

/* Splitter */
QSplitter::handle {{
    background-color: {t["border_subtle"]};
}}
QSplitter::handle:horizontal {{
    width: 2px;
}}
QSplitter::handle:vertical {{
    height: 2px;
}}
"""


def get_light_stylesheet():
    t = DESIGN_TOKENS["light"]
    return f"""
/* === v14.0 Enhanced Light Theme with Design Tokens === */

/* Main Window & Base */
QMainWindow, QWidget {{ 
    background-color: {t["bg_primary"]}; 
    color: {t["text_primary"]}; 
    font-family: 'Malgun Gothic', 'Segoe UI', -apple-system, sans-serif;
    font-size: {FONT_SIZE["md"]};
}}

/* GroupBox - Modern Card Style */
QGroupBox {{ 
    border: 1px solid {t["border_subtle"]};
    border-radius: {RADIUS["lg"]}; 
    margin-top: 1.5em; 
    padding: {SPACING["lg"]};
    padding-top: {SPACING["xl"]};
    font-weight: 600;
    font-size: {FONT_SIZE["lg"]};
    background-color: {t["bg_card"]};
}}
QGroupBox::title {{ 
    subcontrol-origin: margin; 
    left: {SPACING["lg"]}; 
    padding: 0 {SPACING["md"]};
    color: {t["accent_blue"]};
    font-weight: bold;
}}

/* Input Fields */
QLineEdit, QSpinBox, QTimeEdit, QDoubleSpinBox, QComboBox {{ 
    background-color: {t["bg_input"]};
    border: 1px solid {t["border_subtle"]}; 
    border-radius: {RADIUS["md"]}; 
    padding: {SPACING["sm"]} {SPACING["md"]}; 
    color: {t["text_primary"]}; 
    min-height: 34px;
    selection-background-color: {t["accent_blue"]};
    selection-color: #fff;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ 
    border: 2px solid {t["accent_blue"]};
    background-color: #fff;
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{ 
    border-color: {t["border_medium"]};
}}
QComboBox::drop-down {{
    border: none;
    padding-right: {SPACING["sm"]};
}}
QComboBox QAbstractItemView {{
    background-color: {t["bg_secondary"]};
    border: 1px solid {t["border_subtle"]};
    border-radius: {RADIUS["md"]};
    selection-background-color: {t["accent_blue"]};
    selection-color: #fff;
    padding: {SPACING["xs"]};
}}

/* Table Widget - Clean */
QTableWidget {{ 
    background-color: {t["bg_secondary"]};
    gridline-color: {t["border_subtle"]};
    border: 1px solid {t["border_subtle"]}; 
    border-radius: {RADIUS["lg"]}; 
    color: {t["text_primary"]};
    alternate-background-color: {t["bg_primary"]};
    outline: none;
}}
QTableWidget::item {{
    border-bottom: 1px solid {t["border_subtle"]};
    padding: 6px {SPACING["sm"]};
}}
QTableWidget::item:selected {{ 
    background-color: {t["accent_blue"]};
    color: #fff;
}}
QTableWidget::item:hover {{ 
    background-color: {t["bg_hover"]};
}}
QHeaderView::section {{ 
    background-color: {t["bg_primary"]};
    padding: {SPACING["md"]}; 
    border: none;
    border-bottom: 2px solid {t["accent_blue"]};
    color: {t["text_secondary"]}; 
    font-weight: bold;
    font-size: {FONT_SIZE["sm"]};
}}
QHeaderView::section:first {{
    border-top-left-radius: {RADIUS["md"]};
}}
QHeaderView::section:last {{
    border-top-right-radius: {RADIUS["md"]};
}}

/* Text Browser / Log */
QTextBrowser {{ 
    background-color: {t["bg_secondary"]};
    color: {t["accent_green"]};
    border: 1px solid {t["border_subtle"]};
    border-radius: {RADIUS["lg"]}; 
    font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace; 
    font-size: {FONT_SIZE["sm"]};
    padding: {SPACING["md"]};
}}

/* Buttons */
QPushButton {{ 
    background-color: {t["bg_primary"]};
    border: 1px solid {t["border_subtle"]}; 
    border-radius: {RADIUS["md"]}; 
    padding: {SPACING["md"]} {SPACING["xl"]}; 
    color: {t["text_secondary"]}; 
    font-weight: 600; 
    min-height: 38px;
}}
QPushButton:hover {{ 
    background-color: {t["bg_hover"]};
    border-color: {t["border_medium"]};
    color: {t["text_primary"]};
}}
QPushButton:pressed {{ 
    background-color: {t["border_medium"]};
}}
QPushButton:disabled {{ 
    background-color: {t["bg_primary"]}; 
    color: {t["text_muted"]}; 
    border-color: {t["bg_primary"]};
}}

/* Start Button - Green Gradient */
QPushButton#startButton {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 {t["accent_green_hover"]}, stop:1 {t["accent_green"]});
    border: none;
    color: #fff;
    font-size: {FONT_SIZE["xl"]};
    font-weight: bold;
}}
QPushButton#startButton:hover {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 #4ade80, stop:1 {t["accent_green_hover"]});
}}
QPushButton#startButton:disabled {{
    background: #bbf7d0;
    color: rgba(255, 255, 255, 0.7);
}}

/* Stop Button - Red Gradient */
QPushButton#stopButton {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 {t["accent_red_hover"]}, stop:1 {t["accent_red"]});
    border: none;
    color: #fff;
    font-weight: bold;
}}
QPushButton#stopButton:hover {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 #fca5a5, stop:1 {t["accent_red_hover"]});
}}

/* Save Button - Blue Gradient */
QPushButton#saveButton {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 {t["accent_blue_hover"]}, stop:1 {t["accent_blue"]});
    border: none;
    color: #fff;
    font-weight: bold;
}}
QPushButton#saveButton:hover {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 #93c5fd, stop:1 {t["accent_blue_hover"]});
}}

/* Link Button - Purple */
QPushButton#linkButton {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 {t["accent_purple"]}, stop:1 #6b21a8);
    border: none;
    color: #fff;
    min-width: 65px; 
    padding: 6px {SPACING["md"]}; 
    min-height: 28px;
    font-size: {FONT_SIZE["sm"]};
}}
QPushButton#linkButton:hover {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 #a78bfa, stop:1 {t["accent_purple"]});
}}

/* Progress Bar */
QProgressBar {{ 
    border: none;
    border-radius: {RADIUS["lg"]}; 
    text-align: center; 
    background-color: {t["border_subtle"]};
    color: {t["text_secondary"]};
    min-height: 28px;
    font-weight: bold;
}}
QProgressBar::chunk {{ 
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 {t["accent_blue"]}, stop:0.5 {t["accent_purple"]}, stop:1 {t["accent_green"]});
    border-radius: {RADIUS["md"]};
}}

/* Checkbox & Radio */
QCheckBox, QRadioButton {{ 
    color: {t["text_primary"]};
    spacing: {SPACING["md"]};
    font-size: {FONT_SIZE["md"]};
}}
QCheckBox::indicator {{ 
    width: 22px; 
    height: 22px; 
    border-radius: {RADIUS["sm"]}; 
    border: 2px solid {t["border_medium"]};
    background-color: #fff;
}}
QCheckBox::indicator:hover {{
    border-color: {t["accent_blue"]};
}}
QCheckBox::indicator:checked {{ 
    background-color: {t["accent_blue"]}; 
    border-color: {t["accent_blue"]};
}}

/* Tab Widget */
QTabWidget::pane {{ 
    border: 1px solid {t["border_subtle"]}; 
    border-radius: {RADIUS["lg"]}; 
    background-color: {t["bg_secondary"]};
    margin-top: -1px;
}}
QTabBar::tab {{ 
    background-color: {t["bg_primary"]};
    color: {t["text_secondary"]}; 
    padding: {SPACING["md"]} {SPACING["xl"]}; 
    margin-right: 4px; 
    border-top-left-radius: {RADIUS["md"]}; 
    border-top-right-radius: {RADIUS["md"]};
    font-size: {FONT_SIZE["md"]};
    font-weight: 500;
}}
QTabBar::tab:selected {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 {t["accent_blue"]}, stop:1 #1d4ed8);
    color: #fff;
    font-weight: bold;
}}
QTabBar::tab:hover:!selected {{ 
    background-color: {t["bg_hover"]};
    color: {t["text_primary"]};
}}

/* Scroll Bars - Minimal */
QScrollBar:vertical {{ 
    background-color: transparent; 
    width: 12px; 
    border-radius: 6px;
    margin: 3px;
}}
QScrollBar::handle:vertical {{ 
    background-color: {t["border_medium"]}; 
    border-radius: 5px; 
    min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{ 
    background-color: {t["text_muted"]};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ 
    height: 0px;
}}
QScrollBar:horizontal {{
    background-color: transparent;
    height: 12px;
    border-radius: 6px;
    margin: 3px;
}}
QScrollBar::handle:horizontal {{
    background-color: {t["border_medium"]};
    border-radius: 5px;
    min-width: 40px;
}}

/* Menu */
QMenu {{ 
    background-color: {t["bg_secondary"]};
    border: 1px solid {t["border_subtle"]};
    border-radius: {RADIUS["lg"]};
    color: {t["text_primary"]}; 
    padding: {SPACING["sm"]};
}}
QMenu::item {{ 
    padding: {SPACING["md"]} {SPACING["xl"]};
    border-radius: {RADIUS["sm"]};
    margin: 2px;
}}
QMenu::item:selected {{ 
    background-color: {t["accent_blue"]};
    color: #fff;
}}
QMenu::separator {{
    height: 1px;
    background-color: {t["border_subtle"]};
    margin: {SPACING["sm"]} {SPACING["md"]};
}}

/* Slider */
QSlider::groove:horizontal {{ 
    height: 8px; 
    background: {t["border_subtle"]};
    border-radius: 4px;
}}
QSlider::handle:horizontal {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 {t["accent_blue_hover"]}, stop:1 {t["accent_blue"]});
    width: 20px; 
    height: 20px;
    margin: -6px 0; 
    border-radius: 10px;
}}
QSlider::handle:horizontal:hover {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
        stop:0 #93c5fd, stop:1 {t["accent_blue_hover"]});
}}
QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
        stop:0 {t["accent_blue"]}, stop:1 {t["accent_blue_hover"]});
    border-radius: 4px;
}}

/* Tooltip */
QToolTip {{ 
    background-color: {t["text_primary"]};
    color: #fff; 
    border: none;
    border-radius: {RADIUS["md"]}; 
    padding: {SPACING["sm"]} {SPACING["md"]};
    font-size: {FONT_SIZE["sm"]};
}}

/* List Widget */
QListWidget {{
    background-color: {t["bg_secondary"]};
    border: 1px solid {t["border_subtle"]};
    border-radius: {RADIUS["lg"]};
    alternate-background-color: {t["bg_primary"]};
    outline: none;
}}
QListWidget::item {{
    padding: {SPACING["md"]};
    border-radius: {RADIUS["sm"]};
    margin: 2px;
}}
QListWidget::item:selected {{
    background-color: {t["accent_blue"]};
    color: #fff;
}}
QListWidget::item:hover:!selected {{
    background-color: {t["bg_hover"]};
}}

/* Status Bar */
QStatusBar {{
    background-color: {t["bg_primary"]};
    color: {t["text_secondary"]};
    border-top: 1px solid {t["border_subtle"]};
    padding: {SPACING["xs"]};
}}

/* Menu Bar */
QMenuBar {{
    background-color: {t["bg_secondary"]};
    color: {t["text_primary"]};
    padding: {SPACING["xs"]};
    border-bottom: 1px solid {t["border_subtle"]};
}}
QMenuBar::item {{
    padding: {SPACING["sm"]} {SPACING["lg"]};
    border-radius: {RADIUS["sm"]};
}}
QMenuBar::item:selected {{
    background-color: {t["accent_blue"]};
    color: #fff;
}}

/* Dialog Styles */
QDialog {{
    background-color: {t["bg_primary"]};
    border-radius: {RADIUS["xl"]};
}}

/* Frame Styles */
QFrame[frameShape="4"] {{ /* HLine */
    background-color: {t["border_subtle"]};
    max-height: 1px;
}}
QFrame[frameShape="5"] {{ /* VLine */
    background-color: {t["border_subtle"]};
    max-width: 1px;
}}

/* Splitter */
QSplitter::handle {{
    background-color: {t["border_subtle"]};
}}
QSplitter::handle:horizontal {{
    width: 2px;
}}
QSplitter::handle:vertical {{
    height: 2px;
}}
"""


def get_stylesheet(theme="dark"):
    """테마에 맞는 스타일시트 반환"""
    return get_light_stylesheet() if theme == "light" else get_dark_stylesheet()


def get_token(theme="dark", key=None):
    """특정 디자인 토큰 값 반환"""
    if key:
        return DESIGN_TOKENS.get(theme, {}).get(key)
    return DESIGN_TOKENS.get(theme, {})
