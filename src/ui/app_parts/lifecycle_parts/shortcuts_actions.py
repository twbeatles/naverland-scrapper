from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppLifecycleShortcutsActionsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...
    def _init_shortcuts(self: Any):
        self._register_shortcut(SHORTCUTS["start_crawl"], self._start_crawling)
        self._register_shortcut(SHORTCUTS["stop_crawl"], self._stop_crawling)
        self._register_shortcut(SHORTCUTS["save_excel"], self._save_excel)
        self._register_shortcut(SHORTCUTS["save_csv"], self._save_csv)
        self._register_shortcut(SHORTCUTS["refresh"], self._refresh_tab)
        self._register_shortcut(SHORTCUTS["search"], self._focus_search)
        self._register_shortcut(SHORTCUTS["toggle_theme"], self._toggle_theme)
        self._register_shortcut(SHORTCUTS["minimize_tray"], self._minimize_to_tray)
        self._register_shortcut(SHORTCUTS["quit"], self._quit_app)
        self._register_shortcut(SHORTCUTS["settings"], self._show_settings)

    def _register_shortcut(self: Any, key_sequence, callback):
        shortcut = QShortcut(QKeySequence(key_sequence), self)
        shortcut.activated.connect(callback)
        self._shortcuts[key_sequence] = shortcut

    def _start_crawling(self: Any):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab.start_crawling()

    def _stop_crawling(self: Any):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab.stop_crawling()

    def _save_excel(self: Any):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab.save_excel()

    def _save_csv(self: Any):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab.save_csv()

    def _save_json(self: Any):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab.save_json()
