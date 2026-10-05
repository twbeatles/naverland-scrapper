# Update History

## 2026-10-05: UI/UX 리팩토링 (쉬운 용어 · 화면 밀도 정리 · 흐름 보완, v15.4)

- 매물 수집: 왼쪽 패널을 `수집할 단지 → 거래 종류 → 조건·속도(접힘)` 순으로 재구성하고 `수집 시작/중지/결과 저장`을 항상 보이는 하단 바에 고정. 세로 스플리터로 잘리던 문제 제거, `단지 찾기`를 기본 추가 방법으로 승격, 나머지는 `불러오기` 메뉴로 통합
- 지도로 찾기: 위도·경도 대신 `지역 찾기`(지역 이름 검색)로 위치 지정, 좌표·세부 값은 접어 둠. 예약 수집에는 `「지도로 찾기」에서 정한 위치 가져오기` 추가
- 빈 화면 안내: `EmptyStateWidget`이 아이콘만 그리던 버그 수정(제목·설명 누락). 결과/내 단지/묶음/즐겨찾기/기록/대시보드에 상황별 안내 적용, 비었을 때는 빈 표를 숨김
- 용어: complex/geo_sweep, APT/VL, DB, 크롤링, 엔진·모드 등 내부 용어를 화면에서 제거 (`src/utils/ui_labels.py`, 표는 delegate로 표시만 변환해 저장 값은 그대로)
- 상태 표시줄의 진단 수치(PW/응답/매칭/drain/marker…)는 쉬운 진행 문구로 바꾸고, 원래 수치는 진행 표시 툴팁·`last_diagnostic_text`·진행 기록에 유지
- 버그 수정: 상단 메뉴가 아이콘만 보이던 문제, 메인 창에서 여는 대화창(설정·알림 등)에 테마가 적용되지 않던 문제(`DialogThemer`), 카드 거래 종류 배지 색 깨짐(8자리 hex → `tint()`)
- 스타일: 버튼 위계 정리(보조=중립, 삭제=외곽선), 그룹 제목을 카드 안쪽으로, 공통 페이지 제목(`build_page_header`)
- 가이드 화면 재작성: Qt rich text가 그리지 못하는 둥근 상자·inline-block을 걷어내고 표 기반의 단계/2열 구성으로 정리, 공통 페이지 제목 적용
- 체크박스에 체크 표시 추가(임시 폴더에 SVG 생성), 진행 기록은 요약 보기가 기본이고 `자세히 보기`로 진단 기록 전환, 설정 고급 탭의 드문 묶음 3개는 접어 둠
- 설정 키·DB·수집 로직·단축키는 변경 없음. 문구를 검사하던 테스트만 새 문구로 갱신 (479 passed)

## 2026-10-04: 감사 지적 수정 + 키워드 검색 고도화 (v15.3)

- 키워드 단지 검색 고도화: 자동완성/검색 페이지네이션, 429 단일 재시도+30s 쿨다운, 실패 generation 가드, 지역 선택 → 지도로 찾기 중심 좌표 연동, cortarNo 기반 단일 마커 조회
- 감사 수정: 키워드 세션 생성 실패 시 드라이버/브라우저 정리(ISSUE-001), 스냅샷 워커 종료 대기 5s+캐시 flush(ISSUE-002), 카드 별 실패 시 양 탭 롤백, 사망 `retry.py` 제거·VL 사전 안내
- 회귀 테스트: `tests/test_keyword_search*.py`, `tests/test_result_filters.py`, `tests/test_geo_markers_cortar.py`, 스냅샷 대기·캐시 flush·별 롤백 (전체 479 passed + 19 subtests, Pyright 0)

## 2026-09-27: PROJECT_AUDIT.md 지적 전체 수정 (P1-P3, v15.2)

- P0 3건: 손상 geometry 검증 단일 경로 + 오프스크린 클램프, CrawlLock release(None) 분리, 즐겨찾기 DB 실패 시 UI 미반영 + 실패 통지
- P1 7건: 스냅샷 rollback, 락/저장 순서 정리, 워커·타이머 종료 정리, UnicodeDecodeError 복구, detail 풀 중단 체크, 그룹/메모 DB 보호, 알림 수치 가드
- P2 8건: 테마 독스트링 정합, export 원자 저장, 캐시 방어 복사, 탭 전환 디바운스, 에러 토스트 + 버튼 복구, 토스트 지오메트리, 단축키 중복 해제 (ISSUE-009/013/015는 추정 유지로 미변경)
- 회귀 테스트 `tests/test_audit_fixes.py` 신규 (T-001~T-010)
- Pyright 0 errors, CI 서브셋 + 신규 테스트 289 passed + 19 subtests

## 2026-09-27: 상단 라벨 명암 반전 수정 (Fluent 테마 고정 + 다크 보조텍스트 밝게)

- 원인: OS 테마 감시(3초 poll + colorSchemeChanged)가 명시적 dark/light 선택을 매번 덮어써 Fluent 내비 상단 라벨·아이콘이 반대 테마 색으로 렌더됨 (다크에서 어둡게 / 라이트에서 흰색으로)
- `src/ui/fluent/theme.py`에 핀 고정 도입: 명시 선택 시 OS 동기 무시·테마 재확인, AUTO에서만 OS 연동; `is_dark_theme()` AUTO 해소 수정
- 다크 보조 텍스트 밝게 (`design_tokens.py` + `colors.py` dark `text_secondary`)
- 재발방지: `tests/test_fluent_theme.py`에 OS 감시 덮어쓰기 회귀 테스트 추가
- Pyright 0 errors, CI subset 251 passed + 12 subtests, exe 재빌드 + `--preflight` exit 0

## 2026-09-27: 메뉴 라벨 정리 (이모지 제거·팝업 메뉴 텍스트색 명시)

- 메뉴바·팝업 메뉴 20여 곳의 이모지를 FluentIcon으로 교체
- `QMenu`에 텍스트색 토큰 명시 (테마별 팝업 가독성 보장)

## 2026-09-27: 내비 라벨 투명화 수정 (펼침 시점 연기)

- 내비 `expand()`를 창 표시 이후(`QTimer.singleShot(0)`)로 연기해 아이템 애니메이션·불투명도가 안정된 상태에서 펼치도록 변경
- 라이트/다크 캡처로 라벨 표시 재확인, 내비 회귀 테스트 통과

## 2026-09-27: Fluent 전면 재설계 (P1-P10) + CI 복구

- 좌측 내비 시작 시 펼침으로 변경 (48px 아이콘 전용 → 208px 라벨 내비, srtgo parity)
- EmptyState 아이콘을 Fluent IconWidget으로 교체, 버튼·진행 표시의 이모지 제거 후 FluentIcon 적용
- 페이지 간격·타이포를 디자인 토큰으로 통일, 카드 radius 14→8, QSS 그라디언트 잔여분 제거
- CI 실패 수정: `darkdetect>=1.4.0` 오기재 → `>=0.8.0`; 재발방지로 핀 정합 테스트 + install fail-fast
- 신규 `tests/test_requirements_pins.py`, 내비 펼침 회귀 테스트 3건
- Pyright 0 errors, CI subset 250개 통과
- QMessageBox 호출부는 기존 테스트 계약이므로 유지 (파괴적 확인은 기본 No)

## 2026-09-27: Fluent UI 정리 (DESKTOP_UI_DESIGN_RULES + srtgo 기준)

- `src/ui/fluent/design_tokens.py` 신설: spacing 4/8/12/16/24/32, 카드 radius 8, 창 크기 토큰, 시맨틱 보조 텍스트 색상
- 테마 OS 연동: `setup_app_theme()` + `darkdetect` + `colorSchemeChanged` 감시, 설정에 "시스템 연동(auto)" 추가 (`requirements.txt`에 `darkdetect`)
- 저장 기본 테마는 기존 계약 유지 (`dark`, `tests/test_managers_cache.py` 회귀 확인)
- High-DPI PassThrough (`src/main.py`), 화면 가용 영역 맞춤 초기 창 크기 + 최소 960x640
- QSS 절제: 그라디언트 제거(플랫 역할색), 카드 radius 12→8, Glassmorphism 명칭 정리
- 보조 라벨 `#888` 인라인 9곳을 토큰 헬퍼로 교체, 단축키 안내 이모지 제거
- 신규 `tests/test_fluent_theme.py` (6건) + CI subset 등록 (ci.yml / ci_check.ps1)
- Pyright 0 errors, CI subset 전체 통과

## 2026-09-25: 수집 경량 기본값 (헤드리스 + 동시 4 + lazy 풀)

- 상세 동시 조회 기본값 12 → 4, 브라우저 창 숨김(헤드리스) 기본값 끔 → 켬
- 상세 페이지 풀은 시작 시 최대 2개만 사전 생성, 수요에 따라 설정 상한까지 확장
- 기존 settings.json의 구 기본값(headed·동시 12)은 1회 마이그레이션 (로그 기록, 이후 명시적 선택 존중)
- 신규 테스트: 기본값·마이그레이션 (`tests/test_managers_cache.py`), 풀 수요 확장 (`tests/test_playwright_engine_stabilization.py`)

## 2026-09-20: SOLID 코드 분할 리팩토링 (v15.1)

- 장문 5개 파일을 단일 책임 `_parts/` 패키지로 분할, 기존 경로는 파사드로 유지 (호출부 수정 없음)
- `detail_fetcher.py` → `detail_fetcher_parts/` 11모듈 / `managers.py` → `managers_parts/` 8모듈 / `coercion.py` → `coercion_parts/` 3믹스인 / `stats_schedule.py` → 5믹스인 / `lifecycle.py` → 8믹스인
- 기계적 줄 단위 이동 + 커버리지/name-set 검증으로 코드 누락 없음 확인
- 신규 `tests/test_solid_split_facades.py` (파사드 parity 7건) + CI subset 등록
- `APP_VERSION` v15.0 → v15.1, README 배지 동기화


## 2026-09-07: Dependabot PR 병합 및 주간 봇 제거

- Dependabot PR #2–#7 squash 병합 (모두 CI quality 3.11/3.14 통과)
  - pip: `selenium>=4.48.0`, `cryptography>=50.0.1`
  - Actions: `actions/checkout@v7`, `actions/setup-python@v7`, `actions/setup-node@v7`, `softprops/action-gh-release@v3`
- `main` 이외 원격 브랜치 정리 (Dependabot head는 병합 후 삭제)
- `.github/dependabot.yml` 삭제: 데스크톱 앱에 주간 버전 PR이 쌓이기만 해서 비활성. 하한은 `requirements.txt` / 워크플로에서 직접 올림
- README·`docs/RELEASE_UPDATES.md`에 CI/릴리스 액션 및 Dependabot 비활성 상태를 맞춤

## 2026-08-13: Light-mode cards + Fluent binding guard

- 라이트 모드 매물 카드가 흑색 배경으로 남던 문제: `ArticleCard` objectName/`QFrame#articleCard` QSS, 불투명 surface 토큰, `CardViewWidget.set_theme`로 재렌더
- 테마 전환 시 기존 카드를 다시 그려 라이트/다크 배경·본문색을 맞춤
- `PySide6-Fluent-Widgets`가 `qfluentwidgets`를 덮어쓰면 패키징 EXE가 `No module named 'PySide6'`로 실패. spec/preflight가 PyQt6 변종을 강제
- `README.md` / `PROJECT_AUDIT.md`에 설치·빌드 주의 명시

## 2026-08-12: Docs / spec / gitignore sync + push prep

- `naverland-scrapper.spec`: 2026-08-12 사이트 계약 모듈 hiddenimport 핀·주석
- `.gitignore`: 제품 docs/src 추적 규칙 명시, 에이전트 문서 삭제 상태 유지, 세션/도구 덤프 패턴 보강
- `README.md`: 확장 컬럼·패키징 메모·survey 링크 정합
- `PROJECT_AUDIT.md` / `docs/NAVER_LAND_SURVEY_2026-08-12.md` 조치 완료 상태 유지
- 에이전트 문서(`claude.md` 등)는 저장소 미추적 (로컬만 존재 가능)

## 2026-08-12: Remaining reform sweep (settings/session/smoke/fields)

- 설정: `detail_front_api_only` (HTML 생략·API만) 기본/고급 배선 + thread kwargs
- 목록 필드: `상세주소`, `직거래`, `중개ID` + 컬럼/export
- front-api 세션 워밍: new.land goto + `/front-api/v1/auth/si`
- live-smoke: `geo-contract`(`b=`), `realtorName=yes/no`, 마커 DOM 실패 시 API 캡처만으로 ok 허용
- 카드: 확인일·중개소명 메타 한 줄
- 앱 종료: `crawl_lock.force_release`
- survey 체크리스트 완료 동기화

## 2026-08-12: Audit fix plan (Phase 1–3)

PROJECT_AUDIT 권고 전면 반영:

### 1단계 진단·안정성

- mixin rebind globals 가드 테스트 `tests/test_playwright_engine_globals.py`
- 상세 통계: `detail_list_meta_only` / `detail_host_unreachable` / `detail_429` + finish 로그
- 상세 워커: 429·host 불안정 시 워커 축소, 배치 조기 중단, **입력 순서 보존**
- front-api-only (`prefer_front_api_only`) 경로

### 2단계

- geo `single-markers/2.0` 직접 호출 + DOM 전환 실패 시 API 폴백
- live-smoke: fin HTML dead를 overall fail에서 제외(host-health degraded)

### 3단계

- 결과 컬럼/export: 동일주소최고·최저, 확인유형
- name_lookup: complexes overview API 우선
- README / Claude 문서 동기화

## 2026-08-12: Naver site drift P0 (geo b=, list realtor, fin degrade)

### 라이브 관측

- `new.land` Article API / single-markers / overview 정상
- `fin.land` HTML(`/`, `/map`, `/articles/*`) → `financial.pstatic.net/404` (자동화 경로)
- geo: 사이트는 거래유형 키 **`b=`** 유지, 앱이 쓰던 **`tradeTypes`는 URL에서 소실**
- 목록 JSON에 `realtorName` 등 존재하나 앱 미매핑

### 코드

- `src/core/services/site_contract.py` — 호스트·geo/complex URL·front-api 계약
- geo scan / complex page URL: `a` + `b` + `e=RETAIL` (`build_geo_map_url` / `build_complex_page_url`)
- `normalize_article_payload`: `realtorName`→`부동산상호`, 동일주소 최고/최저, 확인유형
- entry plan 기본: `direct` + `new_home` only (`playwright_allow_fin_m_entry_plans` 로 레거시 복구)
- desktop warmup: `new.land` 단독 (fin/m 홈 스킵)
- detail: fin 404 시 m 연쇄 축소, list 중개명 empty wipe 방지, list-partial 상태
- Selenium complex URL도 `b=` 정렬
- 문서: `docs/NAVER_LAND_SURVEY_2026-08-12.md`

### 검증

- `tests/test_site_contract.py` 추가, normalize/detail 테스트 확장

## 2026-08-05: Fix CI Pyright (Fluent prepare_page types)

- Root cause: `prepare_page()` returned bare `QWidget`, so `crawler_tab`/`geo_tab`/… lost concrete types (75 pyright errors on `test_ui_wiring` + menu Optional).
- Fix: `TypeVar` on `prepare_page`; null-safe `QMenu.addAction`/`addMenu` in result toolbar.
- Recurrence: `scripts/ci_check.ps1` + CI comments; run `powershell -File scripts/ci_check.ps1` before UI pushes.

## 2026-08-05: Theme contrast + slim PyInstaller

- 라이트 모드: 도메인 QSS에서 bare `QWidget` 배경/색 강제 제거 → Fluent 입력·카드 검은 깨짐 완화
- 가이드: 테마별 HTML(`src/ui/guide_content.py`)로 다크/라이트 본문 대비 확보, 테마 전환 시 재렌더
- `naverland-scrapper.spec` 슬림 설계: playwright 전량 collect 중단, selenium/devtools 옵션화, ML 스택 exclude+TOC 필터
- README 슬림 빌드 env 표 보강

## 2026-08-05: Docs / Spec / Gitignore sync (Fluent push)

- `README.md` / `PROJECT_AUDIT.md` / `docs/NAVER_LAND_SURVEY_2026-08-04.md`: Fluent 네비·설정 기본/고급·테스트 수 정합
- `naverland-scrapper.spec`: 2026-08-05 Fluent hiddenimport 메모 갱신
- `.gitignore`: OS junk, egg-info, `.env.*`, zip 산출물, 에이전트 로컬 문서 패턴 보강 (제품 `src/ui/fluent/` 는 추적)
- 에이전트 문서(`claude.md` 등) 미추적 상태 유지

## 2026-08-05: Fluent UI / UX refactor (shell + simplify)

- `PyQt6-Fluent-Widgets` 도입 (`qfluentwidgets`), 좌측 `NavigationInterface` + 페이지 스택
- 수평 탭 10개 → 그룹 구분 네비(수집 / 보관함 / 분석 / 자동화 / 가이드·설정)
- 설정 UI: **기본 / 고급** progressive disclosure (엔진·타임아웃·워커는 고급)
- 매물 수집: 좌측 우선순위 재배치, 면적·가격 필터 접기, 엔진 콤보 숨김(설정 단일 소스)
- 결과 툴바: 검색·뷰 전환 중심, 묶기/정렬/고급필터/표시항목은「더보기」메뉴
- 호환: `TabCompatBridge`로 기존 `tabs.*` / 탭 인덱스 테스트·믹신 유지
- 패키징: `qfluentwidgets` / `qframelesswindow` hiddenimports
- 검증: UI 관련 pytest 94 passed (전체 스위트는 동일 세션에서 재실행)

### 후속 (지도·공통 컴포넌트)

- 지도 탭: 위치/범위 1차 노출, 칸 간격·대기는 접기 옵션
- `SearchBar` → Fluent `SearchLineEdit` (가능 시), `show_toast` → InfoBar 우선
- 내 단지 / 단지 묶음 / 예약·기록·통계 버튼 라벨 정리
- 검증: pytest 전체 재실행

### 후속 (대시보드·카드)

- `StatCard` KPI 카드 재구성(좌측 액센트 바, 테마 연동)
- 대시보드/요약 카드/즐겨찾기 라벨 정리, EmptyState 통일
- `ArticleCard` 서피스 스타일 정돈(상단 거래유형 액센트)
- 도메인 QSS는 콘텐츠 스택에만 적용 (네비 비간섭)

## 2026-08-04: Docs / Spec / Gitignore Sync

- `README.md`: 탭 이름·전역 수집 락·실행/빌드/문서 링크를 코드와 맞춤
- `docs/NAVER_LAND_SURVEY_2026-08-04.md`: 옵션·락·테스트 반영 체크리스트 갱신
- `naverland-scrapper.spec`: 2026-08-04 모듈 추가에 대한 번들 메모 갱신 (추가 hiddenimport 불필요)
- `.gitignore`: `agent-tools/`, `pyright_src*` 명시; 프로젝트 `docs/`·루트 감사 문서는 추적 유지
- 에이전트 전용 문서(`CLAUDE.md` 등)는 계속 미추적 (이전 커밋의 문서 삭제/언트랙 상태 유지)

## 2026-08-04: Audit Fixes (Lock, Feedback, Docs)

### 1단계 안정성

- 전역 수집 락(`src/core/crawl_lock.py`): 매물 수집·지도 탐색이 DB를 동시에 쓰지 않도록 상호 배제
- 예약 수집도 락/실행 중 탭을 확인해 건너뜀
- 수집 완료 로그에 상세 skip·상한·상세 off·목록 API 실패 사유 요약 추가

### 2단계 UX

- 「표시 항목」메뉴: 닫기만으로는 저장하지 않고, 체크 변경 시에만 설정 저장
- `detail_cap_truncated` / `detail_enrichment_disabled` 통계 분리

### 3단계 구조·문서

- 탭/설정 탭 라벨 상수화 (`src/utils/ui_labels.py`)
- README 주요 설정 표를 실제 옵션에 맞게 갱신
- 일부 `except Exception` 범위를 구체 예외로 축소 (finish/start/column hide)

### 검증

- 단위 테스트: crawl lock, finish 요약, 기존 스위트 — `pytest` **328 passed**

## 2026-08-04: Options, Tabbed Settings, Light UI

### 옵션 (DB 무변경)

- 수집: `include_pre_sale_rights`, `detail_enrichment_enabled`, `detail_enrichment_max_per_complex`, `detail_front_api_enabled`, `article_api_page_delay_ms`
- 표시: `result_extra_columns`, `card_show_extra_meta`
- sanitize 클램프(워커≤16, delay≤2000, 상세 상한≤500) 및 확장 컬럼 id 화이트리스트
- CrawlerThread / complex·geo 시작 경로에 `collection_runtime_kwargs` 연결

### UI

- 설정 다이얼로그를 **일반 | 수집 | 성능 | 지도 | 표시** 탭으로 분리
- 결과 테이블 확장 컬럼(확인일·동·타입명 등) 추가, **기본 숨김**, 툴바「컬럼」메뉴·설정 동기화
- 엑셀 템플릿에 메타 컬럼 추가(기본 off)
- 카드 뷰: 동/타입명 한 줄(중개 연락처 제외)
- 가이드 탭에 옵션 요약 섹션

### 경량 원칙

- article_history 등 DB 스키마 확장 없음
- OPST 미도입, PRE 기본 off, 확장 컬럼 기본 숨김

### 검증

- `pytest` **322 passed**

## 2026-08-04: Naver Land Site Survey And Compatibility

### 조사

- `docs/NAVER_LAND_SURVEY_2026-08-04.md`에 Npay/`new.land`/`fin.land`/`m.land` 현황과 앱 갭을 정리했습니다.
- CodeGraph + 라이브 Playwright 프로브 기준: 목록 Article API는 유지, 상세 HTML은 404/map 빈발, `front-api/v1/article/agent` 등이 상세 보강의 실경로입니다.

### 상세 보강 (P0)

- `detail_fetcher`가 DOM 실패 시에도 `front-api` agent/basicInfo를 request 컨텍스트로 보충 조회합니다.
- agent JSON 키 집합(중개소/전화 nested 등)을 확장하고, 응답 캡처 필터에 `front-api`를 명시했습니다.
- m.land detail URL은 fin 리다이렉트 환경에 맞춰 후순위로 유지합니다.

### 목록·Geo·Rate limit

- `normalize_article_payload`에 `확인일`, `동`, `타입명`, `동일주소건수`, `정보제공` 및 매물 좌표 보강을 추가했습니다.
- Geo 스캔 URL의 `a=`를 `APT:ABYG:JGC` / VL 복합 타입(+ `e=RETAIL`)으로 사이트 기본값과 정렬했습니다.
- Article API 페이지 간 짧은 delay, 429/`TOO_MANY_REQUESTS` 구분 실패 통계를 추가했습니다.
- `article_api_real_estate_type(..., include_pre=)` 옵션을 추가했습니다(기본 false).

### 검증

- 단위 테스트: detail front-api, normalize 메타 필드, PRE 옵션 — `pytest` **319 passed**
- live-smoke: `logs/live-smoke-after-naver-survey.json` — detail-fields `parse_state=success`, `core_field_count=3`, agent/network 응답 보충 확인

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
