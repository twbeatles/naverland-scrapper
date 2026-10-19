"""Price-trend analysis over stored ``price_snapshots`` rows (Qt-free).

`get_price_snapshots()` 가 돌려주는 행
``(date, trade_type, pyeong, min, max, avg, count, metric, legacy_monthly)``
을 시리즈(거래 종류 × 평형)로 묶고, 기간 필터와 변화 요약을 계산한다.
가격 단위는 DB와 같은 만원 정수다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Iterable, Optional, Sequence

# (label, days) — days=None 이면 전체 기간
PERIOD_OPTIONS: tuple[tuple[str, Optional[int]], ...] = (
    ("전체 기간", None),
    ("최근 1개월", 31),
    ("최근 3개월", 92),
    ("최근 6개월", 183),
    ("최근 1년", 366),
)

TRADE_TYPE_PRIORITY: tuple[str, ...] = ("매매", "전세", "월세")

MSG_PICK_TRADE_TYPE = (
    "거래 종류를 하나 고르면 그래프가 나타납니다.\n"
    "매매·전세·월세는 가격 기준이 달라 한 그래프에 겹쳐 그리지 않습니다."
)


@dataclass(frozen=True)
class TrendPoint:
    day: date
    date_text: str
    min_price: int
    max_price: int
    avg_price: int
    item_count: int


@dataclass
class TrendSeries:
    trade_type: str
    pyeong: float
    metric: str
    points: list[TrendPoint] = field(default_factory=list)

    @property
    def key(self) -> tuple[str, float]:
        return (self.trade_type, self.pyeong)


@dataclass(frozen=True)
class TrendSummary:
    latest_avg: int
    latest_date: str
    latest_count: int
    first_avg: int
    first_date: str
    period_change: int
    period_change_pct: Optional[float]
    prev_change: Optional[int]
    prev_change_pct: Optional[float]
    period_low: int
    period_high: int
    record_days: int


def parse_snapshot_date(value) -> Optional[date]:
    text = str(value or "").strip()
    if not text:
        return None
    for candidate in (text[:10], text):
        try:
            return datetime.strptime(candidate, "%Y-%m-%d").date()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def _to_int(value) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def build_series(snapshots: Iterable[Sequence]) -> list[TrendSeries]:
    """스냅샷 행을 (거래 종류, 평형) 시리즈로 묶고 날짜 오름차순 정렬한다."""
    grouped: dict[tuple[str, float], TrendSeries] = {}
    for row in snapshots:
        if len(row) < 7:
            continue
        day = parse_snapshot_date(row[0])
        if day is None:
            continue
        try:
            pyeong = float(row[2])
        except (TypeError, ValueError):
            continue
        trade_type = str(row[1] or "")
        metric = str(row[7] if len(row) > 7 and row[7] else "price")
        key = (trade_type, pyeong)
        series = grouped.get(key)
        if series is None:
            series = TrendSeries(trade_type=trade_type, pyeong=pyeong, metric=metric)
            grouped[key] = series
        series.points.append(
            TrendPoint(
                day=day,
                date_text=str(row[0])[:10],
                min_price=_to_int(row[3]),
                max_price=_to_int(row[4]),
                avg_price=_to_int(row[5]),
                item_count=max(0, _to_int(row[6])),
            )
        )
    result = list(grouped.values())
    for series in result:
        series.points.sort(key=lambda p: p.day)
    result.sort(key=lambda s: (_trade_rank(s.trade_type), s.pyeong))
    return result


def _trade_rank(trade_type: str) -> int:
    try:
        return TRADE_TYPE_PRIORITY.index(trade_type)
    except ValueError:
        return len(TRADE_TYPE_PRIORITY)


def period_cutoff(days: Optional[int], *, today: Optional[date] = None) -> Optional[date]:
    if not days:
        return None
    return (today or date.today()) - timedelta(days=int(days))


def filter_period(snapshots: Iterable[Sequence], days: Optional[int], *, today: Optional[date] = None) -> list:
    """``days`` 이내 스냅샷만 남긴다. 날짜를 못 읽는 행은 전체 기간에서만 유지."""
    rows = list(snapshots)
    cutoff = period_cutoff(days, today=today)
    if cutoff is None:
        return rows
    kept = []
    for row in rows:
        day = parse_snapshot_date(row[0] if row else None)
        if day is not None and day >= cutoff:
            kept.append(row)
    return kept


def _pct(delta: int, base: int) -> Optional[float]:
    if base <= 0:
        return None
    return delta / base * 100.0


def summarize(series: TrendSeries) -> Optional[TrendSummary]:
    points = [p for p in series.points if p.avg_price > 0]
    if not points:
        return None
    first, last = points[0], points[-1]
    prev = points[-2] if len(points) >= 2 else None
    period_change = last.avg_price - first.avg_price
    prev_change = (last.avg_price - prev.avg_price) if prev is not None else None
    lows = [p.min_price for p in points if p.min_price > 0] or [p.avg_price for p in points]
    highs = [p.max_price for p in points if p.max_price > 0] or [p.avg_price for p in points]
    return TrendSummary(
        latest_avg=last.avg_price,
        latest_date=last.date_text,
        latest_count=last.item_count,
        first_avg=first.avg_price,
        first_date=first.date_text,
        period_change=period_change,
        period_change_pct=_pct(period_change, first.avg_price),
        prev_change=prev_change,
        prev_change_pct=_pct(prev_change, prev.avg_price) if prev is not None and prev_change is not None else None,
        period_low=min(lows),
        period_high=max(highs),
        record_days=len(points),
    )


def previous_avg_map(series_list: Iterable[TrendSeries]) -> dict[tuple[str, float, str], int]:
    """(거래 종류, 평형, 날짜) → 직전 기록일 평균가. 표의 '직전 대비' 칸에 쓴다."""
    result: dict[tuple[str, float, str], int] = {}
    for series in series_list:
        prev_avg: Optional[int] = None
        for point in series.points:
            if prev_avg is not None and prev_avg > 0:
                result[(series.trade_type, series.pyeong, point.date_text)] = prev_avg
            if point.avg_price > 0:
                prev_avg = point.avg_price
    return result


def format_pct(value: Optional[float]) -> str:
    if value is None:
        return ""
    if abs(value) < 0.05:
        return "0.0%"
    return f"{value:+.1f}%"


def per_pyeong_series(snapshots: Iterable[Sequence], trade_type: str = "") -> Optional[TrendSeries]:
    """날짜별 평당 평균가(만원/평) 시리즈. 면적이 다른 단지끼리 비교할 때 쓴다.

    같은 날의 여러 면적은 매물 수로 가중 평균한다. ``pyeong`` 은 0으로 둔다.
    """
    by_day: dict[date, list] = {}
    texts: dict[date, str] = {}
    metric = "price"
    for row in snapshots:
        if len(row) < 7:
            continue
        day = parse_snapshot_date(row[0])
        if day is None:
            continue
        try:
            pyeong = float(row[2])
        except (TypeError, ValueError):
            continue
        avg = _to_int(row[5])
        if pyeong <= 0 or avg <= 0:
            continue
        weight = max(1, _to_int(row[6]))
        per = avg / pyeong
        lo = _to_int(row[3]) / pyeong if _to_int(row[3]) > 0 else per
        hi = _to_int(row[4]) / pyeong if _to_int(row[4]) > 0 else per
        if len(row) > 7 and row[7]:
            metric = str(row[7])
        acc = by_day.setdefault(day, [0.0, 0, per, per, 0])
        acc[0] += per * weight
        acc[1] += weight
        acc[2] = min(acc[2], lo)
        acc[3] = max(acc[3], hi)
        acc[4] += max(0, _to_int(row[6]))
        texts[day] = str(row[0])[:10]
    if not by_day:
        return None
    series = TrendSeries(trade_type=str(trade_type or ""), pyeong=0.0, metric=metric)
    for day in sorted(by_day):
        total, weight, lo, hi, count = by_day[day]
        series.points.append(
            TrendPoint(
                day=day,
                date_text=texts[day],
                min_price=int(round(lo)),
                max_price=int(round(hi)),
                avg_price=int(round(total / weight)),
                item_count=int(count),
            )
        )
    return series


def pick_chart_series(series_list: Sequence[TrendSeries], limit: int = 6) -> list[TrendSeries]:
    """기록이 많은 순으로 최대 ``limit`` 개를 고르고 평형 순으로 돌려준다."""
    ranked = sorted(series_list, key=lambda s: (-len(s.points), s.pyeong))[: max(1, int(limit))]
    return sorted(ranked, key=lambda s: s.pyeong)
