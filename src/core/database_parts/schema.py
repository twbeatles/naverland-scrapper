from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


class ComplexDatabaseSchemaMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

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
                snapshot_date DATE DEFAULT CURRENT_DATE
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS alert_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                complex_id TEXT,
                complex_name TEXT,
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
                asset_type TEXT DEFAULT '',
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
                UNIQUE(article_id, complex_id)
            )''')
            # v12.0: cache table for query-level response reuse
            c.execute('''CREATE TABLE IF NOT EXISTS article_favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id TEXT NOT NULL,
                complex_id TEXT NOT NULL,
                is_favorite INTEGER DEFAULT 1,
                note TEXT DEFAULT "",
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(article_id, complex_id)
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS article_alert_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER NOT NULL,
                article_id TEXT NOT NULL,
                complex_id TEXT NOT NULL,
                notified_on DATE DEFAULT CURRENT_DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(alert_id, article_id, complex_id, notified_on)
            )''')
            # Alert log table
            c.execute('CREATE INDEX IF NOT EXISTS idx_article_complex ON article_history(complex_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_article_id ON article_history(article_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_crawl_history_crawled_at ON crawl_history(crawled_at DESC)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_price_snapshots_lookup ON price_snapshots(complex_id, trade_type, snapshot_date DESC)')
            
            # additive migrations
            migration_columns = {
                "article_history": {
                    "status": "TEXT DEFAULT 'active'",
                    "asset_type": "TEXT DEFAULT ''",
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
                },
            }
            for table_name, columns in migration_columns.items():
                for column_name, ddl in columns.items():
                    try:
                        self._ensure_column(c, table_name, column_name, ddl)
                    except Exception as me:
                        logger.warning(f"{table_name}.{column_name} column migration failed (ignored): {me}")
            
            # status column backfill (best effort; do not block startup)
            try:
                c.execute('CREATE INDEX IF NOT EXISTS idx_article_status ON article_history(status)')
            except Exception:
                logger.debug("status column backfill failed (ignored)")
            c.execute('CREATE INDEX IF NOT EXISTS idx_article_status_last_seen ON article_history(status, last_seen)')
            
            c.execute('CREATE INDEX IF NOT EXISTS idx_favorites ON article_favorites(article_id, complex_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_favorites_updated_at ON article_favorites(updated_at DESC)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_alert_lookup ON alert_settings(complex_id, trade_type, enabled)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_alert_log_lookup ON article_alert_log(alert_id, article_id, complex_id, notified_on)')

            # v14.x: normalize legacy price_snapshots string values (for example, "34?", "1?2,000?")
            try:
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
    
