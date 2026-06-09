# Update History

## 2026-06-09: Performance And Structure Refactor

### 수집 성능

- Playwright complex 수집에 Article API fast path를 추가했습니다.
- API 실패, 비정상 payload, 403/404/429, 네트워크 예외는 기존 response-capture 경로로 fallback합니다.
- API 200 + 빈 목록은 확정 empty로 처리합니다.
- response-capture는 article API 응답 감지 시 조기 종료합니다.
- 마지막 성공 entry plan을 우선 시도하되 실패 시 기존 plan을 유지합니다.

### DB 성능

- `price_snapshots` 정규화/중복 제거 migration을 추가했습니다.
- `(snapshot_date, asset_type, complex_id, trade_type, pyeong, price_metric, legacy_monthly)` unique index를 추가했습니다.
- `add_price_snapshots_bulk`를 memory dedupe + `executemany INSERT ... ON CONFLICT DO UPDATE`로 바꿨습니다.
- disappeared article 조회/mark 경로용 covering index를 추가했습니다.
- SQLite connection pool에 `temp_store`, `cache_size`, `mmap_size` PRAGMA를 best-effort 적용합니다.

### 사용자 체감 성능

- 가격 스냅샷 저장을 UI 완료 처리 이후 worker로 넘깁니다.
- 결과 테이블 렌더링 설정값을 batch 단위로 캐시합니다.
- dashboard lazy 생성과 첫 열기 성능을 유지했습니다.

### 구조 분리

- `src/utils/mixin_rebind.py` 공통 rebind 유틸을 추가했습니다.
- DB, Playwright, CrawlerTab, parser, live smoke, dashboard, styles를 facade + `*_parts/` 구조로 분리했습니다.
- 기존 공개 class/function import 경로는 유지했습니다.
- `tests/test_rebind_methods.py`를 MRO 기반 nested mixin 검사와 facade import smoke로 확장했습니다.

### 검증

- `python -m pytest -q` -> `287 passed`
- `python scripts/perf_baseline.py` 통과
- `python app_entry.py --live-smoke --smoke-headless --live-smoke-detail-fields --smoke-json-log logs/live-smoke-after-structure.json` 통과

## 현재 운영 메모

- 신규 크롤링 의존성은 추가하지 않았습니다.
- Scrapling은 도입하지 않았고 기존 Playwright/SQLite/UI 구조를 유지합니다.
- PyInstaller spec에는 추가 hidden import/data 변경이 필요 없습니다.
- `.gitignore`의 기존 generated artifact 규칙은 현재 변경에도 충분합니다.
