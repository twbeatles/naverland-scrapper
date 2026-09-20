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

        # 위치 계산 (쌓이도록)
        margin = 20
        y = self.height() - margin - toast.height()
        for t in self.toast_widgets:
            y -= (t.height() + 10)

        x = self.width() - margin - toast.width()
        toast.move(x, y)
        toast.show_toast(duration)

        self.toast_widgets.append(toast)
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
            self.status_bar.showMessage("⏸ 매물 링크를 열 수 없습니다.")
            return

        payload["단지ID"] = complex_id
        payload["매물ID"] = article_id
        payload["자산유형"] = asset_type
        try:
            self.recently_viewed.add(payload)
        except Exception as e:
            ui_logger.debug(f"최근 본 매물 기록 실패 (무시): {e}")
        webbrowser.open(get_article_url(complex_id, article_id, asset_type))

    def _show_recently_viewed_dialog(self: Any):
        """최근 본 매물 다이얼로그 (v13.0)"""
        dlg = QDialog(self)
        dlg.setWindowTitle("🕐 최근 본 매물")
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
