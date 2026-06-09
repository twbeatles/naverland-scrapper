from __future__ import annotations

from src.ui.widgets.crawler_tab_parts.crawl_control_parts.dialogs import CrawlerTabDialogOpsMixin
from src.ui.widgets.crawler_tab_parts.crawl_control_parts.finish import CrawlerTabFinishMixin
from src.ui.widgets.crawler_tab_parts.crawl_control_parts.snapshot_worker import CrawlerTabSnapshotWorkerMixin
from src.ui.widgets.crawler_tab_parts.crawl_control_parts.start_stop import CrawlerTabStartStopMixin
from src.ui.widgets.crawler_tab_parts.crawl_control_parts.tasks import CrawlerTabTaskOpsMixin


class CrawlerTabCrawlControlMixin(
    CrawlerTabTaskOpsMixin,
    CrawlerTabDialogOpsMixin,
    CrawlerTabStartStopMixin,
    CrawlerTabFinishMixin,
    CrawlerTabSnapshotWorkerMixin,
):
    pass
