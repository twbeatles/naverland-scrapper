# 기능 구현 점검 리포트 (2026-03-14)

## 구현 반영 상태 (2026-03-14)
- 이 문서에서 제안한 핵심 수정 항목은 모두 반영 완료되었습니다.
- 반영 범위:
  - 알림 스코프 `asset_type` 분리 + shared `ALL` 규칙 지원
  - complex 모드 작업 목록 `cid` dedupe 고정
  - `_push_item()` 반환값 기반 집계 정합화
  - `crawl_history`의 `asset_type`/`engine`/`mode` 저장 및 히스토리 UI 노출
  - stats 차트의 단일 시리즈 정책 적용
- 검증:
  - `PYTHONPATH=. pytest -q`
  - 결과 `131 passed`
- 후속 문서 정합:
  - `README.md`, `claude.md`, `gemini.md`, `update_history.md`와 구현 상태를 동기화했습니다.
  - `naverland-scrapper.spec`는 2026-03-14 기준 재점검했고 추가 hidden import/runtime hook 수정은 필요하지 않았습니다.
  - `.gitignore`는 현재 규칙으로 충분하여 추가 변경 없이 유지했습니다.

## 검토 범위
- 참조 문서: `README.md`, `claude.md`
- 기존 점검 문서: `implementation_functional_audit_2026-03-10.md`, `implementation_risk_review_2026-03-11.md`
- 실제 확인 범위: `src/` 전반, 주요 UI/크롤링/DB 경계 코드, 테스트 코드
- 검증: `pytest -q` 실행 결과 `123 passed`

## 현재 상태 요약
- 3/10, 3/11 점검 문서에서 지적된 큰 리스크는 상당수 반영되어 있습니다.
- 현재 남아 있는 이슈는 "즉시 크래시"보다는, `APT/VL` 동시 지원 이후의 데이터 정합성, 중복 실행, 집계 정확도, UI 해석 혼선 쪽에 더 가깝습니다.
- 특히 `README.md`와 `claude.md`가 강조하는 `APT/VL` 동시 지원, 알림/이력/통계 기능은 구현은 되어 있지만 일부 경로가 아직 `complex_id` 단일 기준에 머물러 있습니다.

## 핵심 발견사항

### 1) [High] APT/VL 동시 지원 대비 알림 경로가 아직 `complex_id` 중심이라 자산유형 충돌 위험이 남아 있음
근거:
- `src/core/database_parts/schema.py:67`의 `alert_settings` 테이블에는 `asset_type` 컬럼이 없습니다.
- `src/core/database_parts/schema.py:125`의 `article_alert_log`도 `alert_id + article_id + complex_id + notified_on` 기준으로만 dedupe 합니다.
- `src/core/database_parts/alert_ops.py:13-42`는 알림 생성/조회 시 `complex_id`만 사용합니다.
- `src/ui/dialogs/settings.py:315`는 알림 대상 콤보박스에 `name (cid)`만 표시하고, 선택 데이터도 `(cid, name)`만 저장합니다.
- 반면 프로젝트는 `src/core/database_parts/schema.py:17-24` 기준으로 `(asset_type, complex_id)` 복합 키를 이미 공식 지원합니다.

영향:
- 같은 `complex_id`를 공유하는 `APT`/`VL`이 있을 때, 한쪽에 건 알림이 다른 쪽 매물에 잘못 발동할 수 있습니다.
- 알림 dedupe 로그도 자산유형을 구분하지 못해, 정상 알림이 "이미 보낸 알림"으로 잘못 눌릴 수 있습니다.
- 알림 UI에서도 사용자가 어떤 자산유형에 규칙을 걸었는지 구분할 수 없습니다.

권장:
- `alert_settings`, `article_alert_log`에 `asset_type` 컬럼을 추가하고 조회/기록 인덱스를 `(asset_type, complex_id, ...)` 기준으로 재정의하는 것이 좋습니다.
- `AlertSettingDialog`에서도 `단지명 (APT:12345)`처럼 자산유형을 노출해야 합니다.
- 회귀 테스트를 추가하는 것이 좋습니다: "같은 `complex_id`의 `APT/VL` 각각에 다른 알림을 걸었을 때 교차 발동하지 않는지".

### 2) [Medium-High] 작업 목록에 같은 단지를 중복으로 넣을 수 있어, 실제 크롤링이 불필요하게 반복될 수 있음
근거:
- `src/ui/widgets/crawler_tab_parts/crawl_control.py:27-34`의 `add_task()` / `_add_row()`는 중복 검사 없이 그대로 행을 추가합니다.
- DB 불러오기, 그룹 불러오기, 최근 검색 불러오기, URL 일괄 등록도 모두 같은 경로를 사용합니다.
  - `src/ui/widgets/crawler_tab_parts/crawl_control.py:93-94`
  - `src/ui/widgets/crawler_tab_parts/crawl_control.py:111`
  - `src/ui/widgets/crawler_tab_parts/crawl_control.py:131-133`
  - `src/ui/widgets/crawler_tab_parts/crawl_control.py:177`
  - `src/ui/widgets/crawler_tab_parts/crawl_control.py:189`
  - `src/ui/app_parts/stats_schedule.py:57`
- `src/ui/widgets/crawler_tab_parts/crawl_control.py:231-233`는 테이블 행을 그대로 `target_list`로 넘기므로, 중복 행은 중복 요청으로 이어집니다.

영향:
- 같은 단지가 여러 번 크롤링되어 실행 시간이 늘고, 차단 리스크도 같이 올라갑니다.
- 결과 아이템은 `_push_item()` 단계에서 일부 dedupe 되더라도, 네트워크 요청/로그/이력 기록은 이미 중복으로 발생할 수 있습니다.
- 예약 실행이나 그룹 로딩 후 사용자가 이를 눈치채기 어렵습니다.

권장:
- 최소한 `start_crawling()` 직전 `(name, cid)` 기준 dedupe를 한 번 더 거는 것이 안전합니다.
- 가능하면 `add_task()` 단계부터 중복 행을 막고, 이미 존재하면 포커스 이동 또는 상태 메시지로 알려주는 편이 UX상 좋습니다.
- 회귀 테스트를 추가하는 것이 좋습니다: "같은 `cid`를 2회 추가해도 실제 target은 1회만 생성되는지".

### 3) [Medium] 중복 매물이 dedupe로 걸러져도, 완료 건수/이력 건수는 그대로 증가할 수 있음
근거:
- `src/core/crawler_parts/state_runtime.py:222-227`의 `_push_item()`은 중복 키면 바로 반환합니다.
- 그런데 `_push_item()` 호출 뒤 반환값 확인 없이 카운트를 올리는 경로가 남아 있습니다.
  - `src/core/crawler_parts/history_alerts.py:106`
  - `src/core/crawler_parts/selenium_flow.py:244`
  - `src/core/crawler_parts/dom_scroll_parse.py:211`
- 이후 이 `count` 값은 단지별 완료 로그와 `crawl_history.item_count`, `by_trade_type` 통계에 재사용됩니다.

영향:
- 화면에 실제로 남은 매물 수보다 `단지 완료: N건`, `crawl_history.item_count`가 더 크게 기록될 수 있습니다.
- fallback, 캐시 적중, 응답 중복 등 "dedupe가 실제로 필요한 상황"에서 숫자만 부풀려질 가능성이 있습니다.

권장:
- `_push_item()`이 실제 push 여부를 `bool`로 반환하게 바꾸고, `matched_count += 1`은 성공한 경우에만 수행하는 편이 안전합니다.
- 회귀 테스트를 추가하는 것이 좋습니다: "중복 article을 두 번 넣었을 때 `collected_data`와 `count`가 같은지".

### 4) [Medium] `complex` 모드의 크롤링 이력은 여전히 `asset_type`가 비어 저장되고, 이력 UI도 메타데이터를 보여주지 않음
근거:
- `src/core/database_parts/schema.py:41-53`와 `src/core/database_parts/crawl_snapshot_ops.py:12-47`는 `crawl_history.asset_type`, `engine`, `mode`, `source_lat/lon/zoom` 저장을 지원합니다.
- `src/core/engines/playwright_parts/geo_mode.py:128-137`는 실제로 `asset_type`까지 넘깁니다.
- 하지만 `complex` 경로는 `asset_type`를 넘기지 않습니다.
  - `src/core/engines/playwright_parts/complex_mode.py:98-104`
  - `src/core/crawler_parts/selenium_flow.py:199-205`
- 조회/표시는 더 축약되어 있습니다.
  - `src/core/database_parts/crawl_snapshot_ops.py:91-99`
  - `src/ui/app_parts/stats_schedule.py:115-127`

영향:
- `complex` 모드에서 쌓이는 이력은 사실상 "APT로 해석해야 하는 빈 값"이 됩니다.
- 현재 일부 조회 코드는 이를 관용적으로 `APT` 취급하지만, 히스토리 데이터 자체는 계속 모호하게 쌓입니다.
- 문서에서 강조한 `engine/mode/asset_type` 기반 운영 추적이 실제 히스토리 탭에서는 보이지 않습니다.

권장:
- `complex` 모드 이력에도 `asset_type='APT'`를 명시 저장하는 편이 좋습니다.
- 히스토리 탭은 최소한 `engine`, `mode`, `asset_type`까지는 보여주는 것이 운영 추적에 도움이 됩니다.

## 추가 보강 제안

### A) 통계 차트는 현재 "첫 번째 시리즈만" 그리는 구조라 오해 소지가 있음
근거:
- `src/ui/app_parts/stats_schedule.py:245-276`는 테이블에는 여러 `trade_type/pyeong` row를 넣을 수 있지만, 차트는 첫 번째 시리즈와 동일한 항목만 누적합니다.

권장:
- `전체` 조건일 때는 차트 대신 "시리즈를 하나 선택해 달라"는 안내를 띄우거나,
- 여러 시리즈를 범례 포함 multi-line chart로 렌더하는 방향 중 하나로 정리하는 것이 좋습니다.

### B) `APT/VL` 분리 지원에 맞춘 회귀 테스트가 알림/작업중복/집계정확도 쪽에는 아직 부족함
추천 테스트:
- 같은 `complex_id`의 `APT/VL`에 서로 다른 알림 규칙을 걸었을 때 교차 발동이 없는지
- 동일 단지를 여러 경로(DB/그룹/최근검색/URL)로 추가해도 실제 크롤링 target이 dedupe 되는지
- item dedupe가 발생했을 때 `crawl_history.item_count`와 실제 결과 건수가 일치하는지

## 우선순위 제안
1. 알림 경로의 `asset_type` 분리부터 먼저 반영
2. 작업 목록 dedupe 추가
3. `_push_item()` 기준으로 완료 건수/이력 건수 정합화
4. `crawl_history`의 `asset_type`/`engine`/`mode` 노출 강화

## 메모
- 이번 점검에서는 "현재 코드 기준으로 남아 있는 잠재 리스크"를 중심으로 작성했습니다.
- 이전 문서(3/10, 3/11)에서 지적된 대형 리스크는 상당수 이미 해소된 상태로 보입니다.
