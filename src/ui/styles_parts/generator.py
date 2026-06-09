from src.ui.styles_parts.colors import COLORS


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
    border-radius: 12px;
    margin-top: 0.8em;
    padding: 10px;
    padding-top: 22px;
    font-weight: 600;
    font-size: 13px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 12px;
    color: {c['accent']};
    background: transparent;
    font-weight: 700;
    font-size: 12px;
    letter-spacing: 0.2px;
}}

/* === Buttons === */
QPushButton {{
    background-color: {c['accent_bg']};
    color: {c['accent']};
    border: 1px solid {c['accent_border']};
    padding: 7px 14px;
    border-radius: 7px;
    font-weight: 600;
    min-height: 26px;
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
    padding: 7px 11px;
    border: 1px solid {c['border']};
    border-radius: 7px;
    background-color: {c['bg_input']};
    color: {c['text_primary']};
    selection-background-color: {c['accent']};
    selection-color: {select_text};
    min-height: 24px;
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
QComboBox QAbstractItemView {{
    background-color: {c['dropdown_bg']};
    color: {c['dropdown_text']};
    border: 1px solid {c['dropdown_border']};
    selection-background-color: {c['dropdown_selected_bg']};
    selection-color: {c['dropdown_selected_text']};
    outline: none;
}}
QComboBox QAbstractItemView::item {{
    min-height: 24px;
    padding: 6px 10px;
}}
QComboBox QAbstractItemView::item:hover {{
    background-color: {c['dropdown_hover']};
    color: {c['dropdown_text']};
}}
QComboBox QAbstractItemView::item:selected {{
    background-color: {c['dropdown_selected_bg']};
    color: {c['dropdown_selected_text']};
}}
QComboBox QAbstractItemView::item:disabled {{
    color: {c['dropdown_disabled_text']};
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

/* === Section Header (v15.1) === */
QLabel#sectionHeader {{
    font-size: 11px;
    font-weight: 700;
    color: {c['accent']};
    letter-spacing: 0.8px;
    text-transform: uppercase;
    padding-bottom: 4px;
    border-bottom: 1px solid {c['border_subtle']};
}}

/* === Hint / Helper Label (v15.1) === */
QLabel#hintLabel {{
    font-size: 11px;
    color: {c['text_secondary']};
    font-style: italic;
    line-height: 1.5;
}}

/* === Step Badge (v15.1) === */
QLabel#stepBadge {{
    font-size: 11px;
    font-weight: 700;
    color: {c['bg_primary']};
    background-color: {c['accent']};
    border-radius: 10px;
    padding: 2px 7px;
    min-width: 18px;
}}

/* === Icon-only small button (v15.1) === */
QPushButton#iconButton {{
    background-color: {c['accent_bg']};
    color: {c['accent']};
    border: 1px solid {c['accent_border']};
    padding: 4px 8px;
    border-radius: 6px;
    font-weight: 600;
    min-height: 24px;
    min-width: 28px;
    max-width: 52px;
}}
QPushButton#iconButton:hover {{
    background-color: {c['accent_bg_hover']};
    border-color: {c['accent']};
}}

/* === Result Toolbar panel (v15.1) === */
QWidget#resultToolbar {{
    background-color: {c['bg_header']};
    border: 1px solid {c['border_subtle']};
    border-radius: 8px;
    padding: 4px 8px;
}}

/* === Control Row (labeled row inside group) === */
QWidget#controlRow {{
    background-color: transparent;
}}

/* === Filter Badge === */
QLabel#filterBadgeOn {{
    font-size: 11px;
    font-weight: 700;
    color: {c['bg_primary']};
    background-color: {c['accent']};
    border-radius: 10px;
    padding: 2px 8px;
}}
QLabel#filterBadgeOff {{
    font-size: 11px;
    color: {c['text_secondary']};
    background-color: transparent;
    padding: 2px 8px;
}}

/* === Semantic Button Roles === */
QPushButton#primaryBtn {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {c['success_light']}, stop:1 {c['success']});
    color: #ffffff;
    border: 1px solid {c['success_border']};
    border-radius: 7px;
    padding: 7px 18px;
    font-weight: 700;
    font-size: 13px;
    min-height: 32px;
}}
QPushButton#primaryBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {c['success_hover_light']}, stop:1 {c['success_hover']});
}}
QPushButton#primaryBtn:pressed {{
    background: {c['success_pressed']};
}}
QPushButton#primaryBtn:disabled {{
    background: {c['bg_disabled']};
    color: {c['text_disabled']};
    border-color: transparent;
}}

QPushButton#dangerBtn {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {c['error_light']}, stop:1 {c['error']});
    color: #ffffff;
    border: 1px solid {c['error_border']};
    border-radius: 7px;
    padding: 7px 18px;
    font-weight: 700;
    font-size: 13px;
    min-height: 32px;
}}
QPushButton#dangerBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {c['error_hover_light']}, stop:1 {c['error_hover']});
}}
QPushButton#dangerBtn:pressed {{
    background: {c['error_pressed']};
}}
QPushButton#dangerBtn:disabled {{
    background: {c['bg_disabled']};
    color: {c['text_disabled']};
    border-color: transparent;
}}

QPushButton#secondaryBtn {{
    background: {c['accent_bg']};
    color: {c['accent_bright']};
    border: 1px solid {c['accent_bg_hover']};
    border-radius: 7px;
    padding: 6px 14px;
    font-weight: 600;
    font-size: 12px;
    min-height: 28px;
}}
QPushButton#secondaryBtn:hover {{
    background: {c['accent_bg_hover']};
    border-color: {c['accent']};
}}
QPushButton#secondaryBtn:pressed {{
    background: {c['accent_pressed']};
    color: #ffffff;
}}
QPushButton#secondaryBtn:disabled {{
    background: {c['bg_disabled']};
    color: {c['text_disabled']};
    border-color: transparent;
}}
"""
