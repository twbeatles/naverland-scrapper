from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403


class ComplexDatabaseArticleOpsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

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

