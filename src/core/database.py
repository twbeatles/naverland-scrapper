import re
import sqlite3
import os
from pathlib import Path
from queue import Queue, Empty, Full
from threading import Lock, Condition
import time
import shutil
from src.utils.paths import DB_PATH
from src.utils.logger import get_logger
from src.utils.helpers import DateTimeHelper, PriceConverter

logger = get_logger("DB")

from src.utils.mixin_rebind import rebind_inherited_methods

from src.core.database_parts.pool import ConnectionPool
from src.core.database_parts.coercion import ComplexDatabaseCoercionMixin
from src.core.database_parts.schema import ComplexDatabaseSchemaMixin
from src.core.database_parts.complex_group_ops import ComplexDatabaseComplexGroupOpsMixin
from src.core.database_parts.crawl_snapshot_ops import ComplexDatabaseCrawlSnapshotOpsMixin
from src.core.database_parts.article_ops import ComplexDatabaseArticleOpsMixin
from src.core.database_parts.alert_ops import ComplexDatabaseAlertOpsMixin
from src.core.database_parts.backup_restore_ops import ComplexDatabaseBackupRestoreOpsMixin


class ComplexDatabase(
    ComplexDatabaseCoercionMixin,
    ComplexDatabaseSchemaMixin,
    ComplexDatabaseComplexGroupOpsMixin,
    ComplexDatabaseCrawlSnapshotOpsMixin,
    ComplexDatabaseArticleOpsMixin,
    ComplexDatabaseAlertOpsMixin,
    ComplexDatabaseBackupRestoreOpsMixin,
):
    _NUMERIC_RE = re.compile(r"-?\d+(?:\.\d+)?")
    _RESTORE_REQUIRED_TABLES = (
        "complexes",
        "groups",
        "group_complexes",
        "crawl_history",
        "price_snapshots",
        "alert_settings",
        "article_history",
        "article_favorites",
        "article_alert_log",
    )



rebind_inherited_methods(
    ComplexDatabase,
    mixin_classes=[
        ComplexDatabaseCoercionMixin,
        ComplexDatabaseSchemaMixin,
        ComplexDatabaseComplexGroupOpsMixin,
        ComplexDatabaseCrawlSnapshotOpsMixin,
        ComplexDatabaseArticleOpsMixin,
        ComplexDatabaseAlertOpsMixin,
        ComplexDatabaseBackupRestoreOpsMixin,
    ],
    globals_dict=globals(),
)