# Project Audit

**감사 기준일**: 2026-08-04 (UI 동기화 갱신: 2026-08-05)  
**범위**: 기능 구현 관점 (최근 네이버 사이트 호환·옵션·Fluent UI 포함)  
**방법**: `README.md` 정독, CodeGraph MCP 호출 경로/blast radius, 보조적 파일·테스트 확인  
**참고**: 루트 에이전트 전용 문서(`CLAUDE.md` 등)는 **저장소 미추적** (`.gitignore`). 규칙·제품 문서는 `README.md`, `docs/NAVER_LAND_SURVEY_2026-08-04.md`, `update_history.md`, 본 파일을 교차함.

---

## 1. Executive Summary

Naverland Scrapper Pro Plus는 **PyQt6 + PyQt6-Fluent-Widgets 데스크톱 UI + Playwright 수집 엔진 + SQLite 로컬 DB** 구조의 네이버(Npay) 부동산 매물 수집 앱입니다. Article API 페이지네이션, front-api 상세 보강, 수집/표시 옵션, **Fluent 좌측 네비 + 기본/고급 설정**, 결과 확장 컬럼이 반영되어 있습니다. 단위 테스트는 **328 passed** 수준입니다.

**전체 위험도: Medium (일부 항목 완화됨)**

| 영역 | 위험도 | 한 줄 요약 |
|------|--------|------------|
| 수집 ↔ 지도 동시 실행 | **완화됨** | 전역 `crawl_lock`으로 상호 배제 |
| 상세 보강 끄기/상한 UX | **Medium** | 옵션은 동작하나, 상한 초과 매물은 상세 없이 통과(완료 로그에 요약 있음) |
| 「표시 항목」/더보기 메뉴 | **Low~Medium** | 토글 시 저장 정책 정리됨; 결과 툴바는 overflow「더보기」 |
| 광범위 `except Exception` | **Medium** | 폴백 설계상 의도 있으나, 실패 원인 분류·재현이 어려움 |
| README vs 실제 설정 | **완화됨** | 기본/고급 설정 표·네비 IA 반영 (2026-08-05) |
| 비공식 Naver API / 429 | **Medium** | 구조적 리스크; 완화 옵션은 있으나 차단 시 수집 불완전 가능 |
| Settings 싱글톤 | **Low~Medium** | 테스트 격리 API 존재; 프로덕션 단일 프로세스에서는 실무 리스크 낮음 |
| Fluent/GPL UI 라이브러리 | **Low** | `PyQt6-Fluent-Widgets` GPLv3(비상업); README 고지 |

**조치 상태 (2026-08-04 후속 + 2026-08-05 UI)**: 전역 수집 락, 완료 로그 상세 skip/상한/API 실패 요약, 표시 항목 토글 저장, 예약 busy+락 가드, `ui_labels` 상수, Fluent 네비·설정 기본/고급, 수집/지도 UX 단순화. `docs/`·spec·`.gitignore`·README 동기화. 검증: `pytest` **328 passed**.

---

## 2. Project Understanding

### 목적 (README)

- 네이버 부동산 매물 **자동 수집**
- **가격 이력·알림·소멸 추적**
- 테이블/카드 결과, 대시보드, 즐겨찾기, 중복 묶기
- 데이터는 로컬 SQLite (`data/`), 외부 전송 없음

### 아키텍처 (CodeGraph + 모듈 구조)

```
app_entry.py
  ├─ --preflight / --live-smoke
  └─ GUI → src/main.py → src/ui/app.py (RealEstateApp)
        ├─ NavigationInterface (src/ui/fluent/) + TabCompatBridge
        │     수집: 매물 수집 / 지도로 찾기
        │     보관함: 내 단지 / 단지 묶음 / 즐겨찾기
        │     분석: 대시보드 / 가격 통계 / 수집 기록
        │     자동화: 예약 수집
        │     하단: 가이드 · 설정
        └─ 설정 다이얼로그 (기본 / 고급 progressive disclosure)

CrawlerThread (QThread, state_runtime + crawler mixins)
  └─ PlaywrightCrawlerEngine
        ├─ complex: article_api fast path → response_capture fallback → detail_enrichment
        └─ geo: marker scan → per-complex crawl

ComplexDatabase (SQLite facade + database_parts/*)
SettingsManager 싱글톤 → data/settings.json (atomic write)
```

### 주요 실행 흐름

1. **단지 수집**: UI가 단지 목록·거래유형·필터 검증 → `CrawlerThread(complex)` 시작 → Article API multi-page 또는 브라우저 캡처 → (옵션) 상세 front-api → 이력/스냅샷/UI 배치 반영.
2. **지도 수집**: 좌표·범위·주택 종류 검증 → `CrawlerThread(geo_sweep)` → 마커 스캔 후 단지별 수집.
3. **옵션 배선**: `collection_runtime_kwargs(settings)` → thread 속성  
   `include_pre_sale_rights`, `detail_enrichment_*`, `detail_front_api_enabled`, `article_api_page_delay_ms`.
4. **결과 표시**: `collected_data` 메모리 리스트 + 테이블/카드; 확장 컬럼은 **DB 미저장**.

### 최근 기능 (감사 대상 핵심)

| 기능 | 구현 위치 | 기본값(경량) |
|------|-----------|--------------|
| front-api 상세 보충 | `detail_fetcher.py` | on |
| 상세 on/off·단지당 상한 | `detail_enrichment.py` + settings | on / 0(무제한) |
| PRE 분양권 | `article_api` + geo `a=` | off |
| 목록 메타 필드 | `normalize_article_payload` | dict only |
| 확장 컬럼 UI | 테이블 18+ 슬롯, 기본 숨김 | 빈 목록 |
| 설정 UI (기본/고급) | `dialogs/settings.py` | 일상 옵션 / 엔진·타임아웃 분리 |

---

## 3. High-Risk Issues

### H-1. 매물 수집 탭과 지도 탭 동시 크롤 가능 (공유 DB)

* **위치**: `CrawlerTabStartStopMixin.start_crawling`, `GeoCrawlerTab.start_crawling`  
  (`src/ui/widgets/crawler_tab_parts/crawl_control_parts/start_stop.py`, `src/ui/widgets/geo_crawler_tab.py`)
* **문제**: 각 탭은 **자기 `crawler_thread`만** 실행 중인지 검사합니다. 다른 탭 스레드는 보지 않습니다. 두 탭은 동일 `self.db`(ComplexDatabase)를 공유합니다.
* **영향**: 동시 실행 시 SQLite 쓰기 경합, 이력/스냅샷 꼬임, UI 통계 혼선, “이미 실행 중” 가드 우회.
* **근거**: CodeGraph blast — 두 start 경로 독립; `isRunning()` 은 인스턴스 로컬. app은 동일 DB 인스턴스를 양 탭에 주입.
* **권장 수정 방향**: 앱 전역 “수집 락”(한 번에 하나의 crawl), 또는 시작 시 다른 탭 `shutdown_crawl`/경고 후 거부.
* **우선순위**: **High**

### H-2. 「표시 항목」메뉴가 닫힐 때 설정을 무조건 저장

* **위치**: `CrawlerTabTableRowRenderMixin._open_extra_columns_menu`  
  (`src/ui/widgets/crawler_tab_parts/result_render_parts/table_rows.py`)
* **문제**: `QMenu.exec` 후 체크 상태를 모아 `settings.set("result_extra_columns", selected)` 를 **항상** 호출합니다. 바깥 클릭으로 닫아도 저장됩니다. 의도적 “적용” UX가 아닙니다.
* **영향**: 실수로 체크만 바꾼 뒤 메뉴를 닫으면 설정 파일이 바뀌고, 다음 실행/다른 화면에 반영.
* **근거**: 메뉴 종료 후 무조건 `settings.set` 호출 코드.
* **권장 수정 방향**: “적용” 액션 분리, 또는 변경 시에만 저장, 또는 체크 토글 시점에만 set.
* **우선순위**: **Medium** (데이터 손실은 아니나 설정 오염)

### H-3. 상세 상한/비활성 시 사용자 피드백 부족

* **위치**: `PlaywrightDetailEnrichmentMixin._process_raw_items_with_filtered_details`  
  (`detail_enrichment.py`)
* **문제**: `detail_enrichment_enabled=false` 또는 `max_per_complex` 초과 시 상세 없이 passthrough 하고 `detail_fetch_skipped_count`만 증가. 로그/UI 요약에 잘 안 드러날 수 있음.
* **영향**: 중개·갭 필드가 비어 “버그”로 오인; 상한 때문에 일부만 상세인 줄 모름.
* **근거**: skip 분기 + stats 카운터만 증가, 완료 메시지 연계는 finish 경로에 선택적.
* **권장 수정 방향**: 수집 완료 로그에 skip/상한 건수 명시; 설정 툴팁과 통계 카드 연동.
* **우선순위**: **Medium**

### H-4. 광범위 예외 삼키기 (폴백 경로)

* **위치**: Playwright runtime, detail_fetcher, parser browser_fallback, UI start/finish 등 다수 `except Exception`
* **문제**: 네트워크/파싱/UI 오류가 단일 경로로 삼켜져 원인 분류가 어렵습니다. 일부는 의도적 폴백입니다.
* **영향**: 현장 장애 시 “왜 0건인지” 재현 비용 증가; 간헐적 버그 은폐.
* **근거**: core/ui 전반 다수 Exception 캐치 패턴 (grep·CodeGraph 탐색).
* **권장 수정 방향**: 수집 경로 핵심 구간만 예외 타입 분리 + 구조화 통계 키 유지 확대.
* **우선순위**: **Medium**

### H-5. 비공식 API·429·상세 SPA 불안정 (외부 의존)

* **위치**: `article_api.py`, `detail_fetcher.py`, live-smoke 프로브
* **문제**: Naver 내부 API/SPA 변경 및 rate limit. 완화(delay, front-api, fallback)는 있으나 완전 해결 불가.
* **영향**: 수집 불완전, 상세 partial/fail, smoke 간헐 실패.
* **근거**: 조사 문서·live-smoke 이력; 429 처리 분기 존재.
* **권장 수정 방향**: live-smoke를 CI 게이트로 유지; 실패 시 “부분 성공” UX; 사용자 가이드에 차단 대응 명시.
* **우선순위**: **Medium** (외부 요인, 앱 내부 High는 아님)

### H-6. README 설명과 구현 불일치

* **위치**: `README.md` 「주요 설정」표 vs `DEFAULT_SETTINGS` / 설정 UI
* **문제**: README는 엔진·대기시간·중복·대시보드 지연 정도만 언급. 실제는 PRE, 상세 보강, 페이지 간격, 표시 항목, 워커 상한 등 다수 옵션 존재. “Python 3.9 이상” vs 로컬 3.13/3.14 캐시 혼재.
* **영향**: 사용자·기여자가 기능을 못 찾거나 환경 오해.
* **근거**: README 표와 managers DEFAULT_SETTINGS 비교.
* **권장 수정 방향**: README 설정 절 갱신 + 조사 문서 링크 유지 (이미 일부 있음).
* **우선순위**: **Medium**

### H-7. 테마/엔진 콤보 값이 표시 문자열과 분리됨 (회귀 주의)

* **위치**: `SettingsDialog` 테마·엔진 콤보 (`addItem(label, data)` + `currentData()`)
* **문제**: 최근 사용자 친화 라벨 도입 후, 다른 코드가 `currentText()`로 theme/engine을 읽으면 깨짐. 현재 save는 `currentData()` 사용.
* **영향**: 추후 패치 시 회귀 가능; 기존 테스트가 text를 가정하면 실패.
* **근거**: settings `_load`/`_save` 구현.
* **권장 수정 방향**: 테마/엔진은 data 역할만 문서화; 테스트로 data round-trip 고정.
* **우선순위**: **Low**

### H-8. (이전 감사 대비) Article API page=1 전용 — **완화됨**

* **위치**: `services/article_api.py`, complex `article_api` mixin
* **문제**: 과거 fast path 1페이지만 수집.
* **근거**: multi-page 루프·`isMoreData`·supplement 존재; 단위·live-smoke 검증.
* **우선순위**: **Low** (잔여: 페이지 cap 50, 429 시 부분 수집)

---

## 4. Potential Functional Gaps

1. **전역 수집 뮤텍스 부재** (확실, H-1): 탭 간 동시 수집.
2. **상세 상한 시 균등 샘플링 없음** (추정): 앞쪽 N건만 상세 → 편향 가능.
3. **PRE on 시 결과 구분 표시 약함** (추정): 분양권/일반 매물 구분이 UI에 약할 수 있음.
4. **확장 컬럼 ↔ 엑셀 템플릿 비동기** (확실): 표 표시 항목과 엑셀 체크가 별개 설정.
5. **OPST 미지원** (확실, 의도): 경량 원칙; 사용자 요구 시 큰 작업.
6. **meta 필드 DB 미영속** (확실, 의도): 확인일·동 등은 재수집 전 이력 분석에 못 씀.
7. **Selenium + VL 거부** (확실): complex 시작 시 가드; 사용자는 Playwright로 우회 필요.
8. **예약 수집과 UI 옵션 정합** (추정): 스케줄 경로가 최신 `collection_runtime_kwargs`를 항상 타는지 경로 점검 권장.
9. **대시보드 lazy load** (확실): 첫 진입 시 생성; README와 대체로 일치.
10. **가이드/탭 이름** (확실): 메뉴 친화화 후 가이드 문구 동기화됨; 외부 문서 일부는 구명칭 잔존 가능.

---

## 5. Recommended Fix Plan

### 1단계 — 즉시 (안정성·데이터 무결성)

1. **전역 수집 락**: 매물 수집/지도/예약 시작 시 단일 실행 강제.
2. 완료 로그에 `detail_fetch_skipped_count` / 상한 적용 여부 노출.
3. README 주요 설정 표 최신화.

### 2단계 — 안정성·UX

1. 「표시 항목」메뉴 저장 정책 수정 (변경 확인 또는 토글 즉시 저장 + 되돌리기).
2. 수집 실패 원인 코드 표준화 (`article_api_failure_reasons` 확장, UI 요약).
3. 스케줄 시작 경로가 `collection_runtime_kwargs`와 동일한지 회귀 테스트.

### 3단계 — 구조

1. 탭 라벨/가이드/단축키 문자열 중앙 상수화.
2. 핵심 경로 `except Exception` 축소 (네트워크 vs 파싱 vs 권한).
3. (선택) 메타 필드 영속은 **별도 경량 테이블 또는 JSON side-car**로만 검토 — 본 이력 테이블 비대화 금지 원칙 유지.

---

## 6. Test Recommendations

| 테스트 | 목적 |
|--------|------|
| **전역 락**: crawler start 중 geo start → False | H-1 회귀 |
| **표시 항목 메뉴**: 취소 시 settings 불변 (정책 확정 후) | H-2 |
| **detail off**: enrich 미호출, 아이템 push 유지 | 옵션 배선 |
| **detail max=2**: 3후보 중 2만 network detail | 상한 |
| **include_pre=True**: URL에 PRE, geo `a=` 동일 | 옵션 정합 |
| **settings theme/engine**: data round-trip (`dark`/`playwright`) | 라벨 분리 회귀 |
| **sanitize**: workers/delay/extra_columns 클램프 (이미 일부 있음) | 유지 |
| **schedule path**: 예약 실행 kwargs에 collection 옵션 포함 | 추정 갭 |
| **live-smoke**: detail success + pages_fetched (네트워크 가용 시) | 외부 API |

---

## 부록 A. 이번 세션에서 반영한 UI 문구 (감사 외 요청)

사용자 요청으로 **메뉴/탭/설정 라벨 친화화**는 코드에 반영했습니다 (기능 로직·DB 변경 없음).

| 구분 | 예 |
|------|-----|
| 좌측 네비 | 매물 수집, 지도로 찾기, 내 단지, 단지 묶음, 즐겨찾기, 대시보드, 가격 통계, 수집 기록, 예약 수집, 가이드, 설정 |
| 설정 | **기본** / **고급** (엔진·타임아웃·표시 컬럼 등은 고급) |
| 옵션 | 분양권 매물도 함께 수집, 중개사·기전세 등 상세 정보 가져오기, 빠른 목록 조회 … |
| 결과 툴바 | 검색 · 표/카드 · 「더보기」(묶기/정렬/고급 필터/표시 항목) |
| 지도 | 위도·경도·범위 1차 노출; 칸 간격·대기는 접기 |

저장 값은 기존과 동일 토큰 유지 (`theme=dark|light`, `crawl_engine=playwright|selenium`, 자산 `APT`/`VL`).

---

## 부록 B. 이전 감사 대비 상태

| 이전 이슈 | 현재 |
|-----------|------|
| Article API page=1 only | 다중 페이지 + supplement |
| frozen Windows-only path | cross-platform frozen root |
| Settings 테스트 오염 | `reset_for_tests` / accessor |
| 상세 DOM 붕괴 | front-api 보충 + live-smoke success 이력 |

---

*본 문서는 기능 감사 산출물이며, High-Risk 수정 구현은 별도 작업으로 진행하는 것을 권장합니다.*
