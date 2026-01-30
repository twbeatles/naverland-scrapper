import sqlite3
from pathlib import Path
from queue import Queue, Empty, Full
from threading import Lock
import shutil
from src.utils.paths import DB_PATH
from src.utils.logger import get_logger
from src.utils.helpers import DateTimeHelper

logger = get_logger("DB")

class ConnectionPool:
    def __init__(self, db_path, pool_size=5):
        self.db_path = Path(db_path)
        self.pool_size = pool_size
        self._pool = Queue(maxsize=pool_size)
        self._lock = Lock()
        logger.info(f"ConnectionPool 초기화: {self.db_path}")
        self._initialize_pool()
    
    def _initialize_pool(self):
        for i in range(self.pool_size):
            try:
                conn = self._create_connection()
                self._pool.put(conn)
            except Exception as e:
                logger.error(f"연결 생성 실패 ({i+1}/{self.pool_size}): {e}")
    
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
            logger.warning(f"풀에서 연결 가져오기 실패, 새 연결 생성: {e}")
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
                logger.debug(f"연결 종료 중 오류: {e}")
    
    def close_all(self):
        """모든 연결 안전하게 종료"""
        logger.info("ConnectionPool 종료 시작...")
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
                    logger.warning(f"연결 종료 실패: {e}")
                    error_count += 1
            except Empty:
                # 큐가 비었음
                break
        
        logger.info(f"ConnectionPool 종료 완료: {closed_count}개 종료, {error_count}개 오류")

class ComplexDatabase:
    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        logger.info(f"ComplexDatabase 초기화: {self.db_path}")
        self._pool = ConnectionPool(self.db_path)
        self._init_tables()
    
    def _init_tables(self):
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS complexes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                complex_id TEXT NOT NULL UNIQUE,
                memo TEXT DEFAULT "",
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
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
                FOREIGN KEY (group_id) REFERENCES groups(id),
                FOREIGN KEY (complex_id) REFERENCES complexes(id)
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS crawl_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                complex_name TEXT,
                complex_id TEXT,
                trade_types TEXT,
                item_count INTEGER,
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
            # v7.3 신규: 매물 히스토리 (신규 매물/가격 변동 추적)
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
                UNIQUE(article_id, complex_id)
            )''')
            # v12.0 신규: 매물 즐겨찾기 및 메모
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
            # 인덱스 추가
            c.execute('CREATE INDEX IF NOT EXISTS idx_article_complex ON article_history(complex_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_article_id ON article_history(article_id)')
            
            # v12.0 마이그레이션: 기존 테이블에 status 컬럼 없을 경우 추가
            try:
                c.execute("SELECT status FROM article_history LIMIT 1")
            except Exception:
                logger.info("마이그레이션: article_history 테이블에 status 컬럼 추가...")
                try:
                    c.execute("ALTER TABLE article_history ADD COLUMN status TEXT DEFAULT 'active'")
                    conn.commit()
                    logger.info("마이그레이션 완료: status 컬럼 추가됨")
                except Exception as me:
                    logger.warning(f"마이그레이션 오류 (무시): {me}")
            
            # status 컬럼 인덱스 생성 (마이그레이션 후)
            try:
                c.execute('CREATE INDEX IF NOT EXISTS idx_article_status ON article_history(status)')
            except Exception:
                logger.debug("status 인덱스 생성 실패 (무시)")
            
            c.execute('CREATE INDEX IF NOT EXISTS idx_favorites ON article_favorites(article_id, complex_id)')
            conn.commit()
            logger.info("테이블 초기화 완료")
        except Exception as e:
            logger.exception(f"테이블 초기화 실패: {e}")
        finally:
            self._pool.return_connection(conn)
    
    def add_complex(self, name, complex_id, memo=""):
        """단지 추가 - 디버깅 강화"""
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            # 이미 존재하는지 확인
            c.execute("SELECT id FROM complexes WHERE complex_id = ?", (complex_id,))
            existing = c.fetchone()
            if existing:
                logger.debug(f"단지 이미 존재: {name} ({complex_id})")
                return True  # 이미 존재하면 성공으로 처리
            
            c.execute("INSERT INTO complexes (name, complex_id, memo) VALUES (?, ?, ?)", 
                     (name, complex_id, memo))
            conn.commit()
            logger.info(f"단지 추가 성공: {name} ({complex_id})")
            return True
        except sqlite3.IntegrityError as e:
            logger.debug(f"단지 중복 (정상): {name} ({complex_id})")
            return True
        except Exception as e:
            logger.exception(f"단지 추가 실패: {name} ({complex_id}) - {e}")
            return False
        finally:
            self._pool.return_connection(conn)
    
    def get_all_complexes(self):
        """모든 단지 조회 - 디버깅 강화"""
        conn = self._pool.get_connection()
        try:
            result = conn.cursor().execute(
                "SELECT id, name, complex_id, memo FROM complexes ORDER BY name"
            ).fetchall()
            logger.debug(f"단지 조회: {len(result)}개")
            return result
        except Exception as e:
            logger.exception(f"단지 조회 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)

    def get_complexes_for_stats(self):
        """통계 탭용 단지 목록 조회 (DB + 크롤링 기록 + 스냅샷)"""
        conn = self._pool.get_connection()
        try:
            complex_map = {}

            # 1) 저장된 단지 목록
            rows = conn.cursor().execute(
                "SELECT name, complex_id FROM complexes ORDER BY name"
            ).fetchall()
            for row in rows:
                cid = row["complex_id"]
                name = row["name"]
                if cid and name:
                    complex_map[cid] = name

            # 2) 크롤링 기록(최신 이름 우선)
            history_rows = conn.cursor().execute(
                '''
                SELECT ch.complex_id, ch.complex_name
                FROM crawl_history ch
                JOIN (
                    SELECT complex_id, MAX(crawled_at) AS last_crawl
                    FROM crawl_history
                    GROUP BY complex_id
                ) latest
                ON ch.complex_id = latest.complex_id AND ch.crawled_at = latest.last_crawl
                '''
            ).fetchall()
            for row in history_rows:
                cid = row["complex_id"]
                name = row["complex_name"] or f"단지_{cid}"
                if cid and cid not in complex_map:
                    complex_map[cid] = name

            # 3) 스냅샷에만 존재하는 단지 보강
            snapshot_rows = conn.cursor().execute(
                "SELECT DISTINCT complex_id FROM price_snapshots"
            ).fetchall()
            for row in snapshot_rows:
                cid = row["complex_id"]
                if cid and cid not in complex_map:
                    complex_map[cid] = f"단지_{cid}"

            result = [(name, cid) for cid, name in complex_map.items()]
            result.sort(key=lambda x: x[0])
            logger.debug(f"통계 단지 조회: {len(result)}개")
            return result
        except Exception as e:
            logger.exception(f"통계 단지 조회 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
    
    def delete_complex(self, db_id):
        conn = self._pool.get_connection()
        try:
            conn.cursor().execute("DELETE FROM complexes WHERE id = ?", (db_id,))
            conn.commit()
            logger.info(f"단지 삭제: ID={db_id}")
            return True
        except Exception as e:
            logger.error(f"단지 삭제 실패: {e}")
            return False
        finally:
            self._pool.return_connection(conn)
    
    def delete_complexes_bulk(self, db_ids):
        conn = self._pool.get_connection()
        try:
            if not db_ids:
                return 0
            c = conn.cursor()
            placeholders = ','.join('?' * len(db_ids))
            c.execute(f"DELETE FROM complexes WHERE id IN ({placeholders})", db_ids)
            conn.commit()
            logger.info(f"단지 일괄 삭제: {c.rowcount}개")
            return c.rowcount
        except Exception as e:
            logger.error(f"단지 일괄 삭제 실패: {e}")
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
            logger.error(f"메모 업데이트 실패: {e}")
            return False
        finally:
            self._pool.return_connection(conn)
    
    def create_group(self, name, desc=""):
        conn = self._pool.get_connection()
        try:
            conn.cursor().execute("INSERT INTO groups (name, description) VALUES (?, ?)", (name, desc))
            conn.commit()
            logger.info(f"그룹 생성: {name}")
            return True
        except Exception as e:
            logger.error(f"그룹 생성 실패: {e}")
            return False
        finally:
            self._pool.return_connection(conn)
    
    def get_all_groups(self):
        conn = self._pool.get_connection()
        try:
            result = conn.cursor().execute("SELECT id, name, description FROM groups ORDER BY name").fetchall()
            logger.debug(f"그룹 조회: {len(result)}개")
            return result
        except Exception as e:
            logger.error(f"그룹 조회 실패: {e}")
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
            logger.info(f"그룹 삭제: ID={group_id}")
            return True
        except Exception as e:
            logger.error(f"그룹 삭제 실패: {e}")
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
                    logger.warning(f"그룹에 단지 추가 실패: {cid} - {e}")
            conn.commit()
            logger.info(f"그룹에 단지 추가: {count}개")
            return count
        except Exception as e:
            logger.error(f"그룹에 단지 추가 실패: {e}")
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
            logger.error(f"그룹에서 단지 제거 실패: {e}")
            return False
        finally:
            self._pool.return_connection(conn)
    
    def get_complexes_in_group(self, group_id):
        conn = self._pool.get_connection()
        try:
            result = conn.cursor().execute(
                'SELECT c.id, c.name, c.complex_id, c.memo FROM complexes c '
                'JOIN group_complexes gc ON c.id = gc.complex_id '
                'WHERE gc.group_id = ? ORDER BY c.name', (group_id,)
            ).fetchall()
            return result
        except Exception as e:
            logger.error(f"그룹 내 단지 조회 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
    
    def add_crawl_history(self, name, cid, types, count):
        conn = self._pool.get_connection()
        try:
            conn.cursor().execute(
                "INSERT INTO crawl_history (complex_name, complex_id, trade_types, item_count) VALUES (?, ?, ?, ?)",
                (name, cid, types, count)
            )
            conn.commit()
        except Exception as e:
            logger.error(f"크롤링 기록 저장 실패: {e}")
        finally:
            self._pool.return_connection(conn)
    
    def get_crawl_history(self, limit=100):
        conn = self._pool.get_connection()
        try:
            result = conn.cursor().execute(
                'SELECT complex_name, complex_id, trade_types, item_count, crawled_at '
                'FROM crawl_history ORDER BY crawled_at DESC LIMIT ?', (limit,)
            ).fetchall()
            return result
        except Exception as e:
            logger.error(f"크롤링 기록 조회 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
    
    def get_complex_price_history(self, complex_id, trade_type=None, pyeong=None):
        conn = self._pool.get_connection()
        try:
            sql = 'SELECT snapshot_date, trade_type, pyeong, min_price, max_price, avg_price FROM price_snapshots WHERE complex_id = ?'
            params = [complex_id]
            
            if trade_type and trade_type != "전체":
                sql += ' AND trade_type = ?'
                params.append(trade_type)
            
            if pyeong and pyeong != "전체":
                try:
                    p_val = float(pyeong.replace("평", ""))
                    sql += ' AND pyeong = ?'
                    params.append(p_val)
                except (ValueError, TypeError):
                    logger.debug(f"평형 값 파싱 실패: {pyeong}")
                
            sql += ' ORDER BY snapshot_date DESC, pyeong'
            
            result = conn.cursor().execute(sql, params).fetchall()
            logger.debug(f"가격 히스토리 조회: {len(result)}개 (조건: {trade_type}, {pyeong})")
            return result
        except Exception as e:
            logger.error(f"가격 히스토리 조회 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
    
    def add_price_snapshot(self, complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count):
        """가격 스냅샷 저장"""
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
            logger.error(f"가격 스냅샷 저장 실패: {e}")
            return False
        finally:
            self._pool.return_connection(conn)
    
    def get_price_snapshots(self, complex_id, trade_type=None):
        """가격 스냅샷 조회 (통계용)"""
        conn = self._pool.get_connection()
        try:
            sql = '''
                SELECT snapshot_date, trade_type, pyeong, min_price, max_price, avg_price, item_count
                FROM price_snapshots 
                WHERE complex_id = ?
            '''
            params = [complex_id]
            
            if trade_type and trade_type != "전체":
                sql += ' AND trade_type = ?'
                params.append(trade_type)
            
            sql += ' ORDER BY snapshot_date DESC, trade_type, pyeong'
            
            result = conn.cursor().execute(sql, params).fetchall()
            logger.debug(f"가격 스냅샷 조회: {len(result)}개")
            return result
        except Exception as e:
            logger.error(f"가격 스냅샷 조회 실패: {e}")
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
            logger.info(f"알림 설정 추가: {name}")
            return True
        except Exception as e:
            logger.error(f"알림 설정 추가 실패: {e}")
            return False
        finally:
            self._pool.return_connection(conn)

    def check_article_history(self, article_id, complex_id, current_price):
        """매물 이력 확인 (신규/변동)"""
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            c.execute(
                "SELECT price, status FROM article_history WHERE article_id = ? AND complex_id = ?",
                (article_id, complex_id)
            )
            row = c.fetchone()
            
            if not row:
                return True, 0, 0  # 신규 매물 (is_new=True, change=0, prev=0)
            
            last_price = row['price']
            price_change = current_price - last_price
            
            # 가격 변동이 있거나 이미 변동이 기록된 경우
            return False, price_change, last_price
            
        except Exception as e:
            logger.error(f"매물 이력 확인 실패: {e}")
            return False, 0, 0
        finally:
            self._pool.return_connection(conn)

    def update_article_history(self, article_id, complex_id, complex_name, trade_type, 
                             price, price_text, area, floor, feature):
        """매물 정보 업데이트"""
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            
            # 기존 정보 조회
            c.execute(
                "SELECT price, first_seen FROM article_history WHERE article_id = ? AND complex_id = ?",
                (article_id, complex_id)
            )
            row = c.fetchone()
            
            if row:
                last_price = row['price']
                price_change = price - last_price
                
                c.execute("""
                    UPDATE article_history 
                    SET price=?, price_text=?, last_seen=CURRENT_DATE, 
                        last_price=?, price_change=?, status='active'
                    WHERE article_id=? AND complex_id=?
                """, (price, price_text, last_price, price_change, article_id, complex_id))
            else:
                c.execute("""
                    INSERT INTO article_history (
                        article_id, complex_id, complex_name, trade_type, 
                        price, price_text, area_pyeong, floor_info, feature,
                        first_seen, last_seen, last_price, price_change, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_DATE, CURRENT_DATE, ?, 0, 'active')
                """, (article_id, complex_id, complex_name, trade_type, 
                      price, price_text, area, floor, feature, price))
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"매물 이력 업데이트 실패: {e}")
            return False
        finally:
            self._pool.return_connection(conn)

    def get_article_history_stats(self, complex_id=None):
        """매물 히스토리 통계"""
        conn = self._pool.get_connection()
        try:
            today = DateTimeHelper.now_string("%Y-%m-%d")
            
            if complex_id:
                # 특정 단지 통계
                result = conn.cursor().execute('''
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN first_seen = ? THEN 1 ELSE 0 END) as new_today,
                        SUM(CASE WHEN price_change > 0 THEN 1 ELSE 0 END) as price_up,
                        SUM(CASE WHEN price_change < 0 THEN 1 ELSE 0 END) as price_down
                    FROM article_history WHERE complex_id = ?
                ''', (today, complex_id)).fetchone()
            else:
                # 전체 통계
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
            logger.error(f"매물 통계 조회 실패: {e}")
            return {'total': 0, 'new_today': 0, 'price_up': 0, 'price_down': 0}
        finally:
            self._pool.return_connection(conn)
    
    def cleanup_old_articles(self, days=30):
        """오래된 매물 히스토리 정리"""
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            c.execute('''
                DELETE FROM article_history 
                WHERE julianday('now') - julianday(last_seen) > ?
            ''', (days,))
            deleted = c.rowcount
            conn.commit()
            logger.info(f"오래된 매물 {deleted}개 정리 (>{days}일)")
            return deleted
        except Exception as e:
            logger.error(f"매물 정리 실패: {e}")
            return 0
        finally:
            self._pool.return_connection(conn)

    def toggle_favorite(self, article_id, complex_id, is_active=True):
        """매물 즐겨찾기 토글"""
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
            logger.error(f"즐겨찾기 토글 실패: {e}")
            return False
        finally:
            self._pool.return_connection(conn)

    def update_article_note(self, article_id, complex_id, note):
        """매물 메모 업데이트"""
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
            logger.error(f"메모 업데이트 실패: {e}")
            return False
        finally:
            self._pool.return_connection(conn)

    def get_favorites(self):
        """즐겨찾기 매물 목록"""
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
            logger.error(f"즐겨찾기 목록 조회 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)

    def backup_database(self, path):
        try:
            shutil.copy2(self.db_path, path)
            logger.info(f"백업 완료: {path}")
            return True
        except Exception as e:
            logger.error(f"백업 실패: {e}")
            return False
    
    def restore_database(self, path):
        """DB 복원 - 안전한 복원 로직"""
        logger.info(f"복원 시작: {path}")
        
        # 1. 원본 파일 존재 확인
        if not Path(path).exists():
            logger.error(f"복원 파일이 존재하지 않음: {path}")
            return False
        
        try:
            # 2. 기존 연결 풀 안전하게 종료
            logger.info("기존 연결 풀 종료 중...")
            if self._pool:
                try:
                    self._pool.close_all()
                except Exception as e:
                    logger.warning(f"연결 풀 종료 중 오류 (무시): {e}")
            
            # 3. 잠시 대기 (파일 핸들 해제를 위해)
            import time
            time.sleep(0.5)
            
            # 4. 기존 DB 파일 백업 (안전을 위해)
            backup_path = self.db_path.with_suffix('.db.backup')
            if self.db_path.exists():
                try:
                    shutil.copy2(self.db_path, backup_path)
                    logger.info(f"기존 DB 백업: {backup_path}")
                except Exception as e:
                    logger.warning(f"기존 DB 백업 실패 (무시): {e}")
            
            # 5. 새 파일 복사
            logger.info(f"파일 복사: {path} -> {self.db_path}")
            shutil.copy2(path, self.db_path)
            
            # 6. 새 연결 풀 생성
            logger.info("새 연결 풀 생성 중...")
            # ConnectionPool is defined in this file, so we can use it directly
            self._pool = ConnectionPool(self.db_path)
            
            # 7. 연결 테스트
            conn = self._pool.get_connection()
            test_result = conn.cursor().execute("SELECT COUNT(*) FROM complexes").fetchone()
            self._pool.return_connection(conn)
            logger.info(f"복원 완료! 단지 수: {test_result[0]}개")
            
            # 8. 백업 파일 삭제
            if backup_path.exists():
                try:
                    backup_path.unlink()
                except OSError as e:
                    get_logger('ComplexDatabase').debug(f"백업 파일 삭제 실패 (무시): {e}")
            
            return True
            
        except Exception as e:
            logger.exception(f"복원 실패: {e}")
            
            # 복원 실패 시 기존 백업에서 복구 시도
            backup_path = self.db_path.with_suffix('.db.backup')
            if backup_path.exists():
                try:
                    logger.info("백업에서 복구 시도...")
                    shutil.copy2(backup_path, self.db_path)
                    # ConnectionPool is defined in this file
                    self._pool = ConnectionPool(self.db_path)
                    logger.info("백업에서 복구 완료")
                except Exception as e2:
                    logger.error(f"백업 복구도 실패: {e2}")
            
            return False

    def get_all_alert_settings(self):
        conn = self._pool.get_connection()
        try:
            return conn.cursor().execute(
                'SELECT id, complex_id, complex_name, trade_type, area_min, area_max, price_min, price_max, enabled '
                'FROM alert_settings ORDER BY created_at DESC'
            ).fetchall()
        except Exception as e:
            logger.error(f"알림 설정 조회 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
    
    def toggle_alert_setting(self, aid, enabled):
        conn = self._pool.get_connection()
        try:
            conn.cursor().execute("UPDATE alert_settings SET enabled = ? WHERE id = ?", (1 if enabled else 0, aid))
            conn.commit()
        except Exception as e:
            logger.error(f"알림 설정 토글 실패: {e}")
        finally:
            self._pool.return_connection(conn)
    
    def delete_alert_setting(self, aid):
        conn = self._pool.get_connection()
        try:
            conn.cursor().execute("DELETE FROM alert_settings WHERE id = ?", (aid,))
            conn.commit()
        except Exception as e:
            logger.error(f"알림 설정 삭제 실패: {e}")
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
            logger.error(f"알림 체크 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)

    def get_article_favorite_info(self, article_id, complex_id):
        """특정 매물의 즐겨찾기/메모 정보 조회"""
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
            logger.error(f"매물 즐겨찾기 정보 조회 실패: {e}")
            return {'is_favorite': 0, 'note': ''}
        finally:
            self._pool.return_connection(conn)

    def mark_disappeared_articles(self):
        """오늘 확인되지 않은 매물을 소멸 처리"""
        conn = self._pool.get_connection()
        try:
            # 마지막 확인일이 오늘이 아닌 'active' 매물을 'disappeared'로 변경
            conn.cursor().execute("""
                UPDATE article_history 
                SET status='disappeared' 
                WHERE last_seen < CURRENT_DATE AND status='active'
            """)
            updated = conn.total_changes
            conn.commit()
            if updated > 0:
                logger.info(f"소멸 매물 처리: {updated}개")
            return updated
        except Exception as e:
            logger.error(f"소멸 매물 처리 실패: {e}")
            return 0
        finally:
            self._pool.return_connection(conn)
            
    def get_disappeared_articles(self, limit=50):
        """최근 소멸된 매물 조회"""
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
            logger.error(f"소멸 매물 조회 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)

    def count_disappeared_articles(self):
        """소멸 매물 개수 조회"""
        conn = self._pool.get_connection()
        try:
            row = conn.cursor().execute(
                "SELECT COUNT(*) FROM article_history WHERE status='disappeared'"
            ).fetchone()
            return row[0] if row else 0
        except Exception as e:
            logger.error(f"소멸 매물 개수 조회 실패: {e}")
            return 0
        finally:
            self._pool.return_connection(conn)

    def close(self):
        """DB 연결 풀 종료"""
        try:
            if self._pool:
                self._pool.close_all()
        except Exception as e:
            logger.debug(f"DB 종료 실패 (무시): {e}")
