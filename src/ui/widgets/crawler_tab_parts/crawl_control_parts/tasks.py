from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


class CrawlerTabTaskOpsMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    @staticmethod
    def _normalize_task_asset_type(asset_type) -> str:
        token = str(asset_type or "APT").strip().upper()
        return token if token in {"APT", "VL"} else "APT"

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
        asset_type = self._normalize_task_asset_type(
            self.combo_manual_asset.currentText() if hasattr(self, "combo_manual_asset") else "APT"
        )
        self._add_row(name, cid, asset_type)
        self.input_name.clear()
        self.input_id.clear()

    def _normalize_task_name(self: Any, name, cid):
        cid_text = str(cid or "").strip()
        name_text = str(name or "").strip()
        return name_text or f"단지_{cid_text}"

    def _find_task_row_by_cid(self: Any, cid, asset_type="APT"):
        cid_text = str(cid or "").strip()
        asset_token = self._normalize_task_asset_type(asset_type)
        if not cid_text:
            return -1
        for row in range(self.table_list.rowCount()):
            item = self.table_list.item(row, 1)
            asset_item = self.table_list.item(row, 2)
            row_asset = self._normalize_task_asset_type(asset_item.text() if asset_item else "APT")
            if item and item.text().strip() == cid_text and row_asset == asset_token:
                return row
        return -1

    def _append_task_row(self: Any, name, cid, asset_type="APT"):
        row = self.table_list.rowCount()
        self.table_list.insertRow(row)
        self.table_list.setItem(row, 0, QTableWidgetItem(str(name)))
        self.table_list.setItem(row, 1, QTableWidgetItem(str(cid)))
        self.table_list.setItem(row, 2, QTableWidgetItem(self._normalize_task_asset_type(asset_type)))

    def _emit_task_duplicate_skip(self: Any, name, cid, asset_type="APT"):
        asset_token = self._normalize_task_asset_type(asset_type)
        existing_row = self._find_task_row_by_cid(cid, asset_token)
        kept_name = ""
        if existing_row >= 0:
            kept_item = self.table_list.item(existing_row, 0)
            kept_name = kept_item.text().strip() if kept_item else ""
        display_name = kept_name or self._normalize_task_name(name, cid)
        message = f"중복 스킵: {display_name} ({asset_token}:{cid})"
        self.append_log(message, 10)
        self.status_message.emit(message)

    def add_task(self: Any, name, cid, asset_type="APT", *, log_duplicate=True):
        cid_text = str(cid or "").strip()
        asset_token = self._normalize_task_asset_type(asset_type)
        if not cid_text:
            return False
        name_text = self._normalize_task_name(name, cid_text)
        if self._find_task_row_by_cid(cid_text, asset_token) >= 0:
            if log_duplicate:
                self._emit_task_duplicate_skip(name_text, cid_text, asset_token)
            return False
        self._append_task_row(name_text, cid_text, asset_token)
        return True

    def _add_row(self: Any, name, cid, asset_type="APT"):
        return self.add_task(name, cid, asset_type)

    def _dedupe_target_entries(self: Any, rows):
        deduped = []
        seen = set()
        removed = 0
        for row in rows:
            if isinstance(row, dict):
                name = row.get("name", "")
                cid = row.get("cid", row.get("complex_id", ""))
                asset_type = row.get("asset_type", "APT")
            elif isinstance(row, (list, tuple)):
                name = row[0] if len(row) >= 1 else ""
                cid = row[1] if len(row) >= 2 else ""
                asset_type = row[2] if len(row) >= 3 else "APT"
            else:
                continue
            cid_text = str(cid or "").strip()
            asset_token = self._normalize_task_asset_type(asset_type)
            if not cid_text:
                continue
            dedupe_key = (asset_token, cid_text)
            if dedupe_key in seen:
                removed += 1
                continue
            seen.add(dedupe_key)
            deduped.append((self._normalize_task_name(name, cid_text), cid_text, asset_token))
        return deduped, removed

    def _normalize_task_table(self: Any):
        rows = []
        for row in range(self.table_list.rowCount()):
            name_item = self.table_list.item(row, 0)
            cid_item = self.table_list.item(row, 1)
            asset_item = self.table_list.item(row, 2)
            rows.append(
                (
                    name_item.text().strip() if name_item else "",
                    cid_item.text().strip() if cid_item else "",
                    self._normalize_task_asset_type(asset_item.text() if asset_item else "APT"),
                )
            )
        deduped, removed = self._dedupe_target_entries(rows)
        if removed > 0 or len(deduped) != self.table_list.rowCount():
            self.table_list.setRowCount(0)
            for name, cid, asset_type in deduped:
                self._append_task_row(name, cid, asset_type)
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
            asset_item = self.table_list.item(r, 2)
            asset_type = self._normalize_task_asset_type(asset_item.text() if asset_item else "APT")
            status = self.db.add_complex(name, cid, asset_type=asset_type, return_status=True)
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

    def _add_complexes_from_url(self: Any, urls):
        from src.core.parser import NaverURLParser

        count = 0
        for url in urls:
            parsed = NaverURLParser.parse_url_info(str(url or ""))
            cid = str(parsed.get("complex_id", "") or "").strip()
            asset_type = self._normalize_task_asset_type(parsed.get("asset_type", "APT"))
            if cid and self._add_row(f"단지_{cid}", cid, asset_type):
                count += 1
        self.status_message.emit(f"{count}개 URL 등록 완료")
