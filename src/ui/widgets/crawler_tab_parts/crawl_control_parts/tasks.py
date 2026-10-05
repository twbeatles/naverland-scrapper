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
        # Display labels (아파트/빌라) are accepted too so UI text can stay friendly.
        token = {"아파트": "APT", "빌라": "VL", "빌라·연립": "VL"}.get(token, token)
        return token if token in {"APT", "VL"} else "APT"

    def _add_complex(self: Any):
        name = self.input_name.text().strip()
        cid = self.input_id.text().strip()
        if not cid:
            return
        if not self._complex_id_regex.match(cid).hasMatch():
            QMessageBox.warning(self, "입력 확인", "단지 번호는 숫자만 입력할 수 있습니다.")
            self.input_id.setFocus()
            self.input_id.selectAll()
            return
        combo = getattr(self, "combo_manual_asset", None)
        asset_type = self._normalize_task_asset_type(
            (combo.currentData() or combo.currentText()) if combo is not None else "APT"
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
        message = f"이미 목록에 있는 단지입니다: {display_name}"
        self.append_log(message, 20)
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
            message = f"목록에서 겹치는 단지 {removed}곳을 정리했습니다."
            self.append_log(message, 20)
            self.status_message.emit(message)
        return deduped

    def clear_tasks(self: Any):
        self.table_list.setRowCount(0)

    def _delete_complex(self: Any):
        rows = sorted({idx.row() for idx in self.table_list.selectedIndexes()}, reverse=True)
        if not rows:
            row = self.table_list.currentRow()
            rows = [row] if row >= 0 else []
        for row in rows:
            self.table_list.removeRow(row)

    def _clear_list(self: Any):
        self.table_list.setRowCount(0)

    def _save_to_db(self: Any):
        inserted_count = 0
        existing_count = 0
        failed_count = 0
        total = self.table_list.rowCount()
        if total <= 0:
            self.status_message.emit("저장할 단지가 없습니다. 먼저 목록에 단지를 추가해 주세요.")
            return
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
        parts = [f"새로 저장 {inserted_count}곳"]
        if existing_count:
            parts.append(f"이미 있던 단지 {existing_count}곳")
        if failed_count:
            parts.append(f"저장 실패 {failed_count}곳")
        summary = "「내 단지」에 저장했습니다. (" + ", ".join(parts) + ")"
        if failed_count:
            QMessageBox.warning(self, "일부 저장 실패", summary)
        else:
            self.status_message.emit(summary)
            show_toast = getattr(self.window(), "show_toast", None)
            if callable(show_toast):
                show_toast(summary, toast_type="success")

    def _add_complexes_from_url(self: Any, urls):
        from src.core.parser import NaverURLParser

        count = 0
        for url in urls:
            parsed = NaverURLParser.parse_url_info(str(url or ""))
            cid = str(parsed.get("complex_id", "") or "").strip()
            asset_type = self._normalize_task_asset_type(parsed.get("asset_type", "APT"))
            if cid and self._add_row(f"단지_{cid}", cid, asset_type):
                count += 1
        self.status_message.emit(f"주소에서 단지 {count}곳을 추가했습니다.")
