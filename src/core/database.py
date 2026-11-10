import os  # noqa: F401  # star-carried (do not remove)
import re
import shutil  # noqa: F401  # star-carried (do not remove)
import sqlite3  # noqa: F401  # star-carried: `from src.core.database import *` in database_parts/* (do not remove)
import time  # noqa: F401  # star-carried (do not remove)
from pathlib import Path  # noqa: F401  # star-carried (do not remove)
from queue import Empty, Full, Queue  # noqa: F401  # star-carried (do not remove)
from threading import Condition, Lock  # noqa: F401  # star-carried (do not remove)

from src.core.database_parts.alert_ops import ComplexDatabaseAlertOpsMixin
from src.core.database_parts.article_ops import ComplexDatabaseArticleOpsMixin
from src.core.database_parts.backup_restore_ops import (
    ComplexDatabaseBackupRestoreOpsMixin,
)
from src.core.database_parts.coercion import ComplexDatabaseCoercionMixin
from src.core.database_parts.complex_group_ops import (
    ComplexDatabaseComplexGroupOpsMixin,
)
from src.core.database_parts.crawl_snapshot_ops import (
    ComplexDatabaseCrawlSnapshotOpsMixin,
)
from src.core.database_parts.pool import ConnectionPool  # noqa: F401  # star-carried (do not remove)
from src.core.database_parts.schema import ComplexDatabaseSchemaMixin
from src.utils.helpers import DateTimeHelper, PriceConverter  # noqa: F401  # star-carried (do not remove)
from src.utils.logger import get_logger
from src.utils.mixin_rebind import rebind_inherited_methods
from src.utils.paths import DB_PATH  # noqa: F401  # star-carried (do not remove)

logger = get_logger("DB")




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
