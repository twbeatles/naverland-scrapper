from __future__ import annotations

from typing import Any, TYPE_CHECKING

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


logger = get_logger("DB")


class ComplexDatabaseSchemaMixin:
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
            # Alert log table
            c.execute('DROP INDEX IF EXISTS idx_article_complex')
            c.execute('CREATE INDEX IF NOT EXISTS idx_article_complex ON article_history(asset_type, complex_id)')
            c.execute('DROP INDEX IF EXISTS idx_article_id')
            c.execute('CREATE INDEX IF NOT EXISTS idx_article_id ON article_history(asset_type, article_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_crawl_history_crawled_at ON crawl_history(crawled_at DESC)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_price_snapshots_lookup ON price_snapshots(complex_id, trade_type, snapshot_date DESC)')
            
            # additive migrations
            migration_columns = {
                "article_history": {
                    "status": "TEXT DEFAULT 'active'",
                    "asset_type": "TEXT DEFAULT 'APT'",
                    "source_mode": "TEXT DEFAULT 'complex'",
                    "source_lat": "REAL DEFAULT 0",
                    "source_lon": "REAL DEFAULT 0",
                    "source_zoom": "INTEGER DEFAULT 0",
                    "marker_id": "TEXT DEFAULT ''",
                    "broker_office": "TEXT DEFAULT ''",
                    "broker_name": "TEXT DEFAULT ''",
                    "broker_phone1": "TEXT DEFAULT ''",
                    "broker_phone2": "TEXT DEFAULT ''",
                    "prev_jeonse_won": "INTEGER DEFAULT 0",
                    "jeonse_period_years": "INTEGER DEFAULT 0",
                    "jeonse_max_won": "INTEGER DEFAULT 0",
                    "jeonse_min_won": "INTEGER DEFAULT 0",
                    "gap_amount_won": "INTEGER DEFAULT 0",
                    "gap_ratio": "REAL DEFAULT 0",
                },
                "crawl_history": {
                    "engine": "TEXT DEFAULT ''",
                    "mode": "TEXT DEFAULT 'complex'",
                    "source_lat": "REAL DEFAULT 0",
                    "source_lon": "REAL DEFAULT 0",
                    "source_zoom": "INTEGER DEFAULT 0",
                    "asset_type": "TEXT DEFAULT ''",
                    "run_status": "TEXT DEFAULT 'success'",
                },
                "price_snapshots": {
                    "asset_type": "TEXT DEFAULT 'APT'",
                },
                "alert_settings": {
                    "asset_type": "TEXT DEFAULT 'ALL'",
                },
            }
            for table_name, columns in migration_columns.items():
                for column_name, ddl in columns.items():
                    try:
                        self._ensure_column(c, table_name, column_name, ddl)
                    except Exception as me:
                        logger.warning(f"{table_name}.{column_name} column migration failed (ignored): {me}")
            try:
                c.execute(
                    "CREATE INDEX IF NOT EXISTS idx_price_snapshots_asset_lookup "
                    "ON price_snapshots(asset_type, complex_id, trade_type, snapshot_date DESC)"
                )
            except Exception as me:
                logger.warning(f"price_snapshots asset lookup index migration failed (ignored): {me}")
            
            # status column backfill (best effort; do not block startup)
            try:
                c.execute('CREATE INDEX IF NOT EXISTS idx_article_status ON article_history(status)')
            except Exception:
                logger.debug("status column backfill failed (ignored)")
            c.execute('CREATE INDEX IF NOT EXISTS idx_article_status_last_seen ON article_history(status, last_seen)')
            
            c.execute('DROP INDEX IF EXISTS idx_favorites')
            c.execute('CREATE INDEX IF NOT EXISTS idx_favorites ON article_favorites(asset_type, article_id, complex_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_favorites_updated_at ON article_favorites(updated_at DESC)')
            c.execute('DROP INDEX IF EXISTS idx_alert_lookup')
            c.execute(
                'CREATE INDEX IF NOT EXISTS idx_alert_lookup '
                'ON alert_settings(complex_id, trade_type, asset_type, enabled)'
            )
            c.execute('DROP INDEX IF EXISTS idx_alert_log_lookup')
            c.execute(
                'CREATE INDEX IF NOT EXISTS idx_alert_log_lookup '
                'ON article_alert_log(alert_id, article_id, complex_id, asset_type, notified_on)'
            )

            # v14.x: normalize legacy price_snapshots string values (for example, "34?", "1?2,000?")
            try:
                c.execute(
                    """
                    UPDATE price_snapshots
                    SET asset_type = 'APT'
                    WHERE TRIM(COALESCE(asset_type, '')) = ''
                    """
                )
                legacy_rows = c.execute(
                    """
                    SELECT id, pyeong, min_price, max_price, avg_price, item_count
                    FROM price_snapshots
                    WHERE typeof(pyeong)='text'
                       OR typeof(min_price)='text'
                       OR typeof(max_price)='text'
                       OR typeof(avg_price)='text'
                       OR typeof(item_count)='text'
                    """
                ).fetchall()
                updates = []
                for row in legacy_rows:
                    pyeong = self._coerce_float(row["pyeong"], default=None)
                    if pyeong is None:
                        continue
                    updates.append(
                        (
                            pyeong,
                            self._coerce_price(row["min_price"], default=0),
                            self._coerce_price(row["max_price"], default=0),
                            self._coerce_price(row["avg_price"], default=0),
                            max(0, self._coerce_int(row["item_count"], default=0)),
                            row["id"],
                        )
                    )
                if updates:
                    c.executemany(
                        """
                        UPDATE price_snapshots
                        SET pyeong = ?, min_price = ?, max_price = ?, avg_price = ?, item_count = ?
                        WHERE id = ?
                        """,
                        updates,
                    )
                    logger.info(f"migration complete: normalized price_snapshots rows={len(updates)}")
            except Exception as me:
                logger.warning(f"price_snapshots cleanup failed (ignored): {me}")

            try:
                c.execute(
                    """
                    UPDATE article_history
                    SET asset_type = 'APT'
                    WHERE TRIM(COALESCE(asset_type, '')) = ''
                    """
                )
                c.execute(
                    """
                    UPDATE article_favorites
                    SET asset_type = 'APT'
                    WHERE TRIM(COALESCE(asset_type, '')) = ''
                    """
                )
                c.execute(
                    """
                    UPDATE alert_settings
                    SET asset_type = 'ALL'
                    WHERE TRIM(COALESCE(asset_type, '')) = ''
                    """
                )
                c.execute(
                    """
                    UPDATE article_alert_log
                    SET asset_type = 'ALL'
                    WHERE TRIM(COALESCE(asset_type, '')) = ''
                    """
                )
            except Exception as me:
                logger.warning(f"asset scope cleanup failed (ignored): {me}")

            # Remove orphan rows from group_complexes when FK constraints were missing in old schemas
            c.execute(
                """
                DELETE FROM group_complexes
                WHERE complex_id NOT IN (SELECT id FROM complexes)
                   OR group_id NOT IN (SELECT id FROM groups)
                """
            )

            conn.commit()
            logger.info("Database tables initialized")
        except Exception as e:
            logger.exception(f"Database table initialization failed: {e}")
        finally:
            self._pool.return_connection(conn)
    
