# 기능 구현 잠재 이슈/추가 개선 점검 리포트 (2026-03-06)

## 점검 기준
- 참조 문서: `README.md`, `claude.md`
- 점검 범위: 엔진 오케스트레이션, geo sweep, 캐시 정책, 비동기 응답 처리, UI 반영 경로
- 코드 기준: 현재 작업 트리 HEAD

## 핵심 잠재 이슈 (심각도순)

### 1. [S1] 모바일 상세 enrich 중지 시 pending task 방치 가능성
- 근거 위치:
  - `src/core/engines/playwright_engine.py:576`
  - `src/core/engines/playwright_engine.py:579`
- 관찰 내용:
  - `_enrich_items_with_mobile_details()`에서 모든 상세 요청을 `asyncio.create_task()`로 생성한 뒤,
    `self.thread._should_stop()`가 `True`면 `for coro in asyncio.as_completed(tasks)` 루프를 즉시 `break`합니다.
  - 이 경우 아직 완료되지 않은 task들이 cancel/gather 없이 남아 이벤트 루프 종료 시점까지 떠 있을 수 있습니다.
- 잠재 영향:
  - 중지/종료 시 페이지 풀(`_page_pool`) 반환 지연, 브라우저 종료 레이스, 간헐적 리소스 누수/경고 발생 가능.
- 권장 조치:
  - 중단 분기에서 미완료 task를 명시적으로 cancel + gather(return_exceptions=True) 처리.
  - 중단 시나리오 전용 비동기 테스트 추가(중간 stop 발생 후 task 잔존 여부 검증).

### 2. [S2] complex 모드 캐시 키가 엔진(Playwright/Selenium) 간 불일치해 fallback 시 캐시 미활용 가능성
- 근거 위치:
  - `src/core/engines/playwright_engine.py:416`
  - `src/core/engines/playwright_engine.py:424`
  - `src/core/crawler.py:773`
- 관찰 내용:
  - Playwright `complex` 경로는 `cache_ctx`에 `marker_id=cid`가 들어가고(`cache_marker_id = marker_id or cid`),
    `asset_type` 기본값은 빈 문자열입니다.
  - Selenium 경로는 `asset_type="APT"`, `marker_id` 없음으로 조회/저장합니다.
- 잠재 영향:
  - 동일 단지/거래유형이라도 엔진 전환(fallback) 시 캐시 키가 달라져 캐시 재사용률 저하.
  - fallback 시 네트워크/수집 시간 증가.
- 권장 조치:
  - `complex` 모드의 컨텍스트 정규화 규칙을 엔진 공통으로 통일(예: marker_id 제외, asset_type 표준값 통일).
  - 엔진 전환 시 캐시 공유 시나리오 테스트 추가.

### 3. [S2] 소멸 처리 키에서 `asset_type`이 빠져 경계 충돌 가능성
- 근거 위치:
  - `src/core/engines/playwright_engine.py:354`
  - `src/core/engines/playwright_engine.py:292`
  - `src/core/engines/playwright_engine.py:330`
- 관찰 내용:
  - geo 발견/중복 제어는 `asset_type:complex_id`로 분리 처리합니다.
  - 하지만 소멸 처리용 `processed_pairs`는 `(cid, trade_type)`만 사용합니다.
- 잠재 영향:
  - 만약 서로 다른 자산유형에서 `complex_id`가 충돌하는 데이터가 존재할 경우,
    소멸 매물 마킹이 의도와 다르게 적용될 가능성.
- 권장 조치:
  - `processed_pairs` 키에 `asset_type` 포함 여부를 DB API와 함께 재설계.
  - 데이터 특성상 `complex_id` 전역 유일이 보장된다면 코드/문서에 명시 assertion 추가.

### 4. [S3] 응답 drain timeout(3초) 고정으로 저속 환경에서 누락 가능성
- 근거 위치:
  - `src/core/engines/playwright_engine.py:162`
  - `src/core/engines/playwright_engine.py:551`
- 관찰 내용:
  - `_drain_pending_response_tasks()` 기본 timeout이 3000ms로 고정되어 있습니다.
  - timeout 발생 시 pending task를 cancel하고 진행합니다.
- 잠재 영향:
  - 네트워크 지연/서버 응답 지연이 큰 구간에서 일부 데이터가 누락될 수 있음.
- 권장 조치:
  - 설정값(`playwright_response_drain_timeout_ms`)으로 외부화.
  - timeout 발생 횟수/건수를 stats로 집계해 UI/로그에서 추적.

## 추가 권장사항 (기능/운영)
- 운영 가시성 확장:
  - 현재는 로그 중심 노출이므로, `stats_signal`에 `geo_discovered_count`, `geo_dedup_count`, `response_drain_wait_count`, `response_drain_timeout_count`를 추가해 요약 카드/상태바 반영 권장.
- 테스트 강화:
  - drain timeout 초과 시 강제 cancel 경로 테스트.
  - fallback 전환 시 캐시 재사용률 검증 테스트.
  - stop/shutdown 중 상세 워커 task 정리 검증 테스트.
- 문서 보강:
  - README/claude에 “complex 모드 캐시 컨텍스트 정규화 규칙”과 “drain timeout 정책(기본값/튜닝법)”을 명문화.

## 결론
- 현재 구현은 이전 주요 리스크(응답 레이스, geo dedupe, fallback 정책 정합, 캐시 컨텍스트 분리)를 상당 부분 해소했습니다.
- 다만 **중단 시 task 정리**, **엔진 간 캐시 키 정합**, **소멸 처리 키 경계**, **drain timeout 정책화**는 기능 안정성 관점에서 후속 보완 가치가 높습니다.

## 후속 조치 반영 결과 (2026-03-06)

- [x] 중단 시 detail task 정리(`cancel + gather(return_exceptions=True)`) 반영
- [x] complex 캐시 컨텍스트 엔진 공통 정규화 반영
- [x] geo 소멸 처리 경계에 `asset_type` 포함한 3요소 타깃 지원 반영
- [x] drain timeout 설정 외부화(`playwright_response_drain_timeout_ms`) 및 timeout 통계 누적 반영
- [x] Geo 상태바+로그 가시성(발견/중복제거/drain 대기/drain timeout) 반영
- [x] 대응 테스트 세트 추가/강화 반영

### 재검증
- 실행: `PYTHONPATH=. pytest -q tests/test_playwright_engine_stabilization.py tests/test_managers_cache.py tests/test_database_module.py tests/test_geo_tab_wiring.py tests/test_crawler_regressions.py`
- 결과: `44 passed`
