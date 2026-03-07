from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Condition, Lock

from src.utils.logger import get_logger

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

