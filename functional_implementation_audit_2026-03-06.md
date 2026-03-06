# 기능 구현 감사 리포트 (2026-03-06)

## 개요(범위/근거)
- 감사 대상 커밋: `5a83b2947f02b923a4c3a9fd137dcbb5d0943ee0` (`Add Playwright geo crawling upgrade`)
- 기준 문서: `claude.md`, `README.md`
- 문서 기대사항 확인 포인트:
  - `claude.md:10` Playwright 기본 엔진 + Selenium fallback
  - `claude.md:83-85` `CrawlerThread` fallback/`geo_sweep`/엔진 오케스트레이션 명시
  - `README.md:12` Playwright 기본 + Selenium fallback 유지
  - `README.md:15` response interception 기반 목록 수집
- 코드 API 변경 여부: 없음 (코드 수정 없이 감사 문서 산출)
- 영향 인터페이스 추적:
  - `CrawlerThread(engine_name, crawl_mode, geo_config)`
  - `PlaywrightCrawlerEngine` geo 수집 흐름 (`_run_geo`, `_scan_geo_asset_type`, `_collect_target_raw_items`)
  - `ComplexDatabase` 확장 컬럼 경로 (`crawl_history`, `article_history` write/read)

## 핵심 리스크(심각도순)
### 1. [S1] Playwright 응답 수집 비동기 레이스로 인한 결과 누락 가능성
- 위치:
  - `src/core/engines/playwright_engine.py:313`
  - `src/core/engines/playwright_engine.py:447`
  - `src/core/engines/playwright_engine.py:480`
  - `src/core/engines/playwright_engine.py:224`
- 재현 조건:
  - 응답 핸들러에서 `asyncio.create_task(_consume(...))`로 작업만 등록되고, 호출부에서 pending task 완료를 기다리지 않은 채 리스너 제거/다음 단계로 진행되는 경우.
- 영향:
  - 마커/목록 파싱이 늦게 도착하면 `ordered` 또는 `raw_items` 반영 전에 루프가 종료되어 수집 건수가 과소 집계될 수 있음.
  - 간헐적으로 0건 또는 부분 수집처럼 보이는 플래키 동작이 발생할 수 있음.
- 권장 보완 테스트:
  - 지연 응답(Fake response with delayed `json()`)을 주입해 `_collect_target_raw_items`/`_build_marker_handler`가 반환되기 전 pending consume task가 모두 drain되는지 검증하는 비동기 단위 테스트 추가.

### 2. [S1] 캐시 키가 `complex_id + trade_type`에 고정되어 geo/complex 모드 메타데이터 오염 가능성
- 위치:
  - `src/core/cache.py:26`
  - `src/core/engines/playwright_engine.py:364`
  - `src/core/engines/playwright_engine.py:384`
  - `src/core/engines/playwright_engine.py:388`
- 재현 조건:
  - 캐시 활성화 상태에서 동일 단지/거래유형을 `complex` 모드와 `geo_sweep` 모드로 교차 실행할 때.
- 영향:
  - 캐시 적중 시 geo 수집에서 기대하는 `수집모드/자산유형/위도/경도/줌/마커ID`가 이전 모드 데이터로 남아 UI/DB/export 메타데이터의 신뢰도를 떨어뜨릴 수 있음.
- 권장 보완 테스트:
  - `complex` 모드 raw item을 먼저 캐시에 넣은 뒤 `geo_sweep` 실행 시 메타데이터가 geo 값으로 보정되는지(또는 캐시 키 분리로 미적중되는지) 검증하는 통합 테스트 추가.

### 3. [S2] geo sweep 시작 URL이 첫 거래유형만 반영되어 탐색 편향 가능성
- 위치:
  - `src/core/engines/playwright_engine.py:323`
  - `src/core/engines/playwright_engine.py:324-327`
- 재현 조건:
  - 사용자가 다중 거래유형(예: 매매+전세)을 선택한 상태에서 geo sweep 실행.
- 영향:
  - 탐색 URL의 `tradeTypes`가 첫 거래유형 코드 1개로 고정되어, 특정 거래유형 기준으로만 마커가 노출될 가능성이 있음.
  - 후속 상세 수집 전에 후보 단지 자체가 누락될 수 있음.
- 권장 보완 테스트:
  - 다중 거래유형 선택 시 생성 URL 쿼리를 검증하는 단위 테스트(현재는 첫 값만 사용됨).
  - 거래유형별로 발견 단지 수가 달라지는 fixture를 사용해 탐색 편향을 검증하는 통합 테스트.
- 비고:
  - 이 항목은 코드 구조 기반 추론이며(`tradeTypes` 단일 값 사용), 실제 API 동작 확인 테스트가 필요함.

### 4. [S2] 발견 단지 중복 emit으로 UI/DB 반영이 과다 반복될 가능성
- 위치:
  - `src/core/engines/playwright_engine.py:307-309`
  - `src/ui/widgets/geo_crawler_tab.py:236-248`
- 재현 조건:
  - sweep 중 동일 단지가 여러 좌표 응답에서 반복 노출되고 `count`가 같거나 증가하는 경우.
- 영향:
  - `>=` 조건으로 동일 단지가 반복 emit되어 발견 테이블에 중복 row가 누적될 수 있음.
  - `add_complex(... return_status=True)` 호출이 중복 반복되어 불필요한 DB 조회/로그가 늘어날 수 있음.
- 권장 보완 테스트:
  - 동일 `complex_id` 이벤트를 연속 주입했을 때 테이블 row가 1개로 유지되고 카운트/상태만 업데이트되는지 확인하는 UI 단위 테스트.

### 5. [S2] Geo 탭에서 fallback 설정 고정 비활성으로 정책 불일치 가능성
- 위치:
  - `src/ui/widgets/geo_crawler_tab.py:219`
  - `src/core/managers.py:44`
  - `src/ui/dialogs/settings.py:76`
  - `src/ui/dialogs/settings.py:188`
  - `src/ui/dialogs/settings.py:225`
- 재현 조건:
  - 설정에서 fallback 활성화 후 geo 탭 수집 실행.
- 영향:
  - 일반 수집 탭은 설정값을 반영하지만 geo 탭은 `fallback_engine_enabled=False`로 고정되어 Playwright 실패 시 우회 경로가 없음.
  - 문서(`claude.md`, `README.md`)의 “fallback 유지” 기대와 사용자 인식이 어긋날 수 있음.
- 권장 보완 테스트:
  - geo 탭 스레드 생성 시 fallback 설정 반영 여부를 검증하는 wiring 테스트 추가.
  - 만약 의도적으로 미지원이라면 명시 경고(툴팁/로그) 노출 테스트 추가.

### 6. [S2] 신규 경로(geo/응답 인터셉트/캐시 경계) 테스트 커버리지 공백
- 위치:
  - `tests/test_geo_tab_wiring.py:19`
  - `tests/test_map_geometry.py:20`
  - `tests/test_database_engine_extensions.py:38`
- 재현 조건:
  - 현재 테스트 세트는 wiring/기하/DB 컬럼 저장 확인 위주로 구성되어 있음.
- 영향:
  - 실제 위험 구간(비동기 응답 레이스, 캐시 경계, 중복 발견/테이블 갱신, geo fallback 정책)의 회귀를 사전에 탐지하기 어려움.
- 권장 보완 테스트:
  - 리스크 1~5를 각각 직접 검증하는 테스트를 최소 1개씩 추가해 1:1 매핑으로 회귀 방지.

## 추가 필요사항
- 문서-동작 정합성 보강:
  - geo 모드 fallback 정책을 문서와 코드 중 한쪽으로 명확히 맞추기.
- 운영 가시성 보강:
  - geo 탐색 단계에서 “발견 단지 수/중복 제거 수/응답 처리 대기 수”를 로그 또는 상태바에 노출.
- 캐시 정책 명세화:
  - 캐시 키 구성 요소(`mode`, `asset_type`, 좌표 메타데이터 포함 여부)를 README/claude에 명문화.

## 테스트/검증 결과
- 실행 커맨드 및 결과:

```powershell
git show --stat --name-status 5a83b29
```
- 결과 요약: `36 files changed, 2818 insertions(+), 140 deletions(-)`

```powershell
$env:PYTHONPATH='.'; pytest -q tests/test_database_engine_extensions.py tests/test_gap_analysis.py tests/test_map_geometry.py
```
- 결과 요약: `6 passed in 0.06s`

```powershell
$env:PYTHONPATH='.'; pytest -q
```
- 결과 요약: `29 failed, 58 passed in 14.98s`
- 분리 기록(코드 리스크와 별도): 실패의 공통 원인은 `PIL._imaging` DLL 로드 차단(`애플리케이션 제어 정책에서 이 파일을 차단했습니다`)으로, UI import 경로에서 연쇄 실패함.

## 즉시 액션 체크리스트
- [ ] 리스크 1 대응: 응답 consume task drain/await 전략 정의 및 테스트 추가.
- [ ] 리스크 2 대응: 캐시 키 확장 또는 캐시 적중 시 mode/메타데이터 보정 정책 확정.
- [ ] 리스크 3 대응: geo sweep `tradeTypes` 처리 방식(다중/반복 스캔) 확정.
- [ ] 리스크 4 대응: 발견 단지 dedupe 키(`asset_type + complex_id`)와 UI 업데이트 정책 확정.
- [ ] 리스크 5 대응: geo fallback 정책을 설정/문서/동작에 일치시킴.
- [ ] 리스크 6 대응: 리스크 1~5 각각 1개 이상 회귀 테스트 추가.

---
- 작성 기준: HEAD 기준 파일 라인 번호 사용, 대상 커밋은 `5a83b29`로 고정.

## 후속 반영 완료 상태 (2026-03-06)

- [x] 리스크 1 대응: response consume task drain + timeout/cancel-safe 처리 및 테스트 반영
- [x] 리스크 2 대응: 캐시 키 컨텍스트 분리 + complex 모드 정규화 + legacy 읽기 호환 반영
- [x] 리스크 3 대응: geo sweep 거래유형별 반복 스캔 경로 반영
- [x] 리스크 4 대응: 발견 단지 dedupe/upsert + DB 등록 1회 제한 반영
- [x] 리스크 5 대응: geo fallback 미지원 정책 고정 및 명시 경고 로그 반영
- [x] 리스크 6 대응: 리스크 1:1 매핑 테스트 세트 추가/보강

### 재검증 결과
- 실행: `PYTHONPATH=. pytest -q tests/test_playwright_engine_stabilization.py tests/test_managers_cache.py tests/test_database_module.py tests/test_geo_tab_wiring.py tests/test_crawler_regressions.py`
- 결과: `44 passed`
