from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppLifecycleTimersEventsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...
    def _init_timers(self: Any):
        self.schedule_timer = QTimer(self)
        self.schedule_timer.timeout.connect(self._check_schedule)
        self.schedule_timer.start(60000)

    def _on_crawl_data_collected(self: Any, data):
        self.collected_data = list(data) if data else []
        self._mark_noncritical_stale("history", "stats", "favorites", "dashboard")
        self._refresh_tab(self.tabs.currentIndex())
        self.status_bar.showMessage(f"✅ 수집 결과 반영 완료 ({len(self.collected_data)}건)")

    def _on_alert_triggered(self: Any, complex_name, trade_type, price_text, area_pyeong, alert_id):
        message = f"{complex_name} {trade_type} {price_text} ({area_pyeong:.1f}평)"
        self.show_toast(f"🔔 조건 매물 발견: {message}")
        self.show_notification("조건 매물 알림", message)

    def _on_dashboard_warning(self: Any, message: str):
        text = str(message or "").strip()
        if not text:
            return
        ui_logger.warning(f"Dashboard warning: {text}")
        self.status_bar.showMessage(f"⚠️ {text}")
