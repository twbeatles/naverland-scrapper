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

import inspect
import types

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



def _clone_function_with_globals(func):
    cloned = types.FunctionType(
        func.__code__,
        globals(),
        name=func.__name__,
        argdefs=func.__defaults__,
        closure=func.__closure__,
    )
    cloned.__kwdefaults__ = getattr(func, "__kwdefaults__", None)
    cloned.__annotations__ = dict(getattr(func, "__annotations__", {}))
    cloned.__doc__ = func.__doc__
    cloned.__module__ = __name__
    return cloned


def _rebind_inherited_methods(cls, method_names):
    for name in method_names:
        raw = inspect.getattr_static(cls, name, None)
        if raw is None:
            continue
        if isinstance(raw, staticmethod):
            setattr(cls, name, staticmethod(_clone_function_with_globals(raw.__func__)))
        elif isinstance(raw, classmethod):
            setattr(cls, name, classmethod(_clone_function_with_globals(raw.__func__)))
        elif inspect.isfunction(raw):
            setattr(cls, name, _clone_function_with_globals(raw))
    return cls


_rebind_inherited_methods(
    ComplexDatabase,
    [
    "__init__",
    "_sqlite_error_text",
    "_is_locked_sqlite_error",
    "_is_corruption_sqlite_error",
    "is_write_disabled",
    "get_write_disabled_reason",
    "_disable_writes",
    "_log_corruption_detected",
    "_column_names",
    "_ensure_column",
    "_normalize_asset_type",
    "_normalize_alert_asset_scope",
    "_complexes_table_requires_migration",
    "_migrate_complexes_asset_type_schema",
    "_article_alert_log_requires_migration",
    "_migrate_article_alert_log_asset_type_schema",
    "_sqlite_table_names",
    "_ensure_group_complexes_fk_integrity",
    "_fetchall_safe",
    "_coerce_float",
    "_coerce_int",
    "_coerce_price",
    "_is_all_filter_value",
    "_row_value",
    "_normalize_snapshot_row",
    "_init_tables",
    "add_complex",
    "get_all_complexes",
    "get_complexes_for_stats",
    "_asset_scoped_predicate",
    "_purge_related_for_complex_refs",
    "_fetch_complex_refs_by_db_ids",
    "delete_complex",
    "delete_complexes_bulk",
    "update_complex_memo",
    "create_group",
    "get_all_groups",
    "delete_group",
    "add_complexes_to_group",
    "remove_complex_from_group",
    "get_complexes_in_group",
    "add_crawl_history",
    "get_crawl_history",
    "get_complex_price_history",
    "add_price_snapshot",
    "add_price_snapshots_bulk",
    "get_price_snapshots",
    "add_alert_setting",
    "get_article_history_state_bulk",
    "upsert_article_history_bulk",
    "get_enabled_alert_rules",
    "record_alert_notification",
    "check_article_history",
    "update_article_history",
    "get_article_history_stats",
    "cleanup_old_articles",
    "toggle_favorite",
    "update_article_note",
    "get_favorites",
    "_integrity_check_file",
    "_validate_restored_database",
    "backup_database",
    "restore_database",
    "get_all_alert_settings",
    "toggle_alert_setting",
    "delete_alert_setting",
    "check_alerts",
    "get_article_favorite_info",
    "mark_disappeared_articles",
    "mark_disappeared_articles_for_targets",
    "get_disappeared_articles",
    "count_disappeared_articles",
    "close",
    ],
)
