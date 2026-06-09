from __future__ import annotations

from typing import Any, TYPE_CHECKING

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


logger = get_logger("DB")


class ComplexDatabaseSchemaTableMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...
        @staticmethod
        def _column_names(cursor: Any, table_name: str) -> set[str]: ...

    def _init_tables(self):
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS complexes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                asset_type TEXT NOT NULL DEFAULT 'APT',
                complex_id TEXT NOT NULL,
                memo TEXT DEFAULT "",
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(asset_type, complex_id)
            )''')
            if self._complexes_table_requires_migration(c):
                self._backup_before_schema_migration(conn, "complexes")
            self._migrate_complexes_asset_type_schema(c)
            c.execute('''CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT "",
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS group_complexes (
                group_id INTEGER,
                complex_id INTEGER,
                PRIMARY KEY (group_id, complex_id),
                FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
                FOREIGN KEY (complex_id) REFERENCES complexes(id) ON DELETE CASCADE
            )''')
            self._ensure_group_complexes_fk_integrity(c)
            c.execute('''CREATE TABLE IF NOT EXISTS crawl_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                complex_name TEXT,
                complex_id TEXT,
                trade_types TEXT,
                item_count INTEGER,
                engine TEXT DEFAULT '',
                mode TEXT DEFAULT 'complex',
                source_lat REAL DEFAULT 0,
                source_lon REAL DEFAULT 0,
                source_zoom INTEGER DEFAULT 0,
                asset_type TEXT DEFAULT '',
                run_status TEXT DEFAULT 'success',
                crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS price_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                complex_id TEXT,
                trade_type TEXT,
                pyeong REAL,
                min_price INTEGER,
                max_price INTEGER,
                avg_price INTEGER,
                item_count INTEGER,
                asset_type TEXT DEFAULT 'APT',
                price_metric TEXT DEFAULT 'price',
                legacy_monthly INTEGER DEFAULT 0,
                snapshot_date DATE DEFAULT CURRENT_DATE
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS alert_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                complex_id TEXT,
                complex_name TEXT,
                asset_type TEXT DEFAULT 'ALL',
                trade_type TEXT,
                area_min REAL DEFAULT 0,
                area_max REAL DEFAULT 999,
                price_min INTEGER DEFAULT 0,
                price_max INTEGER DEFAULT 999999999,
                enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            # v7.3: listing history table (initial listing + previous-price baseline)
            c.execute('''CREATE TABLE IF NOT EXISTS article_history (
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
            )''')
            if self._article_history_requires_migration(c):
                self._backup_before_schema_migration(conn, "article_history")
                self._migrate_article_history_asset_scope_schema(c)
            # v12.0: cache table for query-level response reuse
            c.execute('''CREATE TABLE IF NOT EXISTS article_favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_type TEXT NOT NULL DEFAULT 'APT',
                article_id TEXT NOT NULL,
                complex_id TEXT NOT NULL,
                is_favorite INTEGER DEFAULT 1,
                note TEXT DEFAULT "",
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(asset_type, article_id, complex_id)
            )''')
            if self._article_favorites_requires_migration(c):
                self._backup_before_schema_migration(conn, "article_favorites")
                self._migrate_article_favorites_asset_scope_schema(c)
            c.execute('''CREATE TABLE IF NOT EXISTS article_alert_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER NOT NULL,
                article_id TEXT NOT NULL,
                complex_id TEXT NOT NULL,
                asset_type TEXT DEFAULT 'ALL',
                notified_on DATE DEFAULT CURRENT_DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(alert_id, article_id, complex_id, asset_type, notified_on)
            )''')
            if self._article_alert_log_requires_migration(c):
                self._backup_before_schema_migration(conn, "article_alert_log")
            self._migrate_article_alert_log_asset_type_schema(c)
            self._ensure_schema_indexes(c)
            self._cleanup_schema_data(conn, c)

            conn.commit()
            logger.info("Database tables initialized")
        except Exception as e:
            logger.exception(f"Database table initialization failed: {e}")
        finally:
            self._pool.return_connection(conn)
