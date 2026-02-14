# Functional Implementation Risk Review (2026-02-14)

## Scope
- Referenced docs: `README.md`, `claude.md` (and `update_history.md` as needed)
- Focus: "runtime/functionality blockers" (앱 실행/핵심 기능이 실제로 깨지는 요소)
- Commands executed (local):
  - `python -m compileall -q src`
  - `python -m pytest -q`
  - "import smoke test" (pkgutil 기반 전 모듈 import 시도)

## Results Summary
- `README.md` 실행 가이드 기준 엔트리포인트는 `python -m src.main` / `python src/main.py` 이고, 정책은 Python 3.9+ 입니다.
- 정적 점검에서는 `compileall`, `pytest`, 전 모듈 import 스모크 테스트(pkgutil 기반)가 모두 통과합니다.
- 추가 런타임 스모크 테스트(RealEstateApp 인스턴스 생성)를 통해 “import/test는 통과하지만 실제 실행은 깨지는” 문제를 발견했고, 2026-02-14 기준으로 **앱 인스턴스 생성까지 통과하도록 수정 완료**했습니다.

## Evidence (Command Snapshot)
- `python -m compileall -q src`: SUCCESS (exit 0)
- `python -m pytest -q`: `14 passed`
- import smoke test (pkgutil 기반): `failures=0`

## Fix Status (2026-02-14)
- Implemented fixes in working tree:
  - [x] `src/ui/app.py` DB import fixed (`ComplexDatabase`)
  - [x] `src/ui/app.py` stylesheet import fixed (`src.ui.styles.get_stylesheet`)
  - [x] preflight internal import smoke test added (`src/utils/preflight.py`)
  - [x] pytest guard added for UI importability (`tests/test_ui_import.py`)
  - [x] `src/ui/widgets/crawler_tab.py` 누락 import 보강 (`QGridLayout`, `QComboBox`)
  - [x] `src/ui/widgets/database_tab.py` 누락 import 보강 (`QLabel`)
  - [x] `src/ui/widgets/crawler_tab.py` CardViewWidget 생성자 시그니처 불일치 수정 (`theme=` -> `is_dark=`)
  - [x] `src/ui/app.py` 런타임 누락 import 보강 (`ChartWidget`, `SortableTableWidgetItem`, `PriceConverter`, `URLBatchDialog`)
  - [x] `src/ui/app.py` 단축키 핸들러(시작/중지/저장/검색) 위임 래퍼 추가 및 `_focus_search` 수정
  - [x] `src/ui/app.py`에서 `_init_timers()`/`_load_initial_data()`를 `__init__` 실행 흐름에 연결
  - [x] `src/ui/app.py` 누락 메서드 `_restore_window_geometry()` 추가 (스타트업 AttributeError 방지)
  - [x] `src/core/parser.py`가 `/complexes/<id>` URL을 파싱하도록 패턴 추가 + 테스트 보강
  - [x] 런타임 UI 스모크 테스트 추가 (`tests/test_ui_runtime_smoke.py`)
- Verification after fixes:
  - `python -c "import src.ui.app"`: SUCCESS
  - preflight (`run_preflight_checks`): `preflight_ok True`
  - import smoke test (pkgutil 기반): `failures=0`
  - `python -m pytest -q`: `14 passed`
  - `python -m unittest discover -s tests -p "test_*.py"`: `15 tests OK`

## Evidence (Runtime Smoke Tests)
### 1) RealEstateApp 인스턴스 생성 스모크 테스트 (실제 런타임 진입)
- Repro
  - `python -c "from PyQt6.QtWidgets import QApplication; app=QApplication([]); from src.ui.app import RealEstateApp; RealEstateApp(); print('INSTANTIATE_OK')"`
- Result
  - 2026-02-14 (수정 후): `INSTANTIATE_OK`
  - (참고: 수정 전에는 `QGridLayout`, `QComboBox` 등의 누락 import 및 기타 런타임 오류로 `RealEstateApp()` 생성이 중단될 수 있었음)

### 2) 핵심 위젯 단독 생성 스모크 테스트 (db 주입)
- Repro (요약: `QT_QPA_PLATFORM=offscreen` + `ComplexDatabase(':memory:')` + 위젯 생성)
- Result
  - 수정 전: `CrawlerTab(db)`/`DatabaseTab(db)`에서 누락 import로 NameError 가능
  - 수정 후: `RealEstateApp()` 인스턴스 생성 스모크 테스트 통과(위 Evidence 1 참고)

### 3) URL 파서 스모크 테스트 (사용자 입력 URL 형태)
- Repro
  - `python -c "from src.core.parser import NaverURLParser; print(NaverURLParser.extract_complex_id('https://new.land.naver.com/complexes/123456'))"`
- Result
  - 2026-02-14 (수정 후): `123456` (추출 성공)
  - `complexNo=...`, `land.naver.com/complex/...` 형태도 기존대로 추출 성공

## Additional Deep-Dive Findings (2026-02-14)
아래 이슈들은 “import/test는 통과하지만 실제 앱 실행(또는 기능 클릭)에서 깨지는 지점” 위주로 정리했습니다.

### Finding 1 (Critical): 앱이 실제 실행 경로에서 바로 크래시 (CrawlerTab NameError)
- 증상
  - `RealEstateApp()` 생성 중 `CrawlerTab` 초기화에서 크래시
- 재현
  - `python -c "from PyQt6.QtWidgets import QApplication; app=QApplication([]); from src.ui.app import RealEstateApp; RealEstateApp()"`
- 원인 (file:line)
  - `src/ui/widgets/crawler_tab.py:140` `price_grid = QGridLayout()`
  - `src/ui/widgets/crawler_tab.py:1`의 `from PyQt6.QtWidgets import (...)`에 `QGridLayout` 누락
- 영향
  - `python -m src.main`로 앱이 시작되지 않음 (실사용 불가)
- 권장 조치
  - [x] `src/ui/widgets/crawler_tab.py`에 `QGridLayout` import 추가
  - [x] 재검증: `RealEstateApp()` 인스턴스 생성 스모크 테스트 성공 확인

### Finding 2 (Critical): DatabaseTab도 NameError로 탭 렌더링 실패 가능
- 증상
  - `DatabaseTab` 초기화 중 NameError 가능
- 원인 (file:line)
  - `src/ui/widgets/database_tab.py:63`에서 `QLabel(...)` 사용
  - `src/ui/widgets/database_tab.py:1`의 `from PyQt6.QtWidgets import (...)`에 `QLabel` 누락
- 영향
  - CrawlerTab 문제를 고쳐도, 다음 단계에서 DB 탭 생성 시 앱이 크래시할 수 있음
- 권장 조치
  - [x] `src/ui/widgets/database_tab.py`에 `QLabel` import 추가

### Finding 3 (High): RealEstateApp 단축키 바인딩이 현재 모듈화 구조와 불일치
- 근거 (file:line)
  - `src/ui/app.py:295-303`에서 `QShortcut(..., self._start_crawling)` 등 바인딩
  - 하지만 `src/ui/app.py`에는 `_start_crawling`, `_stop_crawling`, `_save_excel`, `_save_csv`가 **구현되어 있지 않음**
    - 관련 주석: `src/ui/app.py:340-342` (obsolete 메서드 목록)
  - `src/ui/app.py:985-986` `_focus_search()`가 `self.result_search`를 사용하지만, 검색바는 `CrawlerTab` 내부에 존재 (`crawler_tab.result_search`)
- 영향
  - (CrawlerTab/DatabaseTab NameError 해결 후) `_init_shortcuts()` 실행 시점에 AttributeError로 앱 시작이 막히거나, 단축키가 동작하지 않음
  - `README.md`의 단축키/내보내기 사용 가이드와 불일치 (예: Ctrl+R, Ctrl+S, Ctrl+F 등)
- 권장 조치
  - [x] 단축키 핸들러를 “탭 위임 래퍼”로 정리: `self.crawler_tab.start_crawling()` 등으로 위임하는 메서드를 `RealEstateApp`에 추가
  - [x] `Ctrl+F`는 `self.tabs.setCurrentWidget(self.crawler_tab)` 후 `self.crawler_tab.result_search`에 포커스 주도록 수정

### Finding 4 (High): 통계/차트 경로에서 NameError 가능 (미import 심볼 사용)
- 근거 (file:line)
  - `src/ui/app.py:103`에서 `_setup_stats_tab()` 호출
  - `src/ui/app.py:197`에서 `ChartWidget()` 사용 (import 없음)
  - `src/ui/app.py:474-476`에서 `SortableTableWidgetItem` 사용 (import 없음)
  - `src/ui/app.py:704/811/857`에서 `PriceConverter` 사용 (import 없음)
- 영향
  - (앞선 크래시를 해결하더라도) 통계/차트 탭 초기화 또는 관련 기능 클릭 시 NameError로 크래시할 가능성 큼
- 권장 조치
  - [x] `src/ui/app.py`에 누락 import 추가
    - `ChartWidget` -> `src/ui/widgets/chart.py`
    - `SortableTableWidgetItem` -> `src/ui/widgets/components.py`
    - `PriceConverter` -> `src/utils/helpers.py`

### Finding 5 (Medium): 예약 크롤링/초기 데이터 로딩이 실행 흐름에서 호출되지 않음
- 근거 (file:line)
  - `src/ui/app.py:316` `_init_timers` 정의
  - `src/ui/app.py:321` `_load_initial_data` 정의
  - 하지만 `src/ui/app.py:71-74`의 `__init__` 실행 흐름에서 위 두 함수가 호출되지 않음
    - `_load_initial_data()` 호출은 `src/ui/app.py:957` (DB 복구 흐름)에서만 확인
- 영향
  - “기능은 코드에 있는데 동작하지 않는” 상태: 스케줄 타이머/초기 로딩/콤보박스 갱신 등이 누락될 수 있음
- 권장 조치
  - [x] `RealEstateApp.__init__`에서 `_init_timers()` 및 `_load_initial_data()` 호출

### Finding 6 (Medium): URLBatchDialog 사용 지점이 미import 상태일 수 있음
- 근거 (file:line)
  - `src/ui/app.py:884`에서 `URLBatchDialog(self)` 사용
  - 그러나 `src/ui/app.py` 상단 import에서 `URLBatchDialog`가 import 되지 않음 (동일 심볼은 `src/ui/widgets/dialogs.py` 및 `src/ui/dialogs/batch.py`에 존재)
- 영향
  - 해당 메뉴/버튼 동작 시 NameError로 크래시 가능
- 권장 조치
  - [x] `src/ui/app.py`에서 `URLBatchDialog`를 명시적으로 import

### Finding 7 (Medium): NaverURLParser가 흔한 URL 형태(`/complexes/<id>`)를 파싱하지 못함
- 근거 (file:line)
  - `src/core/parser.py:13` `NaverURLParser.PATTERNS`에 `new.land.naver.com/complexes/<id>` 경로 패턴이 없음
  - 스모크 테스트 결과: `https://new.land.naver.com/complexes/123456` -> `None` (추출 실패)
- 영향
  - URL 일괄 등록/붙여넣기에서 사용자가 복사한 URL 형태에 따라 단지 ID 추출이 실패할 수 있음
- 권장 조치
  - [x] `PATTERNS`에 `r'new\\.land\\.naver\\.com/complexes/(\\d+)'` 추가 + 테스트 보강

## Recommended Fix Order (Next Steps)
1. (Startup blocker) `CrawlerTab`의 `QGridLayout` import 누락 해결
2. (Startup blocker) `DatabaseTab`의 `QLabel` import 누락 해결
3. (Startup blocker 가능) `RealEstateApp` 단축키 핸들러 정리: 누락 메서드 추가 또는 탭 위임으로 일원화
4. (Startup/feature blocker) 통계/차트 관련 심볼 import 누락 해결
5. (Behavior gap) `_init_timers()`/`_load_initial_data()` 호출 경로를 `__init__`에 연결
6. (Feature crash) `URLBatchDialog` 미import 정리 및 `NaverURLParser` 패턴 보강
7. (Guardrail) `QApplication + RealEstateApp()` 스모크 테스트를 CI에 추가해 런타임 NameError를 조기 차단

## Findings

### 1) Critical: 애플리케이션이 시작 단계에서 ImportError로 중단될 수 있음
- Symptom
  - `python -m src.main` 실행 시, `RealEstateApp` import/로딩 단계에서 크래시 가능
- Root Cause (file:line)
  - `src/ui/app.py:34` `from src.core.db import DatabaseManager` (실제 모듈 없음)
  - `src/ui/app.py:37` `from src.utils.styles import get_stylesheet` (실제 모듈 없음)
- Why this is a doc/impl mismatch
  - `claude.md` 아키텍처 기준 DB는 `src/core/database.py` (ComplexDatabase), 스타일은 `src/ui/styles.py` (get_stylesheet) 입니다.
  - 실제 위젯 구현도 `src.ui.styles`를 사용 중입니다 (`src/ui/widgets/*.py`).
- Impact
  - UI 모듈 import 자체가 실패하므로, 크롤링/DB/익스포트 등 런타임 기능 진입 전에 프로그램이 중단될 수 있습니다.
- Status
  - Resolved on 2026-02-14 (Fix Status 섹션 참조)
- Recommended Actions (완료)
  - [x] `src/ui/app.py`의 DB import를 `src.core.database`로 교체하고, `ComplexDatabase`를 사용하도록 정리
  - [x] `src/ui/app.py`의 스타일 import를 `src.ui.styles`로 교체 (`get_stylesheet` 실제 위치와 일치)
  - [x] 수정 후 스모크 체크: `python -c "import src.ui.app"` 성공 확인

### 2) High: Preflight가 내부 모듈 Import 장애를 조기 차단하지 못함
- Current behavior
  - `src/utils/preflight.py`는 충돌 마커/의존성 설치 여부/디렉토리 생성 위주로 점검합니다.
  - 내부 엔트리포인트 모듈(`src.ui.app`) import 가능 여부는 검사하지 않습니다 (`run_preflight_checks` 내에 import 스모크 테스트 없음).
- Impact
  - `python -m src.main`에서 preflight가 통과해도, 이후 UI import에서 크래시가 발생할 수 있습니다.
- Status
  - Resolved on 2026-02-14 (Fix Status 섹션 참조)
- Recommended Additions (완료)
  - [x] preflight에 “내부 엔트리포인트 import 스모크 테스트” 추가
    - 예: `importlib.import_module("src.ui.app")`를 try/except로 감싸고 실패 시 preflight 에러로 승격
  - [x] 테스트 추가: `tests/`에 “UI import 가능 여부”를 검증하는 케이스 추가

## Acceptance Checklist (Runtime)
- [x] `python -c "from PyQt6.QtWidgets import QApplication; app=QApplication([]); from src.ui.app import RealEstateApp; RealEstateApp(); print('OK')"` 성공
- [x] `python -m compileall -q src` 성공
- [x] `python -m pytest -q` 성공
- [x] `python -m unittest discover -s tests -p "test_*.py"` 성공
- [ ] 단축키 최소 3개(Ctrl+R, Ctrl+F, Ctrl+T) 수동 검증 시 크래시 없이 동작
- [ ] `python -m src.main` 실행 시 메인 윈도우 표시 (수동 확인)
