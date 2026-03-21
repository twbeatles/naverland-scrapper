from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppSettingsPresetMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def _toggle_theme(self: Any, theme=None):
        if theme in ("dark", "light"):
            new_theme = theme
        else:
            new_theme = "light" if self.current_theme == "dark" else "dark"
        self.current_theme = new_theme
        
        # 스타일시트 적용
        self.setStyleSheet(get_stylesheet(new_theme))
        
        # 개별 위젯 테마 업데이트
        if hasattr(self, "crawler_tab"):
            self.crawler_tab.set_theme(new_theme)
        if self.dashboard_widget is not None:
            self.dashboard_widget.set_theme(new_theme)
        if hasattr(self, 'favorites_tab'):
            self.favorites_tab.set_theme(new_theme)
        
        settings.set("theme", new_theme)
        self.show_toast(f"테마가 {new_theme} 모드로 변경되었습니다")
    
    def _show_settings(self: Any):
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_settings()
    
    def _apply_settings(self: Any):
        """설정 변경 후 적용"""
        # 테마 변경 체크
        new_theme = str(settings.get("theme", "dark") or "dark")
        if new_theme != self.current_theme:
            self.current_theme = new_theme
            self.setStyleSheet(get_stylesheet(new_theme))
            
            # 개별 위젯 테마 업데이트 (안전하게)
            try:
                if hasattr(self, 'crawler_tab') and hasattr(self.crawler_tab, 'set_theme'):
                    self.crawler_tab.set_theme(new_theme)
            except Exception as e:
                ui_logger.debug(f"crawler_tab 테마 적용 실패 (무시): {e}")
            try:
                if hasattr(self, 'geo_tab') and hasattr(self.geo_tab, 'set_theme'):
                    self.geo_tab.set_theme(new_theme)
            except Exception as e:
                ui_logger.debug(f"geo_tab 테마 적용 실패 (무시): {e}")
            
            try:
                if self.dashboard_widget is not None and hasattr(self.dashboard_widget, 'set_theme'):
                    self.dashboard_widget.set_theme(new_theme)
            except Exception as e:
                ui_logger.debug(f"dashboard_widget 테마 적용 실패 (무시): {e}")
            
            try:
                if hasattr(self, 'favorites_tab') and hasattr(self.favorites_tab, 'set_theme'):
                    self.favorites_tab.set_theme(new_theme)
            except Exception as e:
                ui_logger.debug(f"favorites_tab 테마 적용 실패 (무시): {e}")
            
            # 메뉴 체크 상태 업데이트
            if hasattr(self, 'action_theme_dark'):
                self.action_theme_dark.setChecked(new_theme == "dark")
            if hasattr(self, 'action_theme_light'):
                self.action_theme_light.setChecked(new_theme == "light")
            
            self.show_toast(f"테마가 {new_theme} 모드로 변경되었습니다")
            
            # 위젯 테마 업데이트
            if hasattr(self, 'crawler_tab'):
                # CrawlerTab doesn't have explicit set_theme yet but standard widgets style updates automatically
                # If specialized manual update is needed, invoke here
                pass

        
        # 속도값 갱신은 슬라이더에서 처리됨
        # 알림 설정 등은 즉시 반영됨
        if self.retry_handler:
            self.retry_handler.max_retries = settings.get("max_retry_count", 3)
        if hasattr(self, 'crawler_tab') and hasattr(self.crawler_tab, 'update_runtime_settings'):
            self.crawler_tab.update_runtime_settings()
        if hasattr(self, 'geo_tab') and hasattr(self.geo_tab, 'update_runtime_settings'):
            self.geo_tab.update_runtime_settings()
        if hasattr(self, "recently_viewed") and hasattr(self.recently_viewed, "set_max_items"):
            self.recently_viewed.set_max_items(settings.get("recently_viewed_count", 50))
        if self.dashboard_widget is not None and hasattr(self.dashboard_widget, "refresh"):
            self.dashboard_widget.refresh()
    
    def _save_preset(self: Any):
        name, ok = QInputDialog.getText(self, "필터 저장", "프리셋 이름:")
        if ok and name:
            ct = self.crawler_tab
            config = {
                "trade": ct.check_trade.isChecked(),
                "jeonse": ct.check_jeonse.isChecked(),
                "monthly": ct.check_monthly.isChecked(),
                "area": {"enabled": ct.check_area_filter.isChecked(), "min": ct.spin_area_min.value(), "max": ct.spin_area_max.value()},
                "price": {
                    "enabled": ct.check_price_filter.isChecked(),
                    "trade_min": ct.spin_trade_min.value(), "trade_max": ct.spin_trade_max.value(),
                    "jeonse_min": ct.spin_jeonse_min.value(), "jeonse_max": ct.spin_jeonse_max.value(),
                    # Legacy monthly keys (rent-based) for compatibility.
                    "monthly_min": ct.spin_monthly_rent_min.value(),
                    "monthly_max": ct.spin_monthly_rent_max.value(),
                    # New split schema for monthly deposit + monthly rent.
                    "monthly_deposit_min": ct.spin_monthly_deposit_min.value(),
                    "monthly_deposit_max": ct.spin_monthly_deposit_max.value(),
                    "monthly_rent_min": ct.spin_monthly_rent_min.value(),
                    "monthly_rent_max": ct.spin_monthly_rent_max.value(),
                }
            }
            if self.preset_manager.save_preset(name, config):
                self.show_toast(f"프리셋 '{name}' 저장 완료")
    
    def _load_preset(self: Any):
        dialog = PresetDialog(self, self.preset_manager)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_preset:
            preset_name = dialog.selected_preset
            config = self.preset_manager.get(preset_name)
            if not config:
                self.show_toast(f"프리셋 '{preset_name}' 불러오기 실패")
                return
            ct = self.crawler_tab
            ct.check_trade.setChecked(config.get("trade", True))
            ct.check_jeonse.setChecked(config.get("jeonse", True))
            ct.check_monthly.setChecked(config.get("monthly", False))
            
            area = config.get("area", {})
            ct.check_area_filter.setChecked(area.get("enabled", False))
            ct.spin_area_min.setValue(area.get("min", 0))
            ct.spin_area_max.setValue(area.get("max", 200))
            
            p = config.get("price", {})
            ct.check_price_filter.setChecked(p.get("enabled", False))
            ct.spin_trade_min.setValue(p.get("trade_min", 0))
            ct.spin_trade_max.setValue(p.get("trade_max", 100000))
            ct.spin_jeonse_min.setValue(p.get("jeonse_min", 0))
            ct.spin_jeonse_max.setValue(p.get("jeonse_max", 50000))
            ct.spin_monthly_deposit_min.setValue(
                p.get("monthly_deposit_min", p.get("monthly_min", 0))
            )
            ct.spin_monthly_deposit_max.setValue(
                p.get("monthly_deposit_max", p.get("monthly_max", 50000))
            )
            ct.spin_monthly_rent_min.setValue(
                p.get("monthly_rent_min", p.get("monthly_min", 0))
            )
            ct.spin_monthly_rent_max.setValue(
                p.get("monthly_rent_max", p.get("monthly_max", 5000))
            )
            self.show_toast("프리셋을 불러왔습니다")
    
    def _show_alert_settings(self: Any):
        AlertSettingDialog(self, self.db).exec()
    
    def _show_advanced_filter(self: Any):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab.open_advanced_filter_dialog()
            return
        ui_logger.warning("CrawlerTab unavailable for advanced filter dialog.")
        self.status_bar.showMessage("고급 필터를 열 수 없습니다.")

    def _apply_advanced_filter(self: Any):
        self._show_advanced_filter()

    def _filter_results_advanced(self: Any):
        self._show_advanced_filter()

    def _clear_advanced_filter(self: Any):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab.clear_advanced_filters()
            return
        ui_logger.warning("CrawlerTab unavailable for clearing advanced filter.")

    def _render_results(self: Any, data, render_only=True):
        ui_logger.warning("Deprecated app-level _render_results invoked; ignoring.")

    def _restore_summary(self: Any):
        ui_logger.warning("Deprecated app-level _restore_summary invoked; ignoring.")

    def _is_default_advanced_filter(self: Any, filters: dict) -> bool:
        defaults = {
            "price_min": 0,
            "price_max": 9999999,
            "area_min": 0,
            "area_max": 500,
            "floor_low": True,
            "floor_mid": True,
            "floor_high": True,
            "only_new": False,
            "only_price_down": False,
            "only_price_change": False,
        }
        for key, val in defaults.items():
            if filters.get(key) != val:
                return False
        if filters.get("include_keywords"):
            return False
        if filters.get("exclude_keywords"):
            return False
        return True

    def _refresh_favorite_keys(self: Any):
        try:
            if hasattr(self.db, "get_favorite_keys"):
                self.favorite_keys = set(self.db.get_favorite_keys() or set())
                return
            favorites = self.db.get_favorites()
            keys = set()
            for fav in favorites:
                aid = fav.get("article_id")
                cid = fav.get("complex_id")
                asset_type = str(fav.get("asset_type", "APT") or "APT").strip().upper() or "APT"
                if aid and cid:
                    keys.add((asset_type, aid, cid))
            self.favorite_keys = keys
        except Exception as e:
            ui_logger.debug(f"즐겨찾기 키 로드 실패 (무시): {e}")
            self.favorite_keys = set()

    def _decorate_items_with_favorite_state(self: Any, items):
        if not items:
            return []
        favorite_keys = set(getattr(self, "favorite_keys", set()) or set())
        decorated = []
        for item in items:
            row = dict(item or {})
            article_id = str(row.get("매물ID", "") or "")
            complex_id = str(row.get("단지ID", "") or "")
            asset_type = str(row.get("자산유형", "APT") or "APT").strip().upper() or "APT"
            row["is_favorite"] = bool(
                article_id and complex_id and (asset_type, article_id, complex_id) in favorite_keys
            )
            decorated.append(row)
        return decorated

    def _on_favorite_toggled(self: Any, article_id, complex_id, asset_type, is_fav):
        if not article_id or not complex_id:
            return
        asset_token = str(asset_type or "APT").strip().upper() or "APT"
        try:
            self.db.toggle_favorite(article_id, complex_id, asset_token, is_fav)
        finally:
            key = (asset_token, article_id, complex_id)
            if is_fav:
                self.favorite_keys.add(key)
            else:
                self.favorite_keys.discard(key)
            if hasattr(self, "crawler_tab"):
                self.crawler_tab._update_favorite_state_for_key(key, is_fav)
            if hasattr(self, "geo_tab"):
                self.geo_tab._update_favorite_state_for_key(key, is_fav)
            if hasattr(self, 'favorites_tab'):
                if self.tabs.currentWidget() is self.favorites_tab:
                    self.favorites_tab.refresh()
                    if hasattr(self, "_noncritical_loaded"):
                        self._noncritical_loaded["favorites"] = True
                elif hasattr(self, "_mark_noncritical_stale"):
                    self._mark_noncritical_stale("favorites")
                elif hasattr(self, "_noncritical_loaded"):
                    self._noncritical_loaded["favorites"] = False
    
    def _check_advanced_filter(self: Any, d):
        if hasattr(self, "crawler_tab"):
            return self.crawler_tab._check_advanced_filter(d)
        return True

    def _show_url_batch_dialog(self: Any):
        # Legacy compatibility: delegate to active CrawlerTab.
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab._show_url_batch_dialog()
            return
        ui_logger.warning("CrawlerTab unavailable for URL batch dialog.")
    
    def _add_complexes_from_url(self: Any, urls):
        if hasattr(self, "crawler_tab"):
            self.crawler_tab._add_complexes_from_url(urls)
            return
        ui_logger.warning("CrawlerTab unavailable for _add_complexes_from_url.")

    def _add_complexes_from_dialog(self: Any, complexes):
        if hasattr(self, "crawler_tab"):
            added = 0
            for name, cid in complexes:
                if self.crawler_tab.add_task(name, cid):
                    added += 1
            if complexes:
                self.show_toast(f"{added}개 단지 추가 완료")
            return
        ui_logger.warning("CrawlerTab unavailable for _add_complexes_from_dialog.")

    def _show_excel_template_dialog(self: Any):
        current_template = settings.get("excel_template")
        dlg = ExcelTemplateDialog(self, current_template=current_template)
        dlg.template_saved.connect(self._save_excel_template)
        dlg.exec()

    def _save_excel_template(self: Any, template):
        settings.set("excel_template", template)
        self.show_toast("엑셀 템플릿이 저장되었습니다")

