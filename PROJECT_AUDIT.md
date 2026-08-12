# Project Audit

**감사 기준일**: 2026-08-12  
**조치 동기화**: 2026-08-12 (감사 권고 1–3단계 + 잔여 개편 스윕 반영)  
**범위**: 기능 구현 관점 — 사이트 드리프트·상세 degrade·geo·설정·live-smoke  
**방법**: `README.md`·로컬 `Claude.md` 정독, CodeGraph MCP, 구현·pytest 교차  
**참고**: 루트 에이전트 전용 문서(`CLAUDE.md` 등)는 저장소 **미추적**. 제품 문서는 `README.md`, `docs/NAVER_LAND_SURVEY_*.md`, `update_history.md`, 본 파일.

---

## 1. Executive Summary

Naverland Scrapper Pro Plus v15.0은 **PyQt6 + Fluent UI + Playwright + SQLite** 기반 네이버(Npay) 부동산 수집 앱이다.

| 기능 축 | 구현 요지 | 상태 (조치 후) |
|---------|-----------|----------------|
| Article API multipage + 429 완화 | `article_api.py` + engine fast path | **양호** |
| 목록 메타·중개명·주소·직거래 | `normalize_article_payload` + 컬럼/export/카드 | **반영** |
| geo `a`/`b`/`e` + markers API | `site_contract` + scan/markers | **반영** |
| fin HTML degrade / front-api-only | warmup·entry·prefer_front_api_only·세션 워밍 | **반영** |
| 상세 통계·워커 제한·순서 보존 | detail_enrichment + finish 로그 | **반영** |
| rebind 가드 | `test_playwright_engine_globals` | **반영** |
| live-smoke 계약 프로브 | host-health / geo-contract / realtorName | **반영** |
| 전역 수집 락 | acquire/release + 종료 시 force_release | **양호** |

**전체 위험도: Medium** (비공식 API·fin 세션 환경 의존은 구조적으로 남음)

| 영역 | 이전 | 조치 후 |
|------|------|---------|
| fin/front-api | High | **Medium** — API-only·워밍·429 축소·list_meta |
| mixin rebind | High | **Low** — globals 가드 테스트 |
| 상세 워커×429 | High | **Medium** — 자동 축소·조기 중단 |
| list-partial 통계 | Medium | **완화** |
| 목록 필드 UI | Medium | **완화** |
| geo 마커 DOM | Medium | **완화** (직접 API 폴백) |
| 문서 드리프트 | Medium | **완화** |
| 비공식 API | Medium | **잔존** (본질) |
| crawl_lock 고착 | Low | **완화** (종료 force_release) |

**검증 스냅샷 (조치 후)**

- UI 제외 pytest: **250+ passed** (환경별 UI 스위트는 PySide6 혼합 시 실패 가능)
- 의도적 비범위: OPST 전면, article_history 스키마 확장, PRE 기본 on

---

## 2. Project Understanding

### 목적 (README)

- 네이버 부동산 매물 **자동 수집** (단지 / 지도)
- **가격 이력·알림·소멸 추적**
- 테이블·카드·대시보드, 로컬 SQLite (`data/`, 외부 전송 없음)
- 상세 보강(중개·기전세) 옵션, 전역 수집 락

### 개발 규칙 (Claude.md / 로컬 AI Context)

- 공개 import·facade 유지, 구현은 `*_parts/`
- **mixin 메서드는 `mixin_rebind` 경로에 포함**되고, 자유 변수는 facade `globals`에 있어야 함
- 수집 안정성 > fast path; API 실패 시 response-capture fallback
- DB migration은 데이터 보존 기본

### 아키텍처 (CodeGraph)

```
app_entry.py
  ├─ --preflight / --live-smoke
  └─ GUI → src/ui/app.py (Fluent Navigation + TabCompatBridge)
        ├─ 매물 수집 / 지도로 찾기
        ├─ 보관함 / 분석 / 예약
        └─ 설정 (기본·고급)

CrawlerThread
  └─ PlaywrightCrawlerEngine  (rebind_inherited_methods → playwright_engine.globals)
        ├─ complex: entry plan → article_api fast path
        │            → response_capture fallback → detail_enrichment
        └─ geo: build_geo_map_url(b=) → marker capture → per-complex crawl

services:
  site_contract.py     hosts + geo/complex/front-api URL 계약
  article_api.py       목록 multipage 순수 함수
  response_capture.py  normalize_article_payload / markers
  detail_fetcher.py    fin/m 네비 + front-api 보충 + apply_mobile_detail

ComplexDatabase (SQLite facade)
SettingsManager → data/settings.json (sanitize + atomic write)
crawl_lock      → complex / geo / schedule 상호 배제
```

### 주요 실행 흐름 (최근 기능 중심)

1. **단지 수집**: 락 획득 → 단지 목록·거래유형 검증 → Article API multipage(Authorization 캡처 필요) → 실패 시 브라우저 캡처 → (옵션) 상세 워커 풀 → 이력/스냅샷/UI.
2. **지도 수집**: 락 획득 → `a`+`b`+`e` 맵 URL → DOM 매물 마커 전환 → `single-markers` 캡처 → 단지별 complex 경로.
3. **목록 정규화**: 가격·면적·확인일·동·`realtorName`→`부동산상호` 등 **메모리 dict** (확장 메타 다수는 **DB 미저장**).
4. **상세**: fin 우선 → 404 시 front-api 시도 → m.land 연쇄 축소 → empty detail이 목록 중개명을 지우지 않음.
5. **완료 로그**: api_hit/fallback/detail_skip·cap·fail 요약 (`finish.py`).

### CodeGraph blast radius (핵심 심볼)

| 심볼 | 호출/영향 | 테스트 |
|------|-----------|--------|
| `build_geo_map_url` | geo scan, engine rebind | `test_site_contract` |
| `build_complex_page_url` | response_capture, selenium_flow | `test_site_contract` |
| `normalize_article_payload` | article_api / capture / enrichment | `test_response_capture_normalize` |
| `fetch_mobile_article_detail` / `apply_mobile_detail` | detail_enrichment, live-smoke | `test_detail_fetcher` |
| `collection_runtime_kwargs` | complex·geo start | crawl_lock 관련 간접 |
| `rebind_inherited_methods` | engine/crawler/db/UI facades | 전용 테스트 약함 |

---

## 3. High-Risk Issues

### H-1. mixin rebind: 신규 import를 facade globals에 넣지 않으면 NameError

* **위치**: `src/utils/mixin_rebind.py` `rebind_inherited_methods`; `src/core/engines/playwright_engine.py` 모듈 하단 rebind; geo/complex mixin 메서드 본문
* **문제**: mixin 메서드는 **파사드 모듈 `globals()`로 재바인딩**된다. `site_contract` 심볼을 mixin 파일에만 import하고 engine에 누락하면 런타임 `NameError`가 난다. 08-12 작업 중 `HOST_NEW` / `build_geo_map_url` 누락으로 안정화 테스트 다수 실패가 실제로 재현되었다.
* **영향**: 수집 전면 중단, CI/로컬 회귀. 향후 Phase 2+ 심볼 추가 시 동일 패턴 재발 가능.
* **근거**: CodeGraph + `playwright_engine.py` rebind 호출; 실패 로그 `NameError: name 'HOST_NEW' is not defined`. Claude.md “mixin rebind 경로 포함” 규칙과 직결.
* **권장 수정 방향**: (1) rebind 대상 자유 변수 체크리스트/테스트 (import 누락 시 fail), (2) 또는 mixin 내부 **함수 로컬 import만** 사용하도록 정책 통일, (3) `PlaywrightArticleApiMixin` 등 미사용 import 정리.
* **우선순위**: **High** (구조적 재발 위험)

### H-2. fin HTML 붕괴 + front-api 429 → 상세 보강 사실상 실패 가능

* **위치**: `src/core/services/detail_fetcher.py` (`fetch_mobile_article_detail`, `_supplement_front_api_artifacts`); 라이브 프로브 2026-08-12
* **문제**: fin `/articles/{id}` 등이 pstatic 404로 떨어지고, 동일 세션에서 front-api cold 호출이 `TOO_MANY_REQUESTS`를 반환할 수 있다. 목록 `realtorName`은 중개소명만 보완하고 **전화·기전세·갭은 여전히 상세 성공에 의존**한다.
* **영향**: 설정 기본값이 “상세 조회 켬”이어도 실환경에서 필드가 비고, 사용자는 버그로 오인. 갭 분석·알림 품질 저하.
* **근거**: 프로브 결과 + README “중개사·기전세 상세 조회” 기본 on; `gap_analysis.enrich_gap_fields`는 `기전세금(원)>0`일 때만 갭 계산.
* **권장 수정 방향**: list-first 기본 UX 문구; front-api-only 모드 + 세션 워밍; 상세 실패 시 완료 로그에 `detail_host_unreachable` 집계; 기전세 대체 소스 조사(Phase 2).
* **우선순위**: **High**

### H-3. 상세 워커 병렬이 front-api rate limit을 악화

* **위치**: `PlaywrightDetailEnrichmentMixin._enrich_items_with_mobile_details` (`detail_enrichment.py`); 설정 `playwright_detail_workers` 기본 12 (`managers.py` clamp 1–16)
* **문제**: 매물마다 agent/basicInfo를 워커 N개가 동시에 요청한다. fin 세션이 약한 상태에서 **429 연쇄**가 나기 쉽다. 429 시 해당 매물 루프 조기 중단은 있으나, 워커 간 전역 백오프/공유 쿨다운은 없다.
* **영향**: 대형 단지 상세 on 시 시간 낭비 + 전 매물 상세 실패 확률 증가.
* **근거**: CodeGraph 호출 경로; `_supplement_front_api_artifacts` 429 break는 **요청 컨텍스트 1회 루프 단위**; 워커 간 공유 상태 없음.
* **권장 수정 방향**: fin 불안정 시 워커 1–2로 자동 축소; 전역 429 쿨다운; 또는 front-api 비활성 시 네비 스킵(list-only).
* **우선순위**: **High**

### H-4. list-partial과 detail_fail 통계 불일치

* **위치**: `detail_enrichment.py` `_fetch_one`; `apply_mobile_detail` (list 중개명 시 `parse_state` failed→partial)
* **문제**: 성공 판정은 `apply_mobile_detail` **이전**의 `detail_meta.parse_state`로 한다. 목록에 `부동산상호`가 있고 detail이 failed여도 `detail_fail_count`가 증가한 뒤, apply가 partial로 고친다. 완료 로그의detail_fail`이 실제 사용자 체감(중개명 있음)과 어긋난다.
* **영향**: 진단 오해, “상세 실패 N건” 과대 보고.
* **근거**: `if detail and parse_state != "failed": detail_success = True` 후 `return apply_mobile_detail(...)`.
* **권장 수정 방향**: apply 이후 메타로 성공/partial/list_meta 재분류; `detail_list_meta_only_count` 통계 추가; finish 로그에 반영.
* **우선순위**: **Medium**

### H-5. 신규 목록 필드가 결과 컬럼·export 카탈로그에 없음

* **위치**: `response_capture.normalize_article_payload` (`동일주소최고가`, `동일주소최저가`, `확인유형`); `src/utils/result_columns.py` `RESULT_EXTRA_COLUMN_DEFS` / `EXPORT_META_COLUMN_KEYS`
* **문제**: 수집 dict에는 들어가나 표시 항목 메뉴·설정 화이트리스트·export 메타 키에 **미등록**. 사용자는 UI에서 켤 수 없고, 엑셀 템플릿 기본 경로에도 없다.
* **영향**: “추가한 기능”이 수집만 되고 제품 기능으로 체감되지 않음.
* **근거**: CodeGraph/grep — `result_columns`에 confirm/building/area/same_addr/cp/broker만 존재.
* **권장 수정 방향**: 컬럼 def·export 키·카드 메타 옵션 추가(기본 숨김 유지); sanitize 화이트리스트 동기화.
* **우선순위**: **Medium**

### H-6. geo 마커 전환의 DOM 취약성 (b= 정렬 이후 잔존)

* **위치**: `geo_mode_parts/markers.py` `_switch_to_listing_markers`; `scan.py` 실패 시 `_mark_geo_incomplete`
* **문제**: 거래유형 쿼리는 `b=`로 맞춰졌으나, 마커 수집은 여전히 “매물/상세매물검색” 등 **UI 클릭**에 의존. 카피·레이아웃 변경 시 `marker_switch_fail` → geo incomplete → 안전 모드에서 등록/이력 스킵 가능.
* **영향**: 지도 탐색 0단지 또는 incomplete 안전 스킵.
* **근거**: CodeGraph markers 핸들러는 `single-markers` URL substring 매칭; 직접 API 호출 경로는 미구현 (Phase 3 계획).
* **권장 수정 방향**: viewport bounds + `single-markers/2.0` request fast path; 실패 시만 DOM 스윕.
* **우선순위**: **Medium**

### H-7. 상세 결과 리스트 순서 비결정성

* **위치**: `detail_enrichment.py` 워커 `result.append(await _fetch_one(item))`
* **문제**: 여러 워커가 완료 순으로 동일 list에 append → **입력 순서와 불일치** 가능. (asyncio 단일 스레드라 데이터 레이스는 드물지만 순서 race는 발생.)
* **영향**: UI 배치·“같은 매물 묶기” 체감 순서 흔들림; 재현성 저하.
* **근거**: 코드 상 index 기반 슬롯 없음.
* **권장 수정 방향**: 인덱스 배열에 기록 후 정렬, 또는 세마포어+순차 병합.
* **우선순위**: **Medium** (Low로 볼 여지 있으나 기능 일관성 이슈)

### H-8. README / Claude 문서와 구현 불일치

* **위치**: `README.md` 문서 표; 로컬 `Claude.md` 검증 절; 구 `PROJECT_AUDIT`의 328 passed
* **문제**:
  1. README 문서 링크에 **`NAVER_LAND_SURVEY_2026-08-12.md` 없음** (08-04만).
  2. Claude/README 계열 “pytest 328 passed”는 08-05 기준; 08-12 이후 테스트 파일 추가·환경 UI 실패 가능.
  3. README는 상세 보강을 핵심 기능으로 소개하나, 실사이트 fin 붕괴 시 **기본 경로 품질 저하** 설명이 부족.
* **영향**: 운영자·에이전트가 잘못된 검증 기준/사이트 상태를 신뢰.
* **근거**: 파일 내용 대조 + update_history 08-12 항목.
* **권장 수정 방향**: README 문서 표·주의 문구 갱신; Claude 검증 수치 날짜 태깅; live-smoke 기대치에 host health.
* **우선순위**: **Medium**

### H-9. 광범위 `except Exception` (의도적 폴백, 관측 비용)

* **위치**: Playwright runtime, detail_fetcher, navigation, geo marker 클릭 루프 등
* **문제**: 네트워크/파싱 오류가 삼켜져 원인 분류가 어렵다. 폴백 설계상 일부는 의도적.
* **영향**: 현장 “0건/상세 공백” 디버깅 비용.
* **근거**: CodeGraph/기존 감사 동일 패턴; finish 요약은 일부만 완화.
* **권장 수정 방향**: 실패 reason 카운터 확장 (`detail_host_unreachable`, `front_api_429`); 로그 레벨 정책.
* **우선순위**: **Medium** (Low~Medium, 신규 기능에서 더 중요해짐)

### H-10. 비공식 내부 API 사용 (보안·약관·운영)

* **위치**: `new.land` `/api/articles/*`, `fin.land` `/front-api/*`
* **문제**: 비공식 엔드포인트·Authorization 헤더 캡처. 개인정보(전화) 수집 가능. 로컬 저장이나 배포·약관 리스크는 제품 정책 문제.
* **영향**: 차단·법적/약관 이슈; rate limit.
* **근거**: 아키텍처 본질 + survey 문서 경고.
* **권장 수정 방향**: README/가이드에 제한·속도 권장 유지; 과도한 병렬 완화(H-3); 민감 필드 export 기본 off 유지.
* **우선순위**: **Medium** (제품 정책) / 기술 완화은 High와 연계

### H-11. crawl_lock 소유권·정리 (잔여 리스크 Low)

* **위치**: `crawl_lock.py`; `start_stop.py` / `geo_crawler_tab.py` / `finish.py`
* **문제**: 검증 실패 시 release, `finished` finally에서 release — 양호. 스레드가 시그널 없이 강제 종료되면 락이 남을 수 **추정** (정상 QThread finished 경로에서는 해제).
* **영향**: 드물게 “다른 수집이 진행 중” 고착.
* **근거**: release는 owner 매칭; force_release는 테스트·유지보수용.
* **권장 수정 방향**: 앱 shutdown/maintenance에서 force_release 확인; 타임아웃 워치독(추정 필요 시).
* **우선순위**: **Low**

---

## 4. Potential Functional Gaps

확실하지 않은 항목은 **추정**으로 표시한다.

1. **front-api-only / fin 세션 복구** — Phase 2 미구현. 현재는 HTML 1회 시도 후 cold API.
2. **마커 직접 API** — Phase 3 미구현. UI 클릭 의존 잔존.
3. **complexes/overview name_lookup** — overview API는 라이브에서 200 확인됐으나 파서 주경로 미연결 (**추정**: 이름 조회 실패 시 품질 이득 가능).
4. **동일주소 최고/최저가·확인유형 UI** — 수집만 됨 (H-5).
5. **부동산상호 기본 테이블 컬럼** — extra `broker_office`로만 노출; 기본 18컬럼에 없을 수 있어 상세 off+extra 숨김 시 중개명이 안 보임 (**추정**: 테이블 기본 스키마 확인 필요 — `broker_office`는 extra id).
6. **playwright_allow_fin_m_entry_plans** — 코드 플래그만 있고 설정 UI/sanitize 기본값 문서 없음. 사실상 항상 off.
7. **live-smoke host health** — `b=` 보존, fin 404, list `realtorName` 검증 미확장 (**추정**: 회귀 조기 경보 약화).
8. **DB에 메타·중개명 미저장** — 의도적 경량 원칙이나, 재실행 없이 이력 조회 시 공백 (**추정**: 제품 요구에 따라 갭).
9. **OPST/기타 자산·PRE 기본** — 의도적 비범위.
10. **UI 테스트 환경 PySide6 충돌** — 전체 pytest 그린을 막는 환경 이슈 가능; 기능 코드 회귀와 분리 필요 (**추정**).

---

## 5. Recommended Fix Plan

### 1단계 — 즉시 (안정성·진단)

1. **mixin rebind 가드**: engine globals 필수 심볼 단위 테스트 또는 lint; 신규 site_contract 심볼 누락 방지 (H-1).
2. **상세 통계 정합**: list-partial / host_unreachable / front_api_429 카운터 + finish 로그 (H-2, H-4, H-9).
3. **fin 불안정 시 상세 부하 축소**: 워커 자동 1–2, 또는 연속 429 시 단지 단위 detail 중단 (H-3).
4. **문서 동기화**: README에 08-12 survey 링크; 상세 기능 한계 문구; 검증 수치 날짜화 (H-8).

### 2단계 — 안정성 개선

1. front-api-only 경로 + 세션 워밍 실험 (성공 시에만 채택).
2. geo `single-markers` 직접 호출 fallback (H-6).
3. 상세 결과 **입력 순서 보존** (H-7).
4. live-smoke: host health, geo `b`, list realtorName 프로브.

### 3단계 — 구조·제품 완성도

1. `result_columns` / export / 카드에 신규 메타 필드 등록 (H-5).
2. overview API name_lookup.
3. rebind-free 설계 검토(서비스 계층 호출만 남기고 mixin 자유 변수 최소화).
4. (선택) 메타 DB 저장 여부 제품 결정.

---

## 6. Test Recommendations

| 우선 | 테스트 | 목적 |
|------|--------|------|
| P0 | `test_playwright_engine_globals_include_site_contract_symbols` | rebind NameError 회귀 방지 (H-1) |
| P0 | `test_apply_mobile_detail` + enrichment stats: list realtor + failed detail → partial **및 fail 카운트 정책** | H-4 |
| P0 | `test_fetch_mobile_article_detail` fin 404 + agent 429: host_unreachable 메타, m 재시도 횟수 상한 | H-2 |
| P1 | detail workers 모의: 동시 front-api 호출 수 / 429 시 조기 중단 | H-3 |
| P1 | `normalize` + `result_columns`: 신규 필드 id 화이트리스트 (필드 추가 시) | H-5 |
| P1 | geo URL 빌더: `b` 존재·`tradeTypes` 부재 (이미 `test_site_contract` — 유지) | 회귀 |
| P1 | live-smoke 확장 픽스처/플래그: fin HTML status, article list realtorName | 사이트 드리프트 |
| P2 | detail enrichment **출력 순서 == 입력 순서** | H-7 |
| P2 | crawl_lock: start 실패 전 분기 release, finished finally (기존 보강) | H-11 |
| P2 | UI 스위트: PyQt6 전용 venv에서 분리 실행 문서화 | 환경 이슈 |

**권장 로컬 검증 커맨드**

```powershell
python -m pytest -q tests/test_site_contract.py tests/test_response_capture_normalize.py tests/test_detail_fetcher.py tests/test_article_api.py tests/test_playwright_engine_stabilization.py tests/test_crawl_lock.py tests/test_finish_summary.py
# UI 제외 전체
python -m pytest -q --ignore=tests/test_ui_wiring.py --ignore=tests/test_ui_runtime_smoke.py --ignore=tests/test_geo_tab_wiring.py
# 사이트 회귀 (네트워크)
python app_entry.py --live-smoke --smoke-headless --live-smoke-detail-fields --smoke-json-log logs/live-smoke-audit.json
```

---

## 부록 A. 최근 추가 기능 매핑

| 기능 | 주요 파일 | 감사 이슈 |
|------|-----------|-----------|
| site_contract | `services/site_contract.py`, engine imports | H-1 |
| geo `b=` | `geo_mode_parts/scan.py` | H-6 잔존 |
| 목록 realtorName | `response_capture.py` | H-4, H-5 |
| fin degrade / entry plan | `contexts.py`, `navigation.py`, `detail_fetcher.py` | H-2, H-3 |
| 수집 락 | `crawl_lock.py`, start/geo/finish | H-11 |
| 설정 옵션 | `managers.collection_runtime_kwargs` | PRE/detail/delay 양호; 신규 플래그 UI 없음 |

## 부록 B. 이전 감사 대비

| 이전(08-04/05) | 현재(08-12) |
|----------------|-------------|
| 동시 수집 락 미비 | **완화됨** |
| 표시 항목 무조건 저장 | **완화됨** (변경 시 저장) |
| fin 상세 갭 인지 | **악화 관측** (HTML 404) → H-2/H-3 |
| tradeTypes geo | **수정됨** (`b=`) |
| 문서 Fluent 동기화 | **08-12 survey README 미링크** |

---

*감사 작성: 2026-08-12 · 코드 수정 없음(감사 리포트만) · CodeGraph + README/Claude + 소스 대조*
