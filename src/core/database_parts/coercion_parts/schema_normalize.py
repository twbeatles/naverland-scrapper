from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403
    from src.core.database_parts.pool import ConnectionPool


class ComplexDatabaseSchemaNormalizeMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...
    @staticmethod
    def _column_names(cursor, table_name: str) -> set[str]:
        try:
            rows = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
        except Exception:
            return set()
        names = set()
        for row in rows:
            try:
                names.add(str(row[1]))
            except Exception:
                try:
                    names.add(str(row["name"]))
                except Exception:
                    continue
        return names

    @classmethod
    def _ensure_column(cls, cursor, table_name: str, column_name: str, ddl: str):
        if column_name in cls._column_names(cursor, table_name):
            return
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")

    @staticmethod
    def _normalize_asset_type(asset_type) -> str:
        token = str(asset_type or "APT").strip().upper()
        return token or "APT"

    @staticmethod
    def _normalize_price_metric(price_metric, trade_type=None, default: str = "price") -> str:
        token = str(price_metric or "").strip().lower()
        if token in {"price", "deposit", "rent"}:
            return token
        if str(trade_type or "").strip() == "월세":
            return "deposit"
        fallback = str(default or "").strip().lower()
        if fallback in {"price", "deposit", "rent"}:
            return fallback
        return "price"

    @staticmethod
    def _normalize_alert_asset_scope(asset_type, default: str = "ALL") -> str:
        token = str(asset_type or "").strip().upper()
        if token in {"APT", "VL", "ALL"}:
            return token
        fallback = str(default or "").strip().upper()
        if fallback in {"APT", "VL", "ALL"}:
            return fallback
        return ""

    @classmethod
    def _complexes_table_requires_migration(cls, cursor) -> bool:
        columns = cls._column_names(cursor, "complexes")
        if not columns:
            return False
        if "asset_type" not in columns:
            return True

        # Legacy schema had UNIQUE(complex_id). Keep migrating until composite unique is present.
        try:
            indexes = cursor.execute("PRAGMA index_list(complexes)").fetchall()
        except Exception:
            return True

        has_composite_unique = False
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
            if normalized == ("asset_type", "complex_id"):
                has_composite_unique = True
            if normalized == ("complex_id",):
                has_legacy_unique = True
        return (not has_composite_unique) or has_legacy_unique

    @classmethod
    def _migrate_complexes_asset_type_schema(cls, cursor):
        if not cls._complexes_table_requires_migration(cursor):
            return

        logger.info("complexes schema migration start: add asset_type + composite unique")
        cursor.execute("PRAGMA foreign_keys=OFF")
        try:
            table_names = {
                str(row[0])
                for row in cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            group_rows: list[tuple[int, int]] = []
            if "group_complexes" in table_names:
                try:
                    group_rows = [
                        (int(row[0]), int(row[1]))
                        for row in cursor.execute(
                            "SELECT group_id, complex_id FROM group_complexes"
                        ).fetchall()
                    ]
                except Exception:
                    group_rows = []
                cursor.execute("DROP TABLE IF EXISTS group_complexes")

            cursor.execute("ALTER TABLE complexes RENAME TO complexes_legacy")
            cursor.execute(
                """
                CREATE TABLE complexes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    asset_type TEXT NOT NULL DEFAULT 'APT',
                    complex_id TEXT NOT NULL,
                    memo TEXT DEFAULT "",
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(asset_type, complex_id)
                )
                """
            )
            legacy_columns = cls._column_names(cursor, "complexes_legacy")
            memo_expr = "COALESCE(memo, '')" if "memo" in legacy_columns else "''"
            created_at_expr = (
                "COALESCE(created_at, CURRENT_TIMESTAMP)"
                if "created_at" in legacy_columns
                else "CURRENT_TIMESTAMP"
            )
            if "asset_type" in legacy_columns:
                cursor.execute(
                    f"""
                    INSERT INTO complexes (id, name, asset_type, complex_id, memo, created_at)
                    SELECT
                        id,
                        name,
                        CASE
                            WHEN TRIM(COALESCE(asset_type, '')) = '' THEN 'APT'
                            ELSE UPPER(TRIM(asset_type))
                        END AS asset_type,
                        complex_id,
                        {memo_expr},
                        {created_at_expr}
                    FROM complexes_legacy
                    """
                )
            else:
                cursor.execute(
                    f"""
                    INSERT INTO complexes (id, name, asset_type, complex_id, memo, created_at)
                    SELECT
                        id,
                        name,
                        'APT',
                        complex_id,
                        {memo_expr},
                        {created_at_expr}
                    FROM complexes_legacy
                    """
                )
            cursor.execute("DROP TABLE complexes_legacy")

            if "groups" in table_names:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS group_complexes (
                        group_id INTEGER,
                        complex_id INTEGER,
                        PRIMARY KEY (group_id, complex_id),
                        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
                        FOREIGN KEY (complex_id) REFERENCES complexes(id) ON DELETE CASCADE
                    )
                    """
                )
                if group_rows:
                    cursor.executemany(
                        "INSERT OR IGNORE INTO group_complexes (group_id, complex_id) VALUES (?, ?)",
                        group_rows,
                    )
        finally:
            cursor.execute("PRAGMA foreign_keys=ON")
        logger.info("complexes schema migration complete")

    @staticmethod
    def _sqlite_table_names(cursor) -> set[str]:
        try:
            return {
                str(row[0])
                for row in cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        except Exception:
            return set()

    @classmethod
    def _ensure_group_complexes_fk_integrity(cls, cursor):
        table_names = cls._sqlite_table_names(cursor)
        if "group_complexes" not in table_names:
            return
        try:
            fk_rows = cursor.execute("PRAGMA foreign_key_list(group_complexes)").fetchall()
        except Exception:
            fk_rows = []
        fk_targets = set()
        for row in fk_rows:
            try:
                fk_targets.add(str(row[2]))
            except Exception:
                try:
                    fk_targets.add(str(row["table"]))
                except Exception:
                    continue
        # Expected references: groups + complexes
        if fk_targets == {"groups", "complexes"}:
            return

        try:
            legacy_rows = [
                (int(row[0]), int(row[1]))
                for row in cursor.execute(
                    "SELECT group_id, complex_id FROM group_complexes"
                ).fetchall()
            ]
        except Exception:
            legacy_rows = []

        cursor.execute("PRAGMA foreign_keys=OFF")
        try:
            cursor.execute("DROP TABLE IF EXISTS group_complexes")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS group_complexes (
                    group_id INTEGER,
                    complex_id INTEGER,
                    PRIMARY KEY (group_id, complex_id),
                    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
                    FOREIGN KEY (complex_id) REFERENCES complexes(id) ON DELETE CASCADE
                )
                """
            )
            if legacy_rows:
                cursor.executemany(
                    "INSERT OR IGNORE INTO group_complexes (group_id, complex_id) VALUES (?, ?)",
                    legacy_rows,
                )
        finally:
            cursor.execute("PRAGMA foreign_keys=ON")
