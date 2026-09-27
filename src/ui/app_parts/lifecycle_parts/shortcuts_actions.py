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
        # ISSUE-021: 중복 키 재등록 시 기존 QShortcut을 먼저 해제해야
        # 부모에 좀비 단축키가 남아 이중 발화하지 않는다.
        try:
            _reg = getattr(self, "_shortcuts", None)
            _old = _reg.pop(key_sequence, None) if isinstance(_reg, dict) else None
        except Exception:
            _old = None
        if _old is not None:
            for _op in ("activated.disconnect", "setEnabled", "setParent", "deleteLater"):
                try:
                    if _op == "activated.disconnect":
                        _old.activated.disconnect()
                    elif _op == "setEnabled":
                        _old.setEnabled(False)
                    elif _op == "setParent":
                        _old.setParent(None)
                    else:
                        _old.deleteLater()
                except Exception:
                    pass
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
