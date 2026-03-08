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
    
