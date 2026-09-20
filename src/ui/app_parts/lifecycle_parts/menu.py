from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppLifecycleMenuMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...
    def _init_menu(self: Any):
        menubar = self.menuBar()
        
        # 파일 메뉴
        file_menu = menubar.addMenu("📂 파일")
        self.action_backup_db = file_menu.addAction("💾 DB 백업", self._backup_db)
        self.action_restore_db = file_menu.addAction("📂 DB 복원", self._restore_db)
        file_menu.addSeparator()
        self.action_settings = file_menu.addAction("⚙️ 설정", self._show_settings)
        self.action_quit = file_menu.addAction("❌ 종료", self._quit_app)
        
        # 보기 메뉴 (v13.0)
        view_menu = menubar.addMenu("👁️ 보기")
        view_menu.addAction("🕐 최근 본 매물", self._show_recently_viewed_dialog)
        view_menu.addSeparator()
        
        # 테마 메뉴
        theme_menu = view_menu.addMenu("🎨 테마")
        self.action_theme_dark = QAction("🌙 다크 모드", self)
        self.action_theme_dark.setCheckable(True)
        self.action_theme_dark.setChecked(self.current_theme == "dark")
        self.action_theme_dark.triggered.connect(lambda: self._toggle_theme("dark"))
        theme_menu.addAction(self.action_theme_dark)
        
        self.action_theme_light = QAction("☀️ 라이트 모드", self)
        self.action_theme_light.setCheckable(True)
        self.action_theme_light.setChecked(self.current_theme == "light")
        self.action_theme_light.triggered.connect(lambda: self._toggle_theme("light"))
        theme_menu.addAction(self.action_theme_light)
        
        # 필터 메뉴
        filter_menu = menubar.addMenu("🔍 필터")
        self.action_save_preset = filter_menu.addAction("💾 현재 필터 저장", self._save_preset)
        self.action_load_preset = filter_menu.addAction("📂 필터 불러오기", self._load_preset)
        filter_menu.addSeparator()
        self.action_advanced_filter = filter_menu.addAction("⚙️ 고급 결과 필터", self._show_advanced_filter)
        self.action_clear_advanced_filter = filter_menu.addAction("🧹 고급 필터 해제", self._clear_advanced_filter)
        
        # 알림 메뉴
        alert_menu = menubar.addMenu("🔔 알림")
        alert_menu.addAction("⚙️ 알림 설정", self._show_alert_settings)
        
        # 도움말 메뉴
        help_menu = menubar.addMenu("❓ 도움말")
        help_menu.addAction("⌨️ 단축키", self._show_shortcuts)
        help_menu.addAction("ℹ️ 정보", self._show_about)

    def _show_shortcuts(self: Any):
        ShortcutsDialog(self).exec()

    def _show_about(self: Any):
        AboutDialog(self, theme=self.current_theme).exec()

    def _focus_search(self: Any):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            if hasattr(self.crawler_tab, "result_search"):
                self.crawler_tab.result_search.setFocus()

    def _toggle_view_mode(self: Any):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab._toggle_view_mode()
            return
        ui_logger.warning("CrawlerTab unavailable for _toggle_view_mode.")
