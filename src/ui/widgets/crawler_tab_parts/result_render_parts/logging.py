from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


class CrawlerTabResultLoggingMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def append_log(self: Any, msg, level=20):
        theme_colors = COLORS[self.current_theme]
        color = theme_colors["text_primary"]

        if level >= 40:
            color = theme_colors["error"]
        elif level >= 30:
            color = theme_colors["warning"]
        elif level == 10:
            color = theme_colors["text_secondary"]

        try:
            max_lines = max(200, int(settings.get("max_log_lines", 1500)))
        except (TypeError, ValueError):
            max_lines = 1500
        doc = self.log_browser.document()
        if getattr(self, "_log_max_block_count", None) != max_lines:
            doc.setMaximumBlockCount(max_lines)
            self._log_max_block_count = max_lines
        self.log_browser.append(f'<span style="color:{color}">{msg}</span>')
        sb = self.log_browser.verticalScrollBar()
        sb.setValue(sb.maximum())
