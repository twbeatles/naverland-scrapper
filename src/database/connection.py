import sqlite3
from pathlib import Path
from queue import Queue, Empty, Full
from threading import Lock
from contextlib import contextmanager
from src.utils.logger import get_logger

class ConnectionPool:
    """DB 연결 풀 관리 (v13.1 - 로깅 개선)"""
    
    def __init__(self, db_path, pool_size=5):
        self._logger = get_logger('ConnectionPool')
        self.db_path = Path(db_path)
        self.pool_size = pool_size
        self._pool = Queue(maxsize=pool_size)
        self._lock = Lock()
        self._logger.info(f"ConnectionPool 초기화: {self.db_path}")
        self._initialize_pool()
    
    def _initialize_pool(self):
        created_count = 0
        for i in range(self.pool_size):
            try:
                conn = self._create_connection()
                self._pool.put(conn)
                created_count += 1
            except Exception as e:
                self._logger.error(f"연결 생성 실패 ({i+1}/{self.pool_size}): {e}")
        
        if created_count < self.pool_size:
            self._logger.warning(f"일부 연결만 생성됨: {created_count}/{self.pool_size}")
    
    def _create_connection(self):
        # 부모 디렉토리 확인/생성
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_connection(self):
        try:
            return self._pool.get(timeout=10)
        except Exception as e:
            self._logger.warning(f"풀에서 연결 가져오기 실패, 새 연결 생성: {e}")
            return self._create_connection()
    
    def return_connection(self, conn):
        if conn is None:
            return
        try:
            self._pool.put_nowait(conn)
        except Full:
            try:
                conn.close()
            except Exception as e:
                self._logger.debug(f"연결 종료 중 오류: {e}")
    
    @contextmanager
    def get_connection_context(self):
        """컨텍스트 매니저로 연결 관리 (연결 누수 방지)"""
        conn = self.get_connection()
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            self.return_connection(conn)
    
    def close_all(self):
        """모든 연결 안전하게 종료"""
        self._logger.info("ConnectionPool 종료 시작...")
        closed_count = 0
        error_count = 0
        
        # 최대 시도 횟수 제한
        max_attempts = self.pool_size + 5
        attempts = 0
        
        while attempts < max_attempts:
            attempts += 1
            try:
                conn = self._pool.get_nowait()
                try:
                    conn.close()
                    closed_count += 1
                except Exception as e:
                    self._logger.warning(f"연결 종료 실패: {e}")
                    error_count += 1
            except Empty:
                # 큐가 비었음
                break
        
        self._logger.info(f"ConnectionPool 종료 완료: {closed_count}개 종료, {error_count}개 오류")
