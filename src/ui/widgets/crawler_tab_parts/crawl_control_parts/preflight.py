from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


class CrawlerTabPreflightMixin:
    """수집 시작 전 점검(조건 범위·확인·입력 잠금)과 끝난 뒤 요약."""

    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    SQM_PER_PYEONG = 3.3058

    #: 수집 중에는 바꿔도 반영되지 않으므로 잠가 두는 입력들.
    LOCKABLE_INPUT_NAMES: tuple[str, ...] = (
        "btn_find_complex",
        "btn_load_complex",
        "input_name",
        "input_id",
        "combo_manual_asset",
        "btn_manual_add",
        "check_trade",
        "check_jeonse",
        "check_monthly",
        "filter_panel",
    )

    # ── 조건 범위: 환산 표시 · 검증 · 접힌 상태 요약 ─────────────────
    def _price_filter_rows(self: Any):
        return (
            ("매매 가격", "매매", self.check_trade, self.spin_trade_min, self.spin_trade_max),
            ("전세 가격", "전세", self.check_jeonse, self.spin_jeonse_min, self.spin_jeonse_max),
            (
                "월세 보증금",
                "월세 보증금",
                self.check_monthly,
                self.spin_monthly_deposit_min,
                self.spin_monthly_deposit_max,
            ),
            ("월세", "월", self.check_monthly, self.spin_monthly_rent_min, self.spin_monthly_rent_max),
        )

    @staticmethod
    def _sqm_to_pyeong_text(sqm) -> str:
        try:
            return f"{float(sqm) / 3.3058:.0f}평"
        except (TypeError, ValueError):
            return "-"

    @staticmethod
    def _price_range_text(low, high) -> str:
        return f"{PriceConverter.to_string(int(low))} ~ {PriceConverter.to_string(int(high))}"

    def _filter_range_issues(self: Any):
        """켜져 있는 조건 중 최소가 최대보다 큰 항목을 (이름, 최소 칸)으로 돌려준다."""
        issues = []
        if self.check_area_filter.isChecked() and self.spin_area_min.value() > self.spin_area_max.value():
            issues.append(("면적", self.spin_area_min))
        if self.check_price_filter.isChecked():
            for label, _short, check, spin_min, spin_max in self._price_filter_rows():
                if check.isChecked() and spin_min.value() > spin_max.value():
                    issues.append((label, spin_min))
        return issues

    def _filter_summary_text(self: Any) -> str:
        parts = []
        if self.check_area_filter.isChecked():
            parts.append(f"면적 {self.spin_area_min.value()}~{self.spin_area_max.value()}㎡")
        if self.check_price_filter.isChecked():
            parts.append("가격 범위 지정")
        slider = getattr(self, "speed_slider", None)
        speed = slider.current_speed() if slider is not None else ""
        if not parts:
            text = "조건 없음 · 모든 매물을 수집합니다"
        else:
            text = "적용 중: " + " · ".join(parts)
        if speed:
            text += f" · 속도 {speed}"
        if self._filter_range_issues():
            text = "확인 필요 · " + text
        return text

    def _refresh_filter_feedback(self: Any, *_args):
        """조건 영역의 환산 표시·오류 안내·접힌 상태 요약을 현재 값에 맞춘다."""
        if getattr(self, "lbl_filter_summary", None) is None:
            return
        area_on = self.check_area_filter.isChecked()
        self.lbl_area_hint.setVisible(area_on)
        if area_on:
            self.lbl_area_hint.setText(
                f"약 {self._sqm_to_pyeong_text(self.spin_area_min.value())}"
                f" ~ {self._sqm_to_pyeong_text(self.spin_area_max.value())}"
            )

        price_on = self.check_price_filter.isChecked()
        price_parts = []
        for _label, short, check, spin_min, spin_max in self._price_filter_rows():
            active = price_on and check.isChecked()
            # 고르지 않은 거래 종류의 가격 칸은 쓰이지 않으므로 꺼 둔다.
            spin_min.setEnabled(active)
            spin_max.setEnabled(active)
            if active:
                price_parts.append(f"{short} {self._price_range_text(spin_min.value(), spin_max.value())}")
        self.lbl_price_hint.setVisible(price_on)
        if price_on:
            self.lbl_price_hint.setText(
                " · ".join(price_parts) if price_parts else "위에서 거래 종류를 먼저 골라 주세요."
            )

        issues = self._filter_range_issues()
        self.lbl_filter_error.setVisible(bool(issues))
        if issues:
            names = ", ".join(name for name, _spin in issues)
            self.lbl_filter_error.setText(f"최소 값이 최대 값보다 큽니다: {names}")

        self.lbl_filter_summary.setText(self._filter_summary_text())
        toggle = getattr(self, "btn_filter_toggle", None)
        # 펼쳐 두었더라도 범위가 잘못됐으면 맨 위에서 바로 보이게 한다.
        self.lbl_filter_summary.setVisible(bool(issues) or toggle is None or not toggle.isChecked())

    def _validate_filter_ranges(self: Any) -> bool:
        issues = self._filter_range_issues()
        if not issues:
            return True
        self._reveal_filter_panel()
        names = ", ".join(name for name, _spin in issues)
        self._notify_start_blocked(
            f"조건 범위를 확인해 주세요. 최소 값이 최대 값보다 큽니다: {names}"
        )
        try:
            issues[0][1].setFocus()
        except RuntimeError:
            pass
        return False

    # ── 시작이 거부될 때: 진행 기록만이 아니라 눈에 보이게 알린다 ──────
    def _notify_start_blocked(self: Any, message: str) -> None:
        self.append_log(message, 30)
        self.status_message.emit(message)
        try:
            show_toast = getattr(self.window(), "show_toast", None)
            if callable(show_toast):
                show_toast(message, toast_type="warning")
        except RuntimeError:
            pass

    # ── 사람이 직접 시작할 때의 진입점 (예약·자동 실행은 start_crawling) ──
    def _is_crawl_running(self: Any) -> bool:
        thread = getattr(self, "crawler_thread", None)
        try:
            return bool(thread is not None and thread.isRunning())
        except (RuntimeError, AttributeError):
            return False

    def _confirm_start(self: Any) -> bool:
        if self._is_crawl_running():
            return True
        count = len(getattr(self, "collected_data", None) or [])
        if count <= 0 or getattr(self, "_results_exported", False):
            return True
        answer = QMessageBox.question(
            self,
            "이전 결과를 지우고 다시 수집할까요?",
            f"지금 화면의 매물 {count}건은 아직 파일로 저장하지 않았습니다.\n"
            "다시 수집하면 이 목록은 화면에서 지워집니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def request_start(self: Any) -> bool:
        if not self._confirm_start():
            return False
        return bool(self.start_crawling())

    def _begin_crawl_session(self: Any) -> None:
        """새 수집이 실제로 시작될 때 한 번: 상태 초기화 + 입력 잠금."""
        import time

        self._stop_requested = False
        self._results_exported = False
        self._crawl_started_at = time.monotonic()
        self._hide_run_summary()
        self._set_inputs_locked(True)

    # ── 수집 중 입력 잠금 ────────────────────────────────────────────
    def _set_inputs_locked(self: Any, locked: bool) -> None:
        self._inputs_locked = bool(locked)
        for name in self.LOCKABLE_INPUT_NAMES:
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setEnabled(not locked)
        notice = getattr(self, "lbl_inputs_locked", None)
        if notice is not None:
            notice.setVisible(bool(locked))
        self._update_task_list_state()
        if not locked:
            self._refresh_filter_feedback()

    # ── 끝난 뒤 요약 ────────────────────────────────────────────────
    @staticmethod
    def _format_elapsed(seconds) -> str:
        try:
            total = max(0, int(seconds))
        except (TypeError, ValueError):
            return ""
        minutes, secs = divmod(total, 60)
        if minutes >= 60:
            hours, minutes = divmod(minutes, 60)
            return f"{hours}시간 {minutes}분"
        return f"{minutes}분 {secs}초" if minutes else f"{secs}초"

    @staticmethod
    def _run_summary_texts(count: int, stats: dict, *, stopped: bool, elapsed_text: str = ""):
        """(한 줄 요약, 참고 사항)을 만든다."""

        def _n(key):
            try:
                return int(stats.get(key, 0) or 0)
            except (TypeError, ValueError, AttributeError):
                return 0

        if stopped:
            head = [f"수집을 중지했습니다 · 그때까지 모은 매물 {count}건"]
        elif count > 0:
            head = [f"수집 완료 · 매물 {count}건"]
        else:
            head = ["수집 완료 · 조건에 맞는 매물이 없습니다"]
        for label, key in (("신규", "new_count"), ("가격 상승", "price_up"), ("가격 하락", "price_down")):
            if _n(key) > 0:
                head.append(f"{label} {_n(key)}건")
        if elapsed_text:
            head.append(f"소요 {elapsed_text}")

        notes = []
        filtered = _n("filtered_out")
        if filtered > 0:
            note = f"조건(면적·가격)에 맞지 않아 뺀 매물 {filtered}건"
            if count <= 0:
                note += " — 조건을 넓히면 매물이 나올 수 있습니다"
            notes.append(note)
        if _n("block_like_redirect_count") + _n("blocked_page_count") > 0:
            notes.append("네이버가 접속을 제한한 흔적이 있습니다. 속도를 낮춰 다시 시도해 보세요")
        skipped = _n("detail_fetch_skipped_count") + _n("detail_cap_truncated")
        if skipped > 0:
            notes.append(f"{skipped}건은 중개소 등 상세 정보 없이 기본 정보만 담았습니다")
        return " · ".join(head), " / ".join(notes)

    def _show_run_summary(self: Any, count: int, stats: dict, *, stopped: bool) -> None:
        frame = getattr(self, "run_summary", None)
        if frame is None:
            return
        import time

        started = getattr(self, "_crawl_started_at", None)
        elapsed_text = self._format_elapsed(time.monotonic() - started) if started else ""
        head, notes = self._run_summary_texts(count, stats or {}, stopped=stopped, elapsed_text=elapsed_text)
        self.lbl_run_summary.setText(head)
        self.lbl_run_summary_notes.setText(notes)
        self.lbl_run_summary_notes.setVisible(bool(notes))
        frame.setVisible(True)

    def _hide_run_summary(self: Any) -> None:
        frame = getattr(self, "run_summary", None)
        if frame is not None:
            frame.setVisible(False)
