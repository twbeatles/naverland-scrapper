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

class ConnectionPool:
    def __init__(self, db_path, pool_size=5):
        self.db_path = Path(db_path)
        self.pool_size = pool_size
        self._pool = Queue(maxsize=pool_size)
        self._lease_lock = Lock()
        self._lease_cond = Condition(self._lease_lock)
        self._leased_ids = set()
        self._all_connections = {}
        self._closing = False
        logger.info(f"ConnectionPool 珥덇린?? {self.db_path}")
        self._initialize_pool()
    
    def _initialize_pool(self):
        for i in range(self.pool_size):
            try:
                conn = self._create_connection()
                with self._lease_lock:
                    self._all_connections[id(conn)] = conn
                self._pool.put(conn)
            except Exception as e:
                logger.error(f"?곌껐 ?앹꽦 ?ㅽ뙣 ({i+1}/{self.pool_size}): {e}")
    
    def _create_connection(self):
        # 遺紐??붾젆?좊━ ?뺤씤/?앹꽦
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_connection(self):
        with self._lease_lock:
            if self._closing:
                raise RuntimeError("ConnectionPool is closing; ?좉퇋 ?곌껐 ???遺덇?")
        try:
            conn = self._pool.get(timeout=10)
        except Exception as e:
            with self._lease_lock:
                if self._closing:
                    raise RuntimeError("ConnectionPool is closing; ?좉퇋 ?곌껐 ???遺덇?")
            logger.warning(f"??먯꽌 ?곌껐 媛?몄삤湲??ㅽ뙣, ???곌껐 ?앹꽦: {e}")
            conn = self._create_connection()
            with self._lease_lock:
                if self._closing:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    raise RuntimeError("ConnectionPool is closing; ?좉퇋 ?곌껐 ???遺덇?")
                self._all_connections[id(conn)] = conn
        with self._lease_lock:
            if self._closing:
                try:
                    conn.close()
                except Exception:
                    pass
                self._all_connections.pop(id(conn), None)
                raise RuntimeError("ConnectionPool is closing; ?좉퇋 ?곌껐 ???遺덇?")
            self._leased_ids.add(id(conn))
        return conn
    
    def return_connection(self, conn):
        if conn is None:
            return
        conn_id = id(conn)
        with self._lease_cond:
            self._leased_ids.discard(conn_id)
            closing = self._closing
            self._lease_cond.notify_all()
        if closing:
            try:
                conn.close()
            except Exception as e:
                logger.debug(f"?곌껐 醫낅즺 以??ㅻ쪟: {e}")
            with self._lease_lock:
                self._all_connections.pop(conn_id, None)
            return
        try:
            self._pool.put_nowait(conn)
        except Full:
            try:
                conn.close()
            except Exception as e:
                logger.debug(f"?곌껐 醫낅즺 以??ㅻ쪟: {e}")
            with self._lease_lock:
                self._all_connections.pop(conn_id, None)
    
    def close_all(self, timeout_ms=8000):
        """紐⑤뱺 ?곌껐 ?덉쟾?섍쾶 醫낅즺"""
        logger.info("ConnectionPool 醫낅즺 ?쒖옉...")
        closed_count = 0
        error_count = 0

        try:
            wait_seconds = max(0.0, float(timeout_ms) / 1000.0)
        except (TypeError, ValueError):
            wait_seconds = 8.0
        deadline = time.monotonic() + wait_seconds

        with self._lease_cond:
            self._closing = True
            while self._leased_ids:
                remain = deadline - time.monotonic()
                if remain <= 0:
                    logger.warning(
                        f"ConnectionPool close timeout; still leased: {len(self._leased_ids)}"
                    )
                    break
                self._lease_cond.wait(timeout=remain)

            tracked = list(self._all_connections.values())
            self._all_connections.clear()
            self._leased_ids.clear()

        drained = []
        while True:
            try:
                drained.append(self._pool.get_nowait())
            except Empty:
                break

        seen_ids = set()
        for conn in tracked + drained:
            conn_id = id(conn)
            if conn_id in seen_ids:
                continue
            seen_ids.add(conn_id)
            try:
                conn.close()
                closed_count += 1
            except Exception as e:
                logger.warning(f"?곌껐 醫낅즺 ?ㅽ뙣: {e}")
                error_count += 1

        logger.info(f"ConnectionPool 醫낅즺 ?꾨즺: {closed_count}媛?醫낅즺, {error_count}媛??ㅻ쪟")

class ComplexDatabase:
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

    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        logger.info(f"ComplexDatabase 珥덇린?? {self.db_path}")
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
                f"DB write 鍮꾪솢?깊솕: {self._write_disabled_reason} ({exc})"
            )
        else:
            logger.critical(f"DB write 鍮꾪솢?깊솕: {self._write_disabled_reason}")

    def _log_corruption_detected(self, context: str, exc):
        if self._is_corruption_sqlite_error(exc):
            self._disable_writes("database_corruption", exc)
            logger.critical(
                f"DB ?먯긽 媛먯?({context}). ????DB 蹂듭썝 湲곕뒫?쇰줈 ?뺤긽 諛깆뾽蹂몄쓣 蹂듭썝?섏꽭??"
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
                logger.error(f"{context} ?ㅽ뙣: {e}")
            else:
                logger.error(f"DB 議고쉶 ?ㅽ뙣: {e}")
            return []

    @classmethod
    def _coerce_float(cls, value, default=0.0):
        if value is None:
            return default
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(",", "")
        if not text:
            return default
        text = text.replace("평", "").replace("㎡", "")
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
        if any(token in text for token in ("억", "만")):
            parsed = PriceConverter.to_int(text)
            if parsed > 0 or text in {"0", "0만", "0억"}:
                return parsed
        return cls._coerce_int(text, default=default)

    @staticmethod
    def _is_all_filter_value(value) -> bool:
        token = str(value or "").strip().lower()
        return token in {"", "all", "전체", "?꾩껜"}

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
            # v7.3 ?좉퇋: 留ㅻЪ ?덉뒪?좊━ (?좉퇋 留ㅻЪ/媛寃?蹂??異붿쟻)
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
            # v12.0 ?좉퇋: 留ㅻЪ 利먭꺼李얘린 諛?硫붾え
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
            # ?몃뜳??異붽?
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
                        logger.warning(f"{table_name}.{column_name} 留덉씠洹몃젅?댁뀡 ?ㅻ쪟 (臾댁떆): {me}")
            
            # status 而щ읆 ?몃뜳???앹꽦 (留덉씠洹몃젅?댁뀡 ??
            try:
                c.execute('CREATE INDEX IF NOT EXISTS idx_article_status ON article_history(status)')
            except Exception:
                logger.debug("status ?몃뜳???앹꽦 ?ㅽ뙣 (臾댁떆)")
            c.execute('CREATE INDEX IF NOT EXISTS idx_article_status_last_seen ON article_history(status, last_seen)')
            
            c.execute('CREATE INDEX IF NOT EXISTS idx_favorites ON article_favorites(article_id, complex_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_favorites_updated_at ON article_favorites(updated_at DESC)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_alert_lookup ON alert_settings(complex_id, trade_type, enabled)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_alert_log_lookup ON article_alert_log(alert_id, article_id, complex_id, notified_on)')

            # v14.x: legacy price_snapshots ?レ옄 臾몄옄???뺢퇋??(?? "34??, "1??2,000留?)
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
                logger.warning(f"price_snapshots ?뺢퇋???ㅽ뙣 (臾댁떆): {me}")

            # 湲곗〈 踰꾩쟾?먯꽌 ?⑥븘?덉쓣 ???덈뒗 group_complexes 怨좎븘 ?곗씠???뺣━
            c.execute(
                """
                DELETE FROM group_complexes
                WHERE complex_id NOT IN (SELECT id FROM complexes)
                   OR group_id NOT IN (SELECT id FROM groups)
                """
            )

            conn.commit()
            logger.info("?뚯씠釉?珥덇린???꾨즺")
        except Exception as e:
            logger.exception(f"?뚯씠釉?珥덇린???ㅽ뙣: {e}")
        finally:
            self._pool.return_connection(conn)
    
    def add_complex(
        self,
        name,
        complex_id,
        memo="",
        *,
        asset_type: str = "APT",
        return_status: bool = False,
    ):
        """?⑥? 異붽? - ?붾쾭源?媛뺥솕"""
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            # ?대? 議댁옱?섎뒗吏 ?뺤씤
            normalized_asset_type = self._normalize_asset_type(asset_type)
            c.execute(
                "SELECT id FROM complexes WHERE asset_type = ? AND complex_id = ?",
                (normalized_asset_type, complex_id),
            )
            existing = c.fetchone()
            if existing:
                logger.debug(f"?⑥? ?대? 議댁옱: {name} ({complex_id})")
                return "existing" if return_status else True  # ?대? 議댁옱?섎㈃ ?깃났?쇰줈 泥섎━
            
            c.execute(
                "INSERT INTO complexes (name, asset_type, complex_id, memo) VALUES (?, ?, ?, ?)",
                (name, normalized_asset_type, complex_id, memo),
            )
            conn.commit()
            logger.info(f"?⑥? 異붽? ?깃났: {name} ({complex_id})")
            return "inserted" if return_status else True
        except sqlite3.IntegrityError as e:
            logger.debug(f"?⑥? 以묐났 (?뺤긽): {name} ({complex_id})")
            return "existing" if return_status else True
        except Exception as e:
            logger.exception(f"?⑥? 異붽? ?ㅽ뙣: {name} ({complex_id}) - {e}")
            return "error" if return_status else False
        finally:
            self._pool.return_connection(conn)
    
    def get_all_complexes(self):
        """紐⑤뱺 ?⑥? 議고쉶 - ?붾쾭源?媛뺥솕"""
        conn = self._pool.get_connection()
        try:
            result = self._fetchall_safe(
                conn,
                "SELECT id, name, asset_type, complex_id, memo FROM complexes ORDER BY name, asset_type",
                context="?⑥? 議고쉶(complexes)",
            )
            logger.debug(f"complex list loaded: {len(result)}")
            return result
        except Exception as e:
            self._log_corruption_detected("?⑥? 議고쉶", e)
            logger.exception(f"?⑥? 議고쉶 ?ㅽ뙣: {e}")
            return []
        finally:
            self._pool.return_connection(conn)

    def get_complexes_for_stats(self):
        """?듦퀎 ??슜 ?⑥? 紐⑸줉 議고쉶 (DB + ?щ·留?湲곕줉 + ?ㅻ깄??"""
        conn = self._pool.get_connection()
        try:
            complex_map = {}

            # 1) ??λ맂 ?⑥? 紐⑸줉
            rows = self._fetchall_safe(
                conn,
                "SELECT name, complex_id FROM complexes ORDER BY name",
                context="?듦퀎 ?⑥? 議고쉶(complexes)",
            )
            for row in rows:
                cid = row["complex_id"]
                name = row["name"]
                if cid and name:
                    complex_map[cid] = name

            # 2) ?щ·留?湲곕줉(理쒖떊 ?대쫫 ?곗꽑)
            history_rows = self._fetchall_safe(
                conn,
                '''
                SELECT ch.complex_id, ch.complex_name
                FROM crawl_history ch
                JOIN (
                    SELECT complex_id, MAX(crawled_at) AS last_crawl
                    FROM crawl_history
                    GROUP BY complex_id
                ) latest
                ON ch.complex_id = latest.complex_id AND ch.crawled_at = latest.last_crawl
                ''',
                context="?듦퀎 ?⑥? 議고쉶(crawl_history)",
            )
            for row in history_rows:
                cid = row["complex_id"]
                name = row["complex_name"] or f"?⑥?_{cid}"
                if cid and cid not in complex_map:
                    complex_map[cid] = name

            # 3) ?ㅻ깄?룹뿉留?議댁옱?섎뒗 ?⑥? 蹂닿컯
            snapshot_rows = self._fetchall_safe(
                conn,
                "SELECT DISTINCT complex_id FROM price_snapshots",
                context="?듦퀎 ?⑥? 議고쉶(price_snapshots)",
            )
            for row in snapshot_rows:
                cid = row["complex_id"]
                if cid and cid not in complex_map:
                    complex_map[cid] = f"?⑥?_{cid}"

            result = [(name, cid) for cid, name in complex_map.items()]
            result.sort(key=lambda x: x[0])
            logger.debug(f"complex stats source rows: {len(result)}")
            return result
        except Exception as e:
            self._log_corruption_detected("?듦퀎 ?⑥? 議고쉶", e)
            logger.exception(f"?듦퀎 ?⑥? 議고쉶 ?ㅽ뙣: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
    
    @classmethod
    def _asset_scoped_predicate(cls, refs: list[tuple[str, str]], *, include_legacy_empty_for_apt: bool = True):
        clauses: list[str] = []
        params: list[str] = []
        for asset_type, complex_id in refs:
            asset_token = cls._normalize_asset_type(asset_type)
            cid = str(complex_id or "").strip()
            if not cid:
                continue
            if include_legacy_empty_for_apt and asset_token == "APT":
                clauses.append("(complex_id = ? AND (asset_type = ? OR COALESCE(asset_type, '') = ''))")
                params.extend([cid, "APT"])
            else:
                clauses.append("(complex_id = ? AND asset_type = ?)")
                params.extend([cid, asset_token])
        return clauses, params

    def _purge_related_for_complex_refs(self, cursor, refs: list[tuple[str, str]]):
        if not refs:
            return

        clauses, params = self._asset_scoped_predicate(refs)
        if clauses:
            where_asset = " OR ".join(clauses)
            cursor.execute(f"DELETE FROM article_history WHERE {where_asset}", params)
            cursor.execute(f"DELETE FROM crawl_history WHERE {where_asset}", params)

        unique_complex_ids = sorted({str(complex_id or "").strip() for _, complex_id in refs if str(complex_id or "").strip()})
        if not unique_complex_ids:
            return
        placeholders = ",".join("?" * len(unique_complex_ids))
        cursor.execute(f"DELETE FROM price_snapshots WHERE complex_id IN ({placeholders})", unique_complex_ids)
        cursor.execute(f"DELETE FROM alert_settings WHERE complex_id IN ({placeholders})", unique_complex_ids)
        cursor.execute(f"DELETE FROM article_favorites WHERE complex_id IN ({placeholders})", unique_complex_ids)
        cursor.execute(f"DELETE FROM article_alert_log WHERE complex_id IN ({placeholders})", unique_complex_ids)

    def _fetch_complex_refs_by_db_ids(self, cursor, db_ids: list[int]) -> list[tuple[str, str]]:
        if not db_ids:
            return []
        placeholders = ",".join("?" * len(db_ids))
        rows = cursor.execute(
            f"SELECT asset_type, complex_id FROM complexes WHERE id IN ({placeholders})",
            db_ids,
        ).fetchall()
        refs = []
        for row in rows:
            try:
                refs.append((str(row["asset_type"] or "APT"), str(row["complex_id"] or "")))
            except Exception:
                try:
                    refs.append((str(row[0] or "APT"), str(row[1] or "")))
                except Exception:
                    continue
        return refs

    def delete_complex(self, db_id, *, purge_related: bool = False):
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            refs = self._fetch_complex_refs_by_db_ids(c, [int(db_id)]) if purge_related else []
            c.execute("DELETE FROM group_complexes WHERE complex_id = ?", (db_id,))
            c.execute("DELETE FROM complexes WHERE id = ?", (db_id,))
            if purge_related:
                self._purge_related_for_complex_refs(c, refs)
            conn.commit()
            logger.info(f"?⑥? ??젣: ID={db_id}")
            return True
        except Exception as e:
            logger.error(f"?⑥? ??젣 ?ㅽ뙣: {e}")
            return False
        finally:
            self._pool.return_connection(conn)
    
    def delete_complexes_bulk(self, db_ids, *, purge_related: bool = False):
        conn = self._pool.get_connection()
        try:
            if not db_ids:
                return 0
            normalized_ids = [int(x) for x in db_ids]
            c = conn.cursor()
            refs = self._fetch_complex_refs_by_db_ids(c, normalized_ids) if purge_related else []
            placeholders = ",".join("?" * len(normalized_ids))
            c.execute(f"DELETE FROM group_complexes WHERE complex_id IN ({placeholders})", normalized_ids)
            c.execute(f"DELETE FROM complexes WHERE id IN ({placeholders})", normalized_ids)
            deleted_count = int(c.rowcount or 0)
            if purge_related:
                self._purge_related_for_complex_refs(c, refs)
            conn.commit()
            logger.info(f"bulk delete complexes: {deleted_count}, purge_related={bool(purge_related)}")
            return deleted_count
        except Exception as e:
            logger.error(f"?⑥? ?쇨큵 ??젣 ?ㅽ뙣: {e}")
            return 0
        finally:
            self._pool.return_connection(conn)
    
    def update_complex_memo(self, db_id, memo):
        conn = self._pool.get_connection()
        try:
            conn.cursor().execute("UPDATE complexes SET memo = ? WHERE id = ?", (memo, db_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"硫붾え ?낅뜲?댄듃 ?ㅽ뙣: {e}")
            return False
        finally:
            self._pool.return_connection(conn)
    
    def create_group(self, name, desc=""):
        conn = self._pool.get_connection()
        try:
            conn.cursor().execute("INSERT INTO groups (name, description) VALUES (?, ?)", (name, desc))
            conn.commit()
            logger.info(f"洹몃９ ?앹꽦: {name}")
            return True
        except Exception as e:
            logger.error(f"洹몃９ ?앹꽦 ?ㅽ뙣: {e}")
            return False
        finally:
            self._pool.return_connection(conn)
    
    def get_all_groups(self):
        conn = self._pool.get_connection()
        try:
            result = self._fetchall_safe(
                conn,
                "SELECT id, name, description FROM groups ORDER BY name",
                context="洹몃９ 議고쉶(groups)",
            )
            logger.debug(f"group list loaded: {len(result)}")
            return result
        except Exception as e:
            self._log_corruption_detected("洹몃９ 議고쉶", e)
            logger.error(f"洹몃９ 議고쉶 ?ㅽ뙣: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
    
    def delete_group(self, group_id):
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            c.execute("DELETE FROM group_complexes WHERE group_id = ?", (group_id,))
            c.execute("DELETE FROM groups WHERE id = ?", (group_id,))
            conn.commit()
            logger.info(f"洹몃９ ??젣: ID={group_id}")
            return True
        except Exception as e:
            logger.error(f"洹몃９ ??젣 ?ㅽ뙣: {e}")
            return False
        finally:
            self._pool.return_connection(conn)
    
    def add_complexes_to_group(self, group_id, complex_db_ids):
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            count = 0
            for cid in complex_db_ids:
                try:
                    c.execute("INSERT OR IGNORE INTO group_complexes (group_id, complex_id) VALUES (?, ?)", (group_id, cid))
                    count += c.rowcount
                except Exception as e:
                    logger.warning(f"洹몃９???⑥? 異붽? ?ㅽ뙣: {cid} - {e}")
            conn.commit()
            logger.info(f"group complexes added: {count}")
            return count
        except Exception as e:
            logger.error(f"洹몃９???⑥? 異붽? ?ㅽ뙣: {e}")
            return 0
        finally:
            self._pool.return_connection(conn)
    
    def remove_complex_from_group(self, group_id, complex_db_id):
        conn = self._pool.get_connection()
        try:
            conn.cursor().execute("DELETE FROM group_complexes WHERE group_id = ? AND complex_id = ?", (group_id, complex_db_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"洹몃９?먯꽌 ?⑥? ?쒓굅 ?ㅽ뙣: {e}")
            return False
        finally:
            self._pool.return_connection(conn)
    
    def get_complexes_in_group(self, group_id):
        conn = self._pool.get_connection()
        try:
            result = conn.cursor().execute(
                'SELECT c.id, c.name, c.asset_type, c.complex_id, c.memo FROM complexes c '
                'JOIN group_complexes gc ON c.id = gc.complex_id '
                'WHERE gc.group_id = ? ORDER BY c.name', (group_id,)
            ).fetchall()
            return result
        except Exception as e:
            logger.error(f"洹몃９ ???⑥? 議고쉶 ?ㅽ뙣: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
    
    def add_crawl_history(
        self,
        name,
        cid,
        types,
        count,
        *,
        engine="",
        mode="complex",
        source_lat=None,
        source_lon=None,
        source_zoom=None,
        asset_type="",
    ):
        if self.is_write_disabled():
            return False
        conn = self._pool.get_connection()
        try:
            with self._write_lock:
                try:
                    conn.execute("PRAGMA busy_timeout=1200")
                except Exception:
                    pass
                for attempt in range(3):
                    try:
                        conn.cursor().execute(
                            """
                            INSERT INTO crawl_history (
                                complex_name, complex_id, trade_types, item_count,
                                engine, mode, source_lat, source_lon, source_zoom, asset_type
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                name,
                                cid,
                                types,
                                count,
                                engine,
                                mode,
                                float(source_lat or 0),
                                float(source_lon or 0),
                                int(source_zoom or 0),
                                asset_type,
                            ),
                        )
                        conn.commit()
                        return True
                    except sqlite3.OperationalError as e:
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        if self._is_locked_sqlite_error(e) and attempt < 2:
                            time.sleep(0.1 * (attempt + 1))
                            continue
                        if self._is_corruption_sqlite_error(e):
                            self._disable_writes("database_corruption", e)
                        logger.error(f"?щ·留?湲곕줉 ????ㅽ뙣: {e}")
                        return False
                    except sqlite3.DatabaseError as e:
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        if self._is_corruption_sqlite_error(e):
                            self._disable_writes("database_corruption", e)
                        logger.error(f"?щ·留?湲곕줉 ????ㅽ뙣: {e}")
                        return False
        except Exception as e:
            logger.error(f"?щ·留?湲곕줉 ????ㅽ뙣: {e}")
            return False
        finally:
            try:
                conn.execute("PRAGMA busy_timeout=30000")
            except Exception:
                pass
            self._pool.return_connection(conn)
    
    def get_crawl_history(self, limit=100):
        conn = self._pool.get_connection()
        try:
            result = self._fetchall_safe(
                conn,
                'SELECT complex_name, complex_id, trade_types, item_count, crawled_at '
                'FROM crawl_history ORDER BY crawled_at DESC LIMIT ?',
                params=(limit,),
                context="?щ·留?湲곕줉 議고쉶(crawl_history)",
            )
            return result
        except Exception as e:
            self._log_corruption_detected("?щ·留?湲곕줉 議고쉶", e)
            logger.error(f"?щ·留?湲곕줉 議고쉶 ?ㅽ뙣: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
    
    def get_complex_price_history(self, complex_id, trade_type=None, pyeong=None):
        conn = self._pool.get_connection()
        try:
            sql = '''
                SELECT snapshot_date, trade_type, pyeong, min_price, max_price, avg_price, item_count
                FROM price_snapshots
                WHERE complex_id = ?
            '''
            params = [complex_id]

            if not self._is_all_filter_value(trade_type):
                sql += ' AND trade_type = ?'
                params.append(trade_type)

            sql += ' ORDER BY snapshot_date DESC, pyeong'

            raw_rows = self._fetchall_safe(
                conn,
                sql,
                params=params,
                context="媛寃??덉뒪?좊━ 議고쉶(price_snapshots)",
            )
            pyeong_filter = None
            if not self._is_all_filter_value(pyeong):
                pyeong_filter = self._coerce_float(pyeong, default=None)
                if pyeong_filter is None:
                    logger.debug(f"?됲삎 媛??뚯떛 ?ㅽ뙣: {pyeong}")

            result = []
            skipped = 0
            for row in raw_rows:
                normalized = self._normalize_snapshot_row(row)
                if normalized is None:
                    skipped += 1
                    continue
                snapshot_date, row_trade_type, row_pyeong, min_price, max_price, avg_price, _item_count = normalized
                if pyeong_filter is not None and abs(row_pyeong - pyeong_filter) > 1e-6:
                    continue
                result.append(
                    (
                        snapshot_date,
                        row_trade_type,
                        row_pyeong,
                        min_price,
                        max_price,
                        avg_price,
                    )
                )

            if skipped:
                logger.debug(f"price history skipped malformed rows: {skipped}")
            logger.debug(f"媛寃??덉뒪?좊━ 議고쉶: {len(result)}媛?(議곌굔: {trade_type}, {pyeong})")
            return result
        except Exception as e:
            self._log_corruption_detected("媛寃??덉뒪?좊━ 議고쉶", e)
            logger.error(f"媛寃??덉뒪?좊━ 議고쉶 ?ㅽ뙣: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
    
    def add_price_snapshot(self, complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count):
        """Store one price snapshot row."""
        conn = self._pool.get_connection()
        try:
            conn.cursor().execute(
                'INSERT INTO price_snapshots (complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                (complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count)
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"媛寃??ㅻ깄??????ㅽ뙣: {e}")
            return False
        finally:
            self._pool.return_connection(conn)

    def add_price_snapshots_bulk(self, rows):
        """Store price snapshots in bulk."""
        if not rows:
            return 0
        conn = self._pool.get_connection()
        try:
            conn.cursor().executemany(
                '''
                INSERT INTO price_snapshots (
                    complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                rows
            )
            conn.commit()
            return len(rows)
        except Exception as e:
            logger.error(f"媛寃??ㅻ깄???쇨큵 ????ㅽ뙣: {e}")
            return 0
        finally:
            self._pool.return_connection(conn)
    
    def get_price_snapshots(self, complex_id, trade_type=None):
        """Load stored price snapshot rows."""
        conn = self._pool.get_connection()
        try:
            sql = '''
                SELECT snapshot_date, trade_type, pyeong, min_price, max_price, avg_price, item_count
                FROM price_snapshots 
                WHERE complex_id = ?
            '''
            params = [complex_id]
            
            if not self._is_all_filter_value(trade_type):
                sql += ' AND trade_type = ?'
                params.append(trade_type)
            
            sql += ' ORDER BY snapshot_date DESC, trade_type, pyeong'
            
            raw_rows = self._fetchall_safe(
                conn,
                sql,
                params=params,
                context="媛寃??ㅻ깄??議고쉶(price_snapshots)",
            )
            result = []
            skipped = 0
            for row in raw_rows:
                normalized = self._normalize_snapshot_row(row)
                if normalized is None:
                    skipped += 1
                    continue
                result.append(normalized)

            if skipped:
                logger.debug(f"price snapshot skipped malformed rows: {skipped}")
            logger.debug(f"price snapshots loaded: {len(result)}")
            return result
        except Exception as e:
            self._log_corruption_detected("媛寃??ㅻ깄??議고쉶", e)
            logger.error(f"媛寃??ㅻ깄??議고쉶 ?ㅽ뙣: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
    
    def add_alert_setting(self, cid, name, ttype, amin, amax, pmin, pmax):
        conn = self._pool.get_connection()
        try:
            conn.cursor().execute(
                'INSERT INTO alert_settings (complex_id, complex_name, trade_type, area_min, area_max, price_min, price_max) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)', (cid, name, ttype, amin, amax, pmin, pmax)
            )
            conn.commit()
            logger.info(f"?뚮┝ ?ㅼ젙 異붽?: {name}")
            return True
        except Exception as e:
            logger.error(f"?뚮┝ ?ㅼ젙 異붽? ?ㅽ뙣: {e}")
            return False
        finally:
            self._pool.return_connection(conn)

    def get_article_history_state_bulk(self, complex_id, trade_type=None):
        """?⑥?(諛?嫄곕옒?좏삎) 湲곗? 留ㅻЪ ?대젰 ?곹깭瑜??쇨큵 議고쉶"""
        conn = self._pool.get_connection()
        try:
            sql = """
                SELECT article_id, price, status, last_price, price_change
                FROM article_history
                WHERE complex_id = ?
            """
            params = [complex_id]
            if trade_type:
                sql += " AND trade_type = ?"
                params.append(trade_type)

            rows = conn.cursor().execute(sql, params).fetchall()
            result = {}
            for row in rows:
                aid = row["article_id"]
                if not aid:
                    continue
                result[str(aid)] = {
                    "price": int(row["price"] or 0),
                    "status": str(row["status"] or "active"),
                    "last_price": int(row["last_price"] or 0),
                    "price_change": int(row["price_change"] or 0),
                }
            return result
        except Exception as e:
            logger.error(f"留ㅻЪ ?대젰 ?쇨큵 議고쉶 ?ㅽ뙣: {e}")
            return {}
        finally:
            self._pool.return_connection(conn)

    def upsert_article_history_bulk(self, rows):
        """留ㅻЪ ?대젰???쇨큵 upsert"""
        if not rows:
            return 0
        if self.is_write_disabled():
            return 0

        normalized = []
        for row in rows:
            if isinstance(row, dict):
                payload = {
                    "article_id": str(row.get("article_id", "") or ""),
                    "complex_id": str(row.get("complex_id", "") or ""),
                    "complex_name": str(row.get("complex_name", "") or ""),
                    "trade_type": str(row.get("trade_type", "") or ""),
                    "price": int(row.get("price", 0) or 0),
                    "price_text": str(row.get("price_text", "") or ""),
                    "area_pyeong": float(row.get("area", 0) or 0),
                    "floor_info": str(row.get("floor", "") or ""),
                    "feature": str(row.get("feature", "") or ""),
                    "last_price": int(row.get("last_price", row.get("price", 0)) or row.get("price", 0) or 0),
                    "asset_type": str(row.get("asset_type", "") or ""),
                    "source_mode": str(row.get("source_mode", "complex") or "complex"),
                    "source_lat": float(row.get("source_lat", 0) or 0),
                    "source_lon": float(row.get("source_lon", 0) or 0),
                    "source_zoom": int(row.get("source_zoom", 0) or 0),
                    "marker_id": str(row.get("marker_id", "") or ""),
                    "broker_office": str(row.get("broker_office", "") or ""),
                    "broker_name": str(row.get("broker_name", "") or ""),
                    "broker_phone1": str(row.get("broker_phone1", "") or ""),
                    "broker_phone2": str(row.get("broker_phone2", "") or ""),
                    "prev_jeonse_won": int(row.get("prev_jeonse_won", 0) or 0),
                    "jeonse_period_years": int(row.get("jeonse_period_years", 0) or 0),
                    "jeonse_max_won": int(row.get("jeonse_max_won", 0) or 0),
                    "jeonse_min_won": int(row.get("jeonse_min_won", 0) or 0),
                    "gap_amount_won": int(row.get("gap_amount_won", 0) or 0),
                    "gap_ratio": float(row.get("gap_ratio", 0.0) or 0.0),
                }
            else:
                try:
                    (
                        article_id,
                        complex_id,
                        complex_name,
                        trade_type,
                        price,
                        price_text,
                        area,
                        floor,
                        feature,
                        last_price,
                    ) = row
                except Exception:
                    continue
                payload = {
                    "article_id": str(article_id or ""),
                    "complex_id": str(complex_id or ""),
                    "complex_name": str(complex_name or ""),
                    "trade_type": str(trade_type or ""),
                    "price": int(price or 0),
                    "price_text": str(price_text or ""),
                    "area_pyeong": float(area or 0),
                    "floor_info": str(floor or ""),
                    "feature": str(feature or ""),
                    "last_price": int(last_price or price or 0),
                    "asset_type": "",
                    "source_mode": "complex",
                    "source_lat": 0.0,
                    "source_lon": 0.0,
                    "source_zoom": 0,
                    "marker_id": "",
                    "broker_office": "",
                    "broker_name": "",
                    "broker_phone1": "",
                    "broker_phone2": "",
                    "prev_jeonse_won": 0,
                    "jeonse_period_years": 0,
                    "jeonse_max_won": 0,
                    "jeonse_min_won": 0,
                    "gap_amount_won": 0,
                    "gap_ratio": 0.0,
                }

            if not payload["article_id"] or not payload["complex_id"] or payload["price"] <= 0:
                continue
            normalized.append(payload)

        if not normalized:
            return 0

        conn = self._pool.get_connection()
        try:
            with self._write_lock:
                try:
                    conn.execute("PRAGMA busy_timeout=5000")
                except Exception:
                    pass
                for attempt in range(3):
                    try:
                        conn.cursor().executemany(
                            """
                            INSERT INTO article_history (
                                article_id, complex_id, complex_name, trade_type,
                                price, price_text, area_pyeong, floor_info, feature,
                                first_seen, last_seen, last_price, price_change, status,
                                asset_type, source_mode, source_lat, source_lon, source_zoom, marker_id,
                                broker_office, broker_name, broker_phone1, broker_phone2,
                                prev_jeonse_won, jeonse_period_years, jeonse_max_won, jeonse_min_won,
                                gap_amount_won, gap_ratio
                            ) VALUES (
                                :article_id, :complex_id, :complex_name, :trade_type,
                                :price, :price_text, :area_pyeong, :floor_info, :feature,
                                CURRENT_DATE, CURRENT_DATE, :last_price, 0, 'active',
                                :asset_type, :source_mode, :source_lat, :source_lon, :source_zoom, :marker_id,
                                :broker_office, :broker_name, :broker_phone1, :broker_phone2,
                                :prev_jeonse_won, :jeonse_period_years, :jeonse_max_won, :jeonse_min_won,
                                :gap_amount_won, :gap_ratio
                            )
                            ON CONFLICT(article_id, complex_id) DO UPDATE SET
                                complex_name = excluded.complex_name,
                                trade_type = excluded.trade_type,
                                price = excluded.price,
                                price_text = excluded.price_text,
                                area_pyeong = excluded.area_pyeong,
                                floor_info = excluded.floor_info,
                                feature = excluded.feature,
                                asset_type = excluded.asset_type,
                                source_mode = excluded.source_mode,
                                source_lat = excluded.source_lat,
                                source_lon = excluded.source_lon,
                                source_zoom = excluded.source_zoom,
                                marker_id = excluded.marker_id,
                                broker_office = excluded.broker_office,
                                broker_name = excluded.broker_name,
                                broker_phone1 = excluded.broker_phone1,
                                broker_phone2 = excluded.broker_phone2,
                                prev_jeonse_won = excluded.prev_jeonse_won,
                                jeonse_period_years = excluded.jeonse_period_years,
                                jeonse_max_won = excluded.jeonse_max_won,
                                jeonse_min_won = excluded.jeonse_min_won,
                                gap_amount_won = excluded.gap_amount_won,
                                gap_ratio = excluded.gap_ratio,
                                last_seen = CURRENT_DATE,
                                last_price = article_history.price,
                                price_change = excluded.price - article_history.price,
                                status = 'active'
                            """,
                            normalized,
                        )
                        conn.commit()
                        return len(normalized)
                    except sqlite3.OperationalError as e:
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        if self._is_locked_sqlite_error(e) and attempt < 2:
                            time.sleep(0.1 * (attempt + 1))
                            continue
                        if self._is_corruption_sqlite_error(e):
                            self._disable_writes("database_corruption", e)
                        logger.error(f"留ㅻЪ ?대젰 ?쇨큵 ?낆꽌???ㅽ뙣: {e}")
                        return 0
                    except sqlite3.DatabaseError as e:
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        if self._is_corruption_sqlite_error(e):
                            self._disable_writes("database_corruption", e)
                        logger.error(f"留ㅻЪ ?대젰 ?쇨큵 ?낆꽌???ㅽ뙣: {e}")
                        return 0
        except Exception as e:
            logger.error(f"留ㅻЪ ?대젰 ?쇨큵 ?낆꽌???ㅽ뙣: {e}")
            return 0
        finally:
            try:
                conn.execute("PRAGMA busy_timeout=30000")
            except Exception:
                pass
            self._pool.return_connection(conn)

    def get_enabled_alert_rules(self, complex_id, trade_type=None):
        """?쒖꽦?붾맂 ?뚮┝ 猷곗쓣 ?⑥?/嫄곕옒?좏삎 湲곗??쇰줈 議고쉶"""
        conn = self._pool.get_connection()
        try:
            sql = (
                "SELECT id, complex_name, trade_type, area_min, area_max, price_min, price_max "
                "FROM alert_settings WHERE complex_id = ? AND enabled = 1"
            )
            params = [complex_id]
            if trade_type:
                sql += " AND trade_type = ?"
                params.append(trade_type)
            rows = conn.cursor().execute(sql, params).fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"?쒖꽦 ?뚮┝ 猷?議고쉶 ?ㅽ뙣: {e}")
            return []
        finally:
            self._pool.return_connection(conn)

    def record_alert_notification(self, alert_id: int, article_id: str, complex_id: str, notified_on=None) -> bool:
        """Record one alert notification row with same-day dedupe."""
        alert_id = int(alert_id or 0)
        article_id = str(article_id or "").strip()
        complex_id = str(complex_id or "").strip()
        if alert_id <= 0 or not article_id or not complex_id:
            return False

        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            if notified_on:
                notified_on = str(notified_on).strip()
                c.execute(
                    """
                    INSERT INTO article_alert_log (alert_id, article_id, complex_id, notified_on, created_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(alert_id, article_id, complex_id, notified_on) DO NOTHING
                    """,
                    (alert_id, article_id, complex_id, notified_on),
                )
            else:
                c.execute(
                    """
                    INSERT INTO article_alert_log (alert_id, article_id, complex_id, notified_on, created_at)
                    VALUES (?, ?, ?, CURRENT_DATE, CURRENT_TIMESTAMP)
                    ON CONFLICT(alert_id, article_id, complex_id, notified_on) DO NOTHING
                    """,
                    (alert_id, article_id, complex_id),
                )
            conn.commit()
            return (c.rowcount or 0) > 0
        except Exception as e:
            logger.error(f"?뚮┝ dedup 湲곕줉 ?ㅽ뙣: {e}")
            return False
        finally:
            self._pool.return_connection(conn)

    def check_article_history(self, article_id, complex_id, current_price):
        """留ㅻЪ ?대젰 ?뺤씤 (?좉퇋/蹂??"""
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            c.execute(
                "SELECT price, status FROM article_history WHERE article_id = ? AND complex_id = ?",
                (article_id, complex_id)
            )
            row = c.fetchone()
            
            if not row:
                return True, 0, 0  # ?좉퇋 留ㅻЪ (is_new=True, change=0, prev=0)
            
            last_price = row['price']
            price_change = current_price - last_price
            
            # 媛寃?蹂?숈씠 ?덇굅???대? 蹂?숈씠 湲곕줉??寃쎌슦
            return False, price_change, last_price
            
        except Exception as e:
            logger.error(f"留ㅻЪ ?대젰 ?뺤씤 ?ㅽ뙣: {e}")
            return False, 0, 0
        finally:
            self._pool.return_connection(conn)

    def update_article_history(self, article_id, complex_id, complex_name, trade_type,
                             price, price_text, area, floor, feature, extra=None):
        """留ㅻЪ ?뺣낫 ?낅뜲?댄듃"""
        if self.is_write_disabled():
            return False
        conn = self._pool.get_connection()
        try:
            with self._write_lock:
                c = conn.cursor()
                
                # 湲곗〈 ?뺣낫 議고쉶
                c.execute(
                    "SELECT price, first_seen FROM article_history WHERE article_id = ? AND complex_id = ?",
                    (article_id, complex_id)
                )
                row = c.fetchone()
                
                if row:
                    last_price = row['price']
                    price_change = price - last_price
                    extra = dict(extra or {})
                    
                    c.execute("""
                        UPDATE article_history 
                        SET complex_name=?, trade_type=?, price=?, price_text=?, area_pyeong=?, floor_info=?, feature=?,
                            asset_type=?, source_mode=?, source_lat=?, source_lon=?, source_zoom=?, marker_id=?,
                            broker_office=?, broker_name=?, broker_phone1=?, broker_phone2=?,
                            prev_jeonse_won=?, jeonse_period_years=?, jeonse_max_won=?, jeonse_min_won=?,
                            gap_amount_won=?, gap_ratio=?, last_seen=CURRENT_DATE,
                            last_price=?, price_change=?, status='active'
                        WHERE article_id=? AND complex_id=?
                    """, (
                        complex_name, trade_type, price, price_text, area, floor, feature,
                        str(extra.get("asset_type", "") or ""),
                        str(extra.get("source_mode", "complex") or "complex"),
                        float(extra.get("source_lat", 0) or 0),
                        float(extra.get("source_lon", 0) or 0),
                        int(extra.get("source_zoom", 0) or 0),
                        str(extra.get("marker_id", "") or ""),
                        str(extra.get("broker_office", "") or ""),
                        str(extra.get("broker_name", "") or ""),
                        str(extra.get("broker_phone1", "") or ""),
                        str(extra.get("broker_phone2", "") or ""),
                        int(extra.get("prev_jeonse_won", 0) or 0),
                        int(extra.get("jeonse_period_years", 0) or 0),
                        int(extra.get("jeonse_max_won", 0) or 0),
                        int(extra.get("jeonse_min_won", 0) or 0),
                        int(extra.get("gap_amount_won", 0) or 0),
                        float(extra.get("gap_ratio", 0.0) or 0.0),
                        last_price, price_change, article_id, complex_id,
                    ))
                else:
                    extra = dict(extra or {})
                    c.execute("""
                        INSERT INTO article_history (
                            article_id, complex_id, complex_name, trade_type, 
                            price, price_text, area_pyeong, floor_info, feature,
                            first_seen, last_seen, last_price, price_change, status,
                            asset_type, source_mode, source_lat, source_lon, source_zoom, marker_id,
                            broker_office, broker_name, broker_phone1, broker_phone2,
                            prev_jeonse_won, jeonse_period_years, jeonse_max_won, jeonse_min_won,
                            gap_amount_won, gap_ratio
                        ) VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_DATE, CURRENT_DATE, ?, 0, 'active',
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                        )
                    """, (
                        article_id, complex_id, complex_name, trade_type,
                        price, price_text, area, floor, feature, price,
                        str(extra.get("asset_type", "") or ""),
                        str(extra.get("source_mode", "complex") or "complex"),
                        float(extra.get("source_lat", 0) or 0),
                        float(extra.get("source_lon", 0) or 0),
                        int(extra.get("source_zoom", 0) or 0),
                        str(extra.get("marker_id", "") or ""),
                        str(extra.get("broker_office", "") or ""),
                        str(extra.get("broker_name", "") or ""),
                        str(extra.get("broker_phone1", "") or ""),
                        str(extra.get("broker_phone2", "") or ""),
                        int(extra.get("prev_jeonse_won", 0) or 0),
                        int(extra.get("jeonse_period_years", 0) or 0),
                        int(extra.get("jeonse_max_won", 0) or 0),
                        int(extra.get("jeonse_min_won", 0) or 0),
                        int(extra.get("gap_amount_won", 0) or 0),
                        float(extra.get("gap_ratio", 0.0) or 0.0),
                    ))
                
                conn.commit()
                return True
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            if self._is_corruption_sqlite_error(e):
                self._disable_writes("database_corruption", e)
            logger.error(f"留ㅻЪ ?대젰 ?낅뜲?댄듃 ?ㅽ뙣: {e}")
            return False
        finally:
            self._pool.return_connection(conn)

    def get_article_history_stats(self, complex_id=None):
        """留ㅻЪ ?덉뒪?좊━ ?듦퀎"""
        conn = self._pool.get_connection()
        try:
            today = DateTimeHelper.now_string("%Y-%m-%d")
            
            if complex_id:
                # ?뱀젙 ?⑥? ?듦퀎
                result = conn.cursor().execute('''
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN first_seen = ? THEN 1 ELSE 0 END) as new_today,
                        SUM(CASE WHEN price_change > 0 THEN 1 ELSE 0 END) as price_up,
                        SUM(CASE WHEN price_change < 0 THEN 1 ELSE 0 END) as price_down
                    FROM article_history WHERE complex_id = ?
                ''', (today, complex_id)).fetchone()
            else:
                # ?꾩껜 ?듦퀎
                result = conn.cursor().execute('''
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN first_seen = ? THEN 1 ELSE 0 END) as new_today,
                        SUM(CASE WHEN price_change > 0 THEN 1 ELSE 0 END) as price_up,
                        SUM(CASE WHEN price_change < 0 THEN 1 ELSE 0 END) as price_down
                    FROM article_history
                ''', (today,)).fetchone()
            
            return {
                'total': result[0] or 0,
                'new_today': result[1] or 0,
                'price_up': result[2] or 0,
                'price_down': result[3] or 0
            }
        except Exception as e:
            logger.error(f"留ㅻЪ ?듦퀎 議고쉶 ?ㅽ뙣: {e}")
            return {'total': 0, 'new_today': 0, 'price_up': 0, 'price_down': 0}
        finally:
            self._pool.return_connection(conn)
    
    def cleanup_old_articles(self, days=30):
        """?ㅻ옒??留ㅻЪ ?덉뒪?좊━ ?뺣━"""
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            c.execute('''
                DELETE FROM article_history 
                WHERE julianday('now') - julianday(last_seen) > ?
            ''', (days,))
            deleted = c.rowcount
            conn.commit()
            logger.info(f"?ㅻ옒??留ㅻЪ {deleted}媛??뺣━ (>{days}??")
            return deleted
        except Exception as e:
            logger.error(f"留ㅻЪ ?뺣━ ?ㅽ뙣: {e}")
            return 0
        finally:
            self._pool.return_connection(conn)

    def toggle_favorite(self, article_id, complex_id, is_active=True):
        """留ㅻЪ 利먭꺼李얘린 ?좉?"""
        conn = self._pool.get_connection()
        try:
            if is_active:
                conn.cursor().execute("""
                    INSERT INTO article_favorites 
                    (article_id, complex_id, is_favorite, created_at, updated_at)
                    VALUES (?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT(article_id, complex_id) DO UPDATE SET
                        is_favorite=1,
                        updated_at=CURRENT_TIMESTAMP
                """, (article_id, complex_id))
            else:
                conn.cursor().execute("""
                    UPDATE article_favorites 
                    SET is_favorite=0, updated_at=CURRENT_TIMESTAMP
                    WHERE article_id=? AND complex_id=?
                """, (article_id, complex_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"利먭꺼李얘린 ?좉? ?ㅽ뙣: {e}")
            return False
        finally:
            self._pool.return_connection(conn)

    def update_article_note(self, article_id, complex_id, note):
        """留ㅻЪ 硫붾え ?낅뜲?댄듃"""
        conn = self._pool.get_connection()
        try:
            conn.cursor().execute("""
                UPDATE article_favorites 
                SET note=?, updated_at=CURRENT_TIMESTAMP
                WHERE article_id=? AND complex_id=?
            """, (note, article_id, complex_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"硫붾え ?낅뜲?댄듃 ?ㅽ뙣: {e}")
            return False
        finally:
            self._pool.return_connection(conn)

    def get_favorites(self):
        """利먭꺼李얘린 留ㅻЪ 紐⑸줉"""
        conn = self._pool.get_connection()
        try:
            query = """
                SELECT h.*, f.is_favorite, f.note,
                       f.created_at AS favorite_created_at,
                       f.updated_at AS favorite_updated_at
                FROM article_history h
                JOIN article_favorites f ON h.article_id = f.article_id AND h.complex_id = f.complex_id
                WHERE f.is_favorite = 1
                ORDER BY f.updated_at DESC
            """
            rows = conn.cursor().execute(query).fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"利먭꺼李얘린 紐⑸줉 議고쉶 ?ㅽ뙣: {e}")
            return []
        finally:
            self._pool.return_connection(conn)

    @staticmethod
    def _integrity_check_file(db_path: Path) -> bool:
        conn = None
        try:
            conn = sqlite3.connect(str(db_path), timeout=30)
            row = conn.cursor().execute("PRAGMA integrity_check").fetchone()
            if not row:
                return False
            return str(row[0]).strip().lower() == "ok"
        except Exception as e:
            logger.error(f"SQLite integrity_check ?ㅽ뙣 ({db_path}): {e}")
            return False
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def _validate_restored_database(self) -> int:
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            row = c.execute("PRAGMA integrity_check").fetchone()
            if not row or str(row[0]).strip().lower() != "ok":
                raise RuntimeError(f"蹂듭썝 DB integrity_check ?ㅽ뙣: {row[0] if row else 'empty'}")

            names = {
                r[0]
                for r in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            missing = [t for t in self._RESTORE_REQUIRED_TABLES if t not in names]
            if missing:
                raise RuntimeError(f"蹂듭썝 DB ?꾩닔 ?뚯씠釉??꾨씫: {', '.join(missing)}")

            count_row = c.execute("SELECT COUNT(*) FROM complexes").fetchone()
            return int(count_row[0] if count_row else 0)
        finally:
            self._pool.return_connection(conn)

    def backup_database(self, path):
        backup_path = Path(path)
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if backup_path.resolve() == self.db_path.resolve():
                logger.error("諛깆뾽 ?ㅽ뙣: ?먮낯 DB? ?숈씪??寃쎈줈???ъ슜?????놁뒿?덈떎.")
                return False
        except Exception:
            pass

        source_conn = None
        target_conn = None
        try:
            source_conn = self._pool.get_connection()
            target_conn = sqlite3.connect(str(backup_path), timeout=30)
            source_conn.backup(target_conn)
            target_conn.commit()
        except Exception as e:
            logger.error(f"諛깆뾽 ?ㅽ뙣: {e}")
            return False
        finally:
            if target_conn is not None:
                try:
                    target_conn.close()
                except Exception:
                    pass
            if source_conn is not None:
                self._pool.return_connection(source_conn)

        verify_conn = None
        try:
            verify_conn = sqlite3.connect(str(backup_path), timeout=30)
            row = verify_conn.cursor().execute("SELECT COUNT(*) FROM complexes").fetchone()
            if not row:
                logger.error("諛깆뾽 寃利??ㅽ뙣: complexes 吏묎퀎 寃곌낵媛 鍮꾩뼱 ?덉뒿?덈떎.")
                return False
            if not self._integrity_check_file(backup_path):
                logger.error("backup validation failed: integrity_check mismatch")
                return False
            logger.info(f"諛깆뾽 ?꾨즺: {backup_path} (complexes={int(row[0])})")
            return True
        except Exception as e:
            logger.error(f"諛깆뾽 寃利??ㅽ뙣: {e}")
            return False
        finally:
            if verify_conn is not None:
                try:
                    verify_conn.close()
                except Exception:
                    pass
    
    def restore_database(self, path):
        """DB 蹂듭썝 - ?좎?蹂댁닔/?숈떆???덉쟾 蹂듭썝 濡쒖쭅"""
        restore_path = Path(path)
        logger.info(f"蹂듭썝 ?쒖옉: {restore_path}")

        if not restore_path.exists():
            logger.error(f"蹂듭썝 ?뚯씪??議댁옱?섏? ?딆쓬: {restore_path}")
            return False
        if not self._integrity_check_file(restore_path):
            logger.error(f"蹂듭썝 ?뚯씪 integrity_check ?ㅽ뙣: {restore_path}")
            return False

        rollback_path = self.db_path.with_suffix(".db.pre_restore")
        temp_restore_path = self.db_path.with_suffix(".db.restore_tmp")
        rollback_ready = False

        try:
            if temp_restore_path.exists():
                temp_restore_path.unlink()
        except OSError as e:
            logger.warning(f"?꾩떆 蹂듭썝 ?뚯씪 ?뺣━ ?ㅽ뙣 (臾댁떆): {e}")

        try:
            if self.db_path.exists():
                rollback_ready = self.backup_database(rollback_path)
                if not rollback_ready:
                    logger.error("蹂듭썝 以묐떒: 濡ㅻ갚???ъ쟾 諛깆뾽 ?앹꽦 ?ㅽ뙣")
                    return False

            if self._pool:
                self._pool.close_all(timeout_ms=8000)

            shutil.copy2(restore_path, temp_restore_path)
            os.replace(temp_restore_path, self.db_path)

            self._pool = ConnectionPool(self.db_path)
            self._init_tables()
            complex_count = self._validate_restored_database()
            self._write_disabled_reason = ""
            logger.info(f"restore complete: complexes={complex_count}")

            if rollback_ready and rollback_path.exists():
                try:
                    rollback_path.unlink()
                except OSError as e:
                    logger.debug(f"?ъ쟾 諛깆뾽 ?뚯씪 ??젣 ?ㅽ뙣 (臾댁떆): {e}")
            return True

        except Exception as e:
            logger.exception(f"蹂듭썝 ?ㅽ뙣: {e}")
            try:
                if temp_restore_path.exists():
                    temp_restore_path.unlink()
            except OSError:
                pass

            if rollback_ready and rollback_path.exists():
                try:
                    logger.info("蹂듭썝 ?ㅽ뙣濡?濡ㅻ갚???쒕룄?⑸땲??")
                    os.replace(rollback_path, self.db_path)
                    self._pool = ConnectionPool(self.db_path)
                    self._init_tables()
                    self._validate_restored_database()
                    logger.info("濡ㅻ갚 蹂듦뎄 ?꾨즺")
                except Exception as rb_e:
                    logger.error(f"濡ㅻ갚 蹂듦뎄 ?ㅽ뙣: {rb_e}")
            elif self.db_path.exists():
                try:
                    self._pool = ConnectionPool(self.db_path)
                    self._init_tables()
                except Exception as reinit_e:
                    logger.error(f"蹂듭썝 ?ㅽ뙣 ???곌껐? ?ъ큹湲고솕 ?ㅽ뙣: {reinit_e}")
            return False

    def get_all_alert_settings(self):
        conn = self._pool.get_connection()
        try:
            return conn.cursor().execute(
                'SELECT id, complex_id, complex_name, trade_type, area_min, area_max, price_min, price_max, enabled '
                'FROM alert_settings ORDER BY created_at DESC'
            ).fetchall()
        except Exception as e:
            logger.error(f"?뚮┝ ?ㅼ젙 議고쉶 ?ㅽ뙣: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
    
    def toggle_alert_setting(self, aid, enabled):
        conn = self._pool.get_connection()
        try:
            conn.cursor().execute("UPDATE alert_settings SET enabled = ? WHERE id = ?", (1 if enabled else 0, aid))
            conn.commit()
        except Exception as e:
            logger.error(f"?뚮┝ ?ㅼ젙 ?좉? ?ㅽ뙣: {e}")
        finally:
            self._pool.return_connection(conn)
    
    def delete_alert_setting(self, aid):
        conn = self._pool.get_connection()
        try:
            conn.cursor().execute("DELETE FROM alert_settings WHERE id = ?", (aid,))
            conn.commit()
        except Exception as e:
            logger.error(f"?뚮┝ ?ㅼ젙 ??젣 ?ㅽ뙣: {e}")
        finally:
            self._pool.return_connection(conn)
    
    def check_alerts(self, cid, ttype, area, price):
        conn = self._pool.get_connection()
        try:
            return conn.cursor().execute(
                'SELECT id, complex_name FROM alert_settings '
                'WHERE complex_id = ? AND trade_type = ? AND enabled = 1 '
                'AND area_min <= ? AND area_max >= ? AND price_min <= ? AND price_max >= ?',
                (cid, ttype, area, area, price, price)
            ).fetchall()
        except Exception as e:
            logger.error(f"?뚮┝ 泥댄겕 ?ㅽ뙣: {e}")
            return []
        finally:
            self._pool.return_connection(conn)

    def get_article_favorite_info(self, article_id, complex_id):
        """?뱀젙 留ㅻЪ??利먭꺼李얘린/硫붾え ?뺣낫 議고쉶"""
        conn = self._pool.get_connection()
        try:
            row = conn.cursor().execute(
                "SELECT is_favorite, note FROM article_favorites WHERE article_id=? AND complex_id=?",
                (article_id, complex_id)
            ).fetchone()
            if row:
                return dict(row)
            return {'is_favorite': 0, 'note': ''}
        except Exception as e:
            logger.error(f"留ㅻЪ 利먭꺼李얘린 ?뺣낫 議고쉶 ?ㅽ뙣: {e}")
            return {'is_favorite': 0, 'note': ''}
        finally:
            self._pool.return_connection(conn)

    def mark_disappeared_articles(self):
        """?ㅻ뒛 ?뺤씤?섏? ?딆? 留ㅻЪ???뚮㈇ 泥섎━"""
        if self.is_write_disabled():
            return 0
        conn = self._pool.get_connection()
        try:
            with self._write_lock:
                try:
                    conn.execute("PRAGMA busy_timeout=3000")
                except Exception:
                    pass
                # 留덉?留??뺤씤?쇱씠 ?ㅻ뒛???꾨땶 'active' 留ㅻЪ??'disappeared'濡?蹂寃?
                c = conn.cursor()
                c.execute("""
                    UPDATE article_history 
                    SET status='disappeared' 
                    WHERE last_seen < CURRENT_DATE AND status='active'
                """)
                updated = c.rowcount if c.rowcount != -1 else 0
                conn.commit()
                if updated > 0:
                    logger.info(f"marked disappeared articles: {updated}")
                return updated
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            if self._is_corruption_sqlite_error(e):
                self._disable_writes("database_corruption", e)
            logger.error(f"?뚮㈇ 留ㅻЪ 泥섎━ ?ㅽ뙣: {e}")
            return 0
        finally:
            try:
                conn.execute("PRAGMA busy_timeout=30000")
            except Exception:
                pass
            self._pool.return_connection(conn)

    def mark_disappeared_articles_for_targets(self, targets: list[tuple[str, ...]]) -> int:
        """?대쾲 ?ㅽ뻾 ????⑥?ID, 嫄곕옒?좏삎) 踰붿쐞?먯꽌留??뚮㈇ 留ㅻЪ??泥섎━"""
        if self.is_write_disabled():
            return 0
        normalized_pairs: list[tuple[str, str]] = []
        normalized_triples: list[tuple[str, str, str]] = []
        for pair in targets or []:
            if not isinstance(pair, (list, tuple)):
                continue
            if len(pair) >= 3:
                asset_type = str(pair[0] or "").strip().upper()
                complex_id = str(pair[1] or "").strip()
                trade_type = str(pair[2] or "").strip()
                if asset_type and complex_id and trade_type:
                    normalized_triples.append((asset_type, complex_id, trade_type))
                continue
            if len(pair) >= 2:
                complex_id = str(pair[0] or "").strip()
                trade_type = str(pair[1] or "").strip()
                if complex_id and trade_type:
                    normalized_pairs.append((complex_id, trade_type))

        if not normalized_pairs and not normalized_triples:
            return 0

        conn = self._pool.get_connection()
        try:
            with self._write_lock:
                try:
                    conn.execute("PRAGMA busy_timeout=3000")
                except Exception:
                    pass
                scoped_clauses: list[str] = []
                params = []

                if normalized_pairs:
                    where_pairs = " OR ".join(["(complex_id = ? AND trade_type = ?)"] * len(normalized_pairs))
                    scoped_clauses.append(f"({where_pairs})")
                    for complex_id, trade_type in normalized_pairs:
                        params.extend([complex_id, trade_type])

                if normalized_triples:
                    where_triples = " OR ".join(
                        ["(asset_type = ? AND complex_id = ? AND trade_type = ?)"] * len(normalized_triples)
                    )
                    scoped_clauses.append(f"({where_triples})")
                    for asset_type, complex_id, trade_type in normalized_triples:
                        params.extend([asset_type, complex_id, trade_type])

                c = conn.cursor()
                c.execute(
                    f"""
                    UPDATE article_history
                    SET status='disappeared'
                    WHERE last_seen < CURRENT_DATE
                      AND status='active'
                      AND ({' OR '.join(scoped_clauses)})
                    """,
                    params,
                )
                updated = c.rowcount if c.rowcount != -1 else 0
                conn.commit()
                if updated > 0:
                    logger.info(f"marked disappeared (scoped): {updated}")
                return updated
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            if self._is_corruption_sqlite_error(e):
                self._disable_writes("database_corruption", e)
            logger.error(f"???踰붿쐞 ?뚮㈇ 留ㅻЪ 泥섎━ ?ㅽ뙣: {e}")
            return 0
        finally:
            try:
                conn.execute("PRAGMA busy_timeout=30000")
            except Exception:
                pass
            self._pool.return_connection(conn)
            
    def get_disappeared_articles(self, limit=50):
        """理쒓렐 ?뚮㈇??留ㅻЪ 議고쉶"""
        conn = self._pool.get_connection()
        try:
            sql = """
                SELECT * FROM article_history 
                WHERE status='disappeared' 
                ORDER BY last_seen DESC LIMIT ?
            """
            rows = conn.cursor().execute(sql, (limit,)).fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"?뚮㈇ 留ㅻЪ 議고쉶 ?ㅽ뙣: {e}")
            return []
        finally:
            self._pool.return_connection(conn)

    def count_disappeared_articles(self):
        """?뚮㈇ 留ㅻЪ 媛쒖닔 議고쉶"""
        conn = self._pool.get_connection()
        try:
            row = conn.cursor().execute(
                "SELECT COUNT(*) FROM article_history WHERE status='disappeared'"
            ).fetchone()
            return row[0] if row else 0
        except Exception as e:
            logger.error(f"?뚮㈇ 留ㅻЪ 媛쒖닔 議고쉶 ?ㅽ뙣: {e}")
            return 0
        finally:
            self._pool.return_connection(conn)

    def close(self):
        """DB ?곌껐 ? 醫낅즺"""
        try:
            if self._pool:
                self._pool.close_all()
        except Exception as e:
            logger.debug(f"DB 醫낅즺 ?ㅽ뙣 (臾댁떆): {e}")

