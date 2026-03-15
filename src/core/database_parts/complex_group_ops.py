from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


class ComplexDatabaseComplexGroupOpsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    @staticmethod
    def _normalize_asset_type(asset_type) -> str:
        token = str(asset_type or "APT").strip().upper()
        return token if token in {"APT", "VL"} else "APT"

    def add_complex(
        self,
        name,
        complex_id,
        memo="",
        *,
        asset_type: str = "APT",
        return_status: bool = False,
    ):
        """단지 추가 - 중복 처리를 강화한다."""
        if self.is_write_disabled():
            return "error" if return_status else False
        conn = self._pool.get_connection()
        try:
            with self._write_lock:
                try:
                    conn.execute("PRAGMA busy_timeout=1200")
                except Exception:
                    pass
                normalized_asset_type = self._normalize_asset_type(asset_type)
                for attempt in range(3):
                    try:
                        c = conn.cursor()
                        c.execute(
                            "SELECT id FROM complexes WHERE asset_type = ? AND complex_id = ?",
                            (normalized_asset_type, complex_id),
                        )
                        existing = c.fetchone()
                        if existing:
                            logger.debug(f"단지 이미 존재: {name} ({complex_id})")
                            return "existing" if return_status else True

                        c.execute(
                            "INSERT INTO complexes (name, asset_type, complex_id, memo) VALUES (?, ?, ?, ?)",
                            (name, normalized_asset_type, complex_id, memo),
                        )
                        conn.commit()
                        logger.info(f"단지 추가 성공: {name} ({complex_id})")
                        return "inserted" if return_status else True
                    except sqlite3.IntegrityError:
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        logger.debug(f"단지 중복 (정상): {name} ({complex_id})")
                        return "existing" if return_status else True
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
                        logger.error(f"단지 추가 실패(operational): {name} ({complex_id}) - {e}")
                        return "error" if return_status else False
                    except sqlite3.DatabaseError as e:
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        if self._is_corruption_sqlite_error(e):
                            self._disable_writes("database_corruption", e)
                        logger.error(f"단지 추가 실패(database): {name} ({complex_id}) - {e}")
                        return "error" if return_status else False
        except Exception as e:
            logger.exception(f"단지 추가 실패: {name} ({complex_id}) - {e}")
            return "error" if return_status else False
        finally:
            try:
                conn.execute("PRAGMA busy_timeout=30000")
            except Exception:
                pass
            self._pool.return_connection(conn)
    
    def get_all_complexes(self):
        """모든 단지를 조회한다."""
        conn = self._pool.get_connection()
        try:
            result = self._fetchall_safe(
                conn,
                "SELECT id, name, asset_type, complex_id, memo FROM complexes ORDER BY name, asset_type",
                context="단지 조회(complexes)",
            )
            logger.debug(f"complex list loaded: {len(result)}")
            return result
        except Exception as e:
            self._log_corruption_detected("단지 조회", e)
            logger.exception(f"단지 조회 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)

    def get_complexes_for_stats(self):
        """통계용 단지 목록을 조회한다 (DB + 크롤링 이력 + 스냅샷)."""
        conn = self._pool.get_connection()
        try:
            complex_map: dict[tuple[str, str], str] = {}
            cid_assets: dict[str, set[str]] = {}

            def _upsert(asset_type: str, complex_id: str, name: str):
                cid = str(complex_id or "").strip()
                if not cid:
                    return
                asset = self._normalize_asset_type(asset_type)
                key = (asset, cid)
                if key in complex_map:
                    return
                label = str(name or "").strip() or f"단지_{cid}"
                complex_map[key] = label
                cid_assets.setdefault(cid, set()).add(asset)

            # 1) 단지 기본 목록
            rows = self._fetchall_safe(
                conn,
                "SELECT name, asset_type, complex_id FROM complexes ORDER BY name, asset_type",
                context="통계 단지 조회(complexes)",
            )
            for row in rows:
                _upsert(row["asset_type"], row["complex_id"], row["name"])

            # 2) 크롤링 이력(최신 이름 우선)
            history_rows = self._fetchall_safe(
                conn,
                '''
                SELECT
                    complex_id,
                    complex_name,
                    COALESCE(NULLIF(asset_type, ''), 'APT') AS asset_type
                FROM crawl_history ch
                ORDER BY crawled_at DESC
                ''',
                context="통계 단지 조회(crawl_history)",
            )
            for row in history_rows:
                _upsert(row["asset_type"], row["complex_id"], row["complex_name"])

            # 3) 스냅샷에만 남아 있는 단지 보강
            snapshot_rows = self._fetchall_safe(
                conn,
                "SELECT DISTINCT COALESCE(NULLIF(asset_type, ''), 'APT') AS asset_type, complex_id FROM price_snapshots",
                context="통계 단지 조회(price_snapshots)",
            )
            for row in snapshot_rows:
                _upsert(row["asset_type"], row["complex_id"], "")

            collided_cids = {cid for cid, assets in cid_assets.items() if len(assets) > 1}
            result: list[tuple[str, str]] = []
            for (asset_type, cid), name in complex_map.items():
                data_key = cid
                display_name = name
                if cid in collided_cids:
                    data_key = f"{asset_type}:{cid}"
                    display_name = f"{name} ({asset_type})"
                result.append((display_name, data_key))
            result.sort(key=lambda x: x[0])
            logger.debug(f"complex stats source rows: {len(result)}")
            return result
        except Exception as e:
            self._log_corruption_detected("통계 단지 조회", e)
            logger.exception(f"통계 단지 조회 실패: {e}")
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
            cursor.execute(f"DELETE FROM price_snapshots WHERE {where_asset}", params)
            cursor.execute(f"DELETE FROM alert_settings WHERE {where_asset}", params)
            cursor.execute(f"DELETE FROM article_favorites WHERE {where_asset}", params)
            cursor.execute(f"DELETE FROM article_alert_log WHERE {where_asset}", params)

        unique_complex_ids = sorted(
            {str(complex_id or "").strip() for _, complex_id in refs if str(complex_id or "").strip()}
        )
        if not unique_complex_ids:
            return

        placeholders = ",".join("?" * len(unique_complex_ids))
        remaining_rows = cursor.execute(
            f"SELECT DISTINCT complex_id FROM complexes WHERE complex_id IN ({placeholders})",
            unique_complex_ids,
        ).fetchall()
        remaining_ids = {
            str(row["complex_id"]) if hasattr(row, "keys") else str(row[0])
            for row in remaining_rows
        }
        fully_removed_ids = [cid for cid in unique_complex_ids if cid not in remaining_ids]
        if not fully_removed_ids:
            return

        removed_placeholders = ",".join("?" * len(fully_removed_ids))
        cursor.execute(
            f"""
            DELETE FROM alert_settings
            WHERE complex_id IN ({removed_placeholders})
              AND (asset_type = 'ALL' OR COALESCE(asset_type, '') = '')
            """,
            fully_removed_ids,
        )
        cursor.execute(
            f"""
            DELETE FROM article_alert_log
            WHERE complex_id IN ({removed_placeholders})
              AND (asset_type = 'ALL' OR COALESCE(asset_type, '') = '')
            """,
            fully_removed_ids,
        )

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
            logger.info(f"단지 삭제: ID={db_id}")
            return True
        except Exception as e:
            logger.error(f"단지 삭제 실패: {e}")
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
            result = self._fetchall_safe(
                conn,
                "SELECT id, name, description FROM groups ORDER BY name",
                context="그룹 조회(groups)",
            )
            logger.debug(f"group list loaded: {len(result)}")
            return result
        except Exception as e:
            self._log_corruption_detected("그룹 조회", e)
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
                    logger.warning(f"그룹 단지 추가 실패: {cid} - {e}")
            conn.commit()
            logger.info(f"group complexes added: {count}")
            return count
        except Exception as e:
            logger.error(f"그룹 단지 추가 실패: {e}")
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
                'SELECT c.id, c.name, c.asset_type, c.complex_id, c.memo FROM complexes c '
                'JOIN group_complexes gc ON c.id = gc.complex_id '
                'WHERE gc.group_id = ? ORDER BY c.name', (group_id,)
            ).fetchall()
            return result
        except Exception as e:
            logger.error(f"그룹 내 단지 조회 실패: {e}")
            return []
        finally:
            self._pool.return_connection(conn)
    
