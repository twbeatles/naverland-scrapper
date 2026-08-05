# Update History

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
