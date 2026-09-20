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
        self.setMinimumSize(1400, 900)
        geo = settings.get("window_geometry")
        if geo: self.setGeometry(*geo)
        else: self.setGeometry(100, 100, 1500, 950)
        
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
        geo = settings.get("window_geometry")
        if not geo:
            return
        if not isinstance(geo, (list, tuple)) or len(geo) != 4:
            return
        try:
            x, y, w, h = (int(geo[0]), int(geo[1]), int(geo[2]), int(geo[3]))
            self.setGeometry(x, y, w, h)
        except Exception:
            # Best-effort only; invalid saved geometry should not prevent startup.
            return

    def _apply_domain_stylesheet(self: Any, theme: str | None = None):
        """Apply Fluent theme + domain QSS (scoped) without crushing Fluent controls."""
        theme_name = str(theme or getattr(self, "current_theme", "dark") or "dark")
        try:
            from src.ui.fluent.theme import apply_app_theme

            apply_app_theme(theme_name)
        except Exception:
            pass
        from src.ui.styles_parts.colors import COLORS

        c = COLORS.get(theme_name, COLORS["dark"])
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

        sheet = get_stylesheet(theme_name)
        stack = getattr(self, "stackedWidget", None)
        if stack is not None:
            stack.setObjectName("domainContent")
            stack.setStyleSheet(sheet)
        from src.ui.styles_parts.surfaces import apply_theme_surfaces

        for tab_name in ("crawler_tab", "geo_tab"):
            tab = getattr(self, tab_name, None)
            if tab is not None:
                apply_theme_surfaces(tab, theme_name)
        try:
            sb = self.statusBar()
            if sb is not None:
                sb.setObjectName("appStatusBar")
        except Exception:
            pass
        # Guide HTML embeds its own theme colors (QTextBrowser document defaults are black).
        if hasattr(self, "_refresh_guide_theme"):
            try:
                self._refresh_guide_theme(theme_name)
            except Exception:
                pass

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
