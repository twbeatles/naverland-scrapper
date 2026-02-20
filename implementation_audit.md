# 기능 구현 리스크 감사 보고서

## 1) 목적/범위/검토 기준
- 목적: `README.md`, `claude.md`, 소스코드, 테스트를 교차 점검하여 기능 구현상 잠재 문제와 추가 필요사항을 식별하고 개선 우선순위를 제시한다.
- 범위: 런타임 코드 수정 없이 감사 문서 작성만 수행한다.
- 기준 스냅샷: 2026-02-20 워크스페이스 상태.
- 검토 입력: `README.md`, `claude.md`, `src/`, `tests/`, `pytest -q` 실행 결과.

## 2) 검토 요약
- 테스트 현황: `pytest -q` 기준 `21 passed` (경고 1건: pydantic v1 compatibility warning).
- 핵심 결론: 주요 기능의 “UI 선언/DB 메서드 존재”는 있으나, 실제 실행 경로에서 연결되지 않은 파이프라인이 다수 확인됨.
- 영향: 사용자는 기능이 있다고 인지하나 데이터 누적/알림/상태 갱신이 실제로 일어나지 않는 불일치가 발생할 수 있음.

## 3) Findings Schema
- `ID`: 식별자
- `Severity`: `Critical | High | Medium | Low`
- `Claimed Feature`: 문서/설정/구조상 제공을 전제하는 기능
- `Evidence`: 코드 근거(파일/라인)
- `Impact`: 사용자/운영 영향
- `Repro Condition`: 재현 조건
- `Recommendation`: 개선안
- `Priority`: `P0 | P1 | P2`
- `Test Gap`: 부족한 회귀 테스트

## 4) 리스크 매트릭스
| ID | Severity | Priority | 요약 |
|---|---|---|---|
| F-01 | High | P0 | 크롤링 히스토리 저장 파이프라인 미연결 |
| F-02 | High | P0 | 신규/가격변동/소멸/알림 DB 연동 미연결 |
| F-03 | Medium | P1 | 일부 설정값이 런타임에 반영되지 않음 |
| F-04 | Medium | P1 | 종료 확인 팝업 중복 가능성, 트레이 미지원 예외 위험 |
| F-05 | Medium | P1 | `favorite_keys` 초기화 보장 부족 |
| F-06 | Medium | P1 | 그룹 변경 시 예약 탭 동기화 누락 |
| F-07 | Medium | P1 | 최근 검색 기록 저장 경로 미구현 |
| F-08 | Low | P2 | 단축키 문서/상수와 실제 등록 불일치(`Ctrl+,`) |
| F-09 | Low | P2 | 모듈화 이후 잔존 메서드로 유지보수 혼선 가능 |
| F-10 | Medium | P1 | 미연결 기능군에 대한 테스트 공백 |

## 5) 상세 점검 항목

### F-01
- ID: `F-01`
- Severity: `High`
- Claimed Feature: 크롤링 히스토리 누적/조회
- Evidence: `src/core/database.py:433`, `src/core/crawler.py:232`, `src/ui/widgets/crawler_tab.py:571`, `src/ui/widgets/crawler_tab.py:575`
- Impact: 히스토리 탭과 DB 누적 이력이 실제 수집 결과와 분리될 위험
- Repro Condition: 크롤링 완료 후 히스토리 탭 확인 시 기대 누적이 반영되지 않음
- Recommendation: `complex_finished_signal`을 UI에 연결하고 `add_crawl_history()` 호출을 명시적으로 추가
- Priority: `P0`
- Test Gap: 크롤링 완료 후 `crawl_history` row 증가 검증 테스트 부재

### F-02
- ID: `F-02`
- Severity: `High`
- Claimed Feature: 신규/가격변동/소멸 추적 및 알림
- Evidence: `src/core/database.py:570`, `src/core/database.py:596`, `src/core/database.py:875`, `src/core/database.py:907`, `src/core/crawler.py:47`
- Impact: 신규 배지, 가격변동 지표, 소멸 매물, 조건 알림이 동작하지 않거나 고정값으로 노출될 수 있음
- Repro Condition: 동일 단지 다회 크롤링 시 상태 변화 반영 확인 불가
- Recommendation: 크롤링 아이템 처리 루프에서 이력 조회/업데이트/알림 체크/소멸 마킹을 명시 연결
- Priority: `P0`
- Test Gap: 2회 이상 크롤링 기반 상태 전이 테스트 부재

### F-03
- ID: `F-03`
- Severity: `Medium`
- Claimed Feature: 설정 기반 동작 제어
- Evidence: `src/core/managers.py:17`, `src/core/managers.py:18`, `src/core/managers.py:19`, `src/core/managers.py:26`
- Impact: 사용자가 설정을 변경해도 UI/동작이 동일하여 기능 신뢰도 저하
- Repro Condition: 설정 변경 후 결과 렌더링/필터/추적 동작 변화 없음
- Recommendation: 설정값별 실제 소비 지점 연결(`show_new_badge`, `show_price_change`, `price_change_threshold`, `track_disappeared`)
- Priority: `P1`
- Test Gap: 설정 toggle별 동작 분기 테스트 부재

### F-04
- ID: `F-04`
- Severity: `Medium`
- Claimed Feature: 안정적 종료/트레이 최소화 UX
- Evidence: `src/ui/app.py:1105`, `src/ui/app.py:1126`, `src/ui/app.py:371`, `src/ui/app.py:1090`
- Impact: 종료 시 확인 팝업 중복 가능, 트레이 미지원 환경에서 예외 위험
- Repro Condition: 창 닫기(`X`) 시나리오, 트레이 미지원 환경에서 `Ctrl+M`
- Recommendation: 종료 확인 책임을 한 경로로 통합하고 `_minimize_to_tray()`에 트레이 존재 가드 추가
- Priority: `P1`
- Test Gap: 종료 이벤트 분기/트레이 미지원 분기 UI 테스트 부재

### F-05
- ID: `F-05`
- Severity: `Medium`
- Claimed Feature: 즐겨찾기 상태 안정적 동기화
- Evidence: `src/ui/app.py:396`, `src/ui/app.py:867`, `src/ui/app.py:889`
- Impact: 특정 경로에서 `favorite_keys` 접근 시 초기화 순서에 의존
- Repro Condition: `_refresh_favorite_keys()` 호출 이전에 토글 경로 진입
- Recommendation: `__init__`에서 `self.favorite_keys = set()` 명시 초기화
- Priority: `P1`
- Test Gap: 초기 상태에서 즐겨찾기 토글 smoke test 부재

### F-06
- ID: `F-06`
- Severity: `Medium`
- Claimed Feature: 그룹 변경 시 예약 대상 자동 동기화
- Evidence: `src/ui/widgets/group_tab.py:12`, `src/ui/widgets/group_tab.py:86`, `src/ui/widgets/group_tab.py:94`, `src/ui/app.py:447`
- Impact: 사용자에게 그룹 목록/예약 콤보 간 불일치 노출
- Repro Condition: 그룹 생성/삭제 직후 예약 탭 확인
- Recommendation: `GroupTab.groups_updated`를 `RealEstateApp._load_schedule_groups`에 연결
- Priority: `P1`
- Test Gap: 그룹 CRUD 후 예약 콤보 동기화 테스트 부재

### F-07
- ID: `F-07`
- Severity: `Medium`
- Claimed Feature: 최근 검색 기록 저장/재사용
- Evidence: `src/core/managers.py:96`, `src/core/managers.py:120`, `src/ui/app.py:73`
- Impact: 최근 검색 다이얼로그는 존재하나 기록이 누적되지 않아 실사용 가치 저하
- Repro Condition: 검색/크롤링 실행 후 `search_history.json` 변화 없음
- Recommendation: 검색 실행 또는 크롤링 시작 시 `history_manager.add()` 호출 연결
- Priority: `P1`
- Test Gap: 검색 실행 후 히스토리 파일 생성/누적 테스트 부재

### F-08
- ID: `F-08`
- Severity: `Low`
- Claimed Feature: 단축키 일관성
- Evidence: `src/utils/constants.py:14`, `src/ui/app.py:334`
- Impact: 사용자 문서/상수와 실제 동작 차이(`Ctrl+,` 설정창)
- Repro Condition: `Ctrl+,` 입력 시 설정창 미오픈
- Recommendation: `_init_shortcuts()`에 `Ctrl+, -> _show_settings` 추가 또는 상수/문서 정정
- Priority: `P2`
- Test Gap: 단축키 매핑 검증 테스트 부재

### F-09
- ID: `F-09`
- Severity: `Low`
- Claimed Feature: 모듈화 후 단일 책임 구조
- Evidence: `src/ui/app.py:746`, `src/ui/app.py:819`, `src/ui/app.py:1185`
- Impact: 현재 경로에서 사용되지 않는 잔존 메서드가 유지보수 판단을 어렵게 함
- Repro Condition: 앱 구조 분석 시 유효 경로와 잔존 경로 혼재
- Recommendation: 미사용 코드 정리 또는 `deprecated` 표기와 호출 금지 가드 추가
- Priority: `P2`
- Test Gap: 미사용 경로 감지(coverage/정적 분석) 파이프라인 부재

### F-10
- ID: `F-10`
- Severity: `Medium`
- Claimed Feature: 기능 회귀 방지
- Evidence: `tests/test_database_module.py`, `tests/test_ui_runtime_smoke.py`, `tests/test_preflight.py`
- Impact: 현재 테스트는 모듈 스모크/기초 동작 중심이라 연결 누락형 결함을 놓칠 가능성 높음
- Repro Condition: 기능 선언 대비 파이프라인 누락이 테스트에서 탐지되지 않음
- Recommendation: 아래 “테스트 보강 항목”을 우선 자동화
- Priority: `P1`
- Test Gap: 파이프라인 통합 테스트 부족

## 6) 추가 기능 제안 (P1/P2)

### P1
- 통합 이벤트 파이프라인 정리: 크롤러 이벤트(`complex_finished`, alert, item lifecycle)와 DB 업데이트를 명시적 유스케이스 레이어로 통합.
- 설정 반영 추적성: 설정 키별 “소비 위치 맵”을 문서화하고 미소비 키는 경고 로그 출력.
- 종료 시나리오 안정화: 트레이 지원 여부/확인 팝업/스레드 종료를 단일 종료 오케스트레이션으로 정리.

### P2
- 미사용 코드 가시화: `ruff`/`vulture` 기반 dead code 리포트 도입.
- 단축키/문서 동기화 체크: 상수와 실제 바인딩 자동 검증 테스트 추가.

## 7) 테스트 보강 항목
1. 크롤링 완료 후 히스토리 탭 데이터 누적 여부.
2. 신규/가격변동/소멸 상태가 2회 이상 크롤링에서 갱신되는지.
3. 알림 조건 충족 매물 발견 시 신호/알림 UI 동작 여부.
4. `minimize_to_tray` 켜짐/꺼짐 시 닫기 동작 분기.
5. 트레이 미지원 환경에서 `Ctrl+M` 안전 동작.
6. 그룹 생성/삭제 후 예약 그룹 콤보 자동 동기화.
7. 최근 검색 실행 후 `search_history.json` 기록 생성 여부.
8. `Ctrl+,` 단축키로 설정창 오픈 여부.

## 8) 품질 점검 결과
- 각 핵심 항목에 최소 1개 이상 파일 근거를 첨부했다.
- 문서 주장과 코드 근거의 불일치 여부를 재검토했고, 근거 라인은 현재 스냅샷 기준으로 확인했다.
- 본 문서는 감사 보고서이며 런타임 API/타입/동작 코드는 변경하지 않았다.
