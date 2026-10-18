# Project Audit

> 후속 구현: 아래 본문은 수정 전 감사 기록입니다. 사용자의 후속 승인에 따라 확정 이슈와 안정성 보완을 구현했으며, 현재 동작·검증·남은 환경 제약은 [감사 후속 개선 기록](docs/AUDIT_FIXES_2026-10-18.md)에 정리했습니다.

> 감사일: 2026-10-18 (Asia/Seoul). 대상: 현재 `main` 작업 트리. 초점: 실제 매물 수집 → 정규화 → 필터 → 이력/소멸 판정 → 가격 통계 → 내보내기.
> 코드 수정 없이 이 보고서만 작성했다. 기존 2026-10-04 감사서는 현재 소스·테스트·라이브 관측에 근거한 본 보고서로 대체한다. 과거 감사의 결론을 그대로 계승하지 않았다.

## 1. Executive Summary

- **프로젝트 상태:** Playwright 목록 API 중심의 Windows/PySide6 앱이다. 사이트 계약 분리, 상세 정보 대체 조회, SQLite WAL·트랜잭션·고유키, 종료 대기, 불완전 지도 탐색 보호 등이 구현되어 있다. 핵심 단위·통합 테스트 **235개가 통과**했다.
- **전체 위험도: High Risk — 수집 데이터의 의미적 무결성 보완 필요.** DB 파일 자체가 깨지는 문제보다, 불완전하거나 필터링된 표본을 전체 관측 결과처럼 저장·해석하는 문제가 중요하다.
- **가장 중요한 문제:**
  1. 페이지 중간 429/오류 및 잘못된 응답 스키마를 정상 수집/빈 결과로 승격한다. 누락 결과가 캐시·소멸 판정·통계에 전파된다. **High / Confirmed**.
  2. 가격·면적 필터에서 제외된 실제 존재 매물을 다음 날 `disappeared`로 오판한다. **High / Confirmed**.
  3. 같은 날 필터를 바꾸거나 수집을 중단하면 기존 전체 가격 스냅샷을 부분 표본으로 덮어쓸 수 있다. **High / Confirmed**.
  4. 분양권 포함 옵션이 캐시 키에 없어 변경 전 조건의 목록이 재사용된다. **Medium / Confirmed**.
- **데이터 손상/유실:** 물리적 DB 손상이나 원본 DB 파괴를 확인하지는 않았다. 그러나 소멸 상태 오염과 일별 집계 덮어쓰기는 임시 DB에서 재현했다. 집계 이전 표본이 별도 보존되지 않았다면 정확한 과거 집계 복원은 어려워진다.
- **우선 수정 영역:** 수집 완료성 계약 → 전체 관측 ID와 표시 필터 분리 → 통계 표본/실행 단위 저장 정책 순서다.
- **현재 네이버 구조:** `new.land`의 목록·단지 개요·지도 API와 기존 주요 필드는 라이브 브라우저에서 유효했다. `fin.land/articles/{id}`는 이번 세션에서 404가 아니라 `map?layer=...`의 실제 매물 상세 화면으로 연결됐다. 과거 조사 문서의 일괄적인 HTML 장애 가정은 현재 정상 경로를 대표하지 않는다. 구조 변경의 정확한 적용 시점·전체 사용자 적용 여부는 확인하지 못했다.

## 2. Project Understanding

### 목적과 개발 규칙

`README.md`는 APT/VL 매물 수집, 신규/가격 변동/소멸 감시, 예약 수집, 일별 통계, Excel/CSV/JSON 내보내기를 설명한다. `DESKTOP_UI_DESIGN_RULES.md`는 PySide6 단일 바인딩과 일관된 상태 표시를 요구한다.

저장소 루트에는 `CLAUDE.md`와 `AGENTS.md` 파일이 없었다. 대화로 제공된 AGENTS 지시(CodeGraph 우선, 별도 요청 없으면 main)를 적용했다. `.codegraph/`가 있어 CodeGraph MCP를 먼저 사용했다. 브랜치를 생성하지 않았다.

확인한 주요 설정은 `requirements.txt`, `pytest.ini`, `pyrightconfig.json`, `naverland-scrapper.spec`, `.github/workflows/ci.yml`, README의 실행·빌드 안내다. 런타임은 Python, PySide6/Fluent Widgets, Playwright/Chromium, Selenium/undetected-chromedriver, BeautifulSoup, SQLite, openpyxl, matplotlib 등에 의존한다. 의존성을 설치하거나 갱신하지 않았다.

### 주요 entrypoint와 모듈

| 영역 | 주요 경로 | 역할 |
|---|---|---|
| 실행 | `app_entry.py::main` → `src/main.py::main` | 경로 초기화, preflight/live-smoke 또는 GUI 실행 |
| UI 시작 | `crawler_tab_parts/crawl_control_parts/start_stop.py` | 대상·필터·설정 구성, 수집 락, 캐시/워커 생성 |
| 워커 | `src/core/crawler.py::CrawlerThread` | QThread 시그널, 엔진 실행, 배치 결과/이력 처리 |
| 목록 수집 | `engines/playwright_parts/complex_mode_parts/*` | URL 진입, 네트워크 응답 캡처, 인증 헤더 기억, 직접 API 페이지 수집 |
| 지도 수집 | `engines/playwright_parts/geo_mode_parts/*` | 좌표 그리드, cortarNo 조회, 마커 발견, 발견 단지 수집 |
| 정규화 | `services/response_capture.py`, `item_parser.py`, `helpers.py` | API/DOM 필드 매핑, 억·만원 변환, 면적·평당가 계산 |
| 상세 보강 | `services/detail_fetcher_parts/*` | fin/m 상세 HTML, hydration, 네트워크 JSON, front-api 보강 |
| 데이터 처리 | `crawler_parts/history_alerts.py`, `services/price_snapshots.py` | 신규/가격 변화, 알림 중복 억제, 이력, 소멸, 집계 |
| 저장 | `database.py` 및 `database_parts/*` | 단지·그룹·이력·스냅샷·즐겨찾기, 마이그레이션·백업/복원 |
| 자동화/종료 | `app_parts/stats_schedule_parts/schedule_run.py`, `lifecycle_parts/shutdown.py` | 예약 슬롯, 실행 중복 방지, 종료 대기·캐시 flush |
| 출력 | `src/core/export.py` | 선택 열 내보내기, CSV BOM, 수식 주입 방어, 임시 파일 후 교체 |

### 핵심 실행 흐름

**단지 수집:**

`URL/ID·거래유형·가격/면적 조건 → UI 대상 검증/락 → CrawlerThread → PlaywrightCrawlerEngine._run_complex_mode → _crawl_target_with_cache → _collect_target_raw_items → 브라우저 응답 캡처/Article API 페이지 수집 → normalize_article_payload → _process_raw_items_with_filtered_details → 필터/상세 보강 → _enrich_item_with_history_and_alerts → SQLite article_history·알림 + UI 결과 → 소멸 판정 → 완료 UI → build_price_snapshot_rows → price_snapshots → Excel/CSV/JSON`

**지도 수집:**

`좌표·줌·범위·APT/VL → _run_geo → _scan_geo_asset_type → /api/cortars → /single-markers/2.0 + DOM 마커 → 발견 단지 중복 제거 → 동일 목록/정규화 경로 → geo incomplete 보호 → 이력·소멸·결과`

**예약:**

`로컬 시각/예약 슬롯 → 실행 중 워커·CrawlLock 확인 → 그룹 또는 지도 프로필 적용 → 기존 수집 진입점 → 시작 성공 시 last_run_slot 저장`

### 데이터 모델과 보호 장치

- 개발 실행 기본 DB는 **`data/complexes.db`**다. frozen 실행은 사용자 앱 데이터 디렉터리를 사용하며, `NAVERLAND_DATA_DIR`는 bootstrap에서 기준 디렉터리를 바꾸고 그 아래 `data/`, `logs/`를 만든다.
- 단지는 `(asset_type, complex_id)`, 매물 이력은 `(asset_type, article_id, complex_id)`로 구분한다. APT/VL 동일 ID 충돌 방어가 있다.
- 이력의 가격 수치는 만원 단위이고, 기존 전세금·갭 금액은 원 단위다. 월세 집계는 `deposit`와 `rent`를 분리한다.
- `article_history`는 매물별 최신 상태와 이전 가격 기준을 갱신하는 테이블이다. 모든 관측 시점의 원본을 누적 보관하는 이벤트 테이블은 아니다.
- `price_snapshots`는 날짜·자산·단지·거래유형·평형·가격지표별 집계다. 동일 키는 upsert로 교체된다.
- SQLite 연결 풀은 WAL, busy_timeout, foreign_keys를 활성화한다. 이력 bulk에는 write lock, commit/rollback, lock 오류 재시도가 있다. 복원은 사전 백업·연결 종료·검증·롤백을 갖춘다.
- `CrawlCache`는 기본 30분 TTL의 로컬 JSON 캐시이며 모드/자산/좌표/마커를 분리한다. 설정 JSON과 export에는 원자적 파일 쓰기 경로가 있다.

## 3. Audit Coverage & Limitations

### 구조 분석 및 반증 범위

CodeGraph MCP `codegraph_explore`를 실제 사용했다. 다음 호출 관계와 verbatim source를 우선 확인했고, 잘린 함수의 나머지·설정·문서는 직접 열람으로 보완했다.

- entrypoint, `CrawlerThread`/엔진 facade와 mixin 재바인딩 구조.
- `_fetch_article_api_fast_path → _paginate_article_api_request_context → _normalize_article_api_payload → normalize_article_payload`.
- `_crawl_target_with_cache → _process_raw_items_with_filtered_details → _enrich_item_with_history_and_alerts → _flush_history_updates → upsert_article_history_bulk`.
- `_run_complex_mode/_run_geo → _finalize_disappeared_articles → mark_disappeared_articles_for_targets`.
- `_on_crawl_finished → _save_price_snapshots → build_price_snapshot_rows → add_price_snapshots_bulk`.
- 상세 orchestrator/artifact/front-api/field merge, 캐시, DB pool/스키마/백업·복원, 예약·종료·수집 락.

CodeGraph는 일부 큰 파일을 잘라 반환했으며, Qt 시그널·동적 mixin 재바인딩은 정적 caller 목록만으로 완전히 증명되지 않는다. 관련 facade·상위 caller·테스트를 함께 확인했다. 원시 mixin의 전역 이름 누락은 실제 facade 재바인딩으로 공급되므로 production 버그로 분류하지 않았다.

### 실행한 테스트

**실제 결과: 157 passed + 78 passed = 235 passed.** 전체 테스트 스위트, GUI E2E 또는 실제 앱의 대량 스크래핑을 통과했다는 의미는 아니다.

1차는 `python -m pytest -q -p no:cacheprovider`에 아래 파일을 지정했다.

```text
test_helpers.py, test_item_parser.py, test_response_capture_normalize.py,
test_site_contract.py, test_article_api.py, test_detail_fetcher.py,
test_database_module.py, test_database_engine_extensions.py, test_analysis.py,
test_export_module.py, test_managers_cache.py,
test_playwright_engine_stabilization.py, test_geo_markers_cortar.py
결과: 157 passed in 21.88s
```

2차는 임시 기준 디렉터리를 `configure_paths`/bootstrap으로 주입한 Python에서 `pytest.main(['-q', '-p', 'no:cacheprovider', ...])`을 호출했다.

```text
test_parser_module.py, test_keyword_search.py, test_map_geometry.py,
test_gap_analysis.py, test_retry_handler.py, test_crawl_lock.py,
test_browser_pool_guard.py, test_runtime_playwright.py, test_paths_runtime.py,
test_live_smoke.py, test_update_manifest.py, test_update_installer.py
결과: 78 passed in 23.96s
```

1차의 DB·설정·캐시 테스트는 테스트 자체의 임시 파일/patch를 사용했다. 별도 재현은 임시 디렉터리의 synthetic DB와 가짜 API 응답만 사용했다. 디스크에 테스트 코드 파일을 추가하지 않았다. 초기 수동 재현 시 PowerShell stdin 인코딩과 원시 mixin 전역 주입 문제를 수정해 재실행했으며, 아래 이슈의 근거는 수정 후 성공한 재현 결과다.

### 실제 저장 데이터 확인

`data/complexes.db`를 SQLite `mode=ro&immutable=1`, `query_only=ON`으로 열어 스키마·개수·quick_check만 읽었다. 기존 DB에 앱 초기화·마이그레이션·쓰기 쿼리를 실행하지 않았다.

- `PRAGMA quick_check`: **ok**.
- `complexes`, `crawl_history`, `price_snapshots`, `article_history`, `groups`, `group_complexes`, `alert_settings`, `article_alert_log`: **각 0건**.
- `article_favorites`: **1건**. 내용은 보고서에 노출하지 않았다. 즐겨찾기가 이력 없이 존재할 수 있으므로 이것만으로 손상이라고 판단하지 않았다.
- 따라서 실제 누적 매물의 결측률·중복률·가격 이상치·장기간 수집 완전성은 계산할 표본이 없다. 데이터가 비어 있다는 사실은 수집 기능 실패의 증거가 아니다.
- 실행 전후 기존 `data/` 파일의 크기·수정시각은 동일했다.

### 네이버 라이브 구조 확인

2026-10-18 브라우저 세션에서 읽기 전용으로 관측했다. 웹 조회 도구는 접근 오류/timeout이 났고, Playwright 브라우저에서는 실제 페이지를 확인했다. 대량 수집, 로그인, 차단 우회, 사용자 계정 변경은 수행하지 않았다. URL은 아래의 실제 확인 대상이며 세션별 인증값은 기록하지 않았다.

| 확인 대상 | 실제 관측 | 앱과 비교 |
|---|---|---|
| [남산타운 단지 3833](https://new.land.naver.com/complexes/3833) | 정상 목록, `.item/.item_inner/.price` 각 20개 | 기존 DOM 대체 경로의 주요 selector가 유지됨. selector 전체의 완전성 보장은 아님 |
| 브라우저 `/api/articles/complex/3833` | HTTP 200, `articleList` 20건, `isMoreData=true` | 기존 페이지네이션 계약 유효. 단일 페이지가 전체가 아님을 실제로 확인 |
| 목록 필드 | `articleNo`, `tradeTypeCode`, `dealOrWarrantPrc`, `area1/area2`, `realtorName`, `sameAddrCnt`, `detailAddress`, `isDirectTrade` 존재 | 현재 정규화 키와 일치 |
| 실제 수치 표본 | 매매 `19억 5,000`, `area1=139`, `area2=114`, APT | 목록 면적은 정수 근사. 상세에는 공급 139.94㎡·전용 114.88㎡ 표시. 목록의 139㎡를 상세 정밀 면적으로 오해하면 안 됨 |
| `/api/complexes/overview/3833` | 브라우저 요청 200, 단지명/좌표/평형 등 반환 | 개요 조회 엔드포인트 유효 |
| `/api/cortars`, `/api/complexes/single-markers/2.0` | 브라우저 요청 200; `cortarNo` 포함 마커 요청, 표본 응답 16개 | 현재 site_contract의 cortarNo 경로와 부합. bbox-only 비교 실험은 이번에 하지 않음 |
| [관측 목록의 실제 매물 상세](https://fin.land.naver.com/articles/2656054034) | `map?layer=...`로 연결되며 해당 매물번호와 가격·면적·설명이 실제 표시됨 | map 리다이렉트 자체는 오류가 아님. 8월 문서의 404 관측과 다름 |
| 상세 hydration | `script#__NEXT_DATA__` 0개, `self.__next_f.push` 포함 script 존재 | RSC 계열 상태 사용 관측. 기존 hydration helper의 명시적 읽기 대상에는 `__next_f`가 없음. HTML/DOM/네트워크 대체 경로가 있어 전체 상세 실패로 단정하지 않음 |
| 상세 후속 리소스 | `front-api/v1/article/maintenanceFee` 등 여러 front-api 경로 | front-api 계열 자체는 계속 사용됨. agent/basicInfo의 모든 필드·세션 조건은 미검증 |
| 브라우저 외 직접 GET | search·overview에서 HTTP 429 `TOO_MANY_REQUESTS` | 엔드포인트 삭제 증거가 아님. 인증/세션/요청 맥락에 따른 차이로 해석해야 함 |

기존 조사 문서 `docs/NAVER_LAND_SURVEY_2026-08-04.md`, `...08-12.md`와 비교했다. 목록 API의 대대적인 필드 교체는 표본에서 발견하지 못했다. 상세의 map layer 및 RSC 상태는 현재 관측 차이이며, 배포 변경 시점을 확정한 것은 아니다. 라이브 VL·PRE·월세 전체 페이지, 검색 UI, 모바일 상세, 모든 지역·계정·A/B 환경까지 확인하지는 않았다.

### 환경상의 제한

- `.venv-ci`는 삭제된 Python 3.14 실행 파일을 가리켜 시작하지 못했다. `.venv`의 Python에는 pytest가 없었다.
- 사용 가능한 시스템 Python 3.15에서 순수 로직·DB·엔진 stub 테스트를 실행했다. `PYTHONNOUSERSITE=1`에서도 `PySide6.QtCore` import가 DLL 오류를 냈으므로 **GUI 전체 실행과 Qt 시그널 E2E는 미검증**이다. 이를 저장소 자체의 확정 결함으로 분류하지 않았다.
- Windows 외 Linux/macOS, 배포 EXE, 강제 전원 차단, 실제 동시 다중 프로세스, 대규모 DB 마이그레이션·복원은 직접 재현하지 않았다.
- build, Pyright, 전체 CI, 앱의 `--live-smoke` CLI는 실행하지 않았다. `test_live_smoke.py`의 통과와 실제 CLI 성공을 구분한다.

## 4. High-Risk Issues

### [ISSUE-001] 불완전 페이지·오류 응답을 정상 수집으로 처리해 캐시와 후속 데이터 판단에 전파

- **위치:** `src/core/engines/playwright_parts/complex_mode_parts/article_api.py:114,160,205,360`; 같은 디렉터리 `response_capture.py::_collect_target_raw_items`, `cache_flow.py:93-175`, `loop.py:55-70`.
- **우선순위:** High
- **신뢰도:** Confirmed
- **문제:** 2페이지 이후 HTTP 오류/429, JSON 오류, 잘못된 payload가 발생해도 이미 모은 일부 목록을 `_article_api_fast_path_success`로 반환한다. 반환에는 `parse_success=True`, `capture_failed=False`, 빈 `failure_reason`만 남는다. 50페이지 상한 초과도 통계 카운터만 올린다. 한편 목록 키가 없는 dict도 `payload.get('articleList') or ... or []`로 유효한 빈 배열처럼 받아들인다. 브라우저 캡처 콜백에는 HTTP status/오류 코드 확인 없이 동일한 빈 배열 승격이 있다.
- **발생 조건:** 실제 20건 이상 목록의 후속 페이지에서 일시적 429/5xx/비정상 JSON이 발생하거나, 브라우저 목록 응답이 오류 JSON을 반환할 때. 라이브에서 `isMoreData=true`와 직접 요청 429를 각각 관측했지만 실제 사용자 수집의 중간 429 발생 빈도는 측정하지 않았다.
- **영향:** 누락 목록이 정상 캐시로 남고 정상 완료 이력·가격 집계에 사용된다. 미관측 매물은 소멸로 잘못 처리될 수 있다. 오류가 빈 결과로 승격되면 negative cache까지 만들어 다음 시도도 빈 결과가 된다.
- **근거:** 가짜 응답 1페이지 정상 1건/`isMoreData=True`, 2페이지 429를 실제 paginator에 넣은 결과 `rows=1`, `parse_success=true`, `capture_failed=false`, `failure_reason=''`, `api_fast_path=true`. `{'success':False,'code':'SERVER_ERROR'}`를 실제 normalizer에 전달해 `valid_payload=True`도 확인했다. `test_article_api_fast_path_keeps_page_one_when_page_two_fails`는 일부 데이터 보존만 검증하며 후속 완료성 표시는 검증하지 않는다.
- **반증 확인:** 첫 페이지 fast-path의 HTTP 오류는 fallback한다. 예외가 전파되는 경로도 별도 처리가 있다. 그러나 중간 status 오류의 `break`는 예외가 아니며 성공 객체로 귀결된다. 일반 wrapper 재시도는 성공 반환값을 복구하지 않는다. positive cache는 raw_items 존재만으로 저장한다. 상위 loop는 `capture_failed/block_like_redirect`만 검사한다. geo incomplete 보호는 지도 탐색 실패 플래그에 의존해 목록 중간 누락을 자동 차단하지 못한다. DB constraint는 표본 완전성을 보장하지 않는다.
- **호출/영향 범위:** CodeGraph 기준 fast path 및 브라우저 페이지 보충 → cache flow → complex/geo loop → article_history/소멸 처리 → 완료 handler/price_snapshots/export. UI 진단용 실패 카운터가 있어도 저장·성공 판정은 멈추지 않는다.
- **권장 수정 방향:** `complete/partial/failed`와 마지막 성공 페이지·오류·상한 도달을 수집 결과 계약에 포함한다. partial 데이터는 표시·내보내기를 허용하되 완료 캐시, 전체 통계 교체, 소멸 판정을 금지한다. HTTP/status/application code와 목록 키·원소 타입을 함께 검증한다. 명시적 빈 목록과 미지원 스키마를 구별한다.
- **필요한 회귀 테스트:** 페이지 2의 429/500/invalid JSON, 목록 키 누락, 페이지 50 이후 moreData에 대해 partial/failed가 끝까지 전달되고 기존 이력 상태·전체 집계가 유지되는지 검증한다. 정상 `articleList=[]`만 confirmed empty로 인정해야 한다.

### [ISSUE-002] 수집 필터에서 제외한 정상 매물을 소멸로 오판

- **위치:** `src/core/engines/playwright_parts/complex_mode_parts/detail_enrichment.py:26-35,69-78`; `src/core/crawler_parts/history_alerts.py:107-149,398-452`; `src/core/database_parts/article_parts/disappeared_ops.py:63-126`.
- **우선순위:** High
- **신뢰도:** Confirmed
- **문제:** 전체 API 목록을 받은 뒤 가격·면적 필터를 먼저 적용해, 제외된 매물은 `last_seen`을 갱신하지 않는다. 완료 시에는 해당 자산/단지/거래유형 전체에서 `last_seen < CURRENT_DATE`인 active 매물을 disappeared로 바꾼다. 필터 밖의 존재 매물과 실제 미관측 매물을 구분하지 못한다.
- **발생 조건:** 이전 날짜에 넓은 조건으로 저장한 매물이 있고, 다음 DB 날짜에 더 좁은 수집 필터로 같은 단지·거래유형을 정상 수집할 때. 단순 결과 화면 검색 필터가 아니라 수집 가격·면적 필터가 해당한다.
- **영향:** 소멸 대시보드·모니터링 상태가 틀린다. 나중에 필터를 풀어 관측하면 다시 active로 돌아올 수 있지만 그 사이 판단은 잘못된다.
- **근거:** 임시 DB에 어제 관측한 9억/15억 매물 두 건을 생성하고, 두 매물이 모두 포함된 입력을 `최대 10억` 필터로 처리했다. 실제 `_process_raw_items → _enrich_item_with_history_and_alerts → upsert → _finalize_disappeared_articles → DB` 호출 결과는 `[('1','active'), ('2','disappeared')]`였다. Playwright 상세 처리의 선행 필터도 같은 이력 함수를 건너뛴다.
- **반증 확인:** 타깃 자산/단지/거래유형 scope, stop 체크, 성공 타깃만 처리, geo incomplete 보호는 존재한다. 그러나 정상 완료한 좁은 필터 실행은 모두 통과한다. DB에는 필터 범위·이번 실행에서 실제 관측한 전체 ID가 전달되지 않는다. 동일 날짜 재수집에서 문제가 안 보이는 것은 날짜 조건 때문이며 다음 날 경로를 막지는 않는다.
- **호출/영향 범위:** CodeGraph의 cache/detail flow 및 Selenium raw 처리 → history enrichment → 성공 타깃 소멸 처리 → article_history → 소멸 조회/대시보드. API는 가격·면적을 넓게 요청하고 로컬에서 필터링하므로 원래 응답에 존재 증거가 있다.
- **권장 수정 방향:** 전체 관측 ID의 존재 갱신을 표시/알림 필터보다 먼저 수행한다. 소멸은 완전 수집 run의 observed ID 집합을 기준으로 계산한다. 당장 이 분리가 어렵다면 필터 실행의 소멸 판정을 비활성화한다.
- **필요한 회귀 테스트:** 어제 9억/15억 active → 오늘 API에 둘 다 존재 → 최대 10억 필터 → UI 1건이지만 DB 두 건 모두 active. 가격·면적·월세 보증금/월세 필터 조합, 캐시 hit, APT/VL별로 반복한다.

### [ISSUE-003] 필터·중단 결과가 동일 날짜 전체 가격 스냅샷을 덮어씀

- **위치:** `src/ui/widgets/crawler_tab_parts/crawl_control_parts/finish.py:30-50,111-116`; `snapshot_worker.py:13-24`; `src/core/services/price_snapshots.py:14-71`; `src/core/database_parts/crawl_snapshot_parts/price_snapshot_write_ops.py:175-197`.
- **우선순위:** High
- **신뢰도:** Confirmed
- **문제:** 완료 handler는 수집 중단 여부를 화면에 표시하지만 스냅샷 저장은 계속 호출한다. 입력은 필터 적용 후 `collected_data`이고, 집계 키에 run ID·필터·표본 완전성이 없다. 동일 날짜·평형·거래유형·지표의 기존 min/max/avg/count를 이번 부분 표본으로 교체한다.
- **발생 조건:** 같은 날짜에 정상 전체 수집 후 가격/면적 필터를 좁혀 재수집하거나, 같은 그룹의 일부 결과를 모은 뒤 중단할 때. 수집 오류/페이지 누락이 정상 반환되는 ISSUE-001도 같은 영향을 만든다.
- **영향:** 날짜별 시세 추이·표본 수가 수집 조건 변경에 따라 흔들린다. 부분 실행에 없던 다른 평형의 기존 행은 그대로 남아 한 날짜에 서로 다른 관측 범위가 섞일 수도 있다. 과거 전체 집계 값은 현재 행에서 사라진다.
- **근거:** 실제 `build_price_snapshot_rows`와 DB bulk 저장으로 동일 평형의 9억/15억 두 건을 저장한 뒤 9억 한 건을 저장했다. 결과 `(min,max,avg,count)=(90000,90000,90000,1)`로, 기존 `(90000,150000,120000,2)`가 교체됐다. 완료 함수에는 stopped 상태의 저장 skip이나 성공성 검사가 없다.
- **반증 확인:** 날짜별 upsert는 중복 방지에 적절하고, write lock·transaction·월세 지표 분리·자산 구분도 있다. 문제는 upsert 자체가 아니라 교체를 허용하는 표본 기준이 없다는 점이다. 완료 단계는 현재 동기 저장이므로 예전 감사의 백그라운드 스냅샷 종료 경합은 이번 이슈로 재사용하지 않았다. 표 표시용 정렬/묶기만 바꾸는 것과 수집 필터 변경도 구분했다.
- **호출/영향 범위:** CodeGraph 기준 UI finished → `_save_price_snapshots` → rows builder → SQLite upsert → price snapshot queries/분석·차트. export에는 현재 표본이 나가지만, DB 통계에는 필터 조건이 기록되지 않는다.
- **권장 수정 방향:** 표준 일별 통계는 완전한 기준 표본에서만 교체한다. 필터별 통계가 목적이라면 query fingerprint/run ID를 저장하고 차트에서 구분한다. stopped/partial 실행은 전체 통계를 유지하고 별도 부분 실행 기록으로 남긴다. 완전 실행의 그룹 집합 교체 정책도 명확히 한다.
- **필요한 회귀 테스트:** 같은 날짜 전체→필터→중단 순서에서 전체 집계가 유지되는지, 재완료한 전체 실행만 기준 통계를 교체하는지 검증한다. 월세 deposit/rent, 사라진 평형 그룹, 0건·부분 페이지도 포함한다.

### [ISSUE-004] 분양권 포함 설정을 바꿔도 이전 조건의 캐시를 재사용

- **위치:** `src/core/engines/playwright_parts/complex_mode_parts/cache_flow.py:34-80`; `article_api.py:44-65`; `src/core/cache.py:41-97`; `src/ui/app_parts/settings_preset.py:52-118`; `src/ui/dialogs/settings.py:457-522`.
- **우선순위:** Medium
- **신뢰도:** Confirmed
- **문제:** `include_pre_sale_rights`는 API의 `realEstateType`에 `PRE`를 추가하지만 캐시 context/key에는 없다. 설정 저장·runtime 설정 반영 경로에서도 해당 캐시를 무효화하지 않는다. 새 수집마다 캐시 객체를 만들어도 JSON에 저장된 같은 키를 다시 읽는다.
- **발생 조건:** 기본 활성 캐시 TTL 안에 동일 단지/거래유형을 수집하고 분양권 포함을 토글한 뒤 재수집할 때.
- **영향:** 켜도 PRE가 안 나오거나, 끄고도 이전 PRE 포함 결과가 남을 수 있다. TTL 만료/캐시 비활성 후 재수집으로 회복 가능하므로 Medium으로 평가한다.
- **근거:** 실제 `CrawlCache`와 `_crawl_target_with_cache`로 캐시를 미리 채우고 옵션 False→True를 바꿨다. API URL은 달라졌지만 두 실행 모두 `cache_hit=True`, 변경 후 raw_count는 기존 1건이었다. 상세 처리만 stub으로 대체해 캐시 선택 경로를 분리 검증했다.
- **반증 확인:** asset/mode/좌표/마커 분리는 이미 있다. 캐시 hit 뒤 재처리하는 로컬 필터는 가격·면적 필터이며 PRE 포함 여부를 다시 적용하지 않는다. 설정 dialog와 상위 apply_settings/runtime_settings에도 무효화가 없다. 새 엔진의 URL 생성은 캐시 hit 반환 뒤에는 실행되지 않는다.
- **호출/영향 범위:** CodeGraph 기준 settings → runtime kwargs/새 CrawlerThread → cache flow → filtered details/history/UI. APT 직접 수집에서 확정했으며 지도 모드도 같은 cache context 구성 방식을 공유한다.
- **권장 수정 방향:** upstream 결과 집합을 바꾸는 옵션과 schema/version을 캐시 fingerprint에 포함한다. fingerprint 없는 기존 엔트리의 호환 정책을 정한다. 단순 가격·면적 필터는 raw cache 후 적용이므로 무조건 키에 넣을 필요는 없다.
- **필요한 회귀 테스트:** PRE off→on, on→off와 재시작 후 persisted cache 로드에 대해 잘못된 캐시가 hit하지 않아야 한다. 동일 fingerprint 재조회는 계속 hit해야 한다.

## 5. Potential Functional Gaps

- **Confirmed Gap — 상세 hydration의 RSC 명시 처리 부재:** 현재 라이브 페이지에 `self.__next_f.push`가 있고 `_read_hydration_state`는 전통적인 window 전역 목록만 읽는다. 다만 HTML corpus·DOM·front-api 경로가 있으므로 상세 전체 실패라고 결론 내리지 않았다. RSC/streaming 상태를 포함한 현재 상세 표본의 필드별 추출률을 먼저 측정해야 한다.
- **Confirmed Gap — 분석 표본의 출처·완전성 추적 부족:** 스냅샷에 필터 fingerprint, raw_count, valid_count, failed_page, 원본/파서 버전이 없다. ISSUE-001/003 수정 시 함께 필요하다. 물리 DB 무결성 검사만으로는 통계 오류를 탐지할 수 없다.
- **Likely Gap — 목록 면적 정밀도:** 라이브 목록 139㎡와 상세 139.94㎡를 확인했다. 현재 정규화는 목록 `area1` 중심이며 상세 보강은 중개·기전세 중심이다. 소수 경계의 면적 필터·평당가에 차이가 생길 수 있다. 공급/전용 및 근사/정밀값을 구분하는 보완점이며, 목록 계약에 따른 정수 면적 자체를 파싱 버그로 분류하지 않는다.
- **Confirmed Gap — 핵심 안정화 테스트의 CI 누락:** `ci.yml`은 `NAVERLAND_SKIP_PLAYWRIGHT_TESTS=1`이며 core subset에 `test_playwright_engine_stabilization.py`, `test_response_capture_normalize.py`, `test_geo_markers_cortar.py`가 없다. 로컬 235개 성공이 기본 CI에서 같은 경로를 보호한다는 뜻은 아니다. 브라우저 없는 fake 기반 엔진 테스트도 함께 제외되는 현재 구성을 재검토할 필요가 있다.
- **추정 — 광고 표본과 실제 주택 표본의 통계 차이:** 라이브에 `sameAddrCnt` 및 반복 중개 광고가 존재하고, snapshots builder는 입력 행 가격을 그대로 집계한다. 광고별 평균이 목적이면 정상이다. 사용자에게 주택별 시세로 설명하려면 중복 정의·가중치를 먼저 합의해야 하며, 이를 확정적인 중복 저장 버그로 보지 않는다.
- **추정 — 시각/재실행 의미:** 예약은 로컬 datetime, DB 일자는 SQLite CURRENT_DATE를 사용한다. 한국 자정~09시의 일자 기준, 같은 날 재관측·소멸 지연, 중간 종료 후 재개 정책을 명시할 필요가 있다. 이번 감사에서 시간대 전체 경계를 재현하지 않았으므로 별도 확정 이슈는 만들지 않았다.

## 6. Documentation Mismatches

| 문서 설명 | 현재 구현/관측 | 영향 및 정정 방향 |
|---|---|---|
| README의 저장 위치 `data/real_estate.db` | `paths.py::get_db_path`는 `data/complexes.db`; frozen은 사용자 앱 데이터 기준 | 백업·장애 분석 시 잘못된 파일을 찾을 수 있음. 실행 형태별 실제 경로를 안내해야 함 |
| README의 모든 수집 데이터를 SQLite에 보관한다는 표현 | article_history는 최신 상태 갱신이며 목록의 모든 원본 필드·각 실행의 원본 표본을 누적 저장하지 않음. 캐시는 TTL 있는 별도 JSON | 완전한 데이터 아카이브와 가격 이력 기능의 범위를 구분해야 함 |
| 8월 사이트 조사 문서의 fin HTML 장애/404 중심 설명 | 이번 실제 매물 URL은 지도 layer에 정상 상세를 표시; RSC 상태 존재 | 문서는 당시 관측으로는 유효하지만 현재 장애 판정 기준으로 일반화하면 안 됨. 현재 정상/오류 표본을 함께 갱신해야 함 |
| 기존 PROJECT_AUDIT의 PyQt6 표기·스냅샷 종료 경합 | 현재 PySide6이며 완료 시 동기 스냅샷 저장과 워커 대기 메서드 존재 | 이전 결과는 현 상태를 대표하지 않아 이 보고서에서 교체함 |

README의 Playwright 기본/Selenium 보조, APT/VL 범위, CSV/Excel, 예약 수집 설명은 확인 범위에서 대체로 구현과 일치한다. Linux/macOS 정식 지원이 약속된 프로젝트로 해석하지 않았다.

## 7. Recommended Fix Plan

### Phase 1 — Immediate

1. **ISSUE-001:** 수집 결과에 complete/partial/failed 및 정상 빈 결과의 스키마 검증을 도입한다. partial/failed가 정상 캐시·소멸·전체 통계 교체로 흐르지 않도록 끝까지 전달한다.
2. **ISSUE-002:** 원본 관측 ID/존재 갱신을 필터와 분리한다. 변경 전까지 필터 활성 실행의 소멸 판정을 막는다.
3. **ISSUE-003:** 중단/부분/필터 실행이 기존 기준 통계를 덮어쓰지 않도록 저장 게이트를 둔다. 기존 집계 복구는 충분한 원본이 있는 경우에만 수행한다.

이 단계는 실제 수집 데이터의 신뢰도 회복이 목적이다. 이번 감사 중 기존 데이터 재분류·통계 재계산은 수행하지 않았다.

### Phase 2 — Stability

1. ISSUE-004의 PRE/cache fingerprint를 수정한다.
2. 429·5xx 재시도는 페이지별 진행 상태와 bounded backoff를 유지하고, 복구 실패 시 partial을 보존한다. 무조건 추가 재시도나 Selenium 전환이 데이터 완전성을 보장한다고 가정하지 않는다.
3. 목록/상세의 필수 필드·가격/면적 유효성·오류 코드·필드 결측률을 계측하고, invalid row를 정상 0값 데이터와 구분한다.
4. Windows 실행 환경의 Qt DLL 문제를 별도 깨끗한 환경에서 확인한다. 실행 경로 문서와 데이터 백업 경로를 정정한다.
5. 한국 일자 기준, 같은 날 소멸 지연 정책, 앱 중단 후 재수집·예약 catch-up 의미를 명시하고 경계 테스트를 추가한다.

### Phase 3 — Structural

1. 수집 결과를 타입 있는 실행 결과 모델로 만들고 API/DOM/캐시/fallback의 완료성 의미를 통일한다.
2. 실행 메타데이터·관측 표본·표시 결과·기준 통계의 책임을 분리한다. 필요에 따라 보관 기간이 있는 원본 또는 관측 이벤트 저장을 도입한다.
3. 실제 네이버 응답을 최소화·익명화한 계약 fixture를 유지하고, 브라우저 없는 핵심 엔진 테스트를 기본 CI에 포함한다.
4. 상세 parser는 현재 map layer/RSC/네트워크 JSON을 필드별로 검증하고 DOM fallback과의 선택 기준을 정한다. 작동하는 전체 경로를 근거 없이 재작성할 필요는 없다.

## 8. Test Recommendations

| 종류 | 입력/조건 | 기대 결과 |
|---|---|---|
| Unit / ISSUE-001 | 200 정상 목록 20건/more=true → 429, 500, invalid JSON, missing list | 앞선 데이터는 보존하되 complete=false; 마지막 성공 페이지·실패 원인 포함 |
| Unit / ISSUE-001 | `articleList=[]`, `articles=[]`, `{}`, `{'success':false}`, `articleList`의 비-list·비-dict 원소 | 명시적 유효 빈 목록만 confirmed_empty; 나머지는 schema/HTTP 오류 또는 invalid row로 분리 |
| Integration / ISSUE-001 | partial 응답을 실제 cache flow→loop→이력/스냅샷으로 전달 | 정상 positive/negative 캐시 생성 금지, run_status partial/failed, 소멸·기준 집계 교체 없음 |
| Regression / ISSUE-001 | 50번째 페이지에서도 more=true | truncated/partial이 최종 결과까지 유지되고 UI/이력에서 완전 완료와 구별됨 |
| Integration / ISSUE-002 | 어제 저장한 9억/15억, 오늘 둘 다 응답, 최대 10억 필터 | 표시 1건, 존재/active 2건; 15억을 소멸시키지 않음 |
| Regression / ISSUE-002 | 위 사례의 면적·월세 보증금·월세 필터, 캐시 hit, APT/VL 동일 ID | 존재 판정이 필터와 독립적이며 자산·거래 scope가 섞이지 않음 |
| Integration / ISSUE-003 | 같은 날 전체 2건 평균 12억 → 필터 1건 9억 → stopped | 기준 통계 평균 12억/count=2 유지. 부분 실행은 별도 기록 |
| Regression / ISSUE-003 | 전체 재완료 때 특정 평형 0건, 월세 deposit/rent, failed 타깃 공존 | 그룹 삭제/유지 정책 일관, 지표 분리, 실패 타깃 과거 통계 보존 |
| Unit/Integration / ISSUE-004 | PRE off→on→off, 동일 raw cache JSON 재로드 | 옵션이 달라지면 이전 조건 cache miss, 동일 fingerprint만 hit |
| E2E / 단지 | 격리 데이터 디렉터리, 소형 APT 단지, 매매/전세/월세, 전체 페이지 캡처 | API unique ID 수와 정규화 수/필터 수/DB 수가 설명 가능; 누락·중복·오류가 계수로 남음 |
| E2E / 지도 | 알려진 좌표와 cortarNo, APT/VL 각각 한 범위, 마커 전환 실패 주입 | API 마커 대체 경로 또는 명확한 incomplete; 미완료 영역의 소멸/기준 통계 갱신 없음 |
| E2E / 상세 | 정상 fin map layer, 과거 404, 늦은 hydration, 429 front-api | 정상 map을 오류로 오판하지 않고 매물 ID 일치 확인; 빈 상세가 기존 중개 정보를 지우지 않음 |
| Unit / 실응답 정규화 | `19억 5,000`, 139/114㎡ 목록, 139.94/114.88㎡ 상세, `2억/220` 월세 | 195000만원·20,000만원/220만원 분리; 공급/전용·근사/정밀의 출처 유지 |
| Concurrency | 수동/지도/예약 동시에 시작, 기존 crawl lock 소유자 있음 | 한 실행만 시작, 다른 실행이 타인의 락을 해제하지 않음; 종료 후 락 재획득 가능 |
| Concurrency / 복구 | SQLite locked·disk full, history bulk 실패 후 개별 실패, 종료 중 저장 | rollback 또는 명시적 저장 실패; 성공으로 숨기지 않음. 기존 원본 DB는 보존 |
| Platform-specific | 한글/공백/긴 경로, 읽기 전용 출력, Excel 열린 파일, CSV 한글 | 성공 파일은 완전한 UTF-8 BOM/Excel, 실패 시 기존 파일 보존과 명확한 오류 |
| Platform-specific | Windows x64/ARM64, Python 지원 버전의 깨끗한 환경 | PySide6/Fluent binding·DLL import 및 packaged Chromium 실행 확인. Linux/macOS는 지원할 경우 별도 수행 |
| Regression / 일자 | KST 00:00/08:59/09:00, DB UTC 경계, 같은 날 2회와 다음 날 실행 | 정의된 snapshot_date·last_seen·소멸 시점 일치; 예약 슬롯 중복 실행 없음 |
| Data Quality | 0/누락 가격·면적, 필수 ID 누락, 중복 광고, 상세 결측 | invalid/missing/duplicate 수를 구분하고 분석 포함 기준이 고정됨; 알 수 없는 값을 실제 0으로 오해하지 않음 |

대상 API가 429를 반환하면 계약 검증 실패로 기록하고 요청을 종료/완화한다. captcha나 차단을 우회하는 테스트를 요구하지 않는다. 모든 쓰기 테스트는 임시 DB·설정·출력 경로에서 수행한다.

## 9. Final Assessment

| 항목 | 평가 | 근거 |
|---|---|---|
| Functional Correctness | **Needs Work** | 목록 계약은 현재 표본과 맞지만 수집 완전성·필터·소멸 의미가 어긋남 |
| Runtime Stability | **Acceptable** | 엔진/캐시/DB/재시도 테스트 통과, 종료·락 방어 존재. GUI 런타임 전체는 환경 제약으로 미검증 |
| Data Integrity | **High Risk** | 임시 DB에서 정상 매물의 소멸 오판과 기준 가격 집계 덮어쓰기 재현 |
| Error Resilience | **Needs Work** | 429·일부 오류 방어는 있으나 중간 실패/오류 JSON을 성공으로 처리할 수 있음 |
| Cross-platform Robustness | **Needs Work** | Windows 목표와 경로 분기 존재; 로컬 Qt DLL 문제 및 다른 OS/배포본 미검증으로 신뢰 근거 제한 |
| Test Confidence | **Needs Work** | 235개 통과는 강점. 현재 이슈의 후속 데이터 영향·GUI E2E·실사이트 완전 수집·기본 CI 커버리지는 부족 |

**실제로 먼저 수정할 문제 3개:**

1. **ISSUE-001:** 중간 실패·오류 응답을 정상 완료/정상 빈 결과로 승격하지 않도록 한다.
2. **ISSUE-002:** 필터에서 제외된 존재 매물이 소멸하지 않도록 관측 ID와 표시 필터를 분리한다.
3. **ISSUE-003:** 불완전·중단·필터 실행이 기존 기준 가격 스냅샷을 덮어쓰지 않도록 한다.
