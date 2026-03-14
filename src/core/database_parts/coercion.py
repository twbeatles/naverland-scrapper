from __future__ import annotations

from typing import Any, TYPE_CHECKING
import re

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


class ComplexDatabaseCoercionMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...
    _NUMERIC_RE = re.compile(r"-?\d+(?:\.\d+)?")

    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        logger.info(f"ComplexDatabase initialized: {self.db_path}")
        self._pool = ConnectionPool(self.db_path)
        self._write_lock = Lock()
        self._write_disabled_reason = ""
        self._init_tables()

    @staticmethod
    def _sqlite_error_text(exc) -> str:
        try:
            return str(exc).lower()
        except Exception:
            return ""

    @classmethod
    def _is_locked_sqlite_error(cls, exc) -> bool:
        text = cls._sqlite_error_text(exc)
        return (
            "database is locked" in text
            or "database table is locked" in text
            or "database schema is locked" in text
        )

    @classmethod
    def _is_corruption_sqlite_error(cls, exc) -> bool:
        text = cls._sqlite_error_text(exc)
        return (
            "database disk image is malformed" in text
            or "malformed database schema" in text
            or "file is not a database" in text
        )

    def is_write_disabled(self) -> bool:
        return bool(self._write_disabled_reason)

    def get_write_disabled_reason(self) -> str:
        return str(self._write_disabled_reason or "")

    def _disable_writes(self, reason: str, exc=None):
        if self._write_disabled_reason:
            return
        self._write_disabled_reason = str(reason or "unknown")
        if exc is not None:
            logger.critical(
                f"DB writes disabled: {self._write_disabled_reason} ({exc})"
            )
        else:
            logger.critical(f"DB writes disabled: {self._write_disabled_reason}")

    def _log_corruption_detected(self, context: str, exc):
        if self._is_corruption_sqlite_error(exc):
            self._disable_writes("database_corruption", exc)
            logger.critical(
                f"DB corruption detected ({context}). Recover from backup or recreate the database."
            )

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

    def _fetchall_safe(self, conn, query: str, params=(), context: str = ""):
        try:
            return conn.cursor().execute(query, params).fetchall()
        except Exception as e:
            self._log_corruption_detected(context or "read", e)
            if context:
                logger.error(f"{context} query failed: {e}")
            else:
                logger.error(f"DB query failed: {e}")
            return []

    @classmethod
    def _coerce_float(cls, value, default: float | None = 0.0):
        if value is None:
            return default
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(",", "")
        if not text:
            return default
        text = text.strip()
        match = cls._NUMERIC_RE.search(text)
        if not match:
            return default
        try:
            return float(match.group(0))
        except (TypeError, ValueError):
            return default

    @classmethod
    def _coerce_int(cls, value, default=0):
        if value is None:
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        text = str(value).strip().replace(",", "")
        if not text:
            return default
        match = cls._NUMERIC_RE.search(text)
        if not match:
            return default
        try:
            return int(float(match.group(0)))
        except (TypeError, ValueError):
            return default

    @classmethod
    def _coerce_price(cls, value, default=0):
        if value is None:
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        text = str(value).strip().replace(",", "")
        if not text:
            return default
        parsed = PriceConverter.to_int(text)
        if parsed > 0:
            return parsed
        if text in {"0", "0.0"}:
            return 0
        return cls._coerce_int(text, default=default)
    @staticmethod
    def _is_all_filter_value(value) -> bool:
        token = str(value or "").strip().lower()
        return token in {"", "all", "전체"}

    @staticmethod
    def _row_value(row, key, index, default=None):
        if row is None:
            return default
        try:
            return row[key]
        except Exception:
            pass
        try:
            return row[index]
        except Exception:
            return default

    def _normalize_snapshot_row(self, row):
        snapshot_date = str(self._row_value(row, "snapshot_date", 0, "") or "")
        trade_type = str(self._row_value(row, "trade_type", 1, "") or "")
        pyeong = self._coerce_float(self._row_value(row, "pyeong", 2, None), default=None)
        if pyeong is None:
            return None
        min_price = self._coerce_price(self._row_value(row, "min_price", 3, 0), default=0)
        max_price = self._coerce_price(self._row_value(row, "max_price", 4, 0), default=0)
        avg_price = self._coerce_price(self._row_value(row, "avg_price", 5, 0), default=0)
        item_count = max(0, self._coerce_int(self._row_value(row, "item_count", 6, 0), default=0))
        return (snapshot_date, trade_type, pyeong, min_price, max_price, avg_price, item_count)
    
