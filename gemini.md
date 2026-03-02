# AI Context: Naver Real Estate Crawler Pro Plus (v15.0)

이 문서는 AI 에이전트가 프로젝트 작업 시 참조할 컨텍스트 정보입니다.

## 1. Project Overview
- **Name**: Naver Real Estate Crawler Pro Plus v15.0 (네이버 부동산 매물 크롤러)
- **Goal**: 네이버 부동산 매물 수집, 분석, 모니터링, 관리를 위한 데스크톱 앱
- **Key Features**: 
    - 다중 단지 크롤링 & 그룹 관리
    - 실시간 가격 추세 분석 & 시각화 (히스토그램, 파이차트)
    - Excel/CSV/JSON 내보내기 (템플릿 지원)
    - 카드 뷰/대시보드/즐겨찾기/최근 본 매물
    - 신규/가격 변동/소멸 매물 추적
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
- 모든 위젯 및 탭(`CrawlerTab`, `DatabaseTab`, `GroupTab`, `FavoritesTab`, `DashboardWidget` 등)에 `EmptyStateWidget`이 적용되었고, 인라인 QSS가 제거되었습니다.
- 다이얼로그 창(`AboutDialog`, `FilterDialog` 등)의 테마 일관성(HTML 및 색상 포함)이 향상되었습니다.

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

## 2. Technical Stack
- **Language**: Python 3.9+
- **GUI Framework**: `PyQt6` (Widgets, Core, Gui)
- **Web Automation**: 
    - `undetected-chromedriver` (동적 콘텐츠 & 우회)
    - `beautifulsoup4` (파싱)
    - `urllib` (API 호출)
    - `winreg` (Windows 레지스트리 기반 Chrome 버전 감지)
- **Data Storage**: 
    - **SQLite** (`data/complexes.db`): 메인 데이터 저장
    - **JSON**: 설정, 프리셋, 캐시, 히스토리
- **Visualization**: `matplotlib` (PyQt6 임베디드)
- **Build Tool**: `PyInstaller`
- **Distribution Profile**: `naverland-scrapper.spec` (기본 `onefile`, `NAVERLAND_ONEFILE=0` 시 `onedir`)
- **Optional**: `psutil` (메모리 모니터링), `plyer` (알림)

## 3. Architecture (v14.2 Modular)

> **IMPORTANT**: 코드베이스가 모놀리식에서 모듈화 아키텍처로 리팩토링됨

```
src/
├── main.py                     # 진입점
│
├── core/                       # 비즈니스 로직
│   ├── crawler.py              # CrawlerThread (QThread)
│   ├── database.py             # ConnectionPool, ComplexDatabase
│   ├── parser.py               # NaverURLParser (RetryHandler 적용)
│   ├── cache.py                # CrawlCache (TTL 기반)
│   ├── analysis.py             # MarketAnalyzer, ComplexComparator
│   ├── export.py               # DataExporter, ExcelTemplate
│   └── managers.py             # SettingsManager, FilterPresetManager, SearchHistoryManager, RecentlyViewedManager
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
│       ├── dashboard.py        # DashboardWidget, CardViewWidget, ArticleCard
│       ├── toast.py            # ToastWidget (애니메이션 알림)
│       ├── chart.py            # ChartWidget (matplotlib)
│       ├── tabs.py             # 탭 관련 위젯
│       ├── crawler_tab.py      # CrawlerTab (데이터 수집 탭)
│       ├── database_tab.py     # DatabaseTab (DB 관리 탭)
│       ├── group_tab.py        # GroupTab (그룹 관리 탭)
│       └── dialogs.py          # 위젯 수준 다이얼로그
│
└── utils/                      # 유틸리티
    ├── constants.py            # APP_TITLE, SHORTCUTS, TRADE_COLORS
    ├── helpers.py              # PriceConverter, AreaConverter, DateTimeHelper, ChromeParamHelper
    ├── logger.py               # get_logger()
    ├── paths.py                # DATA_DIR, DB_PATH, LOG_DIR
    ├── retry_handler.py        # RetryHandler (지수 백오프)
    ├── retry.py                # 재시도 유틸리티 (legacy)
    ├── error_handler.py        # NetworkErrorHandler
    └── plot.py                 # 차트 유틸리티
```

### 3.1 Key Classes

#### **Core Logic**
| 클래스 | 파일 | 설명 |
|--------|------|------|
| `CrawlerThread` | `crawler.py` | QThread 기반 크롤링, 메모리 관리 |
| `NaverURLParser` | `parser.py` | URL 파싱, RetryHandler로 API 호출 |
| `CrawlCache` | `cache.py` | TTL 기반 크롤링 결과 캐싱 |
| `MarketAnalyzer` | `analysis.py` | 가격 추세 분석 |
| `RetryHandler` | `retry_handler.py` | 지수 백오프 재시도 로직 |

#### **Database**
| 클래스 | 파일 | 설명 |
|--------|------|------|
| `ConnectionPool` | `database.py` | SQLite 커넥션 풀 (스레드 안전) |
| `ComplexDatabase` | `database.py` | CRUD, 즐겨찾기, 매물 이력 관리 |

#### **UI Components**
| 클래스 | 파일 | 설명 |
|--------|------|------|
| `RealEstateApp` | `app.py` | 메인 윈도우 (탭 관리 및 통합) |
| `CrawlerTab` | `crawler_tab.py` | 크롤링 UI 및 로직 |
| `DatabaseTab` | `database_tab.py` | DB 데이터 조회 및 관리 |
| `GroupTab` | `group_tab.py` | 단지 그룹핑 및 배치 관리 |
| `DashboardWidget` | `dashboard.py` | 통계 대시보드 |
| `CardViewWidget` | `dashboard.py` | 카드 형태 매물 표시 |
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
├── pytest.ini              # 테스트/플러그인 설정
├── README.md               # 사용자 문서
├── claude.md               # AI 컨텍스트 (Claude)
└── gemini.md               # 이 파일 (AI 컨텍스트)
```

## 6. Style Guide (v14.2)

### Color Palette
```python
# Dark Theme (Warm Glassmorphism)
COLORS["dark"] = {
    "accent": "#f59e0b",          # Warm Amber
    "accent_hover": "#d97706",    # Darker Amber
    "bg_primary": "#0f0f1a",      # Deep dark
    "bg_card": "rgba(30, 30, 40, 0.85)",  # Glassmorphism
    "success": "#22c55e",
    "warning": "#f59e0b",
    "error": "#ef4444",
}

# Light Theme (Clean & Modern)
COLORS["light"] = {
    "accent": "#0ea5e9",          # Sky Blue
    "accent_hover": "#0284c7",    
    "bg_primary": "#f8fafc",      
    "bg_card": "rgba(255, 255, 255, 0.9)",
    "border": "#e2e8f0",          # Slate border
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
