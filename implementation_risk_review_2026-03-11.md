# Implementation Risk Review (2026-03-11)

## Scope
- Source plan: F-01 ~ F-09 (batch application)
- Fixed decisions:
  - F-05 = Hybrid circuit breaker
  - F-06 = List-key-only split
  - F-07 = Skip empty history

## Applied Status

### F-01 Selenium reliability / negative cache correctness
- Status: Applied
- Implementation points:
  - Added parse/crawl metadata: `response_seen`, `parse_success`, `empty_confirmed`, `blocked_detected`
  - Negative cache save condition tightened to confirmed-empty only
  - Cache reason normalized to `confirmed_empty`
- Test coverage:
  - Selenium negative cache strict-condition regressions

### F-02 UI retry consistency (Geo tab)
- Status: Applied
- Implementation points:
  - Geo crawler start path now enforces `max_retry_count=0` when `retry_on_error=False`
- Test coverage:
  - Geo tab wiring test for retry-off path

### F-03 DB scalability (disappeared update chunking)
- Status: Applied
- Implementation points:
  - `mark_disappeared_articles_for_targets` now updates in parameter-safe chunks
  - Returns accumulated updated-row count
- Test coverage:
  - Large target (500+) chunk behavior test

### F-04 DB lock contention hardening
- Status: Applied
- Implementation points:
  - `add_complex` write lock + busy-timeout + lock retry + rollback path
- Test coverage:
  - `database is locked` retry path test

### F-05 Block detection breaker (hybrid)
- Status: Applied
- Fixed values:
  - Pair streak threshold: 2
  - Pair cooldown: 90s
  - Global abort threshold: 5
- Implementation points:
  - Cooldown pair skip + disappeared-mark exclusion
  - Global threshold triggers session abort
- Test coverage:
  - Pair cooldown / global abort regressions

### F-06 Stats key collision policy
- Status: Applied
- Implementation points:
  - Internal keying with `(asset_type, complex_id)` to avoid collisions
  - Return plain CID by default; collision CID only => `asset:cid`
  - Stats UI parser accepts both plain and compound keys
- Test coverage:
  - Compound key interpretation + collision split tests

### F-07 Geo empty history skip
- Status: Applied
- Implementation points:
  - Skip `crawl_history` write when `complex_trade_types` is empty
- Test coverage:
  - Geo mode empty-history skip test

### F-08 Playwright string cleanup
- Status: Applied
- Implementation points:
  - Replaced unreadable/broken log/exception strings in:
    - `playwright_parts/complex_mode.py`
    - `playwright_parts/geo_mode.py`
- Test coverage:
  - Functional regression coverage maintained in Playwright stabilization tests

### F-09 Observability metrics expansion
- Status: Applied
- Added stats payload keys:
  - `response_seen_count`
  - `parse_success_count`
  - `parse_fail_count`
  - `detail_success_count`
  - `detail_fail_count`
  - `blocked_page_count`
- Test coverage:
  - Selenium/Playwright metric increment regressions

## Verification Summary
- Targeted regressions: passed
- Full test run:
  - Command: `pytest -q`
  - Result: `112 passed`

## Packaging Recheck
- `naverland-scrapper.spec` reviewed against F-01~F-09 code changes.
- Result: no additional hidden-import/runtime-hook change required.

## Document Sync
- Synced files:
  - `README.md`
  - `claude.md`
  - `gemini.md`
  - `update_history.md`
