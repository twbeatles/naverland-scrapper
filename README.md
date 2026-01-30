# 🏠 네이버 부동산 매물 크롤러 Pro Plus (v14.0)

네이버 부동산의 아파트 매물 정보를 수집, 분석, 관리할 수 있는 **강력한 데스크톱 애플리케이션**입니다.

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![PyQt6](https://img.shields.io/badge/PyQt6-GUI-green.svg)](https://pypi.org/project/PyQt6/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ 주요 기능

### 🆕 v14.0 신규 기능 (UI/UX Revolution)
- **🎨 Glassmorphism 테마**: 반투명 배경, 그라디언트 버튼, Warm Amber 악센트 컬러
- **☀️ 완전한 Light 테마**: Tailwind CSS 색상 팔레트 기반, Sky Blue 악센트 컬러
- **🎬 Toast 알림 시스템**: 페이드 인/아웃 애니메이션, 슬라이드 효과, 호버 시 일시정지
- **🔧 모듈화된 아키텍처**: `src/` 디렉토리 기반 깔끔한 코드 구조
- **⚡ 최적화된 스크롤**: 컨텐츠 변화 감지 기반 동적 스크롤링
- **🛡️ 메모리 관리**: 임계치 초과 시 드라이버 자동 재시작

### 📊 분석 기능 (v13.0)
- **시세 분석 대시보드**: 통계 카드, 파이차트, 히스토그램
- **트렌드 분석**: 주간/월간 가격 추이 분석
- **카드 뷰 모드**: 시각적인 매물 카드 표시
- **즐겨찾기**: 관심 매물 저장 및 메모 관리
- **가격 변동 추적**: 동일 매물의 가격 변화 감지 (📈/📉 표시)
- **신규 매물 배지**: 오늘 처음 발견된 매물에 NEW 배지 표시
- **최근 본 매물**: 최근 열람 기록 자동 저장

### 🔒 안정성 (v13.0)
- **자동 재시도**: 네트워크 오류 시 지수 백오프 (RetryHandler)
- **Rate Limit 감지**: 차단 방지 자동 대기
- **드라이버 자동 재시작**: 메모리 누수 방지 (500MB 임계치)
- **Chrome 버전 자동 감지**: 설치된 Chrome 버전 감지 및 호환 드라이버 사용
- **Connection Pool**: 스레드 안전한 SQLite 연결 관리

### 💡 핵심 기능
- 다중 단지 동시 크롤링 & 그룹 관리
- 실시간 필터링 (가격/면적) + 고급 필터 (층수/키워드/신규/가격변동)
- Excel/CSV/JSON 내보내기 (템플릿 지원)
- SQLite 로컬 DB 저장 및 이력 관리
- URL 일괄 등록 (텍스트에서 자동 추출)
- 고급 필터링 (가격/면적 범위, 층수, 키워드)
- 매물 소멸 추적 (마지막 확인 이후 자동 표시)

---

## 🛠 설치 및 실행

### 1. 요구 사항
- Windows 10/11
- Python 3.9+
- Google Chrome 최신 버전

### 2. 라이브러리 설치
```bash
pip install PyQt6 undetected-chromedriver beautifulsoup4 openpyxl matplotlib plyer psutil
```
> `psutil`은 선택 사항입니다. 미설치 시 드라이버 재시작은 단지 수 기준으로 동작합니다.

### 3. 실행
```bash
# 모듈 방식 실행 (권장)
python -m src.main

# 또는 직접 실행
python src/main.py
```

---

## 📂 프로젝트 구조

```
naverland-scrapper/
├── src/                            # 소스 코드 (v14.0 모듈화)
│   ├── __init__.py
│   ├── main.py                     # 앱 진입점
│   │
│   ├── core/                       # 핵심 비즈니스 로직
│   │   ├── crawler.py              # CrawlerThread (QThread 기반 크롤링)
│   │   ├── database.py             # ConnectionPool, ComplexDatabase
│   │   ├── parser.py               # NaverURLParser (RetryHandler 적용)
│   │   ├── cache.py                # CrawlCache (TTL 기반 캐싱)
│   │   ├── analysis.py             # MarketAnalyzer, ComplexComparator
│   │   ├── export.py               # DataExporter, ExcelTemplate
│   │   └── managers.py             # SettingsManager, FilterPresetManager
│   │
│   ├── ui/                         # 사용자 인터페이스
│   │   ├── app.py                  # RealEstateApp (QMainWindow)
│   │   ├── styles.py               # 테마 스타일시트 (Dark/Light)
│   │   │
│   │   ├── dialogs/                # 다이얼로그 모음
│   │   │   ├── preset.py           # PresetDialog
│   │   │   ├── settings.py         # SettingsDialog, AlertSettingDialog, ShortcutsDialog
│   │   │   ├── filter.py           # AdvancedFilterDialog, MultiSelectDialog
│   │   │   ├── batch.py            # URLBatchDialog
│   │   │   ├── excel.py            # ExcelTemplateDialog
│   │   │   ├── search.py           # RecentSearchDialog
│   │   │   └── common.py           # AboutDialog
│   │   │
│   │   └── widgets/                # UI 컴포넌트
│   │       ├── components.py       # SearchBar, SpeedSlider, SummaryCard 등
│   │       ├── dashboard.py        # DashboardWidget, CardViewWidget, ArticleCard
│   │       ├── toast.py            # ToastWidget (애니메이션 알림)
│   │       ├── chart.py            # ChartWidget (matplotlib)
│   │       ├── tabs.py             # 탭 관련 위젯
│   │       ├── crawler_tab.py      # CrawlerTab (데이터 수집 탭)
│   │       ├── database_tab.py     # DatabaseTab (DB 관리 탭)
│   │       ├── group_tab.py        # GroupTab (그룹 관리 탭)
│   │       └── dialogs.py          # 위젯 수준 다이얼로그
│   │
│   └── utils/                      # 유틸리티
│       ├── constants.py            # APP_TITLE, SHORTCUTS, TRADE_COLORS
│       ├── helpers.py              # PriceConverter, AreaConverter, DateTimeHelper
│       ├── logger.py               # get_logger()
│       ├── paths.py                # DATA_DIR, DB_PATH, LOG_DIR
│       ├── retry_handler.py        # RetryHandler (지수 백오프)
│       ├── retry.py                # 재시도 유틸리티
│       ├── error_handler.py        # NetworkErrorHandler
│       └── plot.py                 # 차트 유틸리티
│
├── data/                           # 데이터 저장소
│   ├── complexes.db                # SQLite 데이터베이스
│   ├── settings.json               # 사용자 설정
│   ├── presets.json                # 필터 프리셋
│   ├── search_history.json         # 최근 검색 기록
│   ├── crawl_cache.json            # 크롤링 캐시
│   └── recently_viewed.json        # 최근 본 매물
│
├── logs/                           # 로그 파일
├── backup/                         # 백업 파일
│   └── legacy/                     # 레거시 단일 파일
│
├── README.md                       # 이 문서
├── claude.md                       # AI 컨텍스트 (Claude)
├── gemini.md                       # AI 컨텍스트 (Gemini)
└── naverland_crawler.spec          # PyInstaller 빌드 설정
```

---

## 📖 상세 사용 가이드

### 1. 단지 등록

#### 방법 1: URL 등록 (권장)
1. 네이버 부동산에서 원하는 아파트 상세 페이지로 이동
2. 브라우저 주소창의 URL 복사 (예: `https://land.naver.com/...`)
3. `[URL등록]` 버튼 클릭
4. URL 붙여넣기 후 확인

#### 방법 2: 직접 입력
1. 단지명과 단지ID를 직접 입력
2. 단지ID는 네이버 부동산 URL에서 확인 가능

#### 방법 3: URL 일괄 등록
1. `URL등록` 버튼 클릭
2. 여러 URL이나 단지ID가 포함된 텍스트 붙여넣기
3. 자동으로 추출되어 일괄 등록

#### 방법 4: 그룹으로 관리
1. `그룹` 탭에서 새 그룹 생성
2. DB 탭에서 저장된 단지들을 그룹에 추가
3. 그룹 단위로 한번에 불러오기/크롤링 가능

### 2. 크롤링 실행

#### 기본 크롤링
1. 크롤러 탭에서 대상 단지 선택 (체크박스)
2. 거래유형 선택: `매매`, `전세`, `월세` (중복 선택 가능)
3. 속도 조절: `빠름` / `보통` (권장) / `느림`
4. `[▶ 크롤링 시작]` 버튼 또는 `Ctrl+R`

#### 필터 설정
- **면적 필터**: 최소/최대 평수 지정
- **가격 필터**: 매매가/보증금/월세 범위 지정
- **고급 필터**: 층수(저/중/고), 키워드 포함/제외

### 3. 결과 분석

#### 테이블 뷰
- 모든 수집 결과를 테이블 형태로 표시
- 컬럼 헤더 클릭으로 정렬
- 검색창에서 실시간 필터링
- 더블클릭으로 매물 상세페이지 열기

#### 카드 뷰
- 시각적인 카드 형태로 매물 표시
- 거래유형별 색상 구분 (매매: 빨강, 전세: 초록, 월세: 파랑)
- 가격 변동 표시 (📈 상승 / 📉 하락)
- NEW 배지로 신규 매물 표시

#### 대시보드
- **통계 카드**: 전체/신규/가격 상승/가격 하락/소멸 매물 수
- **파이차트**: 거래유형별 비율
- **히스토그램**: 가격대별 분포

### 4. 즐겨찾기 & 메모

1. 결과 테이블/카드에서 관심 매물 선택
2. `⭐ 즐겨찾기` 버튼 클릭
3. 메모 추가 (선택사항)
4. `즐겨찾기` 탭에서 저장된 매물 관리

### 5. 데이터 저장

#### Excel 저장 (`Ctrl+S`)
- 서식이 적용된 엑셀 파일로 저장
- 템플릿 설정으로 원하는 컬럼만 선택/순서 변경 가능

#### CSV 저장 (`Ctrl+Shift+S`)
- 간단한 쉼표 구분 형식으로 저장

#### JSON 저장
- 개발자용 데이터 형식

### 6. 스케줄링 (예약 크롤링)

1. `스케줄` 탭에서 예약 시간 설정
2. 대상 단지와 거래유형 선택
3. 활성화 후 지정된 시간에 자동 실행

---

## ⌨️ 단축키

| 기능 | 단축키 |
|:-----|:-------|
| 크롤링 시작 | `Ctrl+R` |
| 크롤링 중지 | `Ctrl+Shift+R` |
| Excel 저장 | `Ctrl+S` |
| CSV 저장 | `Ctrl+Shift+S` |
| 검색 | `Ctrl+F` |
| 테마 변경 | `Ctrl+T` |
| 트레이 최소화 | `Ctrl+M` |
| 새로고침 | `F5` |
| 종료 | `Ctrl+Q` |

---

## 🎨 테마

### Dark Theme (Warm Glassmorphism)
- **배경**: 반투명 Glassmorphism (#0f0f1a, rgba(30, 30, 40, 0.85))
- **악센트**: Warm Amber (#f59e0b)
- **그라디언트 버튼**: 시작 버튼에 적용
- **부드러운 전환 효과**

### Light Theme (Clean & Modern)
- **배경**: 밝고 깔끔한 디자인 (#f8fafc, #ffffff)
- **악센트**: Sky Blue (#0ea5e9)
- **Tailwind CSS 색상 팔레트**
- **부드러운 그림자와 테두리**

### 거래유형별 색상
| 거래유형 | Dark 테마 | Light 테마 |
|:---------|:----------|:-----------|
| 매매 | #ef4444 | #dc2626 |
| 전세 | #22c55e | #16a34a |
| 월세 | #3b82f6 | #2563eb |

---

## ⚙️ 설정

### 알림 설정
- **가격 알림**: 관심 단지의 특정 가격 이하 매물 등장 시 알림
- **신규 매물 알림**: 새로운 매물 등록 시 알림 (plyer 라이브러리 필요)

### 캐시 설정
- **TTL 설정**: `data/settings.json`의 `cache_ttl_minutes`로 조절
- **캐시 사용 여부**: `cache_enabled`로 on/off

### 단축키 설정
- 단축키 목록 확인 가능
- `도움말 > 단축키`에서 확인

---

## ⚠️ 주의사항

- **네이버 차단 주의**: 과도한 속도 사용 시 일시 차단 가능. '보통' 속도 권장.
- **개인용도 전용**: 수집 데이터의 상업적 이용 책임은 사용자에게 있습니다.
- **Chrome 필수**: undetected-chromedriver는 Chrome 브라우저가 필요합니다.
- **메모리 관리**: 장시간 크롤링 시 자동 드라이버 재시작 기능 활성화됨

---

## 📝 버전 히스토리

| 버전 | 주요 변경사항 |
|:-----|:-------------|
| v14.0 | UI/UX 전면 개편 (Glassmorphism, Light 테마, Toast 애니메이션), 모듈화 아키텍처, 메모리 최적화 |
| v13.0 | 대시보드, 카드뷰, 즐겨찾기, 재시도 핸들러, Connection Pool |
| v12.0 | 크롤링 캐시, 평당가 표시, 매물 소멸 추적 |
| v7.3 | 가격 변동 알림, 신규 매물 배지, 고급 필터링, 엑셀 템플릿 |
| v7.2 | DB 경로 안정성, 복원 기능 강화 |
| v7.1 | 결과 요약 카드, ETA 표시, 검색 기록, 정렬 옵션 |

---

## 🤝 기여

이 프로젝트는 **Claude Opus 4** 및 **Gemini 2.5 Pro**를 활용하여 개발되었습니다.

---

## 📄 라이센스

MIT License - 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.
