from __future__ import annotations

from typing import Any, TYPE_CHECKING

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


logger = get_logger("DB")


class ComplexDatabaseSchemaCleanupMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    def _cleanup_schema_data(self, conn, c):
        # v14.x: normalize legacy price_snapshots string values (for example, "34평", "1억2,000만")
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
            c.execute(
                """
                UPDATE price_snapshots
                SET price_metric = CASE
                    WHEN trade_type = '월세' THEN 'deposit'
                    WHEN TRIM(COALESCE(price_metric, '')) = '' THEN 'price'
                    ELSE LOWER(TRIM(price_metric))
                END
                WHERE TRIM(COALESCE(price_metric, '')) = ''
                   OR LOWER(TRIM(COALESCE(price_metric, ''))) NOT IN ('price', 'deposit', 'rent')
                   OR (trade_type = '월세' AND LOWER(TRIM(COALESCE(price_metric, ''))) = 'price')
                """
            )
            c.execute(
                """
                UPDATE price_snapshots
                SET legacy_monthly = CASE
                    WHEN trade_type = '월세'
                     AND LOWER(TRIM(COALESCE(price_metric, 'price'))) = 'deposit'
                     AND NOT EXISTS (
                         SELECT 1
                         FROM price_snapshots paired
                         WHERE paired.complex_id = price_snapshots.complex_id
                           AND paired.trade_type = price_snapshots.trade_type
                           AND COALESCE(paired.asset_type, 'APT') = COALESCE(price_snapshots.asset_type, 'APT')
                           AND COALESCE(paired.snapshot_date, '') = COALESCE(price_snapshots.snapshot_date, '')
                           AND (
                               (paired.pyeong IS NULL AND price_snapshots.pyeong IS NULL)
                               OR paired.pyeong = price_snapshots.pyeong
                           )
                           AND LOWER(TRIM(COALESCE(paired.price_metric, 'price'))) = 'rent'
                     ) THEN 1
                    ELSE 0
                END
                WHERE trade_type = '월세'
                """
            )
            c.execute(
                """
                UPDATE price_snapshots
                SET snapshot_date = CURRENT_DATE
                WHERE TRIM(COALESCE(snapshot_date, '')) = ''
                """
            )
            c.execute(
                """
                UPDATE price_snapshots
                SET asset_type = 'APT'
                WHERE TRIM(COALESCE(asset_type, '')) = ''
                """
            )
            c.execute(
                """
                UPDATE price_snapshots
                SET price_metric = 'price'
                WHERE TRIM(COALESCE(price_metric, '')) = ''
                """
            )
            c.execute("UPDATE price_snapshots SET legacy_monthly = 0 WHERE legacy_monthly IS NULL")
            c.execute("UPDATE price_snapshots SET complex_id = '' WHERE complex_id IS NULL")
            c.execute("UPDATE price_snapshots SET trade_type = '' WHERE trade_type IS NULL")
            c.execute("UPDATE price_snapshots SET pyeong = 0 WHERE pyeong IS NULL")
            duplicate_count = c.execute(
                """
                SELECT COUNT(*)
                FROM price_snapshots
                WHERE id NOT IN (
                    SELECT MAX(id)
                    FROM price_snapshots
                    GROUP BY
                        snapshot_date,
                        asset_type,
                        complex_id,
                        trade_type,
                        pyeong,
                        price_metric,
                        legacy_monthly
                )
                """
            ).fetchone()[0]
            if int(duplicate_count or 0) > 0:
                conn.commit()
                self._backup_before_schema_migration(conn, "price_snapshots_unique")
                c.execute(
                    """
                    DELETE FROM price_snapshots
                    WHERE id NOT IN (
                        SELECT MAX(id)
                        FROM price_snapshots
                        GROUP BY
                            snapshot_date,
                            asset_type,
                            complex_id,
                            trade_type,
                            pyeong,
                            price_metric,
                            legacy_monthly
                    )
                    """
                )
                logger.info(f"migration complete: deduped price_snapshots rows={int(duplicate_count or 0)}")
            c.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_price_snapshots_daily_unique
                ON price_snapshots(
                    snapshot_date,
                    asset_type,
                    complex_id,
                    trade_type,
                    pyeong,
                    price_metric,
                    legacy_monthly
                )
                """
            )
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
