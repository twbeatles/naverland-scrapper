## 시세 흐름 (formerly 가격 통계)

- The price-statistics page is now `시세 흐름` and redraws as soon as the complex, trade type, size, or period changes. No more pressing `보기`. It opens on `매매` instead of `전체`, so the first visit shows a chart rather than a "narrow it down" message.
- New change summary: latest average, change over the period (amount and %), change since the previous record, period low–high, and number of recorded days.
- New period filter (1/3/6 months, 1 year, all). Prices show in 억/만, and the table adds `매물 수` and `직전 대비` columns (rises red, falls blue).
- Convenience defaults: a complex with only one size selects it automatically. Switching to a complex with no records for the chosen trade type falls back to one that has records. A trade type you pick yourself is never changed.
- Chart: follows dark/light theme and redraws on theme switch. Fixed axis text losing its color after a redraw. 억/만 axis labels, year-aware dates, one average line per size with the period % in the legend, and the exact latest amount on the last point.

## Complex comparison

- `다른 단지와 비교…` overlays up to 5 other complexes. They are compared on average price per pyeong (만원/평) for the same trade type, so complexes with different unit sizes line up. Complexes without records are left out, and the status bar names them. The summary and table still describe the main complex.

## Faster navigation

- `내 단지` → `시세 흐름 보기` button.
- `수집 기록` → double-click a row.
- `매물 수집` / `지도로 찾기` results table and complex list → right-click → `이 단지 시세 흐름 보기`.

## Build and verification

- New Qt-free trend module with unit tests (`tests/test_price_trend.py`, added to the CI subset), plus UI wiring tests for the navigation, fallback, summary, and comparison flows.
- Pyright 0 errors, CI subset and full pytest passing, preflight clean.
