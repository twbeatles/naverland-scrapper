"""
UI 스타일시트 모듈 (v15.0)
- Dark/Light 테마 완전 지원
- Glassmorphism 효과
- 색상 토큰(COLORS) 기반 동적 스타일시트 생성
- Slider / Focus / Disabled / EmptyState 커스텀 스타일
"""

# ===== 색상 팔레트 =====
COLORS = {
    "dark": {
        "bg_primary": "#0f0f1a",
        "bg_secondary": "#1a1a2e",
        "bg_card": "rgba(30, 30, 40, 0.85)",
        "bg_input": "rgba(30, 30, 46, 0.8)",
        "bg_input_focus": "rgba(30, 30, 46, 1)",
        "bg_table": "rgba(30, 30, 46, 0.6)",
        "bg_table_alt": "rgba(40, 40, 60, 0.5)",
        "bg_header": "rgba(50, 50, 70, 0.9)",
        "bg_tab_pane": "rgba(20, 20, 35, 0.5)",
        "bg_progress": "rgba(40, 50, 80, 0.6)",
        "bg_tooltip": "rgba(30, 30, 50, 0.95)",
        "bg_menu": "rgba(30, 30, 50, 0.98)",
        "bg_statusbar": "rgba(15, 15, 26, 0.95)",
        "bg_disabled": "rgba(50, 50, 70, 0.5)",
        "bg_search": "rgba(35, 35, 55, 0.9)",
        "bg_search_focus": "rgba(35, 35, 55, 1)",
        "border": "rgba(255, 255, 255, 0.1)",
        "border_subtle": "rgba(255, 255, 255, 0.08)",
        "border_faint": "rgba(255, 255, 255, 0.05)",
        "border_table_item": "rgba(255, 255, 255, 0.03)",
        "border_focus": "#f59e0b",
        "text_primary": "#f0f0f0",
        "text_secondary": "#a0a0b0",
        "text_disabled": "#555",
        "text_tab_inactive": "#888",
        "text_tab_hover": "#ccc",
        "accent": "#f59e0b",
        "accent_hover": "#d97706",
        "accent_bright": "#fbbf24",
        "accent_pressed": "#b45309",
        "accent_bg": "rgba(245, 158, 11, 0.15)",
        "accent_bg_hover": "rgba(245, 158, 11, 0.25)",
        "accent_bg_strong": "rgba(245, 158, 11, 0.35)",
        "accent_border": "rgba(245, 158, 11, 0.3)",
        "success": "#22c55e",
        "success_bg": "rgba(34, 197, 94, 0.15)",
        "success_border": "rgba(34, 197, 94, 0.3)",
        "warning": "#f59e0b",
        "error": "#ef4444",
        "error_bg": "rgba(239, 68, 68, 0.15)",
        "error_border": "rgba(239, 68, 68, 0.3)",
        "scrollbar": "rgba(245, 158, 11, 0.3)",
        "scrollbar_hover": "rgba(245, 158, 11, 0.5)",
        "scrollbar_bg": "transparent",
        "splitter": "rgba(245, 158, 11, 0.1)",
        "splitter_hover": "rgba(245, 158, 11, 0.3)",
        "hover_light": "rgba(255, 255, 255, 0.05)",
        "hover_faint": "rgba(255, 255, 255, 0.04)",
        "select_bg": "rgba(245, 158, 11, 0.2)",
        "trade_매매": "#ef4444",
        "trade_전세": "#22c55e",
        "trade_월세": "#3b82f6",
        # Slider
        "slider_groove": "rgba(255, 255, 255, 0.08)",
        "slider_handle": "#f59e0b",
        "slider_handle_hover": "#fbbf24",
        "slider_handle_pressed": "#d97706",
        "slider_sub_page": "rgba(245, 158, 11, 0.5)",
        # EmptyState
        "empty_icon_color": "#555",
        "empty_title_color": "#888",
        "empty_desc_color": "#666",
        # SummaryCard
        "summary_bg": "rgba(30, 30, 40, 0.9)",
        "summary_separator": "rgba(255, 255, 255, 0.08)",
        # ArticleCard
        "card_bg": "rgba(30, 30, 46, 0.85)",
        "card_bg_hover": "rgba(40, 40, 60, 0.95)",
        "card_border": "rgba(255, 255, 255, 0.08)",
        "card_border_hover": "rgba(245, 158, 11, 0.4)",
        # StatCard (Dashboard)
        "stat_card_bg": "rgba(30, 30, 46, 0.7)",
    },
    "light": {
        "bg_primary": "#f8fafc",
        "bg_secondary": "#ffffff",
        "bg_card": "rgba(255, 255, 255, 0.9)",
        "bg_input": "#ffffff",
        "bg_input_focus": "#ffffff",
        "bg_table": "#ffffff",
        "bg_table_alt": "#f8fafc",
        "bg_header": "#f1f5f9",
        "bg_tab_pane": "#ffffff",
        "bg_progress": "#e2e8f0",
        "bg_tooltip": "#ffffff",
        "bg_menu": "#ffffff",
        "bg_statusbar": "#f1f5f9",
        "bg_disabled": "#f1f5f9",
        "bg_search": "#ffffff",
        "bg_search_focus": "#ffffff",
        "border": "#e2e8f0",
        "border_subtle": "#e2e8f0",
        "border_faint": "#f1f5f9",
        "border_table_item": "#f1f5f9",
        "border_focus": "#0ea5e9",
        "text_primary": "#1e293b",
        "text_secondary": "#64748b",
        "text_disabled": "#94a3b8",
        "text_tab_inactive": "#64748b",
        "text_tab_hover": "#475569",
        "accent": "#0ea5e9",
        "accent_hover": "#0284c7",
        "accent_bright": "#38bdf8",
        "accent_pressed": "#0369a1",
        "accent_bg": "#f1f5f9",
        "accent_bg_hover": "#e2e8f0",
        "accent_bg_strong": "#cbd5e1",
        "accent_border": "#e2e8f0",
        "success": "#16a34a",
        "success_bg": "#f0fdf4",
        "success_border": "#bbf7d0",
        "warning": "#f59e0b",
        "error": "#dc2626",
        "error_bg": "#fef2f2",
        "error_border": "#fecaca",
        "scrollbar": "#cbd5e1",
        "scrollbar_hover": "#94a3b8",
        "scrollbar_bg": "#f1f5f9",
        "splitter": "#e2e8f0",
        "splitter_hover": "#0ea5e9",
        "hover_light": "#f1f5f9",
        "hover_faint": "#f1f5f9",
        "select_bg": "#e0f2fe",
        "trade_매매": "#dc2626",
        "trade_전세": "#16a34a",
        "trade_월세": "#2563eb",
        # Slider
        "slider_groove": "#e2e8f0",
        "slider_handle": "#0ea5e9",
        "slider_handle_hover": "#38bdf8",
        "slider_handle_pressed": "#0284c7",
        "slider_sub_page": "rgba(14, 165, 233, 0.5)",
        # EmptyState
        "empty_icon_color": "#94a3b8",
        "empty_title_color": "#64748b",
        "empty_desc_color": "#94a3b8",
        # SummaryCard
        "summary_bg": "#ffffff",
        "summary_separator": "#e2e8f0",
        # ArticleCard
        "card_bg": "#ffffff",
        "card_bg_hover": "#f8fafc",
        "card_border": "#e2e8f0",
        "card_border_hover": "#0ea5e9",
        # StatCard (Dashboard)
        "stat_card_bg": "#ffffff",
    }
}


def _generate_stylesheet(theme: str = "dark") -> str:
    """색상 토큰 기반 동적 스타일시트 생성"""
    c = COLORS[theme]

    # 테마별 분기 값
    is_dark = theme == "dark"
    focus_border_width = "1px" if is_dark else "2px"
    checked_text = c["bg_primary"] if is_dark else "#0c4a6e"
    checked_bg = c["accent_bg_strong"] if is_dark else "#e0f2fe"
    select_text = "#ffffff" if is_dark else "#0c4a6e"
    progress_text = "#fff" if is_dark else c["text_primary"]
    tab_selected_bg = c["accent_bg"] if is_dark else "#e0f2fe"
    list_selected_text = c["text_primary"] if is_dark else "#0c4a6e"
    menubar_bg = "transparent" if is_dark else c["bg_primary"]
    menubar_selected = c["accent_bg"] if is_dark else "#e0f2fe"
    dialog_label = "#e0e0e0" if is_dark else "#334155"
    checkbox_border = "rgba(255, 255, 255, 0.2)" if is_dark else "#cbd5e1"
    checkbox_bg = "transparent" if is_dark else "#ffffff"
    start_gradient = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {c['accent']}, stop:1 {c['accent_hover']})"
    start_hover = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {c['accent_bright']}, stop:1 {c['accent']})"
    progress_gradient = f"qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {c['accent']}, stop:1 {c['accent_hover'] if is_dark else c['accent_bright']})"
    start_text = c["bg_primary"] if is_dark else "#ffffff"
    statusbar_border = f"rgba(245, 158, 11, 0.15)" if is_dark else c["border"]

    return f"""
/* ========================================
   v15.0 {theme.title()} Theme — Token-driven Stylesheet
   ======================================== */

/* === Base === */
QMainWindow, QWidget {{
    background-color: {c['bg_primary']};
    color: {c['text_primary']};
    font-family: 'Pretendard', 'SUIT', 'Malgun Gothic', 'Segoe UI', -apple-system, sans-serif;
    font-size: 13px;
}}
QDialog, QMessageBox {{
    background-color: {c['bg_primary']};
}}
QScrollArea {{
    background: transparent;
}}
QFrame {{
    background-color: transparent;
}}

/* === Glassmorphism Card (GroupBox) === */
QGroupBox {{
    background-color: {c['bg_card']};
    border: 1px solid {c['border_subtle']};
    border-radius: 16px;
    margin-top: 1.2em;
    padding: 18px;
    padding-top: 28px;
    font-weight: 600;
    font-size: 14px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 6px 14px;
    color: {c['accent']};
    background: transparent;
    font-weight: 700;
    letter-spacing: 0.3px;
}}

/* === Buttons === */
QPushButton {{
    background-color: {c['accent_bg']};
    color: {c['accent']};
    border: 1px solid {c['accent_border']};
    padding: 10px 20px;
    border-radius: 8px;
    font-weight: 600;
    min-height: 28px;
}}
QPushButton:checked {{
    background-color: {checked_bg};
    color: {checked_text};
    border-color: {c['accent']};
}}
QPushButton:hover {{
    background-color: {c['accent_bg_hover']};
    border-color: {c['accent']};
}}
QPushButton:pressed {{
    background-color: {c['accent_bg_strong']};
}}
QPushButton:disabled {{
    background-color: {c['bg_disabled']};
    color: {c['text_disabled']};
    border-color: {c['border_faint']};
}}

/* Primary Action Button */
QPushButton#startButton {{
    background: {start_gradient};
    color: {start_text};
    font-size: 15px;
    font-weight: 700;
    padding: 12px 24px;
    border: none;
    border-radius: 10px;
}}
QPushButton#startButton:hover {{
    background: {start_hover};
}}
QPushButton#startButton:pressed {{
    background: {c['accent_pressed']};
}}

/* Stop Button */
QPushButton#stopButton {{
    background-color: {c['error_bg']};
    color: {c['error']};
    border: 1px solid {c['error_border']};
}}
QPushButton#stopButton:hover {{
    background-color: {c['error_bg'].replace('0.15', '0.25') if is_dark else '#fee2e2'};
    border-color: {c['error']};
}}

/* Save Button */
QPushButton#saveButton {{
    background-color: {c['success_bg']};
    color: {c['success']};
    border: 1px solid {c['success_border']};
}}
QPushButton#saveButton:hover {{
    background-color: {c['success_bg'].replace('0.15', '0.25') if is_dark else '#dcfce7'};
    border-color: {c['success']};
}}

/* === Input Fields === */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTimeEdit {{
    padding: 10px 14px;
    border: 1px solid {c['border']};
    border-radius: 8px;
    background-color: {c['bg_input']};
    color: {c['text_primary']};
    selection-background-color: {c['accent']};
    selection-color: {select_text};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: {focus_border_width} solid {c['border_focus']};
    background-color: {c['bg_input_focus']};
}}
QLineEdit#searchInput {{
    border-radius: 999px;
    padding: 8px 16px;
    background-color: {c['bg_search']};
}}
QLineEdit#searchInput:focus {{
    border: {focus_border_width} solid {c['border_focus']};
    background-color: {c['bg_search_focus']};
}}
QAbstractItemView {{
    outline: none;
}}
QComboBox::drop-down {{
    border: none;
    padding-right: 10px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {c['accent']};
    margin-right: 8px;
}}

/* === Table === */
QTableWidget {{
    background-color: {c['bg_table']};
    gridline-color: {c['border_faint']};
    border: 1px solid {c['border_subtle']};
    border-radius: 12px;
    selection-background-color: {c['select_bg']};
    selection-color: {select_text};
    alternate-background-color: {c['bg_table_alt']};
}}
QHeaderView::section {{
    background-color: {c['bg_header']};
    padding: 10px 8px;
    border: none;
    color: {c['accent']};
    font-weight: 700;
    font-size: 12px;
    border-bottom: 2px solid {c['accent_border']};
}}
QTableWidget::item {{
    padding: 8px;
    border-bottom: 1px solid {c['border_table_item']};
}}
QTableWidget::item:selected {{
    background-color: {c['accent_bg']};
}}
QTableWidget::item:hover {{
    background-color: {c['hover_faint']};
}}

/* === Scrollbars === */
QScrollBar:vertical {{
    border: none;
    background: {c['scrollbar_bg']};
    width: 8px;
    margin: 4px 2px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {c['scrollbar']};
    min-height: 30px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c['scrollbar_hover']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    border: none;
    background: {c['scrollbar_bg']};
    height: 8px;
    margin: 2px 4px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {c['scrollbar']};
    min-width: 30px;
    border-radius: 4px;
}}

/* === Tab Widget === */
QTabWidget::pane {{
    border: 1px solid {c['border_subtle']};
    border-radius: 12px;
    background-color: {c['bg_tab_pane']};
    margin-top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {c['text_tab_inactive']};
    padding: 12px 24px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    margin-right: 4px;
    font-weight: 500;
}}
QTabBar::tab:selected {{
    background: {tab_selected_bg};
    color: {c['accent']};
    font-weight: 700;
    border-bottom: 3px solid {c['accent']};
}}
QTabBar::tab:hover:!selected {{
    background: {c['hover_light']};
    color: {c['text_tab_hover']};
}}
QTabBar::tab:disabled {{
    color: {c['text_disabled']};
}}

/* === Progress Bar === */
QProgressBar {{
    border: none;
    border-radius: 8px;
    text-align: center;
    background-color: {c['bg_progress']};
    color: {progress_text};
    font-weight: 600;
    min-height: 22px;
    font-size: 12px;
}}
QProgressBar::chunk {{
    background: {progress_gradient};
    border-radius: 7px;
}}

/* === Checkbox === */
QCheckBox {{
    spacing: 8px;
    color: {c['text_primary']};
}}
QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border-radius: 4px;
    border: 2px solid {checkbox_border};
    background: {checkbox_bg};
}}
QCheckBox::indicator:checked {{
    background-color: {c['accent']};
    border-color: {c['accent']};
}}
QCheckBox::indicator:hover {{
    border-color: {c['accent']};
}}

/* === List Widget === */
QListWidget {{
    background-color: {c['bg_table']};
    border: 1px solid {c['border_subtle']};
    border-radius: 10px;
    padding: 5px;
}}
QListWidget::item {{
    padding: 10px;
    border-radius: 6px;
    margin: 2px;
}}
QListWidget::item:selected {{
    background-color: {c['select_bg']};
    color: {list_selected_text};
}}
QListWidget::item:hover {{
    background-color: {c['hover_light']};
}}

/* === Tooltips === */
QToolTip {{
    color: {c['text_primary']};
    background-color: {c['bg_tooltip']};
    border: 1px solid {c['accent']};
    border-radius: 6px;
    padding: 8px 12px;
}}

/* === Menu === */
QMenuBar {{
    background-color: {menubar_bg};
    color: {c['text_primary']};
}}
QMenuBar::item:selected {{
    background-color: {menubar_selected};
    border-radius: 4px;
}}
QMenu {{
    background-color: {c['bg_menu']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 5px;
}}
QMenu::item {{
    padding: 8px 25px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {c['select_bg']};
}}

/* === Status Bar === */
QStatusBar {{
    background-color: {c['bg_statusbar']};
    color: {c['text_secondary']};
    border-top: 1px solid {statusbar_border};
    padding: 4px 12px;
    font-size: 12px;
}}
QStatusBar QLabel {{
    color: {c['text_secondary']};
    padding: 0 4px;
}}

/* === Splitter === */
QSplitter::handle {{
    background-color: {c['splitter']};
}}
QSplitter::handle:hover {{
    background-color: {c['splitter_hover']};
}}

/* === Text Browser === */
QTextBrowser {{
    background-color: {c['bg_table']};
    border: 1px solid {c['border_subtle']};
    border-radius: 10px;
    padding: 12px;
    color: {c['text_primary']};
    line-height: 1.5;
}}

/* === Dialog === */
QDialog {{
    background-color: {c['bg_primary']};
}}
QDialog QGroupBox {{
    margin-top: 1.5em;
}}
QDialog QDialogButtonBox QPushButton {{
    min-width: 90px;
    padding: 8px 20px;
}}
QDialog QLabel {{
    color: {dialog_label};
}}

/* === Slider (v15.0) === */
QSlider::groove:horizontal {{
    border: none;
    height: 6px;
    background: {c['slider_groove']};
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {c['slider_sub_page']};
    border-radius: 3px;
}}
QSlider::add-page:horizontal {{
    background: {c['slider_groove']};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {c['slider_handle']};
    width: 18px;
    height: 18px;
    margin: -6px 0;
    border-radius: 9px;
    border: 2px solid {c['bg_primary']};
}}
QSlider::handle:horizontal:hover {{
    background: {c['slider_handle_hover']};
    width: 20px;
    height: 20px;
    margin: -7px 0;
    border-radius: 10px;
}}
QSlider::handle:horizontal:pressed {{
    background: {c['slider_handle_pressed']};
}}

/* === EmptyState Widget (v15.0) === */
QWidget#emptyStateWidget {{
    background: transparent;
}}
QLabel#emptyStateIcon {{
    font-size: 48px;
    color: {c['empty_icon_color']};
}}
QLabel#emptyStateTitle {{
    font-size: 16px;
    font-weight: 700;
    color: {c['empty_title_color']};
}}
QLabel#emptyStateDesc {{
    font-size: 13px;
    color: {c['empty_desc_color']};
    line-height: 1.5;
}}

/* === SummaryCard (v15.0) === */
QFrame#summaryCard {{
    background-color: {c['summary_bg']};
    border: 1px solid {c['border_subtle']};
    border-radius: 14px;
    padding: 14px 18px;
}}
QLabel#summaryTitle {{
    font-size: 11px;
    font-weight: 600;
    color: {c['text_secondary']};
    letter-spacing: 0.5px;
}}
QLabel#summaryValue {{
    font-size: 22px;
    font-weight: 800;
    color: {c['text_primary']};
}}

/* === ArticleCard (v15.0) === */
QFrame#articleCard {{
    background-color: {c['card_bg']};
    border: 1px solid {c['card_border']};
    border-radius: 14px;
    padding: 16px;
}}
QFrame#articleCard:hover {{
    background-color: {c['card_bg_hover']};
    border-color: {c['card_border_hover']};
}}

/* === StatCard (Dashboard) (v15.0) === */
QFrame#statCard {{
    background-color: {c['stat_card_bg']};
    border: 1px solid {c['border_subtle']};
    border-radius: 12px;
    padding: 16px;
}}
QLabel#statCardTitle {{
    font-size: 11px;
    font-weight: 600;
    color: {c['text_secondary']};
}}
QLabel#statCardValue {{
    font-size: 24px;
    font-weight: 800;
}}
"""


def get_dark_stylesheet() -> str:
    """다크 테마 스타일시트 (v15.0 - Glassmorphism with Warm Colors)"""
    return _generate_stylesheet("dark")


def get_light_stylesheet() -> str:
    """라이트 테마 스타일시트 (v15.0 - Clean & Modern)"""
    return _generate_stylesheet("light")


def get_stylesheet(theme: str = "dark") -> str:
    """테마에 따른 스타일시트 반환"""
    if theme == "dark":
        return get_dark_stylesheet()
    else:
        return get_light_stylesheet()
