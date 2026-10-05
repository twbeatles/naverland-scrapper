from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppLifecycleBootstrapMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...
    def __init__(self: Any):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        try:
            from src.ui.fluent.theme import configure_fluent_window as _configure_fluent
            _configure_fluent(self)
        except Exception:
            pass
        try:
            from PyQt6.QtGui import QGuiApplication as _QGuiApp
            from src.ui.fluent.design_tokens import preferred_window_size as _pref_size
            _screen = _QGuiApp.primaryScreen()
            _avail = _screen.availableGeometry() if _screen is not None else None
            if _avail is not None:
                _pw, _ph = _pref_size(_avail.width(), _avail.height())
                self.resize(_pw, _ph)
        except Exception:
            pass
        from src.ui.fluent.design_tokens import MIN_WINDOW_WIDTH as _MIN_W, MIN_WINDOW_HEIGHT as _MIN_H
        self.setMinimumSize(_MIN_W, _MIN_H)
        # ISSUE-001: geometry is applied only through the validated
        # _restore_window_geometry() single path (no unvalidated setGeometry).
        self._restore_window_geometry()
        
        self.settings_manager = get_settings()
        self.preset_manager = FilterPresetManager()
        self.history_manager = SearchHistoryManager(max_items=settings.get("max_search_history", 20))
        self.recently_viewed = RecentlyViewedManager(
            max_items=settings.get("recently_viewed_count", RecentlyViewedManager.MAX_ITEMS)
        )
        self.advanced_filters: dict[str, Any] | None = None
        self.collected_data: list[dict[str, Any]] = []
        self.is_scheduled_run = False
        self.retry_handler: Any | None = None
        self.tray_icon: Any | None = None
        self._is_shutting_down = False
        self._maintenance_mode = False
        self._maintenance_reason = ""
        self._maintenance_enabled_snapshot: List[Tuple[Any, bool]] = []
        self.favorite_keys: set[tuple[str, str, str]] = set()
        self._shortcuts: dict[str, Any] = {}
        self.schedule_timer: Any | None = None
        self._schedule_skip_notice_key: tuple[str, str] | None = None
        self.db = ComplexDatabase()
        self._noncritical_loaded = {
            "history": False,
            "stats": False,
            "favorites": False,
            "dashboard": False,
        }
        
        # v11.0: Toast 알림 시스템
        self.toast_widgets: List[ToastWidget] = []
        
        self.current_theme = settings.get("theme", "dark")
        try:
            from src.ui.fluent.theme import apply_app_theme

            apply_app_theme(self.current_theme)
        except Exception:
            pass
        # Domain widgets still use the legacy QSS palette; applied after shell init.
        self._input_wheel_guard = install_global_wheel_guard(QApplication.instance())
        
        # UI 초기화
        self._init_ui()
        self._apply_domain_stylesheet(self.current_theme)
        apply_wheel_guard_recursively(self, self._input_wheel_guard)
        self._init_menu()
        self._init_update_controller()
        self._init_shortcuts()
        self._init_tray()
        self._init_timers()
        self._load_initial_data()
        
        # 윈도우 설정
        self._restore_window_geometry()
        
        self.show_toast(f"환영합니다! {APP_TITLE} {APP_VERSION}입니다.")
        startup_notice = ""
        try:
            startup_notice = self.db.get_startup_recovery_notice()
        except Exception:
            startup_notice = ""
        if startup_notice:
            self.status_bar.showMessage(startup_notice, 15000)
            self.show_toast(startup_notice)

    def _restore_window_geometry(self: Any):
        """Apply saved window geometry after validation, clamped to visible screens.

        Invalid saved values fall back to the default size so a corrupt
        settings entry can never crash startup (ISSUE-001).
        """
        from src.ui.fluent.design_tokens import DEFAULT_WINDOW_WIDTH as _DW, DEFAULT_WINDOW_HEIGHT as _DH
        try:
            geo = settings.get("window_geometry")
        except Exception:
            geo = None
        if not geo:
            try:
                self.resize(_DW, _DH)
            except Exception:
                pass
            return
        valid = (
            isinstance(geo, (list, tuple))
            and len(geo) == 4
            and all(not isinstance(v, bool) for v in geo)
        )
        coords = None
        if valid:
            try:
                coords = (int(geo[0]), int(geo[1]), int(geo[2]), int(geo[3]))
            except (TypeError, ValueError):
                coords = None
        if coords is None:
            try:
                ui_logger.warning(f"invalid window_geometry ignored: {geo!r}")
            except Exception:
                pass
            try:
                self.resize(_DW, _DH)
            except Exception:
                pass
            return
        x, y, w, h = coords
        if w <= 0 or h <= 0:
            try:
                ui_logger.warning(f"invalid window_geometry size ignored: {geo!r}")
            except Exception:
                pass
            try:
                self.resize(_DW, _DH)
            except Exception:
                pass
            return
        try:
            from PyQt6.QtGui import QGuiApplication as _QGuiApp
            _screen = _QGuiApp.primaryScreen()
            _avail = _screen.availableGeometry() if _screen is not None else None
        except Exception:
            _avail = None
        if _avail is not None:
            try:
                w = max(1, min(w, int(_avail.width())))
                h = max(1, min(h, int(_avail.height())))
                _margin = 100
                _min_x = int(_avail.x()) - w + _margin
                _max_x = int(_avail.x()) + int(_avail.width()) - _margin
                _min_y = int(_avail.y()) - h + _margin
                _max_y = int(_avail.y()) + int(_avail.height()) - _margin
                if _min_x <= _max_x:
                    x = min(max(x, _min_x), _max_x)
                if _min_y <= _max_y:
                    y = min(max(y, _min_y), _max_y)
            except Exception:
                pass
        try:
            self.setGeometry(x, y, w, h)
        except Exception:
            try:
                self.resize(_DW, _DH)
            except Exception:
                pass

    def _apply_domain_stylesheet(self: Any, theme: str | None = None):
        """Apply Fluent theme + domain QSS (scoped) without crushing Fluent controls."""
        theme_name = str(theme or getattr(self, "current_theme", "dark") or "dark")
        try:
            from src.ui.fluent.theme import apply_app_theme

            apply_app_theme(theme_name)
        except Exception:
            pass
        from src.ui.styles_parts.colors import COLORS

        _key = theme_name
        if _key not in COLORS:
            try:
                import darkdetect
                _key = "light" if darkdetect.theme() == "Light" else "dark"
            except Exception:
                _key = "dark"
        c = COLORS.get(_key, COLORS["dark"])
        # Window chrome only — do not put full domain QSS on QMainWindow (breaks Fluent nav).
        chrome = (
            f"QMainWindow {{ background-color: {c['bg_primary']}; color: {c['text_primary']}; }}"
            f"QMenuBar {{ background-color: {c['bg_secondary']}; color: {c['text_primary']}; }}"
            f"QMenuBar::item:selected {{ background-color: {c['accent_bg']}; }}"
            f"QStatusBar {{ background-color: {c['bg_statusbar']}; color: {c['text_secondary']}; "
            f"border-top: 1px solid {c['border_subtle']}; }}"
            f"QMenu {{ background-color: {c['bg_menu']}; color: {c['text_primary']}; "
            f"border: 1px solid {c['border_subtle']}; }}"
            f"QMenu::item:selected {{ background-color: {c['select_bg']}; }}"
        )
        try:
            self.setStyleSheet(chrome)
        except Exception:
            pass

        sheet = get_stylesheet(_key)
        # 메인 창에서 여는 대화창(설정·알림 등)도 같은 테마를 입는다.
        self._domain_sheet = sheet
        self._install_dialog_themer()
        stack = getattr(self, "stackedWidget", None)
        if stack is not None:
            stack.setObjectName("domainContent")
            stack.setStyleSheet(sheet)
        from src.ui.styles_parts.surfaces import apply_theme_surfaces

        for tab_name in ("crawler_tab", "geo_tab"):
            tab = getattr(self, tab_name, None)
            if tab is not None:
                apply_theme_surfaces(tab, _key)
        try:
            sb = self.statusBar()
            if sb is not None:
                sb.setObjectName("appStatusBar")
        except Exception:
            pass
        # Guide HTML embeds its own theme colors (QTextBrowser document defaults are black).
        if hasattr(self, "_refresh_guide_theme"):
            try:
                self._refresh_guide_theme(_key)
            except Exception:
                pass

    def _install_dialog_themer(self: Any):
        if getattr(self, "_dialog_themer", None) is not None:
            return
        try:
            from src.ui.fluent.theme import DialogThemer

            app = QApplication.instance()
            if app is None:
                return
            self._dialog_themer = DialogThemer(lambda: getattr(self, "_domain_sheet", ""), self)
            app.installEventFilter(self._dialog_themer)
        except Exception:
            self._dialog_themer = None

    def _mark_noncritical_stale(self: Any, *names: str):
        for name in names:
            if name in self._noncritical_loaded:
                self._noncritical_loaded[name] = False

    def _mark_noncritical_loaded(self: Any, name: str):
        if name in self._noncritical_loaded:
            self._noncritical_loaded[name] = True

    def _load_initial_data(self: Any):
        self._load_history()
        self._mark_noncritical_loaded("history")
        self._load_stats_complexes()
        self._mark_noncritical_stale("stats")
        self._refresh_favorite_keys()
        self._mark_noncritical_stale("favorites", "dashboard")
        group_tab = getattr(self, "group_tab", None)
        if group_tab is not None:
            group_tab.load_groups()
        db_tab = getattr(self, "db_tab", None)
        if db_tab is not None:
            db_tab.load_data()
        self._load_schedule_groups()
        self._load_schedule_config()
        
        # Connect signals after loading
        try:
            self.stats_complex_combo.currentIndexChanged.disconnect(self._on_stats_complex_changed)
        except Exception:
            pass
        self.stats_complex_combo.currentIndexChanged.connect(self._on_stats_complex_changed)
