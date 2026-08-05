# Naverland Scrapper Pro Plus

네이버 부동산(Npay / `new.land` / `fin.land`) 매물을 자동으로 수집하고, 가격 이력을 추적하며, 알림과 대시보드 분석을 제공하는 데스크톱 앱입니다.

버전: **v15.0** (`src/utils/version.py`)

UI: **PyQt6 + PyQt6-Fluent-Widgets** (좌측 네비게이션, 기본/고급 설정 분리)

---

## 주요 기능

### 매물 수집

- **단지 수집**: 아파트·빌라/연립 등 자산 유형별 매물 수집 (네비: **매물 수집**)
- **지도 기반 수집**: 좌표·범위로 주변 단지를 찾아 수집 (네비: **지도로 찾기**)
- **상세 정보 보강**: 중개사 연락처, 기전세·갭 등 (설정에서 on/off·단지당 한도)
- **빠른 목록 조회**: Article API 다중 페이지 + 실패 시 브라우저 응답 캡처 fallback
- **전역 수집 락**: 매물 수집·지도 탐색·예약 수집이 동시에 돌지 않도록 상호 배제

### 가격 이력 및 알림

- **가격 스냅샷**: 수집할 때마다 일별 가격 기록을 자동 저장
- **가격 변동 알림**: 등록한 매물의 가격 변동 시 알림 제공
- **사라진 매물 추적**: 이전에 수집됐다가 삭제된 매물을 별도로 표시

### 결과 보기 및 분석

- **세 가지 뷰 모드**: 테이블 / 묶기(컴팩트) / 카드
- **표시 항목**: 확인일·동·타입명 등 확장 컬럼 (기본 숨김, DB 미저장)
- **대시보드**: 가격 분포·평형 통계 등 (첫 진입 시 로드)
- **즐겨찾기·단지 묶음·예약 수집·수집 기록·가격 통계**

### 화면 구성 (Fluent 네비)

| 그룹 | 페이지 |
|------|--------|
| 수집 | 매물 수집, 지도로 찾기 |
| 보관함 | 내 단지, 단지 묶음, 즐겨찾기 |
| 분석 | 대시보드, 가격 통계, 수집 기록 |
| 자동화 | 예약 수집 |
| 하단 | 가이드, 설정 |

---

## 설치

Python 3.9 이상이 필요합니다. (개발·CI는 3.11+ 환경을 권장합니다.)

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
playwright install chromium
```

---

## 실행

```powershell
python app_entry.py
```

앱이 실행되면 GUI 창이 열립니다. 수집하려는 단지 번호나 지도 영역을 지정한 뒤 수집을 시작하면 됩니다.

부가 실행 예:

```powershell
python app_entry.py --preflight
python app_entry.py --live-smoke --smoke-headless --live-smoke-detail-fields
python -m pytest -q
```

---

## 주요 설정

앱 내 **설정**은 **기본** / **고급** 두 탭으로 나뉩니다. 일상 사용은 기본 탭만으로 충분합니다.

| 설정 항목 | 기본 | 위치 | 설명 |
|---|---|---|---|
| 테마 | 어두운 테마 | 기본 | Fluent 다크/라이트 |
| 수집 속도 | 보통 | 기본 | 너무 빠르면 차단될 수 있음 |
| 분양권 매물 포함 | 끔 | 기본 | 목록 건수가 늘 수 있음 |
| 중개사·기전세 상세 조회 | 켬 | 기본 | 끄면 수집이 훨씬 가벼움 |
| 같은 매물 묶어 보기 | 켬 | 기본 | 결과 표 중복 축소 |
| 수집 엔진 | Playwright (권장) | 고급 | Selenium은 보조·fallback |
| 상세 정보 보완 조회 | 켬 | 고급 | 상세 페이지가 비어도 중개 정보 보충 |
| 단지마다 상세 조회 한도 | 제한 없음 | 고급 | 대형 단지 부하 제한용 |
| 목록 페이지 사이 대기 | 150ms | 고급 | 연속 요청 완화 (429) |
| 빠른 목록 조회 | 켬 | 고급 | API로 목록을 먼저 가져옴 |
| 표 표시 항목(확인일·동 등) | 숨김 | 고급 | 결과「더보기」또는 설정→고급 |
| 대시보드 | 첫 진입 시 로드 | — | 시작 속도 향상 |

> **라이선스 참고**: UI 라이브러리 `PyQt6-Fluent-Widgets`는 GPLv3(비상업)입니다. 상용 배포 시 별도 라이선스를 확인하세요.

---

## 배포 파일 빌드 (선택)

소스 없이 실행 가능한 단독 배포 파일을 만들 수 있습니다. 스펙: `naverland-scrapper.spec`

```powershell
python -m PyInstaller --clean --noconfirm naverland-scrapper.spec
```

빌드 옵션:

| 환경 변수 | 설명 |
|---|---|
| `NAVERLAND_ONEFILE=1` | 단일 실행 파일로 빌드 |
| `NAVERLAND_BUNDLE_CHROMIUM=0` | Chromium 제외 (용량 절감, 별도 브라우저 필요) |
| `NAVERLAND_CONSOLE=1` | 콘솔 창 함께 표시 |

기본 빌드는 Chromium이 포함된 폴더 형태(`onedir`, 출력: `dist/naverland/`)로 생성됩니다.

---

## 데이터 저장 위치

모든 수집 데이터와 가격 이력은 앱 폴더 내 SQLite 파일(`data/`)에 로컬 저장됩니다. 외부 서버로 데이터가 전송되지 않습니다.  
환경 변수 `NAVERLAND_DATA_DIR` 로 데이터 루트를 바꿀 수 있습니다.

---

## 문서

| 문서 | 설명 |
|---|---|
| [docs/NAVER_LAND_SURVEY_2026-08-04.md](docs/NAVER_LAND_SURVEY_2026-08-04.md) | Npay/`new.land`/`fin.land` 사이트·API 조사 및 반영 체크리스트 |
| [PROJECT_AUDIT.md](PROJECT_AUDIT.md) | 기능 구현 감사 및 수정 이력 |
| [update_history.md](update_history.md) | 버전별 변경 요약 |

에이전트 전용 문서(`CLAUDE.md`, `AGENTS.md`, `gemini.md` 등)는 저장소에서 추적하지 않습니다 (`.gitignore`). 제품 문서는 본 README, `docs/`, `PROJECT_AUDIT.md`, `update_history.md` 를 따릅니다.

패키징 시 `naverland-scrapper.spec`이 `qfluentwidgets` / `qframelesswindow` 서브모듈을 hidden import로 수집합니다.
