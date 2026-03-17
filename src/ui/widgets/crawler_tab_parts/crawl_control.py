from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


class CrawlerTabCrawlControlMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def _add_complex(self: Any):
        name = self.input_name.text().strip()
        cid = self.input_id.text().strip()
        if not cid:
            return
        if not self._complex_id_regex.match(cid).hasMatch():
            QMessageBox.warning(self, "입력 오류", "단지 ID는 숫자만 입력할 수 있습니다.")
            self.input_id.setFocus()
            self.input_id.selectAll()
            return
        self._add_row(name, cid)
        self.input_name.clear()
        self.input_id.clear()

    def _normalize_task_name(self: Any, name, cid):
        cid_text = str(cid or "").strip()
        name_text = str(name or "").strip()
        return name_text or f"단지_{cid_text}"

    def _find_task_row_by_cid(self: Any, cid):
        cid_text = str(cid or "").strip()
        if not cid_text:
            return -1
        for row in range(self.table_list.rowCount()):
            item = self.table_list.item(row, 1)
            if item and item.text().strip() == cid_text:
                return row
        return -1

    def _append_task_row(self: Any, name, cid):
        row = self.table_list.rowCount()
        self.table_list.insertRow(row)
        self.table_list.setItem(row, 0, QTableWidgetItem(str(name)))
        self.table_list.setItem(row, 1, QTableWidgetItem(str(cid)))

    def _emit_task_duplicate_skip(self: Any, name, cid):
        existing_row = self._find_task_row_by_cid(cid)
        kept_name = ""
        if existing_row >= 0:
            kept_item = self.table_list.item(existing_row, 0)
            kept_name = kept_item.text().strip() if kept_item else ""
        display_name = kept_name or self._normalize_task_name(name, cid)
        message = f"중복 스킵: {display_name} ({cid})"
        self.append_log(message, 10)
        self.status_message.emit(message)

    def add_task(self: Any, name, cid, *, log_duplicate=True):
        cid_text = str(cid or "").strip()
        if not cid_text:
            return False
        name_text = self._normalize_task_name(name, cid_text)
        if self._find_task_row_by_cid(cid_text) >= 0:
            if log_duplicate:
                self._emit_task_duplicate_skip(name_text, cid_text)
            return False
        self._append_task_row(name_text, cid_text)
        return True

    def _add_row(self: Any, name, cid):
        return self.add_task(name, cid)

    def _dedupe_target_entries(self: Any, rows):
        deduped = []
        seen = set()
        removed = 0
        for name, cid in rows:
            cid_text = str(cid or "").strip()
            if not cid_text:
                continue
            if cid_text in seen:
                removed += 1
                continue
            seen.add(cid_text)
            deduped.append((self._normalize_task_name(name, cid_text), cid_text))
        return deduped, removed

    def _normalize_task_table(self: Any):
        rows = []
        for row in range(self.table_list.rowCount()):
            name_item = self.table_list.item(row, 0)
            cid_item = self.table_list.item(row, 1)
            rows.append(
                (
                    name_item.text().strip() if name_item else "",
                    cid_item.text().strip() if cid_item else "",
                )
            )
        deduped, removed = self._dedupe_target_entries(rows)
        if removed > 0 or len(deduped) != self.table_list.rowCount():
            self.table_list.setRowCount(0)
            for name, cid in deduped:
                self._append_task_row(name, cid)
        if removed > 0:
            message = f"중복 스킵: {removed}개 작업을 정리했습니다."
            self.append_log(message, 20)
            self.status_message.emit(message)
        return deduped
    
    def clear_tasks(self: Any):
        self.table_list.setRowCount(0)

    def _delete_complex(self: Any):
        row = self.table_list.currentRow()
        if row >= 0:
            self.table_list.removeRow(row)
    
    def _clear_list(self: Any):
        self.table_list.setRowCount(0)

    def _save_to_db(self: Any):
        inserted_count = 0
        existing_count = 0
        failed_count = 0
        total = self.table_list.rowCount()
        for r in range(total):
            name = self.table_list.item(r, 0).text()
            cid = self.table_list.item(r, 1).text()
            status = self.db.add_complex(name, cid, return_status=True)
            if status == "inserted":
                inserted_count += 1
            elif status == "existing":
                existing_count += 1
            else:
                failed_count += 1
        QMessageBox.information(
            self,
            "저장 완료",
            f"신규 저장: {inserted_count}개\n기존 존재: {existing_count}개\n실패: {failed_count}개",
        )

    def _show_db_load_dialog(self: Any):
        complexes = self.db.get_all_complexes()
        if not complexes:
            QMessageBox.information(self, "알림", "저장된 단지가 없습니다.")
            return
        apt_complexes = []
        excluded_vl = 0
        for _, name, asset_type, cid, _ in complexes:
            asset_token = str(asset_type or "APT").strip().upper() or "APT"
            if asset_token != "APT":
                excluded_vl += 1
                continue
            apt_complexes.append((name, cid))
        if not apt_complexes:
            QMessageBox.information(self, "알림", "complex 모드에서 불러올 수 있는 APT 단지가 없습니다.")
            if excluded_vl > 0:
                self.append_log(f"ℹ️ complex 모드는 APT만 지원하여 VL {excluded_vl}개를 제외했습니다.", 20)
                self.status_message.emit("complex 모드는 APT만 지원하며 VL은 geo_sweep에서만 사용 가능합니다.")
            return
        if excluded_vl > 0:
            self.append_log(f"ℹ️ complex 모드는 APT만 지원하여 VL {excluded_vl}개를 제외했습니다.", 20)
            self.status_message.emit("complex 모드는 APT만 지원하며 VL은 geo_sweep에서만 사용 가능합니다.")
        items = [(f"{name} (APT:{cid})", (name, cid)) for name, cid in apt_complexes]
        dlg = MultiSelectDialog("DB에서 불러오기", items, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            for name, cid in dlg.selected_items():
                self._add_row(name, cid)

    def _show_group_load_dialog(self: Any):
        groups = self.db.get_all_groups()
        if not groups:
            QMessageBox.information(self, "알림", "저장된 그룹이 없습니다.")
            return
        items = [(name, gid) for gid, name, _ in groups]
        dlg = MultiSelectDialog("그룹에서 불러오기", items, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            excluded_vl = 0
            for gid in dlg.selected_items():
                for _, name, asset_type, cid, _ in self.db.get_complexes_in_group(gid):
                    asset_token = str(asset_type or "APT").strip().upper() or "APT"
                    if asset_token != "APT":
                        excluded_vl += 1
                        continue
                    self.add_task(name, cid)
            if excluded_vl > 0:
                self.append_log(f"ℹ️ complex 모드는 APT만 지원하여 VL {excluded_vl}개를 제외했습니다.", 20)
                self.status_message.emit("complex 모드는 APT만 지원하며 VL은 geo_sweep에서만 사용 가능합니다.")

    def _show_recent_search_dialog(self: Any):
        if not self.history_manager:
            return
        
        try:
            dlg = RecentSearchDialog(self, self.history_manager)
            if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_search:
                search = dlg.selected_search
                self.clear_tasks()
                
                complexes = search.get('complexes', [])
                for item in complexes:
                    # Handle both [name, cid] list and dictionary just in case
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        name, cid = item[0], item[1]
                        self.add_task(name, cid)
                    elif isinstance(item, dict):
                        self.add_task(item.get('name', ''), item.get('cid', ''))
                        
                # 거래유형 복원
                types = search.get('trade_types', [])
                self.check_trade.setChecked("매매" in types)
                self.check_jeonse.setChecked("전세" in types)
                self.check_monthly.setChecked("월세" in types)

                area_filter = search.get("area_filter") or {}
                self.check_area_filter.setChecked(bool(area_filter.get("enabled")))
                self.spin_area_min.setValue(int(area_filter.get("min", self.spin_area_min.value()) or 0))
                self.spin_area_max.setValue(int(area_filter.get("max", self.spin_area_max.value()) or 0))

                price_filter = search.get("price_filter") or {}
                self.check_price_filter.setChecked(bool(price_filter.get("enabled")))
                sale = price_filter.get("매매", {}) or {}
                jeonse = price_filter.get("전세", {}) or {}
                monthly = price_filter.get("월세", {}) or {}
                self.spin_trade_min.setValue(int(sale.get("min", self.spin_trade_min.value()) or 0))
                self.spin_trade_max.setValue(int(sale.get("max", self.spin_trade_max.value()) or 0))
                self.spin_jeonse_min.setValue(int(jeonse.get("min", self.spin_jeonse_min.value()) or 0))
                self.spin_jeonse_max.setValue(int(jeonse.get("max", self.spin_jeonse_max.value()) or 0))
                self.spin_monthly_deposit_min.setValue(
                    int(monthly.get("deposit_min", monthly.get("min", self.spin_monthly_deposit_min.value())) or 0)
                )
                self.spin_monthly_deposit_max.setValue(
                    int(monthly.get("deposit_max", monthly.get("max", self.spin_monthly_deposit_max.value())) or 0)
                )
                self.spin_monthly_rent_min.setValue(
                    int(monthly.get("rent_min", monthly.get("min", self.spin_monthly_rent_min.value())) or 0)
                )
                self.spin_monthly_rent_max.setValue(
                    int(monthly.get("rent_max", monthly.get("max", self.spin_monthly_rent_max.value())) or 0)
                )
        except Exception as e:
            QMessageBox.critical(self, "오류", f"최근 검색 기록을 불러오는 중 오류가 발생했습니다:\n{e}")
            logger.error(f"Recent search load failed: {e}")

    def _show_url_batch_dialog(self: Any):
        dlg = URLBatchDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            selected = dlg.get_selected_complexes()
            if selected:
                added = 0
                for name, cid in selected:
                    if self._add_row(name, cid):
                        added += 1
                self.status_message.emit(f"{added}개 URL 등록 완료")
                return
            urls = dlg.get_urls()
            self._add_complexes_from_url(urls)

    def _add_complexes_from_url(self: Any, urls):
        count = 0
        for url in urls:
            m = re.search(r'/complexes/(\d+)', url)
            if m:
                cid = m.group(1)
                if self._add_row(f"단지_{cid}", cid):
                    count += 1
        self.status_message.emit(f"{count}개 URL 등록 완료")

    def _open_complex_url(self: Any):
        item = self.table_list.item(self.table_list.currentRow(), 1)
        if item:
            url = f"https://new.land.naver.com/complexes/{item.text()}"
            webbrowser.open(url)

    def start_crawling(self: Any):
        from src.ui.widgets.crawler_tab import (
            _get_crawl_cache_cls,
            _get_crawler_thread_cls,
        )

        if self.crawler_thread and self.crawler_thread.isRunning():
            self.append_log("⚠️ 이미 크롤링이 실행 중입니다.", 30)
            self.status_message.emit("이미 크롤링이 실행 중입니다.")
            return

        try:
            in_maintenance = bool(self._maintenance_guard()) if callable(self._maintenance_guard) else False
        except Exception:
            in_maintenance = False
        if in_maintenance:
            self.append_log("⛔ 유지보수 모드에서는 크롤링을 시작할 수 없습니다.", 30)
            self.status_message.emit("유지보수 모드에서는 크롤링이 차단됩니다.")
            return

        if self.table_list.rowCount() == 0:
            QMessageBox.warning(self, "경고", "크롤링할 단지를 추가해주세요.")
            return

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_save.setEnabled(False)
        self.log_browser.clear()
        self.progress_widget.reset()
        self.summary_card.reset()
        self.collected_data = []
        self.crawl_cache = None
        self._reset_result_state()
        self.card_view.set_data([])
        self.grouped_rows = {}
        
        target_list = self._normalize_task_table()
        if not target_list:
            QMessageBox.warning(self, "경고", "크롤링할 단지를 추가해주세요.")
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            return
            
        trade_types = []
        if self.check_trade.isChecked(): trade_types.append("매매")
        if self.check_jeonse.isChecked(): trade_types.append("전세")
        if self.check_monthly.isChecked(): trade_types.append("월세")
        
        if not trade_types:
            QMessageBox.warning(self, "경고", "최소 하나의 거래 유형을 선택해주세요.")
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            return

        area_filter = {"enabled": self.check_area_filter.isChecked(), "min": self.spin_area_min.value(), "max": self.spin_area_max.value()}
        price_filter = {
            "enabled": self.check_price_filter.isChecked(),
            "매매": {"min": self.spin_trade_min.value(), "max": self.spin_trade_max.value()},
            "전세": {"min": self.spin_jeonse_min.value(), "max": self.spin_jeonse_max.value()},
            "월세": {
                "deposit_min": self.spin_monthly_deposit_min.value(),
                "deposit_max": self.spin_monthly_deposit_max.value(),
                "rent_min": self.spin_monthly_rent_min.value(),
                "rent_max": self.spin_monthly_rent_max.value(),
                # Legacy keys for backward compatibility with old readers.
                "min": self.spin_monthly_rent_min.value(),
                "max": self.spin_monthly_rent_max.value(),
            },
        }

        if self.history_manager:
            try:
                self.history_manager.add(
                    {
                        "complexes": [{"name": name, "cid": cid} for name, cid in target_list],
                        "trade_types": list(trade_types),
                        "area_filter": area_filter,
                        "price_filter": price_filter,
                    }
                )
            except Exception as e:
                logger.warning(f"최근 검색 기록 저장 실패: {e}")

        try:
            configured_retry_count = max(0, int(settings.get("max_retry_count", 3)))
        except (TypeError, ValueError):
            configured_retry_count = 3
        retry_on_error = bool(settings.get("retry_on_error", True))
        max_retry_count = configured_retry_count if retry_on_error else 0

        if settings.get("cache_enabled", True):
            cache_cls = _get_crawl_cache_cls()
            self.crawl_cache = cache_cls(
                ttl_minutes=settings.get("cache_ttl_minutes", 30),
                write_back_interval_sec=settings.get("cache_write_back_interval_sec", 2),
                max_entries=settings.get("cache_max_entries", 2000),
            )
        
        # Start Thread
        crawler_thread_cls = _get_crawler_thread_cls()
        self.crawler_thread = crawler_thread_cls(
            target_list, trade_types, area_filter, price_filter, self.db,
            speed=self.speed_slider.current_speed(),
            cache=self.crawl_cache,
            ui_batch_interval_ms=settings.get("ui_batch_interval_ms", 120),
            ui_batch_size=settings.get("ui_batch_size", 30),
            max_retry_count=max_retry_count,
            show_new_badge=settings.get("show_new_badge", True),
            show_price_change=settings.get("show_price_change", True),
            price_change_threshold=settings.get("price_change_threshold", 0),
            track_disappeared=settings.get("track_disappeared", True),
            history_batch_size=settings.get("history_batch_size", 200),
            negative_cache_ttl_minutes=settings.get("cache_negative_ttl_minutes", 5),
            engine_name=settings.get("crawl_engine", "playwright"),
            crawl_mode="complex",
            fallback_engine_enabled=settings.get("fallback_engine_enabled", True),
            playwright_headless=settings.get("playwright_headless", False),
            playwright_detail_workers=settings.get("playwright_detail_workers", 12),
            block_heavy_resources=settings.get("playwright_block_heavy_resources", True),
            playwright_response_drain_timeout_ms=settings.get("playwright_response_drain_timeout_ms", 3000),
        )
        self.crawler_thread.log_signal.connect(self.append_log)
        self.crawler_thread.progress_signal.connect(self.progress_widget.update_progress)
        self.crawler_thread.items_signal.connect(self._on_items_batch)
        self.crawler_thread.stats_signal.connect(self._update_stats_ui)
        self.crawler_thread.complex_finished_signal.connect(self._on_complex_finished)
        self.crawler_thread.alert_triggered_signal.connect(self._on_alert_triggered)
        self.crawler_thread.error_signal.connect(lambda msg: self.append_log(f"❌ 크롤링 오류: {msg}", 40))
        self.crawler_thread.finished_signal.connect(self._on_crawl_finished)
        self.crawler_thread.start()
        
        self.crawling_started.emit()

    def stop_crawling(self: Any):
        if self.crawler_thread and self.crawler_thread.isRunning():
            self.crawler_thread.stop()
            self.append_log("🛑 중지 요청 중...", 30)
            self.btn_stop.setEnabled(False)

    def shutdown_crawl(self: Any, timeout_ms: int = 8000) -> bool:
        thread = self.crawler_thread
        if not thread:
            return True
        if not thread.isRunning():
            self.crawler_thread = None
            return True

        if hasattr(thread, "set_shutdown_mode"):
            thread.set_shutdown_mode(True)
        thread.stop()
        try:
            wait_ms = max(100, int(timeout_ms))
        except (TypeError, ValueError):
            wait_ms = 8000
        finished = bool(thread.wait(wait_ms))
        if finished:
            self.crawler_thread = None
            return True
        self.append_log(f"⚠️ 크롤링 종료 대기 타임아웃 ({wait_ms}ms)", 30)
        return False

    def _on_crawl_finished(self: Any, data):
        try:
            self.btn_save.setEnabled(True)
            self.progress_widget.complete()
            self.append_log(f"✅ 크롤링 완료: 총 {len(data)}건 수집")

            if self.crawl_cache:
                self.crawl_cache.flush()
            
            # DB Write
            try:
                self._save_price_snapshots()
            except Exception as e:
                self.append_log(f"⚠️ 가격 스냅샷 저장 실패: {e}", 30)

            if settings.get("play_sound_on_complete", True):
                try:
                    QApplication.beep()
                except Exception as e:
                    logger.debug(f"완료 알림음 재생 실패 (무시): {e}")
            
            self.data_collected.emit(data) # Notify App
            self.crawling_stopped.emit()
            
        except Exception as e:
            self.append_log(f"❌ 크롤링 마무리 중 오류: {e}", 40)
            logger.error(f"Crawl finish handler failed: {e}")
        finally:
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.crawler_thread = None

    def _on_complex_finished(self: Any, name, cid, trade_types, count):
        self.append_log(f"📌 단지 완료: {name} ({cid}) {count}건", 10)

    def _on_alert_triggered(self: Any, complex_name, trade_type, price_text, area_pyeong, alert_id):
        self.append_log(
            f"🔔 알림 조건 충족: {complex_name} {trade_type} {price_text} ({area_pyeong:.1f}평)",
            30,
        )
        self.alert_triggered.emit(complex_name, trade_type, price_text, area_pyeong, int(alert_id or 0))

    def _update_stats_ui(self: Any, stats):
        self.summary_card.update_stats(
            total=stats["total_found"],
            trade=stats["by_trade_type"].get("매매", 0),
            jeonse=stats["by_trade_type"].get("전세", 0),
            monthly=stats["by_trade_type"].get("월세", 0),
            filtered=stats["filtered_out"],
            new_count=stats.get("new_count", 0),
            price_up=stats.get("price_up", 0),
            price_down=stats.get("price_down", 0),
        )

    def _save_price_snapshots(self: Any):
        """크롤링 결과를 가격 스냅샷으로 저장"""
        if not self.collected_data:
            return
        
        # 단지별, 거래유형별, 평형별로 그룹화
        from collections import defaultdict
        grouped = defaultdict(list)
        
        for item in self.collected_data:
            cid = item.get("단지ID", "")
            ttype = item.get("거래유형", "")
            pyeong = item.get("면적(평)", 0)
            asset_type = str(item.get("자산유형", "APT") or "APT").strip().upper() or "APT"
            if asset_type not in {"APT", "VL"}:
                asset_type = "APT"
            
            # 가격 추출
            if ttype == "매매":
                price = PriceConverter.to_int(item.get("매매가", "0"))
            else:
                price = PriceConverter.to_int(item.get("보증금", "0"))
            
            if cid and ttype and price > 0:
                # 평형 그룹화 (5평 단위)
                pyeong_group = round(pyeong / 5) * 5
                key = (asset_type, cid, ttype, pyeong_group)
                grouped[key].append(price)
        
        # 스냅샷 저장
        rows = []
        for (asset_type, cid, ttype, pyeong), prices in grouped.items():
            if prices:
                min_price = min(prices)
                max_price = max(prices)
                avg_price = sum(prices) // len(prices)
                rows.append((cid, ttype, pyeong, min_price, max_price, avg_price, len(prices), asset_type))

        saved = self.db.add_price_snapshots_bulk(rows) if rows else 0
        self.append_log(f"📊 가격 스냅샷 {saved}건 저장", 10)


    def _show_excel_template_dialog(self: Any):
        current_template = settings.get("excel_template")
        dlg = ExcelTemplateDialog(self, current_template=current_template)
        dlg.template_saved.connect(lambda t: settings.set("excel_template", t))
        dlg.exec()
        
    def _open_article_url(self: Any):
        row = self.result_table.currentRow()
        if row < 0:
            return
        item = self.result_table.item(row, self.COL_URL)
        url = item.text() if item else ""
        if url:
            webbrowser.open(url)
