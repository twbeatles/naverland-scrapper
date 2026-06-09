from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


class CrawlerTabDialogOpsMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def _show_db_load_dialog(self: Any):
        complexes = self.db.get_all_complexes()
        if not complexes:
            QMessageBox.information(self, "알림", "저장된 단지가 없습니다.")
            return
        db_complexes = []
        for _, name, asset_type, cid, _ in complexes:
            asset_token = self._normalize_task_asset_type(asset_type)
            db_complexes.append((str(name or ""), str(cid or ""), asset_token))
        items = [(f"{name} ({asset_type}:{cid})", (name, cid, asset_type)) for name, cid, asset_type in db_complexes]
        dlg = MultiSelectDialog("DB에서 불러오기", items, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            for item in dlg.selected_items():
                if isinstance(item, (list, tuple)) and len(item) >= 3:
                    name, cid, asset_type = item[0], item[1], item[2]
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    name, cid, asset_type = item[0], item[1], "APT"
                else:
                    continue
                self._add_row(name, cid, asset_type)

    def _show_group_load_dialog(self: Any):
        groups = self.db.get_all_groups()
        if not groups:
            QMessageBox.information(self, "알림", "저장된 그룹이 없습니다.")
            return
        items = [(name, gid) for gid, name, _ in groups]
        dlg = MultiSelectDialog("그룹에서 불러오기", items, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            for gid in dlg.selected_items():
                for _, name, asset_type, cid, _ in self.db.get_complexes_in_group(gid):
                    self.add_task(name, cid, asset_type)

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
                    if isinstance(item, (list, tuple)) and len(item) >= 3:
                        name, cid, asset_type = item[0], item[1], item[2]
                        self.add_task(name, cid, asset_type)
                    elif isinstance(item, (list, tuple)) and len(item) >= 2:
                        name, cid = item[0], item[1]
                        self.add_task(name, cid, "APT")
                    elif isinstance(item, dict):
                        self.add_task(
                            item.get('name', ''),
                            item.get('cid', ''),
                            item.get('asset_type', 'APT'),
                        )
                        
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
                for item in selected:
                    if isinstance(item, dict):
                        name = item.get("name", "")
                        cid = item.get("cid", item.get("complex_id", ""))
                        asset_type = item.get("asset_type", "APT")
                    elif isinstance(item, (list, tuple)) and len(item) >= 3:
                        name, cid, asset_type = item[0], item[1], item[2]
                    elif isinstance(item, (list, tuple)) and len(item) >= 2:
                        name, cid, asset_type = item[0], item[1], "APT"
                    else:
                        continue
                    if self._add_row(name, cid, asset_type):
                        added += 1
                self.status_message.emit(f"{added}개 URL 등록 완료")
                return
            urls = dlg.get_urls()
            self._add_complexes_from_url(urls)

    def _open_complex_url(self: Any):
        row = self.table_list.currentRow()
        if row < 0:
            return
        cid_item = self.table_list.item(row, 1)
        asset_item = self.table_list.item(row, 2)
        if cid_item:
            asset_type = self._normalize_task_asset_type(asset_item.text() if asset_item else "APT")
            url = get_complex_url(cid_item.text(), asset_type=asset_type)
            webbrowser.open(url)

    def _show_excel_template_dialog(self: Any):
        current_template = settings.get("excel_template")
        dlg = ExcelTemplateDialog(self, current_template=current_template)
        dlg.template_saved.connect(lambda t: settings.set("excel_template", t))
        dlg.exec()

    def _open_article_url(self: Any):
        row = self.result_table.currentRow()
        if row < 0:
            return
        payload = self._row_payload_cache[row] if row < len(self._row_payload_cache) else {}
        if payload and callable(getattr(self, "article_open_handler", None)):
            self.article_open_handler(payload)
            return
        item = self.result_table.item(row, self.COL_URL)
        url = item.text() if item else ""
        if url:
            webbrowser.open(url)
