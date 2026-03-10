# 기능 구현 점검 리포트 (2026-03-10)

## 검토 기준
- 참조 문서: `README.md`, `claude.md`
- 목적: 현재 구현에서 운영 중 문제로 이어질 수 있는 잠재 결함과 보완 필요 항목 식별
- 범위: 크롤링 엔진(Playwright/Selenium), CrawlerThread 오케스트레이션, 캐시/DB, Geo 설정/실행 경로

## 실행 상태 업데이트 (2026-03-10)

- 본 문서에서 제안한 9개 개선 항목(핵심 6 + 추가 3)은 코드 반영을 완료함.
- 적용 정책:
  - `complex` 모드: APT-only
  - 통계 단지 선택: `단지명 (ASSET:CID)` 형태
  - 차단 누적 쿨다운: 연속 3회 감지 시 60초
  - 관측성: 로그 + `stats_signal` payload 범위로 확장

### 반영 완료 항목 체크리스트

- [x] fallback 경계 정합성 복구(부분 성공 prefill + processed pair 누적 + fallback 지표)
- [x] Selenium negative cache 신뢰도 강화(`confirmed_empty`일 때만 저장)
- [x] 설정값 `0` 보존(`max_retry_count`, `geo_grid_rings`)
- [x] `price_snapshots` 자산 분리(스키마/저장/조회/통계/purge)
- [x] `complex` 모드 APT-only 정책 강제(DB/그룹/예약 로딩)
- [x] Geo 이력 기록 노이즈 정리(trade 성공 0건 시 이력 생략)
- [x] 차단 감지 누적 쿨다운 + 지표 확장
- [x] API/인터페이스 변경 반영
- [x] 회귀 테스트 추가/수정

### 검증

- `python -m unittest discover -s tests -p "test_*.py"`: pass (`Ran 120 tests`)

## 핵심 발견사항 (우선순위 순)

### 1) [High] Playwright 실패 후 Selenium fallback 전환 시 일부 성공 결과의 이력/완료 집계가 누락될 수 있음
- 근거:
  - `src/core/engines/playwright_parts/complex_mode.py:49`~`56`에서 예외 시 fallback 호출 후 즉시 `return`.
  - 동일 함수의 `record_crawl_history`는 `src/core/engines/playwright_parts/complex_mode.py:62` 이후에 있어, 중간 `return` 시 실행되지 않음.
  - fallback 대상은 `src/core/crawler_parts/history_alerts.py:117`~`120`의 `_remaining_pairs()` 기반이라, 이미 Playwright에서 성공한 pair는 대상에서 제외됨.
  - Selenium 종료 시 소멸 처리 범위도 Selenium 내부 처리분만 사용(`src/core/crawler_parts/selenium_flow.py:194`).
- 영향:
  - 같은 단지 내 일부 거래유형이 Playwright에서 이미 성공했는데 이후 fallback이 발생하면, 성공분이 `crawl_history`/완료 집계에서 빠질 수 있음.
  - 소멸 처리 범위도 부분 누락 가능.
- 권장:
  - fallback 전환 직전까지의 부분 성공 상태를 먼저 기록하거나, 전체 실행 범위의 processed pair를 thread 단위로 통합해 최종 1회 정산.
  - 회귀 테스트 추가: "첫 trade 성공 + 다음 trade 실패 + fallback" 시 이력/완료 건수가 합산되는지 검증.

### 2) [High] Selenium 경로의 0건 negative cache 저장 조건이 과도하게 관대함
- 근거:
  - `src/core/crawler_parts/selenium_flow.py:265`~`275`에서 `raw_items`가 비면 즉시 `[]` negative cache 저장.
  - Playwright는 `response_seen=True` 및 drain timeout 아님을 조건으로 제한(`src/core/engines/playwright_parts/complex_mode.py:133`~`150`).
- 영향:
  - 차단 페이지/일시 파싱 실패/DOM 변경 같은 일시 오류를 "확정 0건"으로 캐시해, 일정 시간 실제 매물을 놓칠 수 있음.
- 권장:
  - Selenium도 `confirmed_empty` 판단 조건(예: 차단 미감지 + 목록 응답/DOM 안정성 신호)을 추가.
  - 회귀 테스트 추가: 일시 실패 시 negative cache 미저장 검증.

### 3) [Medium-High] `0` 값 설정이 일부 경로에서 기본값으로 덮여 의도대로 적용되지 않음
- 근거:
  - 최대 재시도 로딩: `src/ui/dialogs/settings.py:204` (`int(settings.get(... ) or 3)`)
  - Geo 실행 시 max_retry_count: `src/ui/widgets/geo_crawler_tab.py:220` (`... or 3`)
  - Geo rings 로딩: `src/ui/widgets/geo_crawler_tab.py:56`, `:124`, `src/ui/dialogs/settings.py:239` (`... or 1`)
- 영향:
  - `max_retry_count=0`, `geo_grid_rings=0` 같은 유효값이 저장되어도 재로딩 시 각각 `3`, `1`로 바뀜.
  - 문서/설정 UI에서 기대한 동작과 런타임 동작 불일치.
- 권장:
  - `or 기본값` 패턴 대신 `None` 여부만 판단하는 로더 사용.
  - 테스트 추가: `0` 저장 후 재시작/재로드 시 값 유지 검증.

### 4) [Medium] 스냅샷/통계 축적에서 `asset_type` 차원이 빠져 APT/VL 혼합 가능성
- 근거:
  - 스냅샷 집계 키: `src/ui/widgets/crawler_tab_parts/crawl_control.py:404`의 `(cid, ttype, pyeong_group)`
  - `price_snapshots` 스키마: `src/core/database_parts/schema.py:55`~`65`에 `asset_type` 컬럼 없음.
  - 프로젝트는 APT/VL 동시 지원을 명시(README/claude).
- 영향:
  - 동일 `complex_id`가 자산유형별로 존재할 때 시세 집계/비교가 섞여 정확도 저하 가능.
- 권장:
  - `price_snapshots`에 `asset_type` 추가 및 조회/차트 파이프라인 전반에 반영.
  - 마이그레이션 + 회귀 테스트(동일 complex_id, 상이 asset_type 케이스) 추가.

### 5) [Medium] `complex` 모드 정책과 UI 입력 경로 간 정합성 불명확
- 근거:
  - DB/그룹 불러오기에서 `asset_type` 표시는 하지만 실제 task에는 `(name, cid)`만 전달(`src/ui/widgets/crawler_tab_parts/crawl_control.py:73`~`89`).
  - 반면 complex 모드 캐시 컨텍스트는 사실상 APT 정규화(`src/core/engines/playwright_parts/complex_mode.py:89`~`92`, `src/core/crawler_parts/selenium_flow.py:215`, `:263`).
- 영향:
  - VL 대상이 complex 모드로 들어올 때 정책상/데이터상 처리 일관성이 깨질 수 있음.
- 권장:
  - 정책을 명시적으로 하나로 정리:
  - `complex` 모드는 APT만 허용(입력 차단/필터링) 또는
  - `complex` 모드도 `asset_type`를 1급 파라미터로 전달/캐시/이력에 반영.

### 6) [Low-Medium] Geo 모드에서 trade 성공이 전혀 없어도 완료 이력이 기록됨
- 근거:
  - `src/core/engines/playwright_parts/geo_mode.py:106`에서 `complex_trade_types` 비어도 `record_crawl_history` 호출.
  - complex 모드는 동일 상황에서 `continue`로 스킵(`src/core/engines/playwright_parts/complex_mode.py:60`~`61`).
- 영향:
  - 빈 `trade_types`/0건 이력이 누적되어 운영 로그 해석이 어려워질 수 있음.
- 권장:
  - 최소 1개 trade 성공 시만 이력 기록, 또는 실패 상태 필드(예: `status=failed`)를 분리 기록.

## 추가로 보강이 필요한 항목 (문서 정책 기준)

### A) 차단 감지 누적 기반 쿨다운(circuit breaker)
- `claude.md`의 리스크 메모에는 필요 항목으로 언급되나, 코드 검색 기준 관련 구현이 확인되지 않음.
- 권장:
  - 연속 차단 감지 횟수 기반 쿨다운 및 자동 재시도 지연(엔진 공통 정책) 도입.

### B) 관측성(Observability) 지표 확장
- 현재 일부 지표는 있으나, 운영 트러블슈팅에 필요한 핵심 성공률 지표가 부족함.
- 권장:
  - 최소 추가 지표: API response seen ratio, 상세 fetch 성공률, 엔진별 실패 코드 top-N, fallback 원인 분포.

### C) 테스트 공백 메우기
- 우선 추가 권장 테스트:
  - fallback 중간 전환 시 partial success 이력 합산 검증
  - Selenium negative cache 확정 조건 검증
  - 설정값 `0`(retry/rings) 저장-재로드 유지 검증
  - APT/VL 동일 complex_id 스냅샷 분리 검증

## 우선 실행 제안 (실행 순서)
1. fallback 경계 로직(항목 1) 수정 + 회귀 테스트
2. Selenium negative cache 조건 강화(항목 2) + 회귀 테스트
3. 설정값 `0` 처리 버그 수정(항목 3)
4. `price_snapshots` 자산유형 분리 설계/마이그레이션(항목 4)
5. 정책 정합(항목 5) 확정 후 UI/엔진 파이프라인 정리
