from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppLifecycleNotifyMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...
    def show_toast(self: Any, message, duration=3000, toast_type="info"):
        # Prefer Fluent InfoBar; keep custom Toast as fallback for edge cases.
        try:
            from src.ui.fluent.notify import show_info_bar

            if show_info_bar(
                self,
                message,
                toast_type=toast_type,
                duration=duration,
            ):
                return
        except Exception:
            pass

        toast = ToastWidget(message, toast_type=toast_type, parent=self)
        # ISSUE-020: show 전 width()/height()는 0일 수 있어 adjustSize +
        # sizeHint로 초기 크기를 잡는다 (show 후 _reposition_toasts로 보정).
        try:
            toast.adjustSize()
        except Exception:
            pass
        try:
            _hint = toast.sizeHint()
            _tw = max(int(toast.width()), int(_hint.width()), 320)
            _th = max(int(toast.height()), int(_hint.height()), 1)
        except Exception:
            _tw, _th = 320, 1

        # 위치 계산 (쌓이도록)
        margin = 20
        y = self.height() - margin - _th
        for t in self.toast_widgets:
            y -= (t.height() + 10)

        x = self.width() - margin - _tw
        toast.move(x, y)
        toast.show_toast(duration)

        self.toast_widgets.append(toast)
        # show 후 실제 지오메트리로 위치 재보정 (0-size 폴백 방지).
        try:
            self._reposition_toasts()
        except Exception:
            pass
        # 종료 시 리스트에서 제거
        QTimer.singleShot(
            duration + 500,
            lambda: self.toast_widgets.remove(toast) if toast in self.toast_widgets else None,
        )
        QTimer.singleShot(duration + 500, self._reposition_toasts)

    def _reposition_toasts(self: Any):
        # 이미 삭제된 toast 객체는 목록에서 정리한다.
        alive = []
        for toast in list(self.toast_widgets):
            try:
                toast.isVisible()
                alive.append(toast)
            except RuntimeError:
                continue
            except Exception:
                continue
        self.toast_widgets = alive

        margin = 20
        y = self.height() - margin
        
        # 위치 재조정
        for t in reversed(self.toast_widgets):
            try:
                y -= t.height()
                t.move(self.width() - margin - t.width(), y)
                y -= 10
            except RuntimeError:
                continue

    def show_notification(self: Any, title: str, message: str):
        """시스템 트레이 알림 표시"""
        if (
            settings.get("show_notifications", True)
            and NOTIFICATION_AVAILABLE
            and notification is not None
            and hasattr(notification, "notify")
        ):
            try:
                notification.notify(
                    title=title,
                    message=message,
                    app_name=APP_TITLE,
                    app_icon=None,  # 아이콘 경로 설정 가능
                    timeout=5
                )
            except Exception as e:
                ui_logger.warning(f"알림 표시 실패: {e}")

    def _open_article_and_track(self: Any, article: dict) -> None:
        payload = dict(article or {})
        complex_id = str(payload.get("단지ID", payload.get("complex_id", "")) or "").strip()
        article_id = str(payload.get("매물ID", payload.get("article_id", "")) or "").strip()
        asset_type = (
            str(payload.get("자산유형", payload.get("asset_type", "APT")) or "APT").strip().upper() or "APT"
        )
        if not complex_id or not article_id:
            self.status_bar.showMessage("이 매물은 주소 정보가 없어 열 수 없습니다.")
            return

        payload["단지ID"] = complex_id
        payload["매물ID"] = article_id
        payload["자산유형"] = asset_type
        try:
            self.recently_viewed.add(payload)
        except Exception as e:
            ui_logger.debug(f"최근 본 매물 기록 실패 (무시): {e}")
        webbrowser.open(get_article_url(complex_id, article_id, asset_type))

    def _open_geo_region(self: Any, region: dict) -> None:
        """키워드 검색에서 고른 지역을 지도 탭 중심으로 설정한다."""
        region = dict(region or {})
        name = str(region.get("name", "") or "")
        raw_lat = region.get("latitude")
        raw_lon = region.get("longitude")
        if raw_lat is None or raw_lon is None:
            self.status_bar.showMessage("이 지역은 위치 정보가 없어 지도로 열 수 없습니다.")
            return
        try:
            lat = float(raw_lat)
            lon = float(raw_lon)
        except (TypeError, ValueError):
            self.status_bar.showMessage("이 지역의 위치 정보가 올바르지 않습니다.")
            return
        if not (33.0 <= lat <= 39.5 and 124.0 <= lon <= 132.1):
            self.status_bar.showMessage("이 지역의 위치가 국내 범위를 벗어나 사용할 수 없습니다.")
            return
        geo_tab = getattr(self, "geo_tab", None)
        if geo_tab is None:
            self.status_bar.showMessage("「지도로 찾기」 화면을 열 수 없습니다.")
            return
        try:
            zoom = int(settings.get("geo_default_zoom", 15) or 15)
            rings = int(settings.get("geo_grid_rings", 1) or 0)
            step_px = int(settings.get("geo_grid_step_px", 480) or 480)
            dwell_ms = int(settings.get("geo_sweep_dwell_ms", 600) or 600)
            asset_types = settings.get("geo_asset_types", ["APT", "VL"]) or ["APT", "VL"]
        except (TypeError, ValueError):
            zoom, rings, step_px, dwell_ms, asset_types = 15, 1, 480, 600, ["APT", "VL"]
        geo_tab.apply_geo_profile(
            lat=lat,
            lon=lon,
            zoom=max(12, min(18, zoom)),
            rings=max(0, rings),
            step_px=step_px,
            dwell_ms=dwell_ms,
            asset_types=asset_types,
            persist_last=True,
            region_name=name,
        )
        try:
            self.tabs.setCurrentWidget(geo_tab)
        except Exception as e:
            ui_logger.debug(f"지도 탭 전환 실패 (무시): {e}")
        self.status_bar.showMessage(f"「지도로 찾기」의 탐색 위치를 '{name or '선택한 지역'}'(으)로 정했습니다. 「탐색 시작」을 눌러 주세요.")

    def _show_recently_viewed_dialog(self: Any):
        """최근 본 매물 다이얼로그 (v13.0)"""
        dlg = QDialog(self)
        dlg.setWindowTitle("최근 본 매물")
        dlg.resize(900, 600)
        
        layout = QVBoxLayout(dlg)
        
        # 안내 문구
        recent_limit = int(getattr(self.recently_viewed, "max_items", settings.get("recently_viewed_count", 50)) or 50)
        info = QLabel(f"최근에 확인한 매물 목록입니다 (최대 {recent_limit}개).")
        from src.ui.styles import COLORS

        info_color = COLORS.get(self.current_theme, COLORS["dark"])["text_secondary"]
        info.setStyleSheet(f"color: {info_color}; margin-bottom: 10px; background: transparent;")
        layout.addWidget(info)
        
        # 목록 (CardView 재사용)
        recent_items = self.recently_viewed.get_recent()
        
        if not recent_items:
            empty_lbl = QLabel("최근 본 매물이 없습니다.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty_lbl)
        else:
            from src.ui.widgets.cards import CardViewWidget

            card_view = CardViewWidget(is_dark=(self.current_theme=="dark"))
            card_view.set_data(self._decorate_items_with_favorite_state(recent_items))
            card_view.article_clicked.connect(self._open_article_and_track)
            card_view.favorite_toggled.connect(self._on_favorite_toggled)
            layout.addWidget(card_view)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)
        
        dlg.exec()
