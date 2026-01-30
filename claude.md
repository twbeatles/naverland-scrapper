# AI Context: Naver Real Estate Crawler Pro Plus (v14.0)

이 문서는 AI 에이전트가 프로젝트 작업 시 참조할 컨텍스트 정보입니다.

## 1. Project Overview
- **Name**: Naver Real Estate Crawler Pro Plus v14.0 (네이버 부동산 매물 크롤러)
- **Goal**: 네이버 부동산 매물 수집, 분석, 모니터링, 관리를 위한 데스크톱 앱
- **Key Features**: 
    - 다중 단지 크롤링 & 그룹 관리
    - 실시간 가격 추세 분석 & 시각화 (히스토그램, 파이차트)
    - Excel/CSV/JSON 내보내기 (템플릿 지원)
    - 카드 뷰/대시보드/즐겨찾기/최근 본 매물
    - 신규/가격 변동/소멸 매물 추적
    - **Modern UI - Glassmorphism Dark/Light 테마**
    - Toast 알림 (페이드 인/아웃 애니메이션)
    - 강력한 에러 핸들링 (RetryHandler, Rate limit 감지)
    - 메모리 관리 (임계치 초과 시 드라이버 재시작)

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
- **Optional**: `psutil` (메모리 모니터링), `plyer` (알림)

## 3. Architecture (v14.0 Modular)

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
├── data/                   # 데이터 저장
│   ├── complexes.db        # SQLite 데이터베이스
│   ├── settings.json       # 사용자 설정
│   ├── presets.json        # 필터 프리셋
│   ├── search_history.json # 최근 검색 기록
│   ├── crawl_cache.json    # 크롤링 캐시
│   └── recently_viewed.json # 최근 본 매물
├── logs/                   # 로그 파일
├── backup/legacy/          # 레거시 단일 파일
├── README.md               # 사용자 문서
├── claude.md               # 이 파일 (AI 컨텍스트)
└── gemini.md               # AI 컨텍스트 (Gemini)
```

## 6. Style Guide (v14.0)

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
