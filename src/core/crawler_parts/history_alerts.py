from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.crawler import *  # noqa: F403


class CrawlerHistoryAlertsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    def register_discovered_complex(self, payload: dict):
        if not isinstance(payload, dict):
            return
        cid = str(payload.get("complex_id", "") or "")
        asset_type = str(payload.get("asset_type", "APT") or "APT").upper()
        name = str(payload.get("complex_name", "") or "")
        if not cid or not name:
            return
        dedupe_key = f"{asset_type}:{cid}"
        status = self._discovered_complex_status.get(dedupe_key, "skipped")
        if dedupe_key not in self._registered_discovered_complex_keys:
            self._registered_discovered_complex_keys.add(dedupe_key)
            if self.db:
                try:
                    status = str(
                        self.db.add_complex(
                            name,
                            cid,
                            asset_type=asset_type,
                            return_status=True,
                        )
                        or "skipped"
                    )
                except Exception as e:
                    self.log(f"⚠️ 발견 단지 자동 등록 실패: {name} ({cid}) - {e}", 30)
                    status = "error"
            self._discovered_complex_status[dedupe_key] = status
        emitted = dict(payload)
        emitted["db_status"] = status
        self.discovered_complex_signal.emit(emitted)

    def record_crawl_history(
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
        if not self.db:
            return
        try:
            self.db.add_crawl_history(
                name,
                cid,
                types,
                int(count or 0),
                engine=engine or self.engine_name,
                mode=mode or self.crawl_mode,
                source_lat=source_lat,
                source_lon=source_lon,
                source_zoom=source_zoom,
                asset_type=asset_type,
            )
            if hasattr(self.db, "is_write_disabled") and self.db.is_write_disabled():
                self._notify_db_write_disabled()
        except Exception as e:
            self.log(f"⚠️ 크롤링 기록 저장 실패: {e}", 30)

    def _finalize_disappeared_articles(self, processed_target_pairs):
        if self.track_disappeared and (not self._should_stop()) and self.db:
            try:
                if processed_target_pairs and hasattr(self.db, "mark_disappeared_articles_for_targets"):
                    disappeared = int(
                        self.db.mark_disappeared_articles_for_targets(
                            list(sorted(processed_target_pairs))
                        )
                        or 0
                    )
                else:
                    disappeared = int(self.db.mark_disappeared_articles() or 0)
                if disappeared > 0:
                    self.log(f"🗑️ 소멸 매물 {disappeared}건 처리")
            except Exception as e:
                if hasattr(self.db, "is_write_disabled") and self.db.is_write_disabled():
                    self._notify_db_write_disabled()
                self.log(f"⚠️ 소멸 매물 처리 실패: {e}", 30)

    def _process_raw_items(self, raw_items, requested_trade_type):
        matched_count = 0
        for raw_item in raw_items or []:
            if not isinstance(raw_item, dict):
                continue
            processed_item = self._enrich_item_with_history_and_alerts(dict(raw_item))
            trade_type = str(processed_item.get("거래유형", requested_trade_type) or requested_trade_type)
            if self._check_filters(processed_item, trade_type):
                if self._push_item(processed_item):
                    matched_count += 1
            else:
                self.stats["filtered_out"] += 1
        self._flush_history_updates(force=True)
        self._flush_pending_items_if_needed(force=True)
        return matched_count

    def _run_fallback_selenium(
        self,
        start_name="",
        start_cid="",
        start_trade="",
        *,
        prefill_complex=None,
        prefill_processed_target_pairs=None,
        reason="",
    ):
        original_engine = self.engine_name
        original_allowed_pairs = self._fallback_allowed_pairs
        original_prefill_complexes = self._fallback_prefill_complexes
        original_prefill_pairs = self._fallback_prefill_processed_target_pairs
        try:
            allowed_pairs = set(self._remaining_pairs())
            if start_name and start_cid and start_trade:
                allowed_pairs.add(self._pair_key(start_name, start_cid, start_trade))

            prefill_complexes: dict[tuple[str, str], dict[str, Any]] = {}
            for key, payload in dict(original_prefill_complexes or {}).items():
                if not isinstance(key, tuple) or len(key) < 2 or not isinstance(payload, dict):
                    continue
                ttypes = payload.get("trade_types", [])
                prefill_complexes[(str(key[0]), str(key[1]))] = {
                    "name": str(payload.get("name", "") or key[0]),
                    "cid": str(payload.get("cid", "") or key[1]),
                    "count": int(payload.get("count", 0) or 0),
                    "trade_types": {str(x) for x in (ttypes or []) if str(x)},
                }
            if isinstance(prefill_complex, dict):
                entry_name = str(prefill_complex.get("name", "") or "")
                entry_cid = str(prefill_complex.get("cid", "") or "")
                if entry_name and entry_cid:
                    key = (entry_name, entry_cid)
                    existing = prefill_complexes.get(key)
                    incoming_types = {
                        str(x)
                        for x in (prefill_complex.get("trade_types", []) or [])
                        if str(x)
                    }
                    incoming_count = int(prefill_complex.get("count", 0) or 0)
                    if isinstance(existing, dict):
                        existing["count"] = int(existing.get("count", 0) or 0) + incoming_count
                        existing_types = {
                            str(x)
                            for x in (existing.get("trade_types", []) or [])
                            if str(x)
                        }
                        existing_types.update(incoming_types)
                        existing["trade_types"] = existing_types
                    else:
                        prefill_complexes[key] = {
                            "name": entry_name,
                            "cid": entry_cid,
                            "count": incoming_count,
                            "trade_types": incoming_types,
                        }

            prefill_pairs = set()
            for pair in set(original_prefill_pairs or set()):
                if not isinstance(pair, tuple) or len(pair) < 2:
                    continue
                if len(pair) >= 3:
                    prefill_pairs.add((str(pair[0]), str(pair[1]), str(pair[2])))
                else:
                    prefill_pairs.add(("APT", str(pair[0]), str(pair[1])))
            for pair in set(prefill_processed_target_pairs or set()):
                if not isinstance(pair, tuple) or len(pair) < 2:
                    continue
                if len(pair) >= 3:
                    prefill_pairs.add((str(pair[0]), str(pair[1]), str(pair[2])))
                else:
                    prefill_pairs.add(("APT", str(pair[0]), str(pair[1])))

            self._fallback_allowed_pairs = allowed_pairs
            self._fallback_prefill_complexes = prefill_complexes
            self._fallback_prefill_processed_target_pairs = prefill_pairs
            self.stats["fallback_trigger_count"] = int(self.stats.get("fallback_trigger_count", 0)) + 1
            self.stats["fallback_last_reason"] = str(reason or "unknown_error")
            self.emit_stats()
            self.engine_name = "selenium"
            SeleniumCrawlerEngine(self).run()
        finally:
            self._fallback_allowed_pairs = original_allowed_pairs
            self._fallback_prefill_complexes = original_prefill_complexes
            self._fallback_prefill_processed_target_pairs = original_prefill_pairs
            self.engine_name = original_engine

    def _get_history_state_map(self, complex_id, trade_type, asset_type="APT"):
        key = (str(asset_type or "APT"), str(complex_id or ""), "*")
        if key in self._history_state_cache:
            return self._history_state_cache[key]
        history_map = {}
        if self.db and complex_id:
            try:
                history_map = self.db.get_article_history_state_bulk(
                    complex_id,
                    trade_type=None,
                    asset_type=asset_type,
                )
            except Exception as e:
                self.log(f"   ⚠️ 이력 상태 로드 실패: {e}", 30)
        self._history_state_cache[key] = history_map or {}
        return self._history_state_cache[key]

    def _get_alert_rules(self, complex_id, trade_type, asset_type=""):
        key = self._cache_key(complex_id, trade_type, asset_type)
        if key in self._alert_rules_cache:
            return self._alert_rules_cache[key]
        rules = []
        if self.db and complex_id and trade_type:
            try:
                rules = self.db.get_enabled_alert_rules(complex_id, trade_type, asset_type=asset_type)
            except Exception as e:
                self.log(f"   ⚠️ 알림 룰 로드 실패: {e}", 30)
        self._alert_rules_cache[key] = rules or []
        return self._alert_rules_cache[key]

    def _flush_history_updates_fallback(self, rows):
        if not self.db:
            return 0
        if hasattr(self.db, "is_write_disabled") and self.db.is_write_disabled():
            self._notify_db_write_disabled()
            return 0
        saved = 0
        for row in rows:
            try:
                ok = self.db.update_article_history(
                    article_id=row.get("article_id", ""),
                    complex_id=row.get("complex_id", ""),
                    complex_name=row.get("complex_name", ""),
                    trade_type=row.get("trade_type", ""),
                    price=int(row.get("price", 0) or 0),
                    price_text=row.get("price_text", ""),
                    area=float(row.get("area", row.get("area_pyeong", 0)) or 0),
                    floor=row.get("floor", ""),
                    feature=row.get("feature", ""),
                    extra=row,
                )
                if ok:
                    saved += 1
            except Exception:
                continue
        return saved

    def _notify_db_write_disabled(self):
        if self._db_write_disabled_notified:
            return
        self._db_write_disabled_notified = True
        reason = ""
        if self.db and hasattr(self.db, "get_write_disabled_reason"):
            try:
                reason = str(self.db.get_write_disabled_reason() or "")
            except Exception:
                reason = ""
        suffix = f" ({reason})" if reason else ""
        self.log(
            f"⚠️ DB 쓰기 기능이 비활성화되었습니다{suffix}. 수집은 계속되지만 이력/기록 저장이 제한됩니다.",
            40,
        )

    def _flush_history_updates(self, force=False):
        if not self._pending_history_rows:
            return 0
        if not force and len(self._pending_history_rows) < self.history_batch_size:
            return 0
        rows = list(self._pending_history_rows)
        self._pending_history_rows.clear()
        if not self.db:
            return 0
        if hasattr(self.db, "is_write_disabled") and self.db.is_write_disabled():
            self._notify_db_write_disabled()
            return 0

        try:
            saved = int(self.db.upsert_article_history_bulk(rows) or 0)
            if saved == len(rows):
                return saved
            if hasattr(self.db, "is_write_disabled") and self.db.is_write_disabled():
                self._notify_db_write_disabled()
                return 0
            self.log(
                f"   ⚠️ 이력 일괄 저장 일부 실패 ({saved}/{len(rows)}), 개별 재시도...",
                30,
            )
        except Exception as e:
            if hasattr(self.db, "is_write_disabled") and self.db.is_write_disabled():
                self._notify_db_write_disabled()
                return 0
            self.log(f"   ⚠️ 이력 일괄 저장 실패: {e} (개별 재시도)", 30)
        return self._flush_history_updates_fallback(rows)

    def _enrich_item_with_history_and_alerts(self, data):
        if not isinstance(data, dict):
            return data

        trade_type = str(data.get("거래유형", "") or "")
        complex_id = str(data.get("단지ID", "") or "")
        article_id = str(data.get("매물ID", "") or "")
        complex_name = str(data.get("단지명", "") or "")

        if trade_type == "매매":
            price_text = str(data.get("매매가", "") or "")
        else:
            deposit = str(data.get("보증금", "") or "")
            monthly = str(data.get("월세", "") or "")
            price_text = f"{deposit}/{monthly}" if monthly else deposit
        price_int = PriceConverter.to_int(price_text.split("/")[0] if "/" in price_text else price_text)
        asset_type = str(data.get("자산유형", "APT") or "APT").strip().upper() or "APT"
        if asset_type not in {"APT", "VL"}:
            asset_type = "APT"

        area_pyeong = 0.0
        try:
            area_pyeong = float(data.get("면적(평)", 0) or 0)
        except (TypeError, ValueError):
            area_pyeong = 0.0

        is_new = False
        raw_price_change = 0
        if article_id and complex_id and price_int > 0:
            history_map = self._get_history_state_map(complex_id, trade_type, asset_type)
            prev = history_map.get(article_id)
            prev_price = int(self._row_get(prev, "price", 0) or 0)
            is_new = prev is None
            raw_price_change = 0 if is_new else price_int - prev_price

            history_map[article_id] = {
                "price": price_int,
                "status": "active",
                "last_price": prev_price if prev_price > 0 else price_int,
                "price_change": raw_price_change,
            }

            self._pending_history_rows.append(
                {
                    "article_id": article_id,
                    "complex_id": complex_id,
                    "complex_name": complex_name,
                    "trade_type": trade_type,
                    "price": price_int,
                    "price_text": price_text,
                    "area": area_pyeong,
                    "floor": str(data.get("층/방향", "") or ""),
                    "feature": str(data.get("타입/특징", "") or ""),
                    "last_price": prev_price if prev_price > 0 else price_int,
                    "asset_type": asset_type,
                    "source_mode": str(data.get("수집모드", self.crawl_mode) or self.crawl_mode),
                    "source_lat": float(data.get("위도", 0.0) or 0.0),
                    "source_lon": float(data.get("경도", 0.0) or 0.0),
                    "source_zoom": int(data.get("줌", 0) or 0),
                    "marker_id": str(data.get("마커ID", "") or ""),
                    "broker_office": str(data.get("부동산상호", "") or ""),
                    "broker_name": str(data.get("중개사이름", "") or ""),
                    "broker_phone1": str(data.get("전화1", "") or ""),
                    "broker_phone2": str(data.get("전화2", "") or ""),
                    "prev_jeonse_won": int(data.get("기전세금(원)", 0) or 0),
                    "jeonse_period_years": int(data.get("전세_기간(년)", 0) or 0),
                    "jeonse_max_won": int(data.get("전세_기간내_최고(원)", 0) or 0),
                    "jeonse_min_won": int(data.get("전세_기간내_최저(원)", 0) or 0),
                    "gap_amount_won": int(data.get("갭금액(원)", 0) or 0),
                    "gap_ratio": float(data.get("갭비율", 0.0) or 0.0),
                }
            )
            self._flush_history_updates(force=False)

        price_change = int(raw_price_change)
        if self.price_change_threshold > 0 and abs(price_change) < self.price_change_threshold:
            price_change = 0
        if is_new:
            self.stats["new_count"] = int(self.stats.get("new_count", 0)) + 1
        if price_change > 0:
            self.stats["price_up"] = int(self.stats.get("price_up", 0)) + 1
        elif price_change < 0:
            self.stats["price_down"] = int(self.stats.get("price_down", 0)) + 1

        visible_is_new = bool(is_new) if self.show_new_badge else False
        visible_price_change = int(price_change) if self.show_price_change else 0

        data["is_new"] = visible_is_new
        data["신규여부"] = visible_is_new
        data["price_change"] = visible_price_change
        data["가격변동"] = visible_price_change

        if complex_id and trade_type and area_pyeong > 0 and price_int > 0:
            rules = self._get_alert_rules(complex_id, trade_type, asset_type)
            for rule in rules:
                area_min = float(self._row_get(rule, "area_min", 0) or 0)
                area_max = float(self._row_get(rule, "area_max", 999999) or 999999)
                price_min = int(self._row_get(rule, "price_min", 0) or 0)
                price_max = int(self._row_get(rule, "price_max", 999999999) or 999999999)
                if not (area_min <= area_pyeong <= area_max):
                    continue
                if not (price_min <= price_int <= price_max):
                    continue
                alert_id = int(self._row_get(rule, "id", 0) or 0)
                alert_name = str(self._row_get(rule, "complex_name", complex_name) or complex_name)
                should_emit = True
                if alert_id > 0 and article_id:
                    if hasattr(self.db, "is_write_disabled") and self.db.is_write_disabled():
                        should_emit = True
                    else:
                        try:
                            should_emit = bool(
                                self.db.record_alert_notification(
                                    alert_id=alert_id,
                                    article_id=article_id,
                                    complex_id=complex_id,
                                    asset_type=asset_type,
                                )
                            )
                        except Exception as e:
                            should_emit = True
                            self.log(f"   ⚠️ 알림 dedup 기록 실패 (emit 유지): {e}", 30)
                elif alert_id > 0 and not article_id:
                    self.log("   ℹ️ 매물ID 없음: 알림 dedup 생략", 10)

                if not should_emit:
                    continue
                self.alert_triggered_signal.emit(
                    alert_name,
                    trade_type,
                    price_text,
                    float(area_pyeong),
                    alert_id,
                )

        return data
    
