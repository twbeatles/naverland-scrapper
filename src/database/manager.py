import sqlite3
import shutil
import time
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from threading import Lock

from src.database.connection import ConnectionPool
from src.config import DB_PATH
from src.utils.logger import get_logger

class ComplexDatabase:
    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        print(f"[DB] ComplexDatabase 초기화: {self.db_path}")
        self._pool = ConnectionPool(self.db_path)
        self._restore_lock = Lock()  # 복원 작업 중 동시 접근 방지
        self._init_tables()
    
    def close(self):
        """DB 연결 풀 안전 종료"""
        if self._pool:
            self._pool.close_all()
            self._pool = None
            print("[DB] ComplexDatabase 종료 완료")
    
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
                snapshot_date DATE DEFAULT CURRENT_DATE,
                UNIQUE(complex_id, trade_type, pyeong, snapshot_date)
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
                print("[DB] 마이그레이션: article_history 테이블에 status 컬럼 추가...")
                try:
                    c.execute("ALTER TABLE article_history ADD COLUMN status TEXT DEFAULT 'active'")
                    conn.commit()
                    print("[DB] 마이그레이션 완료: status 컬럼 추가됨")
                except Exception as me:
                    print(f"[DB] 마이그레이션 오류 (무시): {me}")
            
            # status 컬럼 인덱스 생성 (마이그레이션 후)
            try:
                c.execute('CREATE INDEX IF NOT EXISTS idx_article_status ON article_history(status)')
            except Exception:
                pass  # 인덱스 생성 실패해도 무시
            
            c.execute('CREATE INDEX IF NOT EXISTS idx_favorites ON article_favorites(article_id, complex_id)')
            conn.commit()
            print("[DB] 테이블 초기화 완료")
        except Exception as e:
            print(f"[DB ERROR] 테이블 초기화 실패: {e}")
            import traceback
            traceback.print_exc()
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
                print(f"[DB] 단지 이미 존재: {name} ({complex_id})")
                return True  # 이미 존재하면 성공으로 처리
            
            c.execute("INSERT INTO complexes (name, complex_id, memo) VALUES (?, ?, ?)", 
                     (name, complex_id, memo))
            conn.commit()
            print(f"[DB] 단지 추가 성공: {name} ({complex_id})")
            return True
        except sqlite3.IntegrityError as e:
            print(f"[DB] 단지 중복 (정상): {name} ({complex_id})")
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR] 단지 추가 실패: {name} ({complex_id}) - {e}")
            import traceback
            traceback.print_exc()
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
            print(f"[DB] 단지 조회: {len(result)}개")
            return result
        except Exception as e:
            print(f"[DB ERROR] 단지 조회 실패: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            self._pool.return_connection(conn)
    
    def delete_complex(self, db_id):
        conn = self._pool.get_connection()
        try:
            conn.cursor().execute("DELETE FROM complexes WHERE id = ?", (db_id,))
            conn.commit()
            print(f"[DB] 단지 삭제: ID={db_id}")
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR] 단지 삭제 실패: {e}")
            return False
        finally:
            self._pool.return_connection(conn)
    
    def delete_complexes_bulk(self, db_ids):
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            placeholders = ','.join('?' * len(db_ids))
            c.execute(f"DELETE FROM complexes WHERE id IN ({placeholders})", db_ids)
            conn.commit()
            print(f"[DB] 단지 일괄 삭제: {c.rowcount}개")
            return c.rowcount
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR] 단지 일괄 삭제 실패: {e}")
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
            conn.rollback()
            print(f"[DB ERROR] 메모 업데이트 실패: {e}")
            return False
        finally:
            self._pool.return_connection(conn)
    
    def create_group(self, name, desc=""):
        conn = self._pool.get_connection()
        try:
            conn.cursor().execute("INSERT INTO groups (name, description) VALUES (?, ?)", (name, desc))
            conn.commit()
            print(f"[DB] 그룹 생성: {name}")
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR] 그룹 생성 실패: {e}")
            return False
        finally:
            self._pool.return_connection(conn)
    
    def get_all_groups(self):
        conn = self._pool.get_connection()
        try:
            result = conn.cursor().execute("SELECT id, name, description FROM groups ORDER BY name").fetchall()
            print(f"[DB] 그룹 조회: {len(result)}개")
            return result
        except Exception as e:
            print(f"[DB ERROR] 그룹 조회 실패: {e}")
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
            print(f"[DB] 그룹 삭제: ID={group_id}")
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR] 그룹 삭제 실패: {e}")
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
                    print(f"[DB WARN] 그룹에 단지 추가 실패: {cid} - {e}")
            conn.commit()
            print(f"[DB] 그룹에 단지 추가: {count}개")
            return count
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR] 그룹에 단지 추가 실패: {e}")
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
            conn.rollback()
            print(f"[DB ERROR] 그룹에서 단지 제거 실패: {e}")
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
            print(f"[DB ERROR] 그룹 내 단지 조회 실패: {e}")
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
            conn.rollback()
            print(f"[DB ERROR] 크롤링 기록 저장 실패: {e}")
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
            print(f"[DB ERROR] 크롤링 기록 조회 실패: {e}")
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
                    pass
                
            sql += ' ORDER BY snapshot_date DESC, pyeong'
            
            result = conn.cursor().execute(sql, params).fetchall()
            print(f"[DB] 가격 히스토리 조회: {len(result)}개 (조건: {trade_type}, {pyeong})")
            return result
        except Exception as e:
            print(f"[DB ERROR] 가격 히스토리 조회 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
    
    def add_price_snapshot(self, complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count):
        """가격 스냅샷 저장 (UPSERT - 같은 날 중복 방지)"""
        conn = self._pool.get_connection()
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            c = conn.cursor()
            c.execute(
                '''INSERT INTO price_snapshots (complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count, snapshot_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(complex_id, trade_type, pyeong, snapshot_date) DO UPDATE SET
                   min_price = excluded.min_price,
                   max_price = excluded.max_price,
                   avg_price = excluded.avg_price,
                   item_count = excluded.item_count''',
                (complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count, today)
            )
            conn.commit()
            return True
        except sqlite3.OperationalError:
            try:
                conn.cursor().execute(
                    'INSERT INTO price_snapshots (complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count)
                )
                conn.commit()
                return True
            except Exception as e:
                conn.rollback()
                print(f"[DB ERROR] 가격 스냅샷 저장 실패: {e}")
                return False
        except Exception as e:
            print(f"[DB ERROR] 가격 스냅샷 저장 실패: {e}")
            return False
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
            print(f"[DB] 알림 설정 추가: {name}")
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR] 알림 설정 추가 실패: {e}")
            return False
        finally:
            self._pool.return_connection(conn)
    
    def get_all_alert_settings(self):
        conn = self._pool.get_connection()
        try:
            return conn.cursor().execute(
                'SELECT id, complex_id, complex_name, trade_type, area_min, area_max, price_min, price_max, enabled '
                'FROM alert_settings ORDER BY created_at DESC'
            ).fetchall()
        except Exception as e:
            print(f"[DB ERROR] 알림 설정 조회 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
    
    def toggle_alert_setting(self, aid, enabled):
        conn = self._pool.get_connection()
        try:
            conn.cursor().execute("UPDATE alert_settings SET enabled = ? WHERE id = ?", (1 if enabled else 0, aid))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR] 알림 설정 토글 실패: {e}")
        finally:
            self._pool.return_connection(conn)
    
    def delete_alert_setting(self, aid):
        conn = self._pool.get_connection()
        try:
            conn.cursor().execute("DELETE FROM alert_settings WHERE id = ?", (aid,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR] 알림 설정 삭제 실패: {e}")
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
            print(f"[DB ERROR] 알림 체크 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
            
    def check_article_history(self, article_id, complex_id, current_price):
        """
        매물 히스토리 확인 및 업데이트
        Returns: (is_new, price_change, previous_price)
        """
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            c.execute(
                'SELECT price, first_seen FROM article_history WHERE article_id = ? AND complex_id = ?',
                (article_id, complex_id)
            )
            row = c.fetchone()
            
            today = datetime.now().strftime('%Y-%m-%d')
            
            if row is None:
                return True, 0, 0
            else:
                previous_price = row[0] if row[0] else 0
                first_seen = row[1]
                price_change = current_price - previous_price if previous_price else 0
                is_new = (first_seen == today)
                return is_new, price_change, previous_price
                
        except Exception as e:
            print(f"[DB ERROR] 매물 히스토리 확인 실패: {e}")
            return False, 0, 0
        finally:
            self._pool.return_connection(conn)
    
    def update_article_history(self, article_id, complex_id, complex_name, trade_type, 
                               price, price_text, area_pyeong, floor_info, feature):
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            today = datetime.now().strftime('%Y-%m-%d')
            
            c.execute(
                'SELECT id, price FROM article_history WHERE article_id = ? AND complex_id = ?',
                (article_id, complex_id)
            )
            existing = c.fetchone()
            
            if existing:
                old_price = existing[1] if existing[1] else 0
                price_change = price - old_price if old_price else 0
                
                c.execute('''
                    UPDATE article_history SET
                        last_seen = ?,
                        last_price = price,
                        price = ?,
                        price_text = ?,
                        price_change = ?,
                        floor_info = ?,
                        feature = ?
                    WHERE article_id = ? AND complex_id = ?
                ''', (today, price, price_text, price_change, floor_info, feature, article_id, complex_id))
            else:
                c.execute('''
                    INSERT INTO article_history 
                    (article_id, complex_id, complex_name, trade_type, price, price_text, 
                     area_pyeong, floor_info, feature, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (article_id, complex_id, complex_name, trade_type, price, price_text,
                      area_pyeong, floor_info, feature, today, today))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR] 매물 히스토리 업데이트 실패: {e}")
            return False
        finally:
            self._pool.return_connection(conn)
    
    def get_article_history_stats(self, complex_id=None):
        conn = self._pool.get_connection()
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            if complex_id:
                result = conn.cursor().execute('''
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN first_seen = ? THEN 1 ELSE 0 END) as new_today,
                        SUM(CASE WHEN price_change > 0 THEN 1 ELSE 0 END) as price_up,
                        SUM(CASE WHEN price_change < 0 THEN 1 ELSE 0 END) as price_down
                    FROM article_history WHERE complex_id = ?
                ''', (today, complex_id)).fetchone()
            else:
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
            print(f"[DB ERROR] 매물 통계 조회 실패: {e}")
            return {'total': 0, 'new_today': 0, 'price_up': 0, 'price_down': 0}
        finally:
            self._pool.return_connection(conn)
    
    def cleanup_old_articles(self, days=30):
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            c.execute('''
                DELETE FROM article_history 
                WHERE julianday('now') - julianday(last_seen) > ?
            ''', (days,))
            deleted = c.rowcount
            conn.commit()
            print(f"[DB] 오래된 매물 {deleted}개 정리 (>{days}일)")
            return deleted
        except Exception as e:
            print(f"[DB ERROR] 매물 정리 실패: {e}")
            return 0
        finally:
            self._pool.return_connection(conn)
            
    def backup_database(self, path):
        try:
            shutil.copy2(self.db_path, path)
            print(f"[DB] 백업 완료: {path}")
            return True
        except Exception as e:
            print(f"[DB ERROR] 백업 실패: {e}")
            return False

    def restore_database(self, path):
        """DB 복원 - 안전한 복원 로직 (스레드 안전)"""
        # 복원 중 다른 작업 차단
        if not self._restore_lock.acquire(blocking=False):
            print("[DB ERROR] 복원 작업이 이미 진행 중입니다.")
            return False
        
        try:
            print(f"[DB] 복원 시작: {path}")
            
            if not Path(path).exists():
                print(f"[DB ERROR] 복원 파일이 존재하지 않음: {path}")
                return False
            
            print("[DB] 기존 연결 풀 종료 중...")
            if self._pool:
                try:
                    self._pool.close_all()
                except Exception as e:
                    print(f"[DB WARN] 연결 풀 종료 중 오류 (무시): {e}")
            
            time.sleep(0.5)
            
            backup_path = self.db_path.with_suffix('.db.backup')
            if self.db_path.exists():
                try:
                    shutil.copy2(self.db_path, backup_path)
                    print(f"[DB] 기존 DB 백업: {backup_path}")
                except Exception as e:
                    print(f"[DB WARN] 기존 DB 백업 실패 (무시): {e}")
            
            print(f"[DB] 파일 복사: {path} -> {self.db_path}")
            shutil.copy2(path, self.db_path)
            
            print("[DB] 새 연결 풀 생성 중...")
            self._pool = ConnectionPool(self.db_path)
            
            conn = self._pool.get_connection()
            test_result = conn.cursor().execute("SELECT COUNT(*) FROM complexes").fetchone()
            self._pool.return_connection(conn)
            print(f"[DB] 복원 완료! 단지 수: {test_result[0]}개")
            
            if backup_path.exists():
                try:
                    backup_path.unlink()
                except OSError:
                    pass
            
            return True
            
        except Exception as e:
            print(f"[DB ERROR] 복원 실패: {e}")
            import traceback
            traceback.print_exc()
            
            # 복원 실패 시 기존 백업에서 복구 시도
            backup_path = self.db_path.with_suffix('.db.backup')
            if backup_path.exists():
                try:
                    print("[DB] 백업에서 복구 시도...")
                    shutil.copy2(backup_path, self.db_path)
                    self._pool = ConnectionPool(self.db_path)
                    print("[DB] 백업에서 복구 완료")
                except Exception:
                    pass
            
            return False
        finally:
            self._restore_lock.release()

    def toggle_favorite(self, article_id: str, complex_id: str, is_favorite: bool) -> bool:
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            if is_favorite:
                c.execute('''
                    INSERT OR REPLACE INTO article_favorites (article_id, complex_id, is_favorite, updated_at)
                    VALUES (?, ?, 1, CURRENT_TIMESTAMP)
                ''', (article_id, complex_id))
            else:
                c.execute('DELETE FROM article_favorites WHERE article_id = ? AND complex_id = ?',
                         (article_id, complex_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR] 즐겨찾기 토글 실패: {e}")
            return False
        finally:
            self._pool.return_connection(conn)
    
    def update_article_note(self, article_id: str, complex_id: str, note: str) -> bool:
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            c.execute('''
                INSERT INTO article_favorites (article_id, complex_id, note, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(article_id, complex_id) DO UPDATE SET note = ?, updated_at = CURRENT_TIMESTAMP
            ''', (article_id, complex_id, note, note))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR] 메모 업데이트 실패: {e}")
            return False
        finally:
            self._pool.return_connection(conn)
    
    def get_favorites(self) -> List[dict]:
        conn = self._pool.get_connection()
        try:
            rows = conn.cursor().execute('''
                SELECT f.article_id, f.complex_id, f.note, f.created_at,
                       h.complex_name, h.trade_type, h.price, h.price_text, h.area_pyeong, h.floor_info
                FROM article_favorites f
                LEFT JOIN article_history h ON f.article_id = h.article_id AND f.complex_id = h.complex_id
                WHERE f.is_favorite = 1
                ORDER BY f.updated_at DESC
            ''').fetchall()
            return [dict(row) for row in rows] if rows else []
        except Exception as e:
            print(f"[DB ERROR] 즐겨찾기 조회 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
    
    def get_article_favorite_info(self, article_id: str, complex_id: str) -> dict:
        conn = self._pool.get_connection()
        try:
            row = conn.cursor().execute('''
                SELECT is_favorite, note FROM article_favorites
                WHERE article_id = ? AND complex_id = ?
            ''', (article_id, complex_id)).fetchone()
            if row:
                return {'is_favorite': bool(row[0]), 'note': row[1] or ''}
            return {'is_favorite': False, 'note': ''}
        except Exception as e:
            print(f"[DB ERROR] 즐겨찾기 정보 조회 실패: {e}")
            return {'is_favorite': False, 'note': ''}
        finally:
            self._pool.return_connection(conn)
    
    def mark_disappeared_articles(self, complex_id: str, active_article_ids: List[str]) -> int:
        if not active_article_ids:
            return 0
        conn = self._pool.get_connection()
        try:
            c = conn.cursor()
            placeholders = ','.join('?' * len(active_article_ids))
            c.execute(f'''
                UPDATE article_history SET status = 'disappeared'
                WHERE complex_id = ? AND status = 'active' AND article_id NOT IN ({placeholders})
            ''', [complex_id] + active_article_ids)
            disappeared_count = c.rowcount
            c.execute(f'''
                UPDATE article_history SET status = 'active'
                WHERE complex_id = ? AND article_id IN ({placeholders})
            ''', [complex_id] + active_article_ids)
            conn.commit()
            return disappeared_count
        except Exception as e:
            conn.rollback()
            print(f"[DB ERROR] 소멸 매물 표시 실패: {e}")
            return 0
        finally:
            self._pool.return_connection(conn)
    
    def get_disappeared_articles(self, days: int = 7) -> List[dict]:
        conn = self._pool.get_connection()
        try:
            rows = conn.cursor().execute('''
                SELECT article_id, complex_id, complex_name, trade_type, price, price_text, 
                       area_pyeong, floor_info, feature, last_seen
                FROM article_history
                WHERE status = 'disappeared' 
                AND julianday('now') - julianday(last_seen) <= ?
                ORDER BY last_seen DESC
            ''', (days,)).fetchall()
            return [dict(row) for row in rows] if rows else []
        except Exception as e:
            print(f"[DB ERROR] 소멸 매물 조회 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
