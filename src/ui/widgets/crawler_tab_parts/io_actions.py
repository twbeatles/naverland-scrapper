from __future__ import annotations


class CrawlerTabIOActionsMixin:
    def get_filter_state(self):
        """현재 필터 상태 반환"""
        return {
            "area": {
                "enabled": self.check_area_filter.isChecked(),
                "min": self.spin_area_min.value(),
                "max": self.spin_area_max.value()
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
            # Add other settings...
        }

    def set_filter_state(self, state):
        """필터 상태 적용"""
        if "area" in state:
            area = state["area"]
            self.check_area_filter.setChecked(area.get("enabled", False))
            self.spin_area_min.setValue(area.get("min", 0))
            self.spin_area_max.setValue(area.get("max", 0))
        if "price" in state:
            p = state["price"]
            self.check_price_filter.setChecked(p.get("enabled", False))
            self.spin_trade_min.setValue(p.get("trade_min", 0))
            self.spin_trade_max.setValue(p.get("trade_max", 100000))
            self.spin_jeonse_min.setValue(p.get("jeonse_min", 0))
            self.spin_jeonse_max.setValue(p.get("jeonse_max", 50000))
            self.spin_monthly_deposit_min.setValue(
                p.get("monthly_deposit_min", p.get("monthly_min", 0))
            )
            self.spin_monthly_deposit_max.setValue(
                p.get("monthly_deposit_max", p.get("monthly_max", 50000))
            )
            self.spin_monthly_rent_min.setValue(p.get("monthly_rent_min", p.get("monthly_min", 0)))
            self.spin_monthly_rent_max.setValue(
                p.get("monthly_rent_max", p.get("monthly_max", 5000))
            )
        
    def show_save_menu(self):
        menu = QMenu(self)
        menu.addAction("📊 Excel로 저장", self.save_excel)
        menu.addAction("📄 CSV로 저장", self.save_csv)
        menu.addAction("📋 JSON으로 저장", self.save_json)
        menu.addSeparator()
        menu.addAction("⚙️ 엑셀 템플릿 설정", self._show_excel_template_dialog)
        menu.exec(self.btn_save.mapToGlobal(self.btn_save.rect().bottomLeft()))

    def save_excel(self):
        if not self.collected_data: return
        path, _ = QFileDialog.getSaveFileName(self, "Excel 저장", f"부동산_{DateTimeHelper.file_timestamp()}.xlsx", "Excel (*.xlsx)")
        if path:
            from pathlib import Path
            template = settings.get("excel_template")
            try:
                if DataExporter(self.collected_data).to_excel(Path(path), template):
                    QMessageBox.information(self, "저장 완료", f"Excel 파일 저장 완료!\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "저장 실패", f"Excel 저장 중 오류가 발생했습니다:\n{e}")
                logger.error(f"Excel Save Error: {e}")

    def save_csv(self):
        if not self.collected_data: return
        path, _ = QFileDialog.getSaveFileName(self, "CSV 저장", f"부동산_{DateTimeHelper.file_timestamp()}.csv", "CSV (*.csv)")
        if path:
            from pathlib import Path
            template = settings.get("excel_template")
            try:
                if DataExporter(self.collected_data).to_csv(Path(path), template):
                    QMessageBox.information(self, "저장 완료", f"CSV 파일 저장 완료!\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "저장 실패", f"CSV 저장 중 오류가 발생했습니다:\n{e}")
                logger.error(f"CSV Save Error: {e}")

    def save_json(self):
        if not self.collected_data: return
        path, _ = QFileDialog.getSaveFileName(self, "JSON 저장", f"부동산_{DateTimeHelper.file_timestamp()}.json", "JSON (*.json)")
        if path:
            from pathlib import Path
            try:
                if DataExporter(self.collected_data).to_json(Path(path)):
                    QMessageBox.information(self, "저장 완료", f"JSON 파일 저장 완료!\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "저장 실패", f"JSON 저장 중 오류가 발생했습니다:\n{e}")
                logger.error(f"JSON Save Error: {e}")

