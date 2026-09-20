from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppLifecycleTrayMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...
    def _init_tray(self: Any):
        self.tray_icon = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
            self.tray_icon = QSystemTrayIcon(icon, self)
            tray_menu = QMenu()
            tray_menu.addAction("🔼 열기", self._show_from_tray)
            tray_menu.addAction("❌ 종료", self._quit_app)
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.activated.connect(self._tray_activated)
            self.tray_icon.show()

    def _minimize_to_tray(self: Any):
        if not self.tray_icon:
            self.status_bar.showMessage("시스템 트레이를 사용할 수 없습니다.")
            return
        self.hide()
        self.tray_icon.showMessage("알림", "트레이로 최소화되었습니다.", QSystemTrayIcon.MessageIcon.Information, 2000)

    def _show_from_tray(self: Any):
        self.show()
        self.raise_()
        self.activateWindow()

    def _tray_activated(self: Any, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
