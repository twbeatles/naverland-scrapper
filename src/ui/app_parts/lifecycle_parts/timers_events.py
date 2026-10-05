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
        count = len(self.collected_data)
        self.status_bar.showMessage(
            f"수집을 마쳤습니다. 매물 {count}건 · 「결과 저장」으로 파일에 담을 수 있습니다."
            if count
            else "수집을 마쳤지만 조건에 맞는 매물이 없습니다."
        )

    def _on_alert_triggered(self: Any, complex_name, trade_type, price_text, area_pyeong, alert_id):
        try:
            area_text = f"{float(area_pyeong):.1f}평"
        except (TypeError, ValueError):
            fallback = "" if area_pyeong is None else str(area_pyeong).strip()
            area_text = f"{fallback}평" if fallback else "평형 미상"
        message = f"{complex_name} {trade_type} {price_text} ({area_text})"
        self.show_toast(f"알림 조건에 맞는 매물: {message}")
        self.show_notification("가격 알림", message)

    def _on_dashboard_warning(self: Any, message: str):
        text = str(message or "").strip()
        if not text:
            return
        ui_logger.warning(f"Dashboard warning: {text}")
        self.status_bar.showMessage(f"{text}")
