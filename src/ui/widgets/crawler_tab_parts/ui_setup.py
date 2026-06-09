from __future__ import annotations

from src.ui.widgets.crawler_tab_parts.ui_setup_parts.controls import CrawlerTabControlSetupMixin
from src.ui.widgets.crawler_tab_parts.ui_setup_parts.layout import CrawlerTabLayoutSetupMixin
from src.ui.widgets.crawler_tab_parts.ui_setup_parts.result_area import CrawlerTabResultAreaSetupMixin
from src.ui.widgets.crawler_tab_parts.ui_setup_parts.runtime_settings import CrawlerTabRuntimeSettingsSetupMixin


class CrawlerTabUISetupMixin(
    CrawlerTabLayoutSetupMixin,
    CrawlerTabControlSetupMixin,
    CrawlerTabResultAreaSetupMixin,
    CrawlerTabRuntimeSettingsSetupMixin,
):
    pass
