from __future__ import annotations


class ComplexDatabaseCrawlSnapshotOpsMixin:
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
    
