from __future__ import annotations

from typing import Any, TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


FavoriteKey = tuple[str, str, str]
FavoriteKeyProvider = Callable[[], set[FavoriteKey]]
CompactRowKey = tuple[str, str, str, str, str, float, str]
RowPayload = dict[str, Any]
ResultRow = dict[str, Any]


class CrawlerTabRuntimeSettingsSetupMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def _default_sort_criterion(self: Any):
        column = str(settings.get("default_sort_column", "가격") or "가격")
        order = str(settings.get("default_sort_order", "asc") or "asc").lower()
        if column == "거래":
            column = "거래유형"
        if column not in {"가격", "면적", "단지명", "거래유형"}:
            column = "가격"
        arrow = "↑" if order == "asc" else "↓"
        return f"{column} {arrow}"

    def _apply_default_sort_settings(self: Any):
        criterion = self._default_sort_criterion()
        idx = self.combo_sort.findText(criterion)
        if idx < 0:
            return
        self.combo_sort.blockSignals(True)
        self.combo_sort.setCurrentIndex(idx)
        self.combo_sort.blockSignals(False)
        if self.result_table.rowCount() > 0:
            self._sort_results(self.combo_sort.currentText())

    def update_runtime_settings(self: Any):
        try:
            debounce_ms = max(80, int(settings.get("result_filter_debounce_ms", 220)))
        except (TypeError, ValueError):
            debounce_ms = 220
        self._search_timer.setInterval(debounce_ms)
        if hasattr(self, "combo_engine"):
            self.combo_engine.setCurrentText(settings.get("crawl_engine", "playwright"))
        self.speed_slider.set_speed(settings.get("crawl_speed", "보통"))
        self._apply_default_sort_settings()
        if hasattr(self, "_refresh_result_render_options"):
            self._refresh_result_render_options()

        compact = bool(settings.get("compact_duplicate_listings", True))
        self.check_compact_duplicates.setChecked(compact)
