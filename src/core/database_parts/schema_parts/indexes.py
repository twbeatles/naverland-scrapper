from __future__ import annotations

from typing import Any, TYPE_CHECKING

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


logger = get_logger("DB")


class ComplexDatabaseSchemaIndexMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    def _ensure_schema_indexes(self, c):
        # Alert log table
        c.execute('DROP INDEX IF EXISTS idx_article_complex')
        c.execute('CREATE INDEX IF NOT EXISTS idx_article_complex ON article_history(asset_type, complex_id)')
        c.execute('DROP INDEX IF EXISTS idx_article_id')
        c.execute('CREATE INDEX IF NOT EXISTS idx_article_id ON article_history(asset_type, article_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_crawl_history_crawled_at ON crawl_history(crawled_at DESC)')
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_crawl_history_stats_lookup "
            "ON crawl_history(asset_type, complex_id, crawled_at DESC)"
        )
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
                "price_metric": "TEXT DEFAULT 'price'",
                "legacy_monthly": "INTEGER DEFAULT 0",
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
            c.execute("DROP INDEX IF EXISTS idx_price_snapshots_lookup")
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_price_snapshots_lookup "
                "ON price_snapshots(complex_id, trade_type, price_metric, snapshot_date DESC)"
            )
            c.execute("DROP INDEX IF EXISTS idx_price_snapshots_asset_lookup")
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_price_snapshots_asset_lookup "
                "ON price_snapshots(asset_type, complex_id, trade_type, price_metric, snapshot_date DESC)"
            )
            c.execute("DROP INDEX IF EXISTS idx_price_snapshots_stats_pyeong")
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_price_snapshots_stats_pyeong "
                "ON price_snapshots(asset_type, complex_id, trade_type, price_metric, pyeong, snapshot_date DESC)"
            )
        except Exception as me:
            logger.warning(f"price_snapshots asset lookup index migration failed (ignored): {me}")
        
        # status column backfill (best effort; do not block startup)
        try:
            c.execute('CREATE INDEX IF NOT EXISTS idx_article_status ON article_history(status)')
        except Exception:
            logger.debug("status column backfill failed (ignored)")
        c.execute('CREATE INDEX IF NOT EXISTS idx_article_status_last_seen ON article_history(status, last_seen)')
        c.execute(
            'CREATE INDEX IF NOT EXISTS idx_article_disappeared_scope '
            'ON article_history(status, asset_type, complex_id, trade_type, last_seen)'
        )
        
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
