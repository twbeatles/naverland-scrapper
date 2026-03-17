## **v15.0.14 (2026-03-17)**

**문서/.spec/.gitignore 정합성 재점검 + 성능 리팩토링 기준 동기화**

### ✅ 핵심 반영

* 문서/빌드 기준 정합화:
  - `naverland-scrapper.spec`의 실제 기본 프로필을 `onedir + Chromium bundle` 기준으로 명시
  - `NAVERLAND_ONEFILE=1`에서만 onefile이 생성된다는 점을 README/AI 컨텍스트 문서와 일치시킴
  - 카드 뷰 위젯 경로를 `src/ui/widgets/cards.py`로 바로잡고, `dashboard.py`는 대시보드 전용 위젯 문서로 정리
* 성능 기준 문서화:
  - 비핵심 탭 lazy loading 제거 상태와 `startup_lazy_noncritical_tabs=False` 레거시 호환 정책을 명시
  - 대시보드 통계 캐시/소멸 count TTL 캐시/지연 차트 초기화
  - 결과 테이블 검색 캐시 사전 생성, 로그 `maximumBlockCount`, 카드 스타일 캐시를 최신 기준으로 추가
* `.gitignore` 보강:
  - 로컬 개발 산출물 유입 방지를 위해 `.mypy_cache/`, `.ruff_cache/`, `.nox/`, `node_modules/`, `coverage.xml` 추가

### ✅ 검증

* `python -m pytest tests/test_performance_smoke.py tests/test_ui_runtime_smoke.py tests/test_ui_wiring.py -q`
  - 결과: `49 passed`
* `python scripts/perf_baseline.py`
  - 기준 측정: app init `0.9154s`, card set_data(1000) `0.1782s`

## **v15.0.13 (2026-03-16)**

**Repo-wide Pylance/Pyright cleanup + encoding regression guardrails**

### 주요 반영

* 테스트 더블 시그니처 정합성 보강
  - `tests/test_playwright_engine_stabilization.py`에서 `PlaywrightCrawlerEngine` monkeypatch 대상 메서드들의 파라미터명/반환형을 실제 시그니처와 맞춤
  - `_scan_geo_asset_type` 대역은 `bool` 반환으로 고정
  - `_check_memory_and_recycle_if_needed(reason)`, `_build_marker_handler(discovered)`, `response` callback 이름까지 맞춰 Pylance/Pyright attribute access 오류 제거
* 인코딩 회귀 방지 강화
  - `tests/test_mojibake_scan.py` 검사 범위를 `src/tests` Python 파일만이 아니라 `README.md`, `claude.md`, `gemini.md`, `update_history.md`, `.spec`, workflow, editor 설정까지 확장
  - tracked text 파일이 모두 `UTF-8 without BOM`인지와 mojibake indicator가 없는지를 함께 검증
  - 이번 패스에서 tracked 소스/문서/설정 파일 기준 실제 UTF-8 손상은 발견되지 않음
* CI 타입 가드 추가
  - `.github/workflows/ci.yml`에 `actions/setup-node` + `npx --yes pyright`를 추가해 repo-wide 타입 회귀를 CI에서 바로 차단

### 검증

* `npx pyright` => `0 errors`
* `pytest -q` => `150 passed`

## **v15.0.12 (2026-03-16)**

**Geo incomplete 안전모드 / run_status / preflight 정책 반영 + .spec/.md/gitignore 재점검**

### 주요 기능 반영

* preflight 정책 정밀화
  - `data/settings.json`을 직접 읽어 `effective crawl_engine`를 계산
  - Playwright Chromium 미설치는 `effective crawl_engine=playwright`일 때만 시작 차단
  - `effective crawl_engine=selenium`일 때는 warning-only
  - `NAVERLAND_SKIP_PLAYWRIGHT_BROWSER_CHECK`, `NAVERLAND_REQUIRE_PLAYWRIGHT_BROWSER` 우선순위 유지
* geo incomplete 안전모드
  - `geo_incomplete_safety_mode` 기본값 `true`
  - incomplete 사유를 `marker switch fail`, `marker drain timeout`, `geo scan failure`로 추적
  - safety mode ON이면 geo incomplete 런에서 auto-register / crawl history / disappeared marking skip
  - safety mode OFF이면 persistence는 허용하되 `run_status=incomplete`로 저장
* crawl history / UI 계약 보강
  - `crawl_history.run_status` additive migration 추가
  - History 탭 컬럼을 `mode -> status -> trade_types` 순서로 확장
  - complex 모드는 `success|partial|failed`, geo incomplete persisted run은 `incomplete`
* marker / disappeared 처리 보강
  - geo marker 정규화에서 `complex_id`와 `marker_id`를 분리
  - 성공적으로 검증된 pair가 0개인 런에서는 disappeared marking skip
  - discovered complex DB 등록은 geo discovery 이후 flush되며 incomplete safety mode에 따라 차단 가능

### .spec / 문서 / gitignore 점검

* `.spec` 점검 결과
  - `naverland-scrapper.spec`는 hidden import/runtime hook/data bundle 규칙 변경 없이 유지 가능
  - 다만 slim build + `effective crawl_engine=playwright` 조합에서는 local Chromium 또는 bundle Chromium이 필요하다는 주석을 최신 정책 기준으로 보강
* 문서 정합성 반영
  - `README.md`, `claude.md`, `gemini.md`, `implementation_risk_review_2026-03-16.md`, `update_history.md`에 동일 기준 반영
  - 최신 기준:
    - Selenium fallback은 `complex` 모드만 지원
    - `geo_sweep`는 Playwright 전용
    - geo incomplete safety mode 기본값은 `true`
    - history `run_status`는 `success|partial|failed|incomplete`
* `.gitignore` 점검 결과
  - 현재 build/log/data/backup/Playwright 산출물 ignore 규칙으로 충분
  - 이번 범위에서는 추가 수정 없음

### 검증

* `pytest -q`
  - 결과: `149 passed`

## **v15.0.11 (2026-03-16)**

**타이핑/인코딩 정합성 보강 + .spec/.md/.gitignore 재점검**

### ✅ 핵심 반영

* 정적 분석 기준 고정:
  - `pyrightconfig.json` 추가로 검사 범위를 `app_entry.py`, `src/`, `tests/`로 통일
  - 믹스인/동적 속성/테스트 더블 때문에 발생하던 Pylance/Pyright 오탐 정리
* 인코딩 기준 고정:
  - `.editorconfig`, `.vscode/settings.json` 추가로 UTF-8 저장 및 workspace type checking 기준 고정
  - Python/문서 파일에 남아 있던 UTF-8 BOM 제거
  - 깨진 주석/문자열을 의미 기준으로 복구

### 📦 .spec / 문서 / 무시규칙 정합성

* `.spec` 재점검 결과:
  - `naverland-scrapper.spec`는 이번 범위에서도 추가 hidden import/runtime hook/data bundle 수정이 필요하지 않음
  - 재점검 기준 주석 날짜를 `2026-03-16`으로 갱신
* 문서 동기화:
  - `README.md`, `claude.md`, `gemini.md`, `implementation_functional_review_2026-03-15.md`, `update_history.md`에 동일 기준 반영
  - 공통 반영 기준은 `workspace pyright baseline`, `UTF-8 encoding guardrails`, `.spec 재점검 결과`, `.gitignore 예외 규칙`임
* `.gitignore` 재점검 결과:
  - 기존 build/log/data/backup/Playwright 산출물 무시 규칙은 그대로 유지
  - `pyrightconfig.json`, `.vscode/settings.json`은 저장소 기준 설정으로 추적할 수 있게 예외 규칙 추가

### 🧪 검증

* `npx pyright`
  - 결과: `0 errors, 0 warnings, 0 informations`
* `python -m pytest -q`
  - 결과: `137 passed`

## **v15.0.10 (2026-03-15)**

**기능 구현 후속 개선 반영 + .spec/.md/.gitignore 정합성 재점검**

### ✅ 핵심 반영

* 자산 스코프 정합성:
  - `article_history`, `article_favorites`를 `(asset_type, article_id, complex_id)` 기준으로 재구성
  - startup schema migration 전 DB backup 생성
  - legacy blank `asset_type`를 `APT`로 정규화
* disappeared / purge 안전화:
  - disappeared 대상 계산을 `(asset_type, complex_id, trade_type)` 기준으로 통일
  - purge/delete가 `article_history`, `crawl_history`, `price_snapshots`, `alert_settings`, `article_favorites`, `article_alert_log`에 동일 asset-scoped predicate를 적용
* 즐겨찾기 동기화:
  - 카드뷰 direct DB write 제거, app-level favorite handler로 일원화
  - 카드뷰/즐겨찾기탭/최근 본 매물/결과 재렌더가 `(asset_type, article_id, complex_id)` favorite key를 공유
* 저장 semantics 정리:
  - 저장 메뉴를 `화면 기준 저장` / `원본 저장`으로 분리
  - 화면 기준 저장은 현재 검색/고급필터/compact duplicate/정렬 결과를 반영
  - 원본 저장은 전체 `collected_data` 유지
* 예약 실행 확장:
  - 예약 탭에 `complex` / `geo_sweep` 모드 추가
  - geo 예약은 lat/lon을 저장하고 geo 기본값(zoom/rings/step/dwell/asset_types)을 재사용
  - scheduled geo run에서 `VL` 제외 로직 제거
* Geo 운영 통계:
  - marker 처리 시점마다 `geo_discovered_count`, `geo_dedup_count`를 즉시 emit

### 📦 .spec / 문서 / 무시규칙 정합성

* `.spec` 재점검 결과:
  - `naverland-scrapper.spec`는 이번 범위에서도 추가 hidden import/runtime hook/data bundle 수정이 필요하지 않음
  - 재점검 기준 주석 날짜를 `2026-03-15`로 갱신
* 문서 동기화:
  - `README.md`, `claude.md`, `gemini.md`, `implementation_functional_review_2026-03-15.md`, `update_history.md`에 동일 기준 반영
* `.gitignore` 재점검 결과:
  - 현재 build/log/data/backup/Playwright 산출물 무시 규칙으로 충분하며 추가 수정 없음

### 🧪 검증

* `python -m pytest -q`
* 결과: `137 passed`

## **v15.0.9 (2026-03-14)**

**기능 구현 점검 리포트 전 항목 반영 + 문서/.spec/.gitignore 정합성 재점검**

### ✅ 핵심 반영

* 알림 스코프 정합:
  - `alert_settings.asset_type`, `article_alert_log.asset_type` 추가
  - legacy/blank alert scope는 `ALL`로 backfill
  - 알림 조회는 `requested asset_type + ALL` 규칙만 반환
  - 알림 dedupe 키를 `alert_id + article_id + complex_id + asset_type + notified_on`으로 확장
  - 알림 설정 UI에 `단지명 (APT:cid)` / `단지명 (VL:cid)` 표시와 `공통 적용(APT/VL)` 옵션 추가
* complex 모드 작업 dedupe:
  - `CrawlerTab` 작업 추가 경로(수동/DB/그룹/최근검색/URL/예약)를 `cid` 기준 dedupe helper로 통합
  - 중복 `cid`는 첫 이름을 유지하고 후속 항목은 로그/상태바에 "중복 스킵" 안내
  - `start_crawling()` 직전에도 `target_list`를 최종 재정규화
* item dedupe와 집계 일치:
  - `_push_item()`을 `bool` 반환으로 전환
  - raw item / Selenium cache hit / DOM parse 경로 모두 실제 push 성공 건만 `matched_count`와 완료 count에 반영
* 이력/통계 UX 정합:
  - `complex` 모드 `record_crawl_history()`도 `asset_type='APT'` 명시 저장
  - 히스토리 탭 컬럼을 `단지명 / 단지ID / 자산 / 엔진 / 모드 / 거래유형 / 수집건수 / 수집시각`으로 확장
  - 통계 차트는 단일 `(trade_type, pyeong)` 시리즈일 때만 렌더, 다중 시리즈는 안내 메시지로 clear

### 🧪 검증

* `PYTHONPATH=. pytest -q`
* 결과: `131 passed`

### 📦 .spec / 문서 / 무시규칙 정합성

* `.spec` 재점검 결과:
  - `naverland-scrapper.spec`는 이번 범위에서도 추가 hidden import/runtime hook 수정이 필요하지 않음
  - 재점검 기준 주석 날짜를 2026-03-14로 갱신
* 문서 동기화:
  - `README.md`, `claude.md`, `gemini.md`, `implementation_functional_review_2026-03-14.md`, `update_history.md`에 동일 정책 반영
* `.gitignore` 재점검 결과:
  - 현재 build/log/data/Playwright 산출물 무시 규칙으로 충분하며 추가 패턴 수정 없음

---

## **v15.0.7 (2026-03-11)**

**F-01~F-09 구현 리스크 플랜 일괄 반영 + 문서/패키징 정합성 재점검**

### ✅ 핵심 반영

* Selenium 신뢰성/차단/캐시 강화
  - parse metadata(`response_seen`, `parse_success`, `empty_confirmed`, `blocked_detected`) 표준화
  - `confirmed_empty` 조건에서만 negative cache 저장
  - 하이브리드 breaker 고정: pair 2회/90초 cooldown, global 5회 중단
* Playwright 관측성 강화
  - response/parse/detail success-fail 메트릭 추가 및 stats payload 노출
  - Geo 루프에서 빈 `complex_trade_types` 이력 저장 스킵
  - `complex_mode.py`, `geo_mode.py` 깨진 로그/예외 문자열 정리
* UI/DB 안정성 반영
  - Geo 탭 `retry_on_error=False` 시 `max_retry_count=0` 강제
  - `mark_disappeared_articles_for_targets` chunk update 처리
  - `add_complex` lock retry + rollback 경로 추가
  - stats complex key 충돌 시 `asset:cid` 목록키 분리(비충돌은 plain CID 유지)

### 🧪 검증

* `pytest -q` 전체 실행: `112 passed`

### 📦 .spec / 문서 / 무시규칙 정합성

* `.spec` 재점검 결과: `naverland-scrapper.spec`는 추가 hidden import/runtime hook 변경 불필요.
* `README.md`, `claude.md`, `gemini.md`에 동일 정책(F-01~F-09 반영 상태) 동기화.
* `.gitignore`에 PowerShell 캐시 폴더(`Microsoft/`) 무시 규칙 추가.

---
# 업데이트 히스토리

## **v15.0.8 (2026-03-10)**

**기능 감사 계획 전면 반영 + 문서/패키징 정합성 재점검**

### ✅ 핵심 반영

* fallback 경계 정합성:
  - Playwright 성공 pair를 thread 범위에서 누적하고, fallback 전환 시 현재 단지의 부분 성공(`count`, `trade_types`)과 processed pair를 Selenium으로 prefill 전달.
  - fallback 통계 `fallback_trigger_count`, `fallback_last_reason`를 `stats_signal` payload에 추가.
* Selenium negative cache 안전화:
  - Selenium 경로에 `confirmed_empty` 판정(`_is_confirmed_empty_state`)을 추가.
  - `raw_items=[]`라도 `confirmed_empty=False`면 negative cache 저장을 생략.
* 설정값 `0` 보존:
  - `max_retry_count`, `geo_grid_rings` 로딩 경로의 `or default` 패턴 제거.
  - `retry_on_error=False`일 때 Geo도 `max_retry_count=0` 전달을 보장.
* 스냅샷 자산 분리:
  - `price_snapshots.asset_type` 컬럼/인덱스 마이그레이션 추가(legacy 빈 값은 `APT` backfill).
  - 스냅샷 저장/조회/API를 `asset_type` 기준으로 분리.
  - `add_price_snapshots_bulk`가 legacy 7-tuple과 asset 포함 8-tuple을 모두 수용.
  - 통계 단지 소스 반환형을 `(name, asset_type, complex_id)`로 확장.
  - purge 관련 삭제에서 snapshot도 `(asset_type, complex_id)` 스코프를 준수.
* complex 모드 정책 강제:
  - DB/그룹/예약 로딩에서 VL 엔트리를 제외하고 UI 로그/상태바로 안내.
  - `complex`는 APT-only, VL은 `geo_sweep` 경로만 허용.
* Geo 이력 노이즈 정리:
  - 단지별 trade 성공이 0개면 `record_crawl_history`/`complex_finished_signal` 생략.
* 차단 누적 쿨다운 + 관측성:
  - block-like 신호 연속 3회 감지 시 interruptible 60초 쿨다운.
  - 신규 지표 `block_detect_count`, `block_cooldown_count`, `response_seen_count`, `detail_fetch_total`, `detail_fetch_success` 추가.

### ✅ 테스트/검증

* 회귀 테스트 확장:
  - `tests/test_crawler_regressions.py`
  - `tests/test_playwright_engine_stabilization.py`
  - `tests/test_database_module.py`
  - `tests/test_geo_tab_wiring.py`
  - `tests/test_ui_wiring.py`
* 실행 결과:
  - `python -m unittest discover -s tests -p "test_*.py"`: pass (`Ran 120 tests`)

### ✅ 문서/.spec/.gitignore 정합성

* 문서 동기화:
  - `README.md`, `claude.md`, `gemini.md`, `implementation_functional_audit_2026-03-10.md`, `update_history.md`에 동일 기준으로 정책/동작 변경사항 반영.
* `.spec` 재점검:
  - `naverland-scrapper.spec`는 이번 범위에서 hidden import/runtime hook/번들 경로 추가 수정이 필요하지 않음을 확인.
* `.gitignore` 재점검:
  - 현재 build/log/data/backup/Playwright 산출물 무시 규칙으로 충분하여 추가 패턴 수정 없음.

## **v15.0.7 (2026-03-09)**

**인코딩 정리 + Python 3.9 preflight 호환 + 문서 정합 재점검**

### ✅ 핵심 반영

* 인코딩 깨짐 정리:
  - `src/core/database_parts/*`의 매물/알림/백업/그룹/스냅샷 mixin에서 mojibake 상태의 docstring, 주석, 로그, corruption context 라벨을 의미 기준으로 복구.
  - `src/core/engines/playwright_parts/complex_mode.py`, `geo_mode.py`의 런타임 로그와 사이트 텍스트(`매매`)를 정상 문자열로 복원.
* 레거시 키 읽기 호환 유지:
  - canonical payload 키는 계속 `매물ID`를 사용.
  - 과거 깨진 매물 ID key는 escaped constant 기반 fallback으로만 읽고, 새 코드에서는 더 이상 emit하지 않도록 정리.
* Python 3.9 preflight 호환:
  - `src/core/managers.py`, `src/ui/widgets/chart.py`에 postponed annotations를 적용해 `python -m src.utils.preflight`의 3.9 import 오류를 해소.

### ✅ 문서/.spec/.gitignore 정합성

* 문서 동기화:
  - `README.md`, `claude.md`, `gemini.md`, `update_history.md`에 동일 기준으로 인코딩 정리/레거시 키 호환/Python 3.9 호환 점검 결과를 반영.
* `.spec` 재점검:
  - `naverland-scrapper.spec`는 이번 범위에서 추가 hidden import/runtime hook 수정이 필요하지 않음을 재확인.
* `.gitignore` 재점검:
  - 현재 빌드/로그/백업/Playwright 산출물 무시 규칙으로 충분하며 신규 패턴 추가는 불필요.

### ✅ 검증

* `python -m src.utils.preflight`: pass
* `python -m unittest discover -s tests -p "test_*.py"`: pass
* 신규 회귀 테스트:
  - `tests/test_mojibake_scan.py`
  - `tests/test_python39_annotation_compat.py`

## **v15.0.6 (2026-03-08)**

**UI 안정화 + 타입 정리 + 패키징 디버그 경로 보강**

### ✅ 핵심 반영

* 검색 조건 UI 리사이즈 확장:
  - 수집 탭 좌/우 패널과 내부 조건 섹션에 `QSplitter`를 적용하고 비율 상태를 저장/복원하도록 정리.
* 입력 휠 오입력 방지:
  - `QSpinBox/QDoubleSpinBox/QComboBox` 전역 wheel-guard를 추가해 스크롤 중 값 변경을 방지.
  - 콤보박스는 팝업이 열린 경우에만 휠 선택 허용.
* 드롭다운 테마 가독성:
  - 라이트/다크 테마별 `QComboBox QAbstractItemView` 배경/텍스트/hover/selected 색상 분리 적용.
* 전역 타입 정리:
  - `npx pyright src` 기준 `0 errors` 달성(`src/` 기준).

### ✅ .spec 점검/수정

* Matplotlib Qt hidden import를 `matplotlib.backends.backend_qtagg` 기준으로 정리(현 코드 기준).
* `NAVERLAND_CONSOLE=1` 환경변수로 콘솔 빌드를 선택 가능하게 해 GUI 조용한 실패 디버깅 경로를 제공.
* `NAVERLAND_BUNDLE_CHROMIUM=1`에서 Chromium 번들 탐지 실패 시 spec 단계 경고를 출력하도록 개선.

### ✅ 문서 정합성

* `README.md`, `claude.md`, `gemini.md`, `update_history.md`에 동일한 기준으로 UI/타입/.spec 변경사항을 동기화.
* 빌드 가이드에 콘솔 디버그 빌드(`NAVERLAND_CONSOLE=1`)를 추가.

## **v15.0.5 (2026-03-07)**

**.spec/문서 정합성 재점검 + 감사 문서 복구 + 무시 규칙 재확인**

### ✅ 핵심 반영

* `.spec` 재점검: `naverland-scrapper.spec`는 현재 분할 리팩토링 구조(`*_parts`) 기준에서도 추가 수정이 필요하지 않음을 재확인.
* 감사 문서 복구: 실수로 작업 트리에서 제거된 `crawling_scraping_risk_audit_2026-03-07.md`를 복구하고, 문서 정합성 추적 섹션을 추가.
* 문서 동기화: `README.md`, `claude.md`, `gemini.md`에 동일한 운영 기준(fallback/geo/split/.spec 정책)과 점검 결론을 반영.

### ✅ 문서 정합성 보강

* `gemini.md`에 누락되어 있던 최신 정합성 포인트(분할 리팩토링, 감사 리포트 참조, `.spec` 유지 정책)를 보강.
* `README.md`에 2026-03-07 기준 문서/패키징 재점검 결과를 추가해 사용자 문서와 내부 컨텍스트 문서 간 결론을 일치시킴.

### ✅ .gitignore 점검

* `build/`, `dist/`, `logs/`, `backup/`, `backups/`, `playwright-report/`, `test-results/`, `.playwright/`, `ms-playwright/` 규칙이 모두 유효함을 확인.
* 신규 무시 패턴 추가는 불필요.

## **v15.0.4 (2026-03-07)**

**크롤링/스크래핑 리스크 감사 문서화 + 문서/무시규칙 정합 업데이트**

### ✅ 핵심 반영

* 구현 리스크 감사 문서 추가: `crawling_scraping_risk_audit_2026-03-07.md`
* P1~P3 위험 항목 정리:
  - Selenium 경로의 0건 negative cache 저장 조건
  - 차단 감지 누적 기반 쿨다운(circuit breaker) 부재
  - API 경로/DOM 구조 변경 내성 및 관측성(metric) 강화 필요
* 코드 분할 구조를 문서에 동기화:
  - `src/core/database_parts/*`
  - `src/core/crawler_parts/*`
  - `src/core/engines/playwright_parts/*`
  - `src/ui/app_parts/*`
  - `src/ui/widgets/crawler_tab_parts/*`

### ✅ 문서/빌드/무시 규칙 점검

* `.spec` 점검 결과: `naverland-scrapper.spec`는 현재 분할 구조 기준으로 추가 수정 불필요.
* 문서 동기화: `README.md`, `claude.md`에 감사 문서 및 최신 점검 결론 반영.
* `.gitignore` 보강: 백업 산출물 디렉토리 `backups/` 무시 규칙 추가.

## **v15.0.3 (2026-03-07)**

**P0~P2 신뢰성 패치 일괄 반영 + 문서/CI 정합 보강**

### ✅ 핵심 반영

* fallback 정합: Playwright 실패 시 Selenium fallback이 미처리 pair만 이어서 수행되도록 pair 추적 로직 도입.
* 수집 중복 방지: `_push_item`에 `(complex_id, article_id, trade_type)` item dedupe 추가.
* negative cache 안전화: `response_seen=True` + `drain_timed_out=False` 조건에서만 `confirmed_empty` 저장.
* Playwright 메모리 워치독: 500MB 초과 시 browser/context/page pool recycle + 통계 emit.
* DB 스키마 마이그레이션: `complexes`를 `(asset_type, complex_id)` 복합 unique로 전환, legacy row는 `APT` 승격.
* DB 삭제 UX 강화: 삭제 확인 모달 및 `관련 이력까지 삭제` 옵션(기본 off), `purge_related` API 연동.
* Playwright retry 보강: 네트워크 민감 구간 lightweight retry 추가.
* CI 보완: push 테스트 미실행 유지 + `workflow_dispatch` + nightly `schedule(UTC 18:00)` 추가.

### ✅ 문서/빌드/무시 규칙 점검

* `.spec` 점검 결과: `naverland-scrapper.spec`는 현 코드 기준 추가 수정 불필요(Playwright hidden import/runtime hook/Chromium bundle 유지).
* 문서 동기화: `README.md`, `claude.md`, `gemini.md`, `crawling_scraping_risk_audit_2026-03-07.md`에 동일 정책 반영.
* `.gitignore` 점검 결과: 빌드/로그/Playwright 산출물(`build/`, `dist/`, `logs/`, `playwright-report/`, `test-results/`, `.playwright/`, `ms-playwright/`) 규칙이 이미 유효.

### ✅ 검증

* `python -m unittest discover -s tests -p "test_*.py"`: pass
* `python -m src.utils.preflight`: pass

## **v15.0.2 (2026-03-06)**

**Audit+Followup 통합 수정 마감 + 문서/빌드 정합 반영**

### ✅ 통합 수정 완료 항목

* 비동기 안정화 보강: response drain timeout 설정 연동, timeout/wait 통계 누적, 중단 시 detail task cancel+gather 정리.
* 캐시 정합 통일: complex 모드 캐시 컨텍스트를 엔진 공통(mode=complex, asset_type=APT, marker_id="")으로 정규화.
* 레거시 키 읽기 호환: 기존 complex 컨텍스트 키 hit 시 정규 키로 재저장하는 승격 경로 유지.
* DB 경계 강화: 소멸 마킹 API가 (complex_id, trade_type)과 (asset_type, complex_id, trade_type)를 모두 지원.
* Geo 운영 가시성: 상태바+로그에 geo_discovered_count, geo_dedup_count, response_drain_wait_count, response_drain_timeout_count 노출.
* Geo 정책 정합: geo_sweep는 Playwright 전용 유지, Selenium fallback 미지원 경고 로그 명시.

### ✅ 문서/빌드 정합

* 문서 동기화: README.md, claude.md, gemini.md, 감사/후속 리포트 문서에 동일 정책 기준 반영.
* PyInstaller spec 점검: naverland-scrapper.spec 기준에서 이번 범위 추가 수정 불필요 확인.
* .gitignore 점검: build/, dist/, logs/, playwright-report/, test-results/, .playwright/, ms-playwright/ 등 빌드/실행 산출물 무시 규칙이 이미 유효함을 확인.

### ✅ 검증

* PYTHONPATH=. pytest -q tests/test_playwright_engine_stabilization.py tests/test_managers_cache.py tests/test_database_module.py tests/test_geo_tab_wiring.py tests/test_crawler_regressions.py
* 결과: 44 passed

## **v15.0 (기준 릴리즈)**

**기능 구현 감사 리포트(2026-03-02) 전항목 반영 배치**

### ✅ Anti-Bot / Geo 통합 확장 (2026-03-06)

* **Playwright 기본 엔진 도입**: `CrawlerThread`를 엔진 orchestration 레이어로 정리하고, 기본 엔진을 `Playwright`로 확장. 기존 `Selenium`은 fallback 경로로 유지.
* **엔진/모델/서비스 계층 추가**: `src/core/engines`, `src/core/models`, `src/core/services` 추가. `playwright_engine.py`, `map_geometry.py`, `response_capture.py`, `detail_fetcher.py`, `gap_analysis.py` 도입.
* **지도 탐색 탭 추가**: `GeoCrawlerTab`에서 위도/경도/줌/링/그리드 간격/대기시간 기반 `geo sweep` 지원.
* **자동 단지 등록**: 지도 탐색으로 발견한 `APT`, `VL` 단지를 DB에 자동 등록하고 즉시 상세 수집 흐름과 연결.
* **모바일 상세 확장 수집**: `부동산상호`, `중개사이름`, `전화1`, `전화2`, `기전세금(원)`, `전세_기간(년)`, `전세_기간내_최고/최저(원)` 수집 추가.
* **갭 분석 필드 반영**: `갭금액(원)`, `갭비율`, `자산유형`, `수집모드`, `좌표/줌`, `마커ID`를 UI/DB/export 전 구간에 반영.
* **설정 확장**: `crawl_engine`, `fallback_engine_enabled`, `playwright_*`, `geo_*` 설정 추가.
* **PyInstaller spec 확장**: Playwright hidden imports, Chromium 번들, runtime hook 추가.
* **preflight 강화**: Playwright 패키지뿐 아니라 Chromium 브라우저 바이너리 존재 여부까지 확인.
* **테스트 보강**: geometry, gap analysis, DB 확장 컬럼, geo tab wiring 테스트 추가.

### ✅ 핵심 반영 항목

* **종료/복구 중단 안정화**: `RetryCancelledError` 도입, 재시도 대기 구간 인터럽트 가능화, `CrawlerThread.stop()`의 인터럽트 요청 연동.
* **URL 배치 분석 비동기화**: `URLBatchDialog`에 worker thread + 진행률 + 취소 버튼 추가로 UI block 제거.
* **DB 정합성 강화**: 단지 삭제 시 `group_complexes` 선삭제, orphan 정리 SQL 추가, FK 활성화.
* **분석 모듈 중복 제거**: `analysis.py`의 `MarketAnalyzer`/`ComplexComparator` 중복 정의 제거.
* **예약 실행 보호 로직**: 실행 중에는 예약 태스크 목록을 덮어쓰지 않고 skip 처리.
* **검색 히스토리 dedupe 개선**: `trade_types`, `area_filter`, `price_filter` 포함 canonical key 적용.
* **0건 결과 negative cache**: empty list도 short TTL로 저장/재사용.
* **버전 메타데이터 통합**: `src/utils/version.py`의 `APP_VERSION = "v15.0"`를 단일 소스로 사용.
* **DB 저장 카운트 정밀화**: `add_complex(return_status=True)` 기반 `inserted/existing/error` 분리 집계.
* **수동 단지 ID 검증 강화**: 5~10자리 숫자 validator + 최종 정규식 검증 추가.
* **DB 잠금 대응 보강**: 크롤링 이력/매물 이력/소멸 처리 write를 직렬화하고 짧은 재시도 경로를 적용.
* **DB 손상 보호 장치**: `malformed` 감지 시 write circuit-breaker를 활성화해 수집 지속 + 추가 write 차단.
* **UI 멈춤 완화**: `complex_finished` 슬롯의 UI 스레드 DB write를 제거하고 백그라운드 스레드 저장으로 이관.

### 🧪 검증

* **회귀 테스트**: `PYTHONPATH=. pytest -q`
* **결과**: `87 passed`
* **PyInstaller spec 점검**: `naverland-scrapper.spec`은 Playwright Chromium 번들 경로와 runtime hook을 포함하도록 갱신됨.

---

## **v14.2**

**안정성/운영성/스크래핑 정확도 강화 패치**

### ✨ 신규/강화 기능

* **DB 백업/복원 안정화**: SQLite online backup API 기반 백업, 복원 후 `PRAGMA integrity_check` + 필수 테이블 검증 추가
* **복원 유지보수 모드 도입**: 복원 중 크롤링/스케줄/주요 UI 액션 차단 후 완료 시 복구
* **월세 필터 분리 정책**: 월세 필터를 `보증금`/`월세`로 분리하고 두 조건 동시 만족 정책 적용
* **CrawlerTab 고급필터 실구현**: 수집 탭/필터 메뉴에서 고급필터 열기/적용/해제 및 ON/OFF 배지 표시
* **설정 UI 확장**: `retry_on_error`, `max_retry_count`를 설정창에서 직접 제어
* **가격변동 표기 통일**: UI/CSV/Excel 출력 모두 `+/-` 부호 포함 포맷 적용
* **차트 한글 폰트 fallback**: 폰트 미지원 환경에서 통계/대시보드 matplotlib glyph warning 최소화
* **테스트 환경 분리**: `pytest.ini`에서 `langsmith_plugin` 자동 로드 비활성화
* **배포 스펙 정합화**: `naverland-scrapper.spec` 기본 배포를 `onefile`로 고정하고 `NAVERLAND_ONEFILE=0`으로 `onedir` 전환 지원

### 🛠 개선사항

* **캐시 정확도 개선**: 필터 통과 결과가 아닌 원본(raw) 매물 캐시 저장 후 조회 시 재필터링
* **차단 페이지 즉시 실패 처리**: 캡차/접근제한 시그널 감지 시 정상 0건이 아닌 실패 경로로 처리
* **스크롤 내구성 향상**: 내부 컨테이너 스크롤 우선 + window 폴백 + 신규 ID 유입 기반 종료 조건
* **URL 과추출 완화**: 무문맥 숫자 추출 축소, API 이름 미확인 항목은 기본 체크 해제
* **종료 정책 강화**: `shutdown_crawl()` 타임아웃 시 앱 종료 중단 및 DB close 차단
* **Retry base_delay 반영**: `RetryHandler.base_delay`가 실제 대기 계산에 반영되도록 연결
* **프리셋 스키마 확장**: `monthly_min/max`(legacy) + `monthly_deposit_*`, `monthly_rent_*`(신규) 동시 지원
* **빌드 점검**: `naverland-scrapper.spec` 확인 결과 추가 hidden import 수정 불필요

### ✅ 검증

* **회귀 테스트**: `pytest -q` 기준 전체 통과
* **추가 시나리오**:
  * 통계/대시보드 반복 진입 안정성
  * 고급 필터 적용/해제 동작
  * 복원/종료 경계 시나리오
  * 캐시 재평가/월세 이중 조건/차단 감지/Retry 반영 회귀

---

## **v14.0**

**UI/UX Revolution & 모듈화 아키텍처**

### ✨ 신규 기능

* **Glassmorphism 테마**: 반투명 배경, 그라디언트 버튼, Warm Amber 악센트 컬러
* **완전한 Light 테마**: Tailwind CSS 색상 팔레트 기반, Sky Blue 악센트 컬러
* **Toast 알림 시스템**: 페이드 인/아웃 애니메이션, 슬라이드 효과, 호버 시 일시정지, 클릭으로 닫기
* **모듈화 아키텍처**: `src/` 디렉토리 기반 구조 (core, ui, utils 분리)
* **최적화된 스크롤**: 컨텐츠 변화 감지 기반 동적 스크롤링

### 🛠 개선사항

* **메모리 관리**: 임계치(500MB) 초과 시 드라이버 자동 재시작
* **테마 전환**: `Ctrl+T` 단축키로 즉시 Dark/Light 테마 전환
* **다이얼로그 분리**: 10개의 다이얼로그를 별도 폴더(`src/ui/dialogs/`)로 정리
* **이력 DB 배치 업서트**: 매물 이력 반영을 bulk upsert로 전환 (기본 배치 `200`)
* **결과 검색 성능 개선**: 행 검색 캐시 + hidden 상태 캐시 + 디바운스 (기본 `220ms`)
* **로그 탭 최적화**: 최대 라인 제한으로 장시간 실행 시 렌더링 비용 제어 (기본 `1500`)
* **지연 초기화 옵션**: 비핵심 탭의 초기 로드를 지연해 앱 시작 반응성 개선 (기본 `True`)
* **동일 매물 축약 표시**: 동일 가격/평수/층 중심 유사 매물을 `N건`으로 묶어 표시 (기본 `ON`)

---

## **v13.0**

**분석 대시보드 & 안정성 강화**

### ✨ 신규 기능

* **시세 분석 대시보드**: 통계 카드, 파이차트, 히스토그램으로 데이터 시각화
* **카드 뷰 모드**: 매물 정보를 시각적인 카드 형태로 표시
* **즐겨찾기 시스템**: 관심 매물 저장 및 메모 관리 기능
* **Connection Pool**: 스레드 안전한 SQLite 연결 관리

### 🛠 개선사항

* **RetryHandler**: 네트워크 오류 시 지수 백오프 자동 재시도
* **Rate Limit 감지**: 네이버 차단 방지 자동 대기 로직
* **드라이버 재시작**: 메모리 누수 방지를 위한 자동 재시작

---

## **v12.0**

**캐시 시스템 & 매물 추적**

### ✨ 신규 기능

* **크롤링 캐시**: TTL 기반 결과 캐싱으로 중복 크롤링 방지
* **평당가 표시**: 전용면적 기준 평당가 자동 계산 및 표시
* **매물 소멸 추적**: 사라진 매물을 기록하여 시장 분석에 활용

---

## **v7.3**

**기능 확장 및 편의성 개선**

### ✨ 신규 기능

* **가격 변동 알림 시스템**: 동일 매물의 가격 변화를 추적하여 상승(📈)/하락(📉) 아이콘과 변동액 표시
* **신규 매물 배지**: 오늘 처음 발견된 매물에 NEW 배지 부착
* **고급 필터링**: 가격/면적 범위, 층수(저/중/고), 특정 키워드 포함/제외 필터
* **엑셀 템플릿 커스터마이징**: 원하는 컬럼만 선택하거나 순서를 저장하는 템플릿 기능
* **URL 일괄 등록**: 텍스트에서 네이버 부동산 URL이나 단지 ID 자동 추출하여 일괄 등록
* **특징 파싱 개선**: 무의미한 중개사 광고 멘트 제거, 실질적인 매물 특징(올수리, 확장형 등)만 추출

---

## **v7.2**

**안정성 및 유지보수**

### 🛠 개선사항

* **DB 경로 안정성 확보**: 실행 환경(IDE, PyInstaller 등)에 따라 달라지는 경로 문제 해결
* **DB 복원 기능 강화**: Connection Pool 충돌 문제 해결 및 안전한 복원 로직 구현
* **디버깅 로그 강화**: 문제 발생 시 원인 파악을 위한 상세 로그 기록

---

## **v7.1**

**UI/UX 개선 및 기본 기능 강화**

### 🎨 UI/UX 업데이트

* **결과 요약 카드**: 매물 총 개수 및 매매/전세/월세별 현황 대시보드
* **예상 소요 시간(ETA)**: 현재 진행 속도 기반 크롤링 완료 시간 표시
* **링크 버튼 개선**: 텍스트 링크 대신 클릭 가능한 버튼 형태 UI 적용
* **툴팁 도움말**: 주요 버튼과 입력창에 설명 툴팁 추가

### ⚙️ 기능 개선

* **단위 라벨 명시**: 금액(만원/억), 면적(평/㎡) 등의 단위 명확하게 표시
* **최근 검색 기록**: 자주 찾는 단지 조합 저장 및 불러오기 기능
* **정렬 옵션**: 가격순, 면적순, 단지명순 등 다양한 정렬 기능
* **완료 알림음**: 작업 완료 시 소리 알림 옵션


