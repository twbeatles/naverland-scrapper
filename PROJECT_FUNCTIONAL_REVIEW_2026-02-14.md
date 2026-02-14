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
- 정적 점검에서 `compileall`, `pytest`는 통과했지만, **앱 실행 엔트리포인트가 UI import 단계에서 막힐 수 있는 ImportError**가 확인되었습니다.
- 구체적으로 `src.ui.app`가 존재하지 않는 모듈을 import 하며, 이는 `src/main.py`가 `RealEstateApp`을 import 하는 흐름에서 치명적입니다.

## Evidence (Command Snapshot)
- `python -m compileall -q src`: SUCCESS (exit 0)
- `python -m pytest -q`: `13 passed`
- import smoke test (pkgutil 기반): **failures=1**
  - `src.ui.app` -> `ModuleNotFoundError: No module named 'src.core.db'`

## Fix Status (2026-02-14)
- Implemented fixes in working tree:
  - [x] `src/ui/app.py` DB import fixed (`ComplexDatabase`)
  - [x] `src/ui/app.py` stylesheet import fixed (`src.ui.styles.get_stylesheet`)
  - [x] preflight internal import smoke test added (`src/utils/preflight.py`)
  - [x] pytest guard added for UI importability (`tests/test_ui_import.py`)
- Verification after fixes:
  - `python -c "import src.ui.app"`: SUCCESS
  - preflight (`run_preflight_checks`): `preflight_ok True`
  - import smoke test (pkgutil 기반): `failures=0`
  - `python -m pytest -q`: `14 passed`

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
- Recommended Actions (바로 고칠 것)
  - [ ] `src/ui/app.py`의 DB import를 `src.core.database`로 교체하고, `ComplexDatabase`를 사용하도록 정리
  - [ ] `src/ui/app.py`의 스타일 import를 `src.ui.styles`로 교체 (`get_stylesheet` 실제 위치와 일치)
  - [ ] 수정 후 스모크 체크: `python -c "import src.ui.app"` 성공해야 함

### 2) High: Preflight가 내부 모듈 Import 장애를 조기 차단하지 못함
- Current behavior
  - `src/utils/preflight.py`는 충돌 마커/의존성 설치 여부/디렉토리 생성 위주로 점검합니다.
  - 내부 엔트리포인트 모듈(`src.ui.app`) import 가능 여부는 검사하지 않습니다 (`run_preflight_checks` 내에 import 스모크 테스트 없음).
- Impact
  - `python -m src.main`에서 preflight가 통과해도, 이후 UI import에서 크래시가 발생할 수 있습니다.
- Recommended Additions (추가하면 즉시 안정성 올라감)
  - [ ] preflight에 “내부 엔트리포인트 import 스모크 테스트” 추가
    - 예: `importlib.import_module("src.ui.app")`를 try/except로 감싸고 실패 시 preflight 에러로 승격
  - [ ] 테스트 추가: `tests/`에 “UI import 가능 여부”를 검증하는 케이스 추가

## Acceptance Checklist (Fix After Verification)
- [ ] `python -c "import src.ui.app"` 성공
- [ ] `python -m compileall -q src` 성공
- [ ] `python -m pytest -q` 성공
- [ ] `python -m src.main` 실행 시 메인 윈도우 표시 (수동 확인)
