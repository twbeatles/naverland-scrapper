# AI Context: Naver Real Estate Crawler Pro Plus (v15.0)

이 문서는 AI 에이전트가 프로젝트 작업 시 참조할 컨텍스트 정보입니다.

## 1. Project Overview
- **Name**: Naver Real Estate Crawler Pro Plus v15.0 (네이버 부동산 매물 크롤러)
- **Goal**: 네이버 부동산 매물 수집, 분석, 모니터링, 관리를 위한 데스크톱 앱
- **Key Features**: 
    - 다중 단지 크롤링 & 그룹 관리
    - Playwright 기본 엔진 + Selenium fallback(일반 단지 수집 `complex` 모드 전용, `geo_sweep`은 Playwright 전용)
    - 지도 탐색 탭 기반 좌표 sweep (APT/VL, 매매/전세/월세)
    - 응답 가로채기 기반 고속 목록 수집 + 필터 통과 매물 우선 모바일 상세 수집
    - 실시간 가격 추세 분석 & 시각화 (히스토그램, 파이차트)
    - Excel/CSV/JSON 내보내기 (템플릿 지원)
    - 카드 뷰/대시보드/즐겨찾기/최근 본 매물
    - 신규/가격 변동/소멸 매물 추적
    - 중개사/연락처/기전세금/갭 분석 필드 저장 및 export
    - **Modern UI - Glassmorphism & Token-based Design (v15.0)**
    - Toast 알림 (페이드 인/아웃 애니메이션)
    - 강력한 에러 핸들링 (RetryHandler, Rate limit 감지)
    - 메모리 관리 (임계치 초과 시 드라이버 재시작)
    - DB 복원 유지보수 모드(복원 중 크롤링/스케줄 차단)
    - SQLite online backup + restore integrity 검증
    - 가격변동 부호 표기 통일(UI/CSV/Excel)
    - 월세 필터 분리(보증금/월세 동시 조건)
    - 원본(raw) 캐시 저장 후 조회 시 재필터링
    - 차단 페이지 감지 시 즉시 실패 처리

## 0. v15.0 Delta Notes (UI/UX Refactoring)
- `styles.py`: 하드코딩된 색상을 `COLORS` 딕셔너리로 추출하고 `_generate_stylesheet` 함수를 도입하여 QSS 기반 동적 테마를 생성합니다.
- `components.py`: 반복적으로 사용되는 '결과 없음' 상태 처리를 위한 `EmptyStateWidget` 컴포넌트가 추가되었습니다. `SummaryCard`와 `SpeedSlider` 등의 인라인 스타일링이 객체 이름 및 QSS 기반으로 리팩토링되었습니다.
- 모든 위젯 및 탭(`CrawlerTab`, `DatabaseTab`, `GroupTab`, `FavoritesTab`, `DashboardWidget` 등)에 `EmptyStateWidget`이 적용되었습니다.
- 다이얼로그 창(`AboutDialog`, `FilterDialog` 등)의 테마 일관성(HTML 포함)이 QSS와 동적 토큰 전달을 통해 향상되었습니다.

## 0-1. v14.2 Delta Notes
- `CrawlerTab`:
  - 월세 가격 필터 입력이 `monthly_deposit_*`, `monthly_rent_*`로 확장됨.
  - 고급 필터 UI(버튼/상태 배지)와 결과 파이프라인(테이블/카드뷰) 연동 완료.
  - `retry_on_error=False` 설정 시 크롤러 재시도 횟수는 0으로 강제됨.
- `CrawlerThread`:
  - 캐시 저장 포맷을 `raw_items` 중심으로 전환(legacy `items` 읽기 호환 유지).
  - 차단/방어 페이지 시그널(title/page_source) 감지 시 예외 발생.
  - 스크롤은 내부 컨테이너 우선, 실패 시 window 스크롤 폴백.
  - 월세 필터는 보증금/월세 모두 만족해야 통과.
- `RealEstateApp`:
  - DB 복원 중 유지보수 모드로 전환되어 크롤링/일부 UI 동작이 차단됨.
  - 종료 시 `shutdown_crawl()` 실패하면 앱 종료를 중단하고 DB close를 수행하지 않음.
  - 앱 메뉴의 고급 필터 항목은 CrawlerTab으로 위임됨.
- `NaverURLParser`:
  - 단독 숫자 추출을 라인 단독/명시 문맥으로 제한해 과추출 완화.
- Build:
  - `naverland-scrapper.spec` 점검 결과 본 변경에 대한 추가 hidden import 수정 불필요.

## 0-2. v15.0 Functional Stabilization (2026-03-02)
- `RetryHandler`:
  - `RetryCancelledError` 추가, 재시도 대기 구간 취소 가능(cancellable backoff) 처리.
- `CrawlerThread`:
  - `requestInterruption()` 연동, interruptible sleep, shutdown mode, negative cache TTL 분리 적용.
- `URLBatchDialog`:
  - 단지명 조회를 worker thread로 분리하고 진행률/취소 상태를 UI에 반영.
- `ComplexDatabase`:
  - `group_complexes` orphan 정리, 삭제 경로 선정리, `add_complex(return_status=True)` 상태 반환 추가.
- `SearchHistoryManager`:
  - `trade_types/area_filter/price_filter`를 포함하는 canonical dedupe key 적용.
- `RealEstateApp`:
  - 예약 실행 시 이미 크롤링 중이면 목록 덮어쓰기 없이 skip.
- Tests:
  - UI wiring, retry cancellation, DB orphan 정리, negative cache 회귀 케이스 보강.

## 0-3. v15.0 Runtime DB Stability Patch (2026-03-02)
- `ComplexDatabase`:
  - write 경로(`crawl_history`, `article_history`, `disappeared`)에 write lock을 적용해 동시 write 경쟁을 완화.
  - `database is locked`에 대해 짧은 재시도/빠른 실패 정책을 적용해 장시간 UI block 가능성 축소.
  - `database disk image is malformed` 감지 시 write circuit-breaker를 켜서 추가 쓰기를 차단.
- `CrawlerThread`:
  - `complex_finished` 시점의 크롤링 기록 저장을 worker thread에서 처리.
  - DB write 비활성화 상태를 1회 경고 로그로 사용자에게 알림.
- `CrawlerTab`:
  - `complex_finished` 슬롯에서 UI 스레드 DB write를 제거하고 로그 업데이트 전용으로 전환.

## 0-4. v15.0 Anti-Bot / Geo Expansion (2026-03-06)
- `CrawlerThread`:
  - 엔진 오케스트레이션 레이어로 축소되고 `PlaywrightCrawlerEngine`/`SeleniumCrawlerEngine` 선택 및 fallback을 담당.
  - `crawl_mode=complex|geo_sweep`, `engine_name`, `GeoSweepConfig`, `discovered_complex_signal`을 지원.
- `PlaywrightCrawlerEngine`:
  - 기본 Chromium 엔진, response interception 기반 목록 수집, 필터 통과 매물 우선 모바일 상세 워커 풀 수집을 담당.
  - 지도 sweep에서 발견한 단지를 즉시 DB에 등록하고 같은 실행 흐름에서 상세 수집까지 연결.
- `CrawlCache`:
  - 캐시 키는 기본 `complex_id + trade_type`에 `mode/asset_type/source_lat/source_lon/source_zoom/marker_id` 컨텍스트 네임스페이스를 결합해 모드 간 메타데이터 오염을 차단.
- `ComplexDatabase` / `DataExporter`:
  - `asset_type`, broker/contact, `existing_jeonse_price`, `gap_price`, `gap_ratio` 등 신규 컬럼을 저장/조회/export.
  - `crawl_history`에 `engine`, `mode`, `source_lat/lon/zoom` 메타데이터를 저장.
- UI / Build:
  - `GeoCrawlerTab` 추가, 설정에 `crawl_engine`, `playwright_*`, `geo_*` 항목 추가.
  - `naverland-scrapper.spec`는 Playwright hidden import, runtime hook, Chromium bundle 수집을 포함.

## 2. Technical Stack
- **Language**: Python 3.9+
- **GUI Framework**: `PyQt6` (Widgets, Core, Gui)
- **Web Automation**: 
    - `playwright` (기본 Chromium 엔진, response interception, 필터 통과 매물 우선 모바일 상세 수집)
    - `undetected-chromedriver` (동적 콘텐츠 & 우회)
    - `selenium` (fallback 및 DevTools 계층)
    - `beautifulsoup4` (파싱)
    - `urllib` (API 호출)
    - `winreg` (Windows 레지스트리 기반 Chrome 버전 감지)
- **Data Storage**: 
    - **SQLite** (`data/complexes.db`): 메인 데이터 저장
    - **JSON**: 설정, 프리셋, 캐시, 히스토리
- **Visualization**: `matplotlib` (PyQt6 임베디드)
- **Build Tool**: `PyInstaller`
- **Distribution Profile**: `naverland-scrapper.spec` (기본 `onedir + Chromium bundle`, `NAVERLAND_ONEFILE=1` 시 `onefile`, `NAVERLAND_BUNDLE_CHROMIUM=0` 시 slim)
- **Optional**: `psutil` (메모리 모니터링), `plyer` (알림)

## 3. Architecture (v15.0 Modular)

> **IMPORTANT**: 코드베이스가 모놀리식에서 모듈화 아키텍처로 리팩토링됨

```
src/
├── main.py                     # 진입점
│
├── core/                       # 비즈니스 로직
│   ├── crawler.py              # CrawlerThread (QThread, engine orchestration)
│   ├── database.py             # ConnectionPool, ComplexDatabase
│   ├── item_parser.py          # ItemParser (정규화 파싱)
│   ├── parser.py               # NaverURLParser (RetryHandler 적용)
│   ├── cache.py                # CrawlCache (TTL 기반)
│   ├── analysis.py             # MarketAnalyzer, ComplexComparator
│   ├── export.py               # DataExporter, ExcelTemplate
│   ├── managers.py             # SettingsManager, FilterPresetManager, SearchHistoryManager, RecentlyViewedManager
│   ├── engines/                # 크롤링 엔진 계층
│   │   ├── base.py             # CrawlerEngine 인터페이스
│   │   ├── playwright_engine.py # 기본 Playwright 엔진
│   │   └── selenium_engine.py  # 호환 / fallback 엔진
│   ├── models/                 # 크롤링 DTO / enum
│   │   └── crawl_models.py     # CrawlMode, CrawlRequest, GeoSweepConfig
│   └── services/               # Anti-bot / geo 보조 서비스
│       ├── map_geometry.py     # Mercator 변환, sweep 좌표 생성
│       ├── response_capture.py # 목록 응답 정규화
│       ├── detail_fetcher.py   # 모바일 상세 수집
│       └── gap_analysis.py     # 갭 계산 유틸리티
│
├── ui/                         # 사용자 인터페이스
│   ├── app.py                  # RealEstateApp (QMainWindow)
│   ├── styles.py               # get_dark_stylesheet(), get_light_stylesheet()
│   │
│   ├── dialogs/                # 다이얼로그 모음 (분리된 폴더)
│   │   ├── __init__.py         # 모든 다이얼로그 export
│   │   ├── preset.py           # PresetDialog
│   │   ├── settings.py         # SettingsDialog, AlertSettingDialog, ShortcutsDialog
│   │   ├── filter.py           # AdvancedFilterDialog, MultiSelectDialog
│   │   ├── batch.py            # URLBatchDialog
│   │   ├── excel.py            # ExcelTemplateDialog
│   │   ├── search.py           # RecentSearchDialog
│   │   └── common.py           # AboutDialog
│   │
│   └── widgets/                # UI 컴포넌트
│       ├── components.py       # SearchBar, SpeedSlider, SummaryCard 등
│       ├── dashboard.py        # DashboardWidget
│       ├── cards.py            # CardViewWidget, ArticleCard
│       ├── toast.py            # ToastWidget (애니메이션 알림)
│       ├── chart.py            # ChartWidget (matplotlib)
│       ├── tabs.py             # 탭 관련 위젯
│       ├── crawler_tab.py      # CrawlerTab (데이터 수집 탭)
│       ├── geo_crawler_tab.py  # GeoCrawlerTab (지도 탐색 탭)
│       ├── database_tab.py     # DatabaseTab (DB 관리 탭)
│       ├── group_tab.py        # GroupTab (그룹 관리 탭)
│       └── dialogs.py          # 위젯 수준 다이얼로그
│
└── utils/                      # 유틸리티
    ├── constants.py            # APP_TITLE, SHORTCUTS, TRADE_COLORS
    ├── helpers.py              # PriceConverter, AreaConverter, DateTimeHelper, ChromeParamHelper
    ├── logger.py               # get_logger()
    ├── paths.py                # DATA_DIR, DB_PATH, LOG_DIR
    ├── preflight.py            # 실행 전 의존성/브라우저 점검
    ├── live_smoke.py           # GUI 없이 Playwright 실사이트 smoke probe
    ├── runtime_playwright.py   # frozen 환경 Playwright 경로 설정
    ├── retry_handler.py        # RetryHandler (지수 백오프)
    ├── retry.py                # 재시도 유틸리티 (legacy)
    ├── error_handler.py        # NetworkErrorHandler
    └── plot.py                 # 차트 유틸리티
```

### 3.1 Key Classes

#### **Core Logic**
| 클래스 | 파일 | 설명 |
|--------|------|------|
| `CrawlerThread` | `crawler.py` | QThread 기반 오케스트레이션, 엔진 선택/fallback |
| `CrawlerEngine` | `engines/base.py` | 크롤링 엔진 인터페이스 |
| `PlaywrightCrawlerEngine` | `engines/playwright_engine.py` | 기본 anti-bot 수집 엔진 |
| `SeleniumCrawlerEngine` | `engines/selenium_engine.py` | 호환 / fallback 엔진 |
| `NaverURLParser` | `parser.py` | URL 파싱, RetryHandler로 API 호출 |
| `ItemParser` | `item_parser.py` | 매물 payload 정규화 및 상세 필드 보강 |
| `CrawlCache` | `cache.py` | TTL 기반 크롤링 결과 캐싱 |
| `MarketAnalyzer` | `analysis.py` | 가격 추세 분석 |
| `RetryHandler` | `retry_handler.py` | 지수 백오프 재시도 로직 |
| `GeoSweepConfig` | `models/crawl_models.py` | 지도 sweep 파라미터 모델 |

#### **Database**
| 클래스 | 파일 | 설명 |
|--------|------|------|
| `ConnectionPool` | `database.py` | SQLite 커넥션 풀 (스레드 안전) |
| `ComplexDatabase` | `database.py` | CRUD, 즐겨찾기, 매물/크롤링 이력 관리 및 마이그레이션 |

#### **UI Components**
| 클래스 | 파일 | 설명 |
|--------|------|------|
| `RealEstateApp` | `app.py` | 메인 윈도우 (탭 관리 및 통합) |
| `CrawlerTab` | `crawler_tab.py` | 크롤링 UI 및 로직 |
| `GeoCrawlerTab` | `geo_crawler_tab.py` | 좌표 기반 지도 sweep UI |
| `DatabaseTab` | `database_tab.py` | DB 데이터 조회 및 관리 |
| `GroupTab` | `group_tab.py` | 단지 그룹핑 및 배치 관리 |
| `DashboardWidget` | `dashboard.py` | 통계 대시보드 |
| `CardViewWidget` | `cards.py` | 카드 형태 매물 표시 |
| `ToastWidget` | `toast.py` | 애니메이션 알림 |
| `ChartWidget` | `chart.py` | matplotlib 차트 |
| `FavoritesTab` | `tabs.py` | 즐겨찾기 탭 |

#### **Dialogs** (`src/ui/dialogs/`)
| 다이얼로그 | 파일 | 설명 |
|------------|------|------|
| `PresetDialog` | `preset.py` | 필터 프리셋 관리 |
| `SettingsDialog` | `settings.py` | 앱 설정 |
| `AlertSettingDialog` | `settings.py` | 가격 알림 설정 |
| `ShortcutsDialog` | `settings.py` | 단축키 설정 |
| `AdvancedFilterDialog` | `filter.py` | 고급 필터링 |
| `MultiSelectDialog` | `filter.py` | 다중 선택 |
| `URLBatchDialog` | `batch.py` | URL 일괄 등록 |
| `ExcelTemplateDialog` | `excel.py` | 엑셀 템플릿 설정 |
| `RecentSearchDialog` | `search.py` | 최근 검색 기록 |
| `AboutDialog` | `common.py` | 앱 정보 |

## 4. Development Rules

1. **Modular Structure**: 모든 새 기능은 `src/` 아래 적절한 모듈에 추가
2. **Stability First**: 네트워크 요청은 항상 `RetryHandler` 사용. 모든 I/O에 `try-except` 처리
3. **UI/UX**: "Professional & Modern" 미학 유지 (Glassmorphism)
4. **Theme Support**: 모든 UI 컴포넌트는 Dark/Light 테마 지원 필수
5. **Logging**: `src/utils/logger.py`의 `get_logger()` 사용
6. **Memory Management**: 장기 실행 시 메모리 임계치 체크 (500MB)

## 5. File System
```
Root/
├── app_entry.py             # PyInstaller/CLI 진입점 (`--preflight`, `--live-smoke` 지원)
├── src/                    # 소스 코드 (모듈화)
├── tests/                  # pytest 테스트
├── data/                   # 데이터 저장
│   ├── complexes.db        # SQLite 데이터베이스
│   ├── settings.json       # 사용자 설정
│   ├── presets.json        # 필터 프리셋
│   ├── search_history.json # 최근 검색 기록
│   ├── crawl_cache.json    # 크롤링 캐시
│   └── recently_viewed.json # 최근 본 매물
├── logs/                   # 로그 파일
├── naverland-scrapper.spec # PyInstaller 빌드 스펙
├── ANTI_BOT_UPGRADE_PLAN.md # Anti-Bot / Geo 확장 계획 및 상태
├── pytest.ini              # 테스트/플러그인 설정
├── README.md               # 사용자 문서
├── claude.md               # 이 파일 (AI 컨텍스트)
└── gemini.md               # AI 컨텍스트 (Gemini)
```

## 6. Style Guide (v15.0 Tokenized)

### Color Palette
```python
# `src.ui.styles` 내 COLORS 참고
# Dark Theme (Warm Glassmorphism)
COLORS["dark"] = {
    # Brand / Core
    "accent": "#f59e0b",          # Warm Amber
    "success": "#22c55e",
    "danger": "#ef4444",
    
    # Backgrounds
    "bg_window": "#0f0f1a",
    "bg_card": "rgba(30, 30, 40, 0.85)",
    
    # Texts
    "text_primary": "#f8fafc",
    "text_secondary": "#94a3b8",
    "border_light": "#2a2a35",
}

# Light Theme (Clean & Modern)
COLORS["light"] = {
    "accent": "#0ea5e9",          # Sky Blue
    "bg_window": "#f8fafc",
    "bg_card": "rgba(255, 255, 255, 0.9)",
    "text_primary": "#0f172a",
    "border_light": "#e2e8f0",
}
```

### Trade Type Colors
| 거래유형 | Dark Theme | Light Theme |
|----------|------------|-------------|
| 매매 | #ef4444 | #dc2626 |
| 전세 | #22c55e | #16a34a |
| 월세 | #3b82f6 | #2563eb |

### Animation (ToastWidget)
- Toast fade-in: 300ms, OutCubic
- Toast fade-out: 400ms, InCubic
- Slide offset: 30px vertical
- 호버 시 타이머 일시정지

## 0-5. v15.0 Stabilization Addendum (2026-03-06)
- 신규 설정: `playwright_response_drain_timeout_ms` (default: `3000`)
- 캐시 정책(복합 모드): `mode=complex`, `asset_type=APT`, `marker_id=""`로 정규화
- 레거시 complex 캐시 키는 읽기 호환만 유지하고, 적중 시 정규 키로 승격 저장
- `geo_sweep`는 Playwright 전용 유지, Selenium fallback 미지원
- Geo 운영 통계 키: `geo_discovered_count`, `geo_dedup_count`, `response_drain_wait_count`, `response_drain_timeout_count`

## 0-6. Packaging/Docs Consistency (2026-03-06)
- `naverland-scrapper.spec` 점검 결과: 현 시점 코드 기준 추가 hidden import/runtime hook 변경 불필요
- fallback 정책 정합: Selenium fallback은 `complex` 모드 전용, `geo_sweep`는 Playwright 전용
- 캐시 정책 정합: `complex` 모드 컨텍스트는 `mode=complex`, `asset_type=APT`, `marker_id=""`로 엔진 공통 정규화
- 레거시 캐시 정책: legacy complex 키는 읽기 호환만 제공하고 적중 시 정규 키로 재저장

## 0-7. v15.0 Reliability Patch (2026-03-07)
- `CrawlerThread`:
  - pair 단위 큐(`name/cid/trade_type`) 추적으로 Playwright 실패 시 Selenium fallback을 미처리 pair만 수행.
  - `_push_item` dedupe(`complex_id`, `article_id`, `trade_type`) 추가.
- `PlaywrightCrawlerEngine`:
  - negative cache 저장 조건을 `response_seen=True` + `drain_timed_out=False`로 제한.
  - cache payload `reason` 메타(`confirmed_empty`) 저장, timeout 시 negative cache skip.
  - lightweight retry 래퍼를 `goto`/핵심 wait/모바일 상세 구간에 적용.
  - psutil 사용 가능 시 500MB 메모리 워치독으로 browser/context/page pool recycle 수행.
- `ComplexDatabase`:
  - `complexes` unique 키를 `(asset_type, complex_id)`로 전환하는 자동 마이그레이션 도입.
  - `add_complex(..., asset_type='APT')` 계약 반영.
  - 삭제 API에 `purge_related` 플래그 반영.
- UI:
  - DB 탭 삭제 UX에 확인 모달 + `관련 이력까지 삭제` 옵션(기본 off) 추가.
- CI:
  - GitHub CI는 현재 테스트를 실행하지 않습니다.
  - 수행 범위는 정적 검사와 preflight 점검입니다.

## 0-8. v15.0.4 Crawling Risk Audit + Split Refactor Notes (2026-03-07)
- 크롤링/스크래핑 감사 리포트 추가: `crawling_scraping_risk_audit_2026-03-07.md`
- 코드 분할 리팩토링 반영(공개 API 불변):
  - `src/core/database_parts/*`
  - `src/core/crawler_parts/*`
  - `src/core/engines/playwright_parts/*`
  - `src/ui/app_parts/*`
  - `src/ui/widgets/crawler_tab_parts/*`
- 운영 리스크 우선 항목:
  - Selenium 경로의 0건 negative cache 저장 조건 강화 필요
  - 차단 감지 누적 기반 쿨다운(circuit breaker) 필요
  - API/DOM 변경 내성 강화를 위한 관측성(metric) 보강 필요
- 빌드 정합:
  - `naverland-scrapper.spec`는 현재 분할 구조에서도 추가 수정 없이 유지 가능

## 0-9. v15.0.5 Docs/Packaging Recheck (2026-03-07)
- `.spec` 재점검:
  - `naverland-scrapper.spec`는 `database_parts/crawler_parts/playwright_parts/app_parts/crawler_tab_parts` 분할 구조 기준에서도 추가 hidden import/runtime hook 수정이 필요하지 않음.
- 문서 정합성 동기화:
  - `README.md`, `claude.md`, `gemini.md`, `update_history.md`에 동일 정책 반영.
  - 정책 기준: Selenium fallback은 `complex` 모드 전용, `geo_sweep`는 Playwright 전용.
- 감사 문서 상태:
  - `crawling_scraping_risk_audit_2026-03-07.md`를 저장소 기준 문서로 유지하고, 문서 내 정합성 추적 섹션 추가.
- 무시 규칙 검토:
  - `.gitignore`의 빌드/로그/백업/Playwright 산출물 규칙(`build/`, `dist/`, `logs/`, `backup/`, `backups/`, `playwright-report/`, `test-results/`, `.playwright/`, `ms-playwright/`)은 현 상태로 충분.

## 0-10. v15.0.6 UI/Typing/Packaging Stabilization (2026-03-08)
- UI 사용성 정합:
  - 수집 탭 검색 조건 패널에 내부/외부 `QSplitter` 상태 저장/복원 적용.
  - 전역 wheel-guard(`QSpinBox/QDoubleSpinBox/QComboBox`)로 휠 오입력 변경 방지.
  - 콤보박스는 팝업 열린 상태에서만 휠 선택 허용.
  - 라이트/다크 테마별 드롭다운 팝업(`QComboBox QAbstractItemView`) 색상 대비 보정.
- 타입 안정화:
  - `src/` 전역 Pylance/Pyright 오류를 구조 보강 중심으로 정리.
  - 기준: `npx pyright src` -> `0 errors`.
- 패키징 안정화:
  - `.spec` hidden import를 `matplotlib.backends.backend_qtagg` 기준으로 정리.
  - `NAVERLAND_CONSOLE=1` 빌드 스위치 추가(조용한 GUI 실패 디버깅용 콘솔 출력).
  - `NAVERLAND_BUNDLE_CHROMIUM=1`에서 Chromium 탐지 실패 시 spec 경고 로그 출력.

## 0-11. v15.0.7 Reliability Plan Rollup (2026-03-11)
- Scope: `implementation_risk_review_2026-03-11.md`의 F-01~F-09 전 항목 코드 반영 완료.
- Fixed decisions: F-05(hybrid circuit breaker), F-06(list-key-only split), F-07(skip empty history).
- Selenium reliability:
  - parse metadata 표준화(`response_seen`, `parse_success`, `empty_confirmed`, `blocked_detected`)
  - negative cache strict rule(`confirmed_empty` only)
  - blocked breaker(pair 2-hit/90s cooldown, global 5-hit abort)
- Playwright observability:
  - response/parse/detail success-fail counters 수집 및 stats payload 노출
  - Geo empty trade-type history skip
  - broken UTF-8 log/exception 문자열 정리
- DB hardening:
  - disappeared-mark chunk update
  - `add_complex` lock retry + rollback
  - stats complex key collision 분리(`asset:cid` on collision only)

## 0-12. v15.0.9 Functional Consistency Rollup (2026-03-14)
- Alert scope separation:
  - `alert_settings` / `article_alert_log` now treat `asset_type` as a first-class scope.
  - Legacy or blank alert scope rows are migrated/backfilled to `ALL`.
  - Alert lookup returns only the requested asset scope plus shared `ALL` rules.
  - Alert dedupe key is effectively `alert_id + article_id + complex_id + asset_type + notified_on`.
  - `AlertSettingDialog` shows `단지명 (APT:cid)` / `단지명 (VL:cid)` and supports a shared `공통 적용(APT/VL)` rule.
- Complex task dedupe policy:
  - `CrawlerTab` now dedupes complex-mode tasks strictly by `cid`.
  - Manual add, DB/group/recent/URL/scheduled load all reuse the same dedupe path.
  - The first task name wins; later duplicates are skipped with a log/status message.
  - `start_crawling()` performs a final target normalization pass before creating `CrawlerThread`.
- Count consistency:
  - `_push_item()` returns `bool` and only successful pushes increment matched/finished counts.
  - Raw item, Selenium cache-hit, and DOM parse paths all align stats with the actual emitted result set.
- History and stats UX:
  - `complex` mode history explicitly stores `asset_type='APT'`.
  - History UI now exposes `asset_type`, `engine`, and `mode`.
  - Stats chart renders only for a single `(trade_type, pyeong)` series; otherwise it clears with guidance text.
- Packaging/docs hygiene:
  - `naverland-scrapper.spec` was rechecked on 2026-03-14 and still needs no extra hidden import/runtime hook changes.
  - `.gitignore` was rechecked and remains sufficient for build/log/data/Playwright outputs without new patterns.
- UI consistency:
  - Geo start path에서 `retry_on_error=False` => `max_retry_count=0`
- Validation: `pytest -q` => `112 passed`.
- Packaging recheck: `naverland-scrapper.spec`는 추가 hidden import/runtime hook 수정 없이 유지 가능.

## 0-13. v15.0.10 Functional Follow-up (2026-03-15)
- Asset-scoped article state:
  - `article_history`, `article_favorites` now use `(asset_type, article_id, complex_id)` as the effective key.
  - Startup migration creates a one-time DB backup before rebuilding legacy schemas.
  - Legacy blank `asset_type` values are normalized to `APT`.
- Disappeared / purge safety:
  - processed target scope is unified to `(asset_type, complex_id, trade_type)`.
  - purge/delete now applies asset-scoped predicates to `article_history`, `crawl_history`, `price_snapshots`, `alert_settings`, `article_favorites`, and `article_alert_log`.
- Favorite sync:
  - card view, favorites tab, recently viewed dialog, and result rebuilds all share `(asset_type, article_id, complex_id)` favorite keys.
  - direct card-view DB writes were removed in favor of the app-level favorite handler.
- Export semantics:
  - save menu is split into visible export vs raw export.
  - visible export reflects current search/filter/compact/sort state from the rendered result table.
  - raw export preserves the full `collected_data` payload.
- Scheduled execution:
  - schedule tab now supports `complex` and `geo_sweep`.
  - geo schedule stores lat/lon and reuses saved geo defaults for zoom/rings/step/dwell/asset_types.
  - scheduled geo runs no longer exclude `VL`.
- Geo runtime stats:
  - marker handling increments `geo_discovered_count` / `geo_dedup_count` in real time and emits stats immediately.
- `.spec` / `.gitignore` review:
  - `naverland-scrapper.spec` still requires no extra hidden import/runtime hook/data bundle changes for this pass.
  - `.gitignore` remains sufficient for build/log/data/backup/Playwright outputs without new patterns.
- Validation:
  - `python -m pytest -q` => `137 passed`

## 0-14. v15.0.11 Typing/Encoding Consistency Pass (2026-03-16)
- Workspace typing baseline:
  - added `pyrightconfig.json` and fixed the baseline command to `npx pyright` over `app_entry.py + src + tests`
  - current result: `0 errors`
  - mixin/dynamic-attribute/test-double type issues that surfaced in Pylance/Pyright were normalized
- Encoding baseline:
  - added `.editorconfig` and `.vscode/settings.json` to keep UTF-8 workspace defaults stable
  - removed remaining UTF-8 BOMs from Python/docs and repaired a corrupted comment string
- `.spec` / `.gitignore` follow-up:
  - `naverland-scrapper.spec` was rechecked on 2026-03-16 and still needs no extra hidden import/runtime hook/data bundle changes
  - `.gitignore` keeps existing build/log/data/backup/Playwright ignores and now explicitly allows `pyrightconfig.json` and `.vscode/settings.json`
- Validation:
  - `npx pyright` => `0 errors`
  - `python -m pytest -q` => `137 passed`

## 0-15. v15.0.12 Runtime Safety / Packaging Recheck (2026-03-16)
- Preflight contract:
  - `src/utils/preflight.py` now reads `data/settings.json` directly and computes the effective `crawl_engine`.
  - Missing Playwright Chromium is now a startup error only when the effective engine is `playwright`.
  - `NAVERLAND_SKIP_PLAYWRIGHT_BROWSER_CHECK` still skips the browser check entirely.
  - `NAVERLAND_REQUIRE_PLAYWRIGHT_BROWSER` still forces an error regardless of the effective engine.
- Geo incomplete safety:
  - `geo_incomplete_safety_mode` is a persisted setting and defaults to `true`.
  - Incomplete geo discovery now records explicit reasons (`marker switch fail`, `marker drain timeout`, `geo scan failure`).
  - When safety mode is on, geo incomplete runs skip auto-register, `crawl_history`, and disappeared marking.
  - When safety mode is off, geo incomplete runs can persist but use `run_status="incomplete"`.
- Data/UI contract:
  - `crawl_history` now has `run_status` and the history tab shows `mode -> status -> trade_types`.
  - Marker normalization now separates `complex_id` from `marker_id`; do not assume they are interchangeable.
  - Disappeared marking is skipped when there are zero successfully validated pairs.
- Packaging/docs:
  - `naverland-scrapper.spec` was rechecked after the runtime-safety rollout; no hidden import/runtime hook changes were required.
  - The default packaging profile remains `onedir + bundled Chromium`; slim builds still require either local Chromium or an explicit bundled-Chromium build when `playwright` is the effective engine.
- Validation:
  - `pytest -q` => `149 passed`

## 0-16. v15.0.14 Docs/Spec/Gitignore Consistency Pass (2026-03-17)
- Packaging baseline:
  - `naverland-scrapper.spec`의 실제 기본 프로필은 `onedir + Chromium bundle`.
  - `NAVERLAND_ONEFILE=1`에서만 onefile 생성.
- UI/module baseline:
  - `CardViewWidget`, `ArticleCard`는 `src/ui/widgets/cards.py` 소속.
  - `src/ui/widgets/dashboard.py`는 대시보드 집계/차트 위젯 전용.
  - `startup_lazy_noncritical_tabs`는 레거시 호환용 `False` 고정 키만 유지하고, 현재는 대시보드만 첫 진입 시 생성되며 history/stats/favorites는 hidden-tab stale refresh 정책으로 다음 진입 때 갱신됩니다.
- Performance baseline:
  - 대시보드는 통계 캐시 + 소멸 count TTL 캐시 + 지연 차트 캔버스 + 첫 탭 진입 시 위젯 생성 사용.
  - 일반 앱 시작은 lightweight preflight를 사용하고 `--preflight`는 full internal import smoke를 유지합니다.
  - 결과 렌더링은 행 검색 캐시 사전 구성, 로그 maximum block count, 카드 스타일 캐시를 사용.
- Ignore baseline:
  - `.gitignore`에 `.mypy_cache/`, `.ruff_cache/`, `.nox/`, `node_modules/`, `coverage.xml`를 추가해 로컬 개발 산출물 유입을 예방.

## 0-17. v15.0.15 Functional Reliability Update (2026-03-18)
- DB restore safety:
  - restore must stop both `crawler_tab` and `geo_tab` before replacing the SQLite file
  - if either shutdown fails, restore must abort and UI/timer state must recover cleanly
- URL parsing:
  - `NaverURLParser` is the canonical extractor for batch/manual URL registration
  - supported URL families include `new.land.naver.com/complexes/{id}` and `new.land.naver.com/houses/{id}?articleId=...`
- Monthly price snapshots:
  - schema now includes `price_metric` and `legacy_monthly`
  - `매매` / `전세` use `price_metric='price'`
  - `월세` stores paired rows for `deposit` and `rent`
  - default monthly stats/history queries read `rent` and exclude `legacy_monthly=1`
- Stats UI:
  - monthly stats expose a metric selector with default `rent`
  - switching to `deposit` redraws both table and chart from the selected metric only
- JSON runtime state:
  - `settings`, `presets`, `search_history`, `recently_viewed`, `crawl_cache` use atomic temp-write + `os.replace()`
  - malformed JSON is quarantined to `*.broken.<label>.*` and reloaded from defaults
- Geo scheduling / memory:
  - `schedule_config.geo` is the source of truth for scheduled geo runs
  - scheduled geo profile contains `lat`, `lon`, `zoom`, `rings`, `step_px`, `dwell_ms`, `asset_types`
  - manual Geo tab coordinates persist separately as `geo_last_lat` / `geo_last_lon`
  - scheduled runs must not overwrite the remembered manual coordinates
- Packaging / ignore review:
  - `naverland-scrapper.spec` was rechecked and still needs no extra hidden import/runtime hook/data bundle changes
  - `.gitignore` now ignores `*.json.tmp` and `*.json.broken.*` runtime artifacts
- Validation:
  - `pytest -q` => `176 passed`

## 0-18. v15.0.16 Functional Consistency Pass (2026-03-19)
- Article-open / recently-viewed contract:
  - article open is now routed through a single app-level handler
  - crawler result table double-click, crawler cards, recent-view dialog cards, and favorites-tab open all feed the same recently-viewed tracking path
  - `RecentlyViewedManager` now dedupes on `(asset_type, complex_id, article_id)` and respects `recently_viewed_count`
- Schedule contract:
  - scheduled runs now use a persisted slot model with a fixed 10-minute catch-up window
  - `schedule_config` stores `last_run_slot` and `last_run_at`
  - busy / invalid / no-target skips do not consume the slot, so retries can happen inside the same window
- Dashboard / settings contract:
  - `DashboardWidget.refresh()` explicitly clears stale cards/charts/trend text when `_data` is empty
  - `show_trend_analysis` now controls `trend_frame` visibility at runtime
  - trend text is a deterministic summary of total/new/up/down/disappeared + dominant trade type
  - `result_tab_mode` is deprecated and scrubbed from persisted settings; `startup_lazy_noncritical_tabs` remains a legacy no-op key while dashboard is still first-open lazy and history/stats/favorites use hidden-tab stale refresh
- Packaging / ignore / CI review:
  - `naverland-scrapper.spec` still needs no extra hidden imports/runtime hooks/data bundles for this batch
  - `.gitignore` current rules remain sufficient for PyInstaller/build/log/runtime artifacts; no new ignore patterns were needed
  - GitHub CI currently runs static checks and preflight only; tests are not executed there
- Validation:
  - `python -m pytest -q` => `182 passed`
  - `npx pyright` => `0 errors`

## 0-19. v15.0.17 Performance Refactor (2026-03-21)
- Compact live rendering:
  - `compact_duplicate_listings=True` 경로는 배치마다 전체 테이블을 다시 그리지 않고 `dirty key -> row` 증분 갱신을 사용합니다.
  - compact 신규 row는 실시간 수집 중 append 중심으로 반영하고, 전체 정렬 재구성은 사용자 정렬 변경이나 수집 완료 시점에만 수행합니다.
  - card view는 현재 보이는 경우에만 coalesced timer로 다시 그리며, table view에서는 hidden card refresh를 생략합니다.
- Favorites / app refresh policy:
  - `ComplexDatabase.get_favorite_keys()`가 경량 `(asset_type, article_id, complex_id)` 집합을 직접 반환합니다.
  - app-level favorite toggle은 crawler/geo 결과 전체 rebuild 대신 해당 key의 collected/card state만 갱신합니다.
  - `history`, `stats`, `favorites`, `dashboard`는 crawl/restore 이후 hidden 상태면 즉시 refresh하지 않고 stale로 표시한 뒤 다음 탭 진입 때 1회만 갱신합니다.
- Benchmarks / validation:
  - `scripts/perf_baseline.py`에 `compact_live_batches(3000/30)` 지표를 추가했습니다.
  - 2026-03-21 baseline: `compact_live_batches(3000/30) ~= 0.1572s`
  - Validation:
    - `python -m pytest tests/test_ui_wiring.py -q` => `47 passed`
    - `python -m pytest tests/test_performance_smoke.py -q` => `3 passed`

## 0-20. v15.0.18 Typing / Encoding / Smoke Consistency Pass (2026-03-25)
- Repo-wide typing baseline:
  - workspace 기준 `pyright`를 재실행해 새 `live_smoke.py`, 테스트 더블 monkeypatch, Windows registry helper 타입 오류를 정리했습니다.
  - 현재 기준 검증 명령은 `pyright`이며 결과는 `0 errors`입니다.
- Encoding baseline:
  - root `.md/.spec/.gitignore/.editorconfig/.vscode/settings.json/.github/workflows/ci.yml`까지 UTF-8/BOM/mojibake 스캔 대상으로 고정했습니다.
  - 2026-03-25 스캔 기준 실제 UTF-8 손상은 발견되지 않았습니다.
- Workspace / smoke baseline:
  - `.vscode/settings.json`은 `include/exclude/extraPaths/files.encoding`을 명시해 Pylance 범위를 `app_entry.py + src + tests`로 고정합니다.
  - `app_entry.py --live-smoke [--smoke-headless] [--smoke-url ...]`로 GUI 없이 Playwright 실사이트 경로를 점검할 수 있습니다.
  - 2026-03-25 headless smoke 결과:
    - `fin.land` 200
    - `new.land` 200
    - `m.land` -> `fin.land` map redirect
- Packaging / ignore review:
  - `naverland-scrapper.spec`는 이번 패스에서도 hidden import/runtime hook/data bundle 추가 수정이 필요하지 않았습니다.
  - `.gitignore`는 `pyright_report*.json`을 추가로 무시하고 `.vscode/settings.json`은 계속 추적합니다.
