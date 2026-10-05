from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


class CrawlerTabIOActionsMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def get_filter_state(self: Any):
        """현재 필터 상태 반환"""
        return {
            "area": {
                "enabled": self.check_area_filter.isChecked(),
                "min": self.spin_area_min.value(),
                "max": self.spin_area_max.value(),
            },
            "price": {
                "enabled": self.check_price_filter.isChecked(),
                "trade_min": self.spin_trade_min.value(),
                "trade_max": self.spin_trade_max.value(),
                "jeonse_min": self.spin_jeonse_min.value(),
                "jeonse_max": self.spin_jeonse_max.value(),
                "monthly_min": self.spin_monthly_rent_min.value(),
                "monthly_max": self.spin_monthly_rent_max.value(),
                "monthly_deposit_min": self.spin_monthly_deposit_min.value(),
                "monthly_deposit_max": self.spin_monthly_deposit_max.value(),
                "monthly_rent_min": self.spin_monthly_rent_min.value(),
                "monthly_rent_max": self.spin_monthly_rent_max.value(),
            },
        }

    def set_filter_state(self: Any, state):
        """필터 상태 적용"""
        if "area" in state:
            area = state["area"]
            self.check_area_filter.setChecked(area.get("enabled", False))
            self.spin_area_min.setValue(area.get("min", 0))
            self.spin_area_max.setValue(area.get("max", 0))
        if "price" in state:
            price = state["price"]
            self.check_price_filter.setChecked(price.get("enabled", False))
            self.spin_trade_min.setValue(price.get("trade_min", 0))
            self.spin_trade_max.setValue(price.get("trade_max", 100000))
            self.spin_jeonse_min.setValue(price.get("jeonse_min", 0))
            self.spin_jeonse_max.setValue(price.get("jeonse_max", 50000))
            self.spin_monthly_deposit_min.setValue(
                price.get("monthly_deposit_min", price.get("monthly_min", 0))
            )
            self.spin_monthly_deposit_max.setValue(
                price.get("monthly_deposit_max", price.get("monthly_max", 50000))
            )
            self.spin_monthly_rent_min.setValue(
                price.get("monthly_rent_min", price.get("monthly_min", 0))
            )
            self.spin_monthly_rent_max.setValue(
                price.get("monthly_rent_max", price.get("monthly_max", 5000))
            )

    def _visible_export_items(self: Any):
        source_items = (
            list(self._compact_rows_data)
            if self._compact_duplicates
            else self._decorate_favorite_state(self._apply_advanced_filter_items(self.collected_data))
        )
        if not source_items:
            return []

        lookup = {}
        for index, item in enumerate(source_items):
            url = get_article_url(
                item.get("단지ID", ""),
                item.get("매물ID", ""),
                item.get("자산유형", "APT"),
            )
            key = url or f"__row__:{index}"
            lookup.setdefault(key, []).append(dict(item))

        visible = []
        row_count = int(self.result_table.rowCount() or 0)
        if row_count <= 0:
            return [dict(item) for item in source_items]

        fallback_items = [dict(item) for item in source_items]
        for row in range(row_count):
            if self.result_table.isRowHidden(row):
                continue
            url_item = self.result_table.item(row, self.COL_URL)
            row_url = url_item.text().strip() if url_item else ""
            matched = lookup.get(row_url, [])
            if matched:
                visible.append(matched.pop(0))
                continue
            if fallback_items:
                visible.append(fallback_items.pop(0))
        return visible or [dict(item) for item in source_items]

    def _export_items_for_scope(self: Any, scope: str):
        if str(scope or "visible").lower() == "raw":
            return [dict(item) for item in self.collected_data]
        return self._visible_export_items()

    def show_save_menu(self: Any):
        menu = QMenu(self)
        menu.addAction("엑셀로 저장 (지금 보이는 목록)", lambda: self.save_excel("visible"))
        other_visible = menu.addMenu("다른 형식으로 저장 (지금 보이는 목록)")
        if other_visible is not None:
            other_visible.addAction("CSV 파일", lambda: self.save_csv("visible"))
            other_visible.addAction("JSON 파일", lambda: self.save_json("visible"))
        menu.addSeparator()
        raw_menu = menu.addMenu("수집한 전체 원본 저장 (묶기·필터 적용 안 함)")
        if raw_menu is not None:
            raw_menu.addAction("엑셀 파일", lambda: self.save_excel("raw"))
            raw_menu.addAction("CSV 파일", lambda: self.save_csv("raw"))
            raw_menu.addAction("JSON 파일", lambda: self.save_json("raw"))
        menu.addSeparator()
        menu.addAction("엑셀에 담을 항목 고르기…", self._show_excel_template_dialog)
        menu.exec(self.btn_save.mapToGlobal(self.btn_save.rect().bottomLeft()))

    def _save_with_export_scope(self: Any, kind: str, scope: str = "visible"):
        from pathlib import Path
        from src.ui.widgets.crawler_tab import _get_data_exporter_cls

        items = self._export_items_for_scope(scope)
        scope_key = str(scope or "visible").lower()
        scope_label = "지금 보이는 목록" if scope_key != "raw" else "전체 원본"
        if not items:
            QMessageBox.information(self, "저장할 매물이 없습니다", "먼저 매물을 수집해 주세요.")
            return

        suffix_map = {
            "excel": ("xlsx", "Excel (*.xlsx)"),
            "csv": ("csv", "CSV (*.csv)"),
            "json": ("json", "JSON (*.json)"),
        }
        suffix, filter_text = suffix_map[kind]
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"{scope_label} 저장",
            f"부동산_{scope_key}_{DateTimeHelper.file_timestamp()}.{suffix}",
            filter_text,
        )
        if not path:
            return

        try:
            exporter_cls = _get_data_exporter_cls()
            exporter = exporter_cls(items)
            template = settings.get("excel_template")
            if kind == "excel":
                if hasattr(exporter, "export_excel"):
                    result = exporter.export_excel(Path(path), template)
                else:
                    result = exporter.to_excel(Path(path), template)
            elif kind == "csv":
                if hasattr(exporter, "export_csv"):
                    result = exporter.export_csv(Path(path), template)
                else:
                    result = exporter.to_csv(Path(path), template)
            else:
                if hasattr(exporter, "export_json"):
                    result = exporter.export_json(Path(path))
                else:
                    result = exporter.to_json(Path(path))

            ok = bool(getattr(result, "ok", result))
            error = str(getattr(result, "error", "") or getattr(exporter, "last_error", "") or "")
            if ok:
                message = f"매물 {len(items)}건을 저장했습니다."
                self.status_message.emit(f"{message} ({path})")
                show_toast = getattr(self.window(), "show_toast", None)
                if callable(show_toast):
                    show_toast(message, toast_type="success")
                else:
                    QMessageBox.information(self, "저장 완료", f"{message}\n{path}")
                return

            if not error:
                error = "파일을 저장하지 못했습니다."
            QMessageBox.critical(self, "저장하지 못했습니다", f"파일을 저장하지 못했습니다. 파일이 다른 프로그램에서 열려 있지 않은지 확인해 주세요.\n\n{error}")
            logger.error(f"{kind.upper()} save failed ({scope_key}): {error}")
        except Exception as exc:
            QMessageBox.critical(self, "저장하지 못했습니다", f"파일을 저장하는 중 문제가 생겼습니다.\n\n{exc}")
            logger.error(f"{kind.upper()} save error ({scope_key}): {exc}")

    def save_excel(self: Any, scope: str = "visible"):
        self._save_with_export_scope("excel", scope)

    def save_csv(self: Any, scope: str = "visible"):
        self._save_with_export_scope("csv", scope)

    def save_json(self: Any, scope: str = "visible"):
        self._save_with_export_scope("json", scope)
