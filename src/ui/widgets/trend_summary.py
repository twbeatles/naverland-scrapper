"""시세 흐름 화면 상단의 변화 요약 띠 (최근 평균 · 기간 변화 · 직전 대비 · 범위 · 기록)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.core.services.price_trend import TrendSummary, format_pct
from src.ui.styles import COLORS
from src.utils.helpers import PriceConverter


def _signed_price(delta: Optional[int]) -> str:
    if delta is None:
        return "-"
    if delta == 0:
        return "변동 없음"
    return PriceConverter.to_signed_string(delta)


class TrendSummaryStrip(QFrame):
    """선택한 시리즈 하나의 시세 변화를 숫자로 요약한다."""

    KEYS = ("latest", "period", "prev", "range", "records")

    def __init__(self, parent=None, theme: str = "dark"):
        super().__init__(parent)
        self.setObjectName("summaryCard")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._theme = theme if theme in COLORS else "dark"
        self._directions: dict[str, int] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        self._titles: dict[str, QLabel] = {}
        self._values: dict[str, QLabel] = {}
        self._subs: dict[str, QLabel] = {}
        specs = (
            ("latest", "최근 평균", "가장 최근 기록일의 평균 가격입니다."),
            ("period", "기간 변화", "고른 기간의 첫 기록 대비 최근 평균 가격 변화입니다."),
            ("prev", "직전 기록 대비", "바로 이전 기록일 대비 평균 가격 변화입니다."),
            ("range", "기간 최저~최고", "고른 기간에 나온 매물 가격의 최저와 최고입니다."),
            ("records", "기록", "가격이 기록된 날짜 수와 기간입니다."),
        )
        for key, title, tip in specs:
            box = QWidget()
            box.setToolTip(tip)
            v = QVBoxLayout(box)
            v.setContentsMargins(8, 2, 8, 2)
            v.setSpacing(2)
            t = QLabel(title)
            val = QLabel("-")
            val.setObjectName("value")
            sub = QLabel("")
            v.addWidget(t)
            v.addWidget(val)
            v.addWidget(sub)
            self._titles[key], self._values[key], self._subs[key] = t, val, sub
            layout.addWidget(box)
        layout.addStretch(1)

        self.hint_label = QLabel("")
        self.hint_label.setWordWrap(True)
        self.hint_label.hide()
        layout.addWidget(self.hint_label, 2)
        self._apply_colors()

    # --- theme -----------------------------------------------------------
    def set_theme(self, theme: str) -> None:
        self._theme = theme if theme in COLORS else "dark"
        self._apply_colors()

    def _direction_color(self, direction: int) -> str:
        c = COLORS[self._theme]
        if direction > 0:
            return c["error_light"]
        if direction < 0:
            return c["trade_월세"]
        return c["text_primary"]

    def _apply_colors(self) -> None:
        c = COLORS[self._theme]
        for key in self.KEYS:
            self._titles[key].setStyleSheet(f"color: {c['text_secondary']}; font-size: 11px; font-weight: 500;")
            self._subs[key].setStyleSheet(f"color: {c['text_secondary']}; font-size: 11px;")
            color = self._direction_color(self._directions.get(key, 0))
            self._values[key].setStyleSheet(f"color: {color}; font-size: 17px; font-weight: 700;")
        self.hint_label.setStyleSheet(f"color: {c['text_secondary']}; font-size: 12px;")

    # --- content ---------------------------------------------------------
    def value_text(self, key: str) -> str:
        return self._values[key].text()

    def _set(self, key: str, value: str, sub: str = "", direction: int = 0) -> None:
        self._values[key].setText(value)
        self._subs[key].setText(sub)
        self._directions[key] = direction

    def clear(self, hint: str = "") -> None:
        for key in self.KEYS:
            self._set(key, "-")
        self.hint_label.setText(hint)
        self.hint_label.setVisible(bool(hint))
        self._apply_colors()

    def set_summary(self, summary: Optional[TrendSummary], *, hint: str = "") -> None:
        if summary is None:
            self.clear(hint or "요약할 가격 기록이 없습니다.")
            return
        to_s = PriceConverter.to_string
        self._set("latest", to_s(summary.latest_avg), f"{summary.latest_date} · 매물 {summary.latest_count}건")
        if summary.record_days >= 2:
            self._set(
                "period",
                _signed_price(summary.period_change),
                f"{format_pct(summary.period_change_pct)} · {summary.first_date}부터".lstrip(" ·"),
                (summary.period_change > 0) - (summary.period_change < 0),
            )
            prev = summary.prev_change or 0
            self._set(
                "prev",
                _signed_price(summary.prev_change),
                format_pct(summary.prev_change_pct),
                (prev > 0) - (prev < 0),
            )
        else:
            self._set("period", "-", "기록이 하루치뿐입니다")
            self._set("prev", "-", "")
        self._set("range", f"{to_s(summary.period_low)} ~ {to_s(summary.period_high)}")
        span = summary.first_date if summary.first_date == summary.latest_date else f"{summary.first_date} ~ {summary.latest_date}"
        self._set("records", f"{summary.record_days}일", span)
        self.hint_label.setText(hint)
        self.hint_label.setVisible(bool(hint))
        self._apply_colors()
