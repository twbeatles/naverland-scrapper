from __future__ import annotations

from src.core.database_parts.article_parts.article_bulk_ops import ComplexDatabaseArticleBulkOpsMixin
from src.core.database_parts.article_parts.article_history_ops import ComplexDatabaseArticleHistoryOpsMixin
from src.core.database_parts.article_parts.disappeared_ops import ComplexDatabaseDisappearedOpsMixin
from src.core.database_parts.article_parts.favorite_ops import ComplexDatabaseFavoriteOpsMixin


class ComplexDatabaseArticleOpsMixin(
    ComplexDatabaseArticleHistoryOpsMixin,
    ComplexDatabaseArticleBulkOpsMixin,
    ComplexDatabaseFavoriteOpsMixin,
    ComplexDatabaseDisappearedOpsMixin,
):
    pass
