from __future__ import annotations

from src.core.database_parts.crawl_snapshot_parts.crawl_history_ops import ComplexDatabaseCrawlHistoryOpsMixin
from src.core.database_parts.crawl_snapshot_parts.price_snapshot_query_ops import ComplexDatabasePriceSnapshotQueryOpsMixin
from src.core.database_parts.crawl_snapshot_parts.price_snapshot_write_ops import ComplexDatabasePriceSnapshotWriteOpsMixin
from src.core.database_parts.crawl_snapshot_parts.snapshot_filters import ComplexDatabaseSnapshotFilterMixin


class ComplexDatabaseCrawlSnapshotOpsMixin(
    ComplexDatabaseSnapshotFilterMixin,
    ComplexDatabaseCrawlHistoryOpsMixin,
    ComplexDatabasePriceSnapshotWriteOpsMixin,
    ComplexDatabasePriceSnapshotQueryOpsMixin,
):
    pass
