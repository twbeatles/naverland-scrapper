from __future__ import annotations

from typing import Any, TYPE_CHECKING

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


logger = get_logger("DB")


class ComplexDatabaseSchemaMigrationMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...
        @staticmethod
        def _column_names(cursor: Any, table_name: str) -> set[str]: ...

    @classmethod
    def _article_history_requires_migration(cls, cursor) -> bool:
        columns = cls._column_names(cursor, "article_history")
        if not columns:
            return False
        if "asset_type" not in columns:
            return True

        expected = ("asset_type", "article_id", "complex_id")
        try:
            indexes = cursor.execute("PRAGMA index_list(article_history)").fetchall()
        except Exception:
            return True

        has_scoped_unique = False
        has_legacy_unique = False
        for idx in indexes:
            try:
                is_unique = int(idx[2]) == 1
                idx_name = str(idx[1])
            except Exception:
                try:
                    is_unique = int(idx["unique"]) == 1
                    idx_name = str(idx["name"])
                except Exception:
                    continue
            if not is_unique:
                continue
            try:
                info_rows = cursor.execute(f"PRAGMA index_info({idx_name})").fetchall()
            except Exception:
                continue
            idx_cols = []
            for info in info_rows:
                try:
                    idx_cols.append(str(info[2]))
                except Exception:
                    try:
                        idx_cols.append(str(info["name"]))
                    except Exception:
                        pass
            normalized = tuple(idx_cols)
            if normalized == expected:
                has_scoped_unique = True
            if normalized == ("article_id", "complex_id"):
                has_legacy_unique = True
        return (not has_scoped_unique) or has_legacy_unique

    @classmethod
    def _article_favorites_requires_migration(cls, cursor) -> bool:
        columns = cls._column_names(cursor, "article_favorites")
        if not columns:
            return False
        if "asset_type" not in columns:
            return True

        expected = ("asset_type", "article_id", "complex_id")
        try:
            indexes = cursor.execute("PRAGMA index_list(article_favorites)").fetchall()
        except Exception:
            return True

        has_scoped_unique = False
        has_legacy_unique = False
        for idx in indexes:
            try:
                is_unique = int(idx[2]) == 1
                idx_name = str(idx[1])
            except Exception:
                try:
                    is_unique = int(idx["unique"]) == 1
                    idx_name = str(idx["name"])
                except Exception:
                    continue
            if not is_unique:
                continue
            try:
                info_rows = cursor.execute(f"PRAGMA index_info({idx_name})").fetchall()
            except Exception:
                continue
            idx_cols = []
            for info in info_rows:
                try:
                    idx_cols.append(str(info[2]))
                except Exception:
                    try:
                        idx_cols.append(str(info["name"]))
                    except Exception:
                        pass
            normalized = tuple(idx_cols)
            if normalized == expected:
                has_scoped_unique = True
            if normalized == ("article_id", "complex_id"):
                has_legacy_unique = True
        return (not has_scoped_unique) or has_legacy_unique

    def _backup_before_schema_migration(self, conn, reason: str):
        import sqlite3
        from pathlib import Path
        from src.utils.helpers import DateTimeHelper

        if getattr(self, "_schema_migration_backup_path", None):
            return

        db_path = Path(getattr(self, "db_path", ""))
        if not db_path:
            return
        try:
            if not db_path.exists() or db_path.stat().st_size <= 0:
                return
        except OSError:
            return

        backup_dir = db_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"{db_path.stem}.schema_migration_{DateTimeHelper.file_timestamp()}.db"
        backup_conn = None
        try:
            backup_conn = sqlite3.connect(str(backup_path), timeout=30)
            conn.backup(backup_conn)
            backup_conn.commit()
            self._schema_migration_backup_path = backup_path
            logger.info(f"schema migration backup created: {backup_path} ({reason})")
        finally:
            if backup_conn is not None:
                try:
                    backup_conn.close()
                except Exception:
                    pass

    @classmethod
    def _migrate_article_history_asset_scope_schema(cls, cursor):
        if not cls._article_history_requires_migration(cursor):
            return

        logger.info("article_history schema migration start: asset-scoped unique")
        cursor.execute("ALTER TABLE article_history RENAME TO article_history_legacy")
        cursor.execute(
            """
            CREATE TABLE article_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id TEXT NOT NULL,
                complex_id TEXT NOT NULL,
                complex_name TEXT,
                trade_type TEXT,
                price INTEGER,
                price_text TEXT,
                area_pyeong REAL,
                floor_info TEXT,
                feature TEXT,
                first_seen DATE DEFAULT CURRENT_DATE,
                last_seen DATE DEFAULT CURRENT_DATE,
                last_price INTEGER,
                price_change INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                asset_type TEXT DEFAULT 'APT',
                source_mode TEXT DEFAULT 'complex',
                source_lat REAL DEFAULT 0,
                source_lon REAL DEFAULT 0,
                source_zoom INTEGER DEFAULT 0,
                marker_id TEXT DEFAULT '',
                broker_office TEXT DEFAULT '',
                broker_name TEXT DEFAULT '',
                broker_phone1 TEXT DEFAULT '',
                broker_phone2 TEXT DEFAULT '',
                prev_jeonse_won INTEGER DEFAULT 0,
                jeonse_period_years INTEGER DEFAULT 0,
                jeonse_max_won INTEGER DEFAULT 0,
                jeonse_min_won INTEGER DEFAULT 0,
                gap_amount_won INTEGER DEFAULT 0,
                gap_ratio REAL DEFAULT 0,
                UNIQUE(asset_type, article_id, complex_id)
            )
            """
        )
        legacy_columns = cls._column_names(cursor, "article_history_legacy")
        def _legacy_expr(column_name: str, fallback_sql: str) -> str:
            if column_name in legacy_columns:
                return f"COALESCE({column_name}, {fallback_sql})"
            return fallback_sql

        asset_expr = (
            "CASE "
            "WHEN TRIM(COALESCE(asset_type, '')) = '' THEN 'APT' "
            "ELSE UPPER(TRIM(asset_type)) "
            "END"
            if "asset_type" in legacy_columns
            else "'APT'"
        )
        complex_name_expr = _legacy_expr("complex_name", "''")
        trade_type_expr = _legacy_expr("trade_type", "''")
        price_expr = _legacy_expr("price", "0")
        price_text_expr = _legacy_expr("price_text", "''")
        area_pyeong_expr = _legacy_expr("area_pyeong", "0")
        floor_info_expr = _legacy_expr("floor_info", "''")
        feature_expr = _legacy_expr("feature", "''")
        first_seen_expr = _legacy_expr("first_seen", "CURRENT_DATE")
        last_seen_expr = _legacy_expr("last_seen", "CURRENT_DATE")
        last_price_expr = _legacy_expr("last_price", price_expr)
        price_change_expr = _legacy_expr("price_change", "0")
        status_expr = _legacy_expr("status", "'active'")
        source_mode_expr = _legacy_expr("source_mode", "'complex'")
        source_lat_expr = _legacy_expr("source_lat", "0")
        source_lon_expr = _legacy_expr("source_lon", "0")
        source_zoom_expr = _legacy_expr("source_zoom", "0")
        marker_id_expr = _legacy_expr("marker_id", "''")
        broker_office_expr = _legacy_expr("broker_office", "''")
        broker_name_expr = _legacy_expr("broker_name", "''")
        broker_phone1_expr = _legacy_expr("broker_phone1", "''")
        broker_phone2_expr = _legacy_expr("broker_phone2", "''")
        prev_jeonse_expr = _legacy_expr("prev_jeonse_won", "0")
        jeonse_period_expr = _legacy_expr("jeonse_period_years", "0")
        jeonse_max_expr = _legacy_expr("jeonse_max_won", "0")
        jeonse_min_expr = _legacy_expr("jeonse_min_won", "0")
        gap_amount_expr = _legacy_expr("gap_amount_won", "0")
        gap_ratio_expr = _legacy_expr("gap_ratio", "0")
        cursor.execute(
            f"""
            INSERT OR IGNORE INTO article_history (
                id, article_id, complex_id, complex_name, trade_type,
                price, price_text, area_pyeong, floor_info, feature,
                first_seen, last_seen, last_price, price_change, status,
                asset_type, source_mode, source_lat, source_lon, source_zoom, marker_id,
                broker_office, broker_name, broker_phone1, broker_phone2,
                prev_jeonse_won, jeonse_period_years, jeonse_max_won, jeonse_min_won,
                gap_amount_won, gap_ratio
            )
            SELECT
                id,
                article_id,
                complex_id,
                {complex_name_expr},
                {trade_type_expr},
                {price_expr},
                {price_text_expr},
                {area_pyeong_expr},
                {floor_info_expr},
                {feature_expr},
                {first_seen_expr},
                {last_seen_expr},
                {last_price_expr},
                {price_change_expr},
                {status_expr},
                {asset_expr} AS asset_type,
                {source_mode_expr},
                {source_lat_expr},
                {source_lon_expr},
                {source_zoom_expr},
                {marker_id_expr},
                {broker_office_expr},
                {broker_name_expr},
                {broker_phone1_expr},
                {broker_phone2_expr},
                {prev_jeonse_expr},
                {jeonse_period_expr},
                {jeonse_max_expr},
                {jeonse_min_expr},
                {gap_amount_expr},
                {gap_ratio_expr}
            FROM article_history_legacy
            ORDER BY id
            """
        )
        cursor.execute("DROP TABLE article_history_legacy")
        logger.info("article_history schema migration complete")

    @classmethod
    def _migrate_article_favorites_asset_scope_schema(cls, cursor):
        if not cls._article_favorites_requires_migration(cursor):
            return

        logger.info("article_favorites schema migration start: add asset_type + scoped unique")
        cursor.execute("ALTER TABLE article_favorites RENAME TO article_favorites_legacy")
        cursor.execute(
            """
            CREATE TABLE article_favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_type TEXT NOT NULL DEFAULT 'APT',
                article_id TEXT NOT NULL,
                complex_id TEXT NOT NULL,
                is_favorite INTEGER DEFAULT 1,
                note TEXT DEFAULT "",
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(asset_type, article_id, complex_id)
            )
            """
        )
        legacy_columns = cls._column_names(cursor, "article_favorites_legacy")
        def _legacy_expr(column_name: str, fallback_sql: str) -> str:
            if column_name in legacy_columns:
                return f"COALESCE({column_name}, {fallback_sql})"
            return fallback_sql

        asset_expr = (
            "CASE "
            "WHEN TRIM(COALESCE(asset_type, '')) = '' THEN 'APT' "
            "ELSE UPPER(TRIM(asset_type)) "
            "END"
            if "asset_type" in legacy_columns
            else "'APT'"
        )
        is_favorite_expr = _legacy_expr("is_favorite", "1")
        note_expr = _legacy_expr("note", "''")
        created_at_expr = _legacy_expr("created_at", "CURRENT_TIMESTAMP")
        updated_at_expr = _legacy_expr("updated_at", "CURRENT_TIMESTAMP")
        cursor.execute(
            f"""
            INSERT OR IGNORE INTO article_favorites (
                id, asset_type, article_id, complex_id, is_favorite, note, created_at, updated_at
            )
            SELECT
                id,
                {asset_expr} AS asset_type,
                article_id,
                complex_id,
                {is_favorite_expr},
                {note_expr},
                {created_at_expr},
                {updated_at_expr}
            FROM article_favorites_legacy
            ORDER BY id
            """
        )
        cursor.execute("DROP TABLE article_favorites_legacy")
        logger.info("article_favorites schema migration complete")

    @classmethod
    def _article_alert_log_requires_migration(cls, cursor) -> bool:
        columns = cls._column_names(cursor, "article_alert_log")
        if not columns:
            return False
        if "asset_type" not in columns:
            return True

        expected = ("alert_id", "article_id", "complex_id", "asset_type", "notified_on")
        try:
            indexes = cursor.execute("PRAGMA index_list(article_alert_log)").fetchall()
        except Exception:
            return True

        for idx in indexes:
            try:
                is_unique = int(idx[2]) == 1
                idx_name = str(idx[1])
            except Exception:
                try:
                    is_unique = int(idx["unique"]) == 1
                    idx_name = str(idx["name"])
                except Exception:
                    continue
            if not is_unique:
                continue
            try:
                info_rows = cursor.execute(f"PRAGMA index_info({idx_name})").fetchall()
            except Exception:
                continue
            idx_cols = []
            for info in info_rows:
                try:
                    idx_cols.append(str(info[2]))
                except Exception:
                    try:
                        idx_cols.append(str(info["name"]))
                    except Exception:
                        pass
            if tuple(idx_cols) == expected:
                return False
        return True

    @classmethod
    def _migrate_article_alert_log_asset_type_schema(cls, cursor):
        if not cls._article_alert_log_requires_migration(cursor):
            return

        logger.info("article_alert_log schema migration start: add asset_type + scoped unique")
        cursor.execute("ALTER TABLE article_alert_log RENAME TO article_alert_log_legacy")
        cursor.execute(
            """
            CREATE TABLE article_alert_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER NOT NULL,
                article_id TEXT NOT NULL,
                complex_id TEXT NOT NULL,
                asset_type TEXT DEFAULT 'ALL',
                notified_on DATE DEFAULT CURRENT_DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(alert_id, article_id, complex_id, asset_type, notified_on)
            )
            """
        )
        legacy_columns = cls._column_names(cursor, "article_alert_log_legacy")
        asset_expr = (
            "CASE "
            "WHEN TRIM(COALESCE(asset_type, '')) = '' THEN 'ALL' "
            "ELSE UPPER(TRIM(asset_type)) "
            "END"
            if "asset_type" in legacy_columns
            else "'ALL'"
        )
        notified_on_expr = (
            "COALESCE(notified_on, CURRENT_DATE)"
            if "notified_on" in legacy_columns
            else "CURRENT_DATE"
        )
        created_at_expr = (
            "COALESCE(created_at, CURRENT_TIMESTAMP)"
            if "created_at" in legacy_columns
            else "CURRENT_TIMESTAMP"
        )
        cursor.execute(
            f"""
            INSERT OR IGNORE INTO article_alert_log (
                id, alert_id, article_id, complex_id, asset_type, notified_on, created_at
            )
            SELECT
                id,
                alert_id,
                article_id,
                complex_id,
                {asset_expr} AS asset_type,
                {notified_on_expr} AS notified_on,
                {created_at_expr} AS created_at
            FROM article_alert_log_legacy
            """
        )
        cursor.execute("DROP TABLE article_alert_log_legacy")
        logger.info("article_alert_log schema migration complete")
