from __future__ import annotations

from src.ui.widgets.crawler_tab_parts.result_render_parts.card_sync import CrawlerTabCardSyncMixin
from src.ui.widgets.crawler_tab_parts.result_render_parts.compact import CrawlerTabCompactRenderMixin
from src.ui.widgets.crawler_tab_parts.result_render_parts.favorites import CrawlerTabFavoriteRenderMixin
from src.ui.widgets.crawler_tab_parts.result_render_parts.filters import CrawlerTabFilterRenderMixin
from src.ui.widgets.crawler_tab_parts.result_render_parts.logging import CrawlerTabResultLoggingMixin
from src.ui.widgets.crawler_tab_parts.result_render_parts.table_rows import CrawlerTabTableRowRenderMixin


class CrawlerTabResultRenderMixin(
    CrawlerTabFilterRenderMixin,
    CrawlerTabFavoriteRenderMixin,
    CrawlerTabCompactRenderMixin,
    CrawlerTabCardSyncMixin,
    CrawlerTabResultLoggingMixin,
    CrawlerTabTableRowRenderMixin,
):
    pass
