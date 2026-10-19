from datetime import date

from src.core.services.price_trend import (
    build_series,
    filter_period,
    format_pct,
    pick_chart_series,
    previous_avg_map,
    summarize,
)


def _row(day, trade, pyeong, mn, mx, avg, cnt=1, metric="price"):
    return (day, trade, pyeong, mn, mx, avg, cnt, metric, 0)


ROWS = [
    # get_price_snapshots 는 날짜 내림차순으로 돌려준다.
    _row("2026-03-01", "매매", 34.0, 100000, 120000, 110000, 3),
    _row("2026-02-01", "매매", 34.0, 98000, 110000, 104000, 2),
    _row("2026-02-01", "매매", 25.0, 70000, 80000, 75000, 4),
    _row("2026-01-01", "매매", 34.0, 95000, 105000, 100000, 5),
]


def test_build_series_groups_by_trade_and_pyeong_sorted_by_date():
    series = build_series(ROWS)
    assert [(s.trade_type, s.pyeong) for s in series] == [("매매", 25.0), ("매매", 34.0)]
    big = series[1]
    assert [p.date_text for p in big.points] == ["2026-01-01", "2026-02-01", "2026-03-01"]


def test_build_series_skips_unparseable_rows():
    series = build_series([("bad-date", "매매", 34.0, 1, 1, 1, 1, "price", 0), ("2026-01-01", "매매", None, 1, 1, 1, 1)])
    assert series == []


def test_summarize_reports_period_and_previous_change():
    big = build_series(ROWS)[1]
    summary = summarize(big)
    assert summary is not None
    assert summary.latest_avg == 110000
    assert summary.first_avg == 100000
    assert summary.period_change == 10000
    assert summary.period_change_pct == 10.0
    assert summary.prev_change == 6000
    assert round(summary.prev_change_pct or 0, 2) == 5.77
    assert (summary.period_low, summary.period_high) == (95000, 120000)
    assert summary.record_days == 3
    assert summary.latest_count == 3


def test_summarize_single_point_has_no_previous():
    small = build_series(ROWS)[0]
    summary = summarize(small)
    assert summary is not None
    assert summary.record_days == 1
    assert summary.prev_change is None
    assert summary.period_change == 0


def test_filter_period_keeps_recent_rows_only():
    kept = filter_period(ROWS, 40, today=date(2026, 3, 5))
    assert {r[0] for r in kept} == {"2026-03-01", "2026-02-01"}
    assert filter_period(ROWS, None) == ROWS


def test_previous_avg_map_points_to_prior_record():
    prev = previous_avg_map(build_series(ROWS))
    assert prev[("매매", 34.0, "2026-03-01")] == 104000
    assert prev[("매매", 34.0, "2026-02-01")] == 100000
    assert ("매매", 34.0, "2026-01-01") not in prev
    assert ("매매", 25.0, "2026-02-01") not in prev


def test_format_pct_and_pick_chart_series():
    assert format_pct(None) == ""
    assert format_pct(0.01) == "0.0%"
    assert format_pct(5.77) == "+5.8%"
    assert format_pct(-3.21) == "-3.2%"
    picked = pick_chart_series(build_series(ROWS), limit=1)
    assert [s.pyeong for s in picked] == [34.0]


def test_per_pyeong_series_weights_sizes_by_item_count():
    from src.core.services.price_trend import per_pyeong_series

    series = per_pyeong_series(ROWS, "매매")
    assert series is not None
    by_day = {p.date_text: p for p in series.points}
    assert [p.date_text for p in series.points] == ["2026-01-01", "2026-02-01", "2026-03-01"]
    assert by_day["2026-01-01"].avg_price == round(100000 / 34)
    # 2/1: 34평(104000, 2건) + 25평(75000, 4건) 가중 평균
    expected = (104000 / 34 * 2 + 75000 / 25 * 4) / 6
    assert by_day["2026-02-01"].avg_price == round(expected)
    assert by_day["2026-02-01"].item_count == 6
    assert per_pyeong_series([], "매매") is None


def test_format_price_axis():
    from src.ui.widgets.chart import format_price_axis

    assert format_price_axis(85000) == "8.5억"
    assert format_price_axis(100000) == "10억"
    assert format_price_axis(300) == "300만"
