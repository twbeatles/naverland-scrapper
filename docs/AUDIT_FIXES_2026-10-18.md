# 감사 후속 개선 — 2026-10-18

대상은 `PROJECT_AUDIT.md`의 확정 이슈와 기능·안정성 권고다. 기존 사용자 DB의 재분류·집계 재계산·복원은 실행하지 않았다. 변경한 스키마는 새로 생성하는 DB와 앱이 다음에 여는 DB에 적용되는 additive migration이다.

## 확정 이슈 처리

| 이슈 | 적용한 동작 | 회귀 검증 |
|---|---|---|
| ISSUE-001 | `CollectionResult`와 공통 완료성 판정. 오류 JSON/누락 목록 키와 명시적 빈 배열 구분. 페이지 실패·상한·취소는 partial/failed로 전달. 앞선 결과는 보존하되 정상 캐시·소멸·기준 통계 교체 제외 | 후속 429/500/timeout/invalid JSON/schema, 잘못된 원소, 페이지 상한, 정상 빈 결과 테스트 |
| ISSUE-002 | 필터 전에 기존 관측 ID의 `last_seen/status`만 갱신. 가격/중개 정보는 보존. 존재 갱신·이력 저장 실패 시 소멸 판정 차단 | 실제 CrawlerThread 필터→DB→소멸 경로에서 9억/15억 모두 active 유지 |
| ISSUE-003 | 중단·필터·부분·저장 실패·캐시 실행은 기존 일별 통계 유지. 완전 실행은 타깃의 당일 전체 그룹을 한 transaction에서 교체하여 사라진 평형도 정리 | 실제 GUI 완료 handler의 기존 평균/count 보존, 정상 0건 그룹 교체, delete 후 insert 실패 rollback |
| ISSUE-004 | API 결과 집합 옵션(PRE)과 계약 버전이 들어간 cache fingerprint. fingerprint 없는 이전 캐시는 main 수집 경로에서 재사용하지 않음 | PRE on/off 및 JSON 캐시 reload 후 격리 확인 |

이전 캐시는 파일을 강제로 삭제하지 않고 자연스럽게 만료된다. 캐시에서 나온 목록은 사용자에게 보여줄 수 있으나 새로운 실시간 전체 관측으로 취급하여 소멸/기준 통계를 변경하지 않는다.

## 안정성·구조 보완

- **페이지별 복구:** transport/5xx는 동일 페이지에서 최대 두 번 시도하고 짧은 backoff를 둔다. 429를 자동 연속 재시도하지 않는다. 복구 실패 시 성공했던 페이지와 실패 페이지·이유를 보존한다.
- **Selenium:** DOM 스크롤의 정체만으로 서버의 전체 목록 완료를 입증할 수 없다. 현재 보조 엔진의 DOM 결과는 partial로 취급한다. 화면/내보내기와 선택 매물 이력은 유지하지만 소멸/기준 통계 교체와 정상 캐시에는 사용하지 않는다. 정상 완료가 확인된 Playwright 타깃의 fallback prefill은 분리해 보존한다.
- **품질 확인:** 목록의 누락 ID/가격/면적, 잘못된 원소, NaN/Infinity를 정상 표본과 구분한다. 유효한 일부 행은 보존하며, 깨진 표본이 포함되면 완료성 보호를 적용한다. 면적이 없거나 유한하지 않은 행은 집계하지 않는다.
- **실행 출처:** `crawl_history.diagnostics_json`을 additive migration으로 추가했다. 실행 ID, 파서/계약 버전, 필터 fingerprint, raw/matched count, cache 여부, 완료성·페이지 오류, 품질 오류 수, 날짜 기준을 기록한다. 기존 이력 조회의 9열 tuple 계약은 유지했다.
- **원본 보존 범위:** 실행 진단 정보와 최신 매물 이력, 일별 집계를 분리했다. 인증 헤더·전화번호를 진단 JSON에 복제하지 않는다. 모든 원본 응답을 장기 보관하는 아카이브는 추가하지 않았다. 현재 목적상 필수라고 확정되지 않은 기능이며 JSON export로 원본 결과를 별도 보존할 수 있다.
- **DB 오류:** 존재 갱신은 write lock/짧은 busy timeout/제한 재시도/rollback을 사용한다. 이력 저장 실패를 상태로 전달해 소멸·전체 통계를 막는다. 스냅샷 쓰기 실패도 저장 성공으로 표시하지 않는다.
- **CI:** 브라우저 없는 Playwright 안정화 테스트를 일괄 skip 대상에서 분리했다. CI와 로컬 동일 검사에 데이터 무결성·정규화·site contract·cortarNo·crawler·crawl lock 회귀를 추가하고 목록 동기화 테스트로 보호한다.

## 현재 네이버 상세 구조 대응

감사 때 관측한 `fin.land/articles/{id} → map?layer=...`는 실제 상세를 포함하는 정상 경로였다. 8월 조사 문서에 당시 관측이라는 주석과 현재 확인 내용을 추가했다. map 주소 자체를 장애로 판정하는 규칙을 추가하지 않았다.

`__next_f`의 Flight 텍스트 프레임에서 JSON 레코드를 읽도록 보완했다. JavaScript eval 없이 크기/프레임 수를 제한하고, 불완전·비JSON 레코드는 건너뛰며 기존 DOM·네트워크·front-api fallback을 유지한다. 모든 RSC 레코드 참조를 복원하는 범용 React 런타임은 구현하지 않는다.

목록의 공급/전용 면적과 출처·정밀도를 분리했다. 구조화된 상세의 `supplyArea/exclusiveArea`를 확보하면 공급면적·평·평당가를 갱신한다. 정수 목록 면적이 필터 경계에 가까운 경우 상세 조회 후보로 남기고, 상세 보강 후 원래 조건으로 최종 필터링한다. 상세 조회가 꺼져 있거나 값을 얻지 못한 경우 목록 표기값을 정밀값으로 가장하지 않는다. Excel/CSV의 선택 열에 공급면적·전용면적·정밀도를 추가했다.

실제 광고 중복을 주택 단위로 확정하는 규칙은 근거 없이 바꾸지 않았다. 가격 집계는 광고별 표본이라는 의미를 README에 명시했다.

## 일자·중단·재실행 정책

- DB의 `CURRENT_DATE`와 기존 데이터는 **UTC 날짜** 기준을 유지한다. 한국 날짜로 기존 기록을 일괄 이동하지 않는다.
- 한국 시간 자정~08:59는 DB 기준 전날이다. 09:00에 UTC 날짜가 바뀐다. 경계 회귀 테스트로 명시했다.
- 예약 시각과 catch-up은 PC의 로컬 wall clock을 따른다. 이미 시작한 예약 슬롯은 자동 중복 시작하지 않는다.
- 같은 DB 날짜 안에서는 이전 실행에서 관측한 매물이 뒤 실행에 안 보여도 즉시 소멸하지 않는다. 다음 날짜의 완전 수집에서 판정한다.
- 재실행은 새 수집이다. 부분/중단 실행의 앞선 결과는 보존·내보내기 가능하지만 자동 페이지 재개를 약속하지 않는다.

## 로컬 검증 환경

기존 `.venv-ci`는 제거된 Python 3.14를 참조했다. 이를 자동 삭제하지 않았다. 기존 `.venv`의 Python 3.15/PySide6 6.12에서는 Qt import와 offscreen GUI 테스트가 동작했다. 이 환경에 테스트용 pytest만 추가했다.

`ci_check.ps1`은 파일 존재뿐 아니라 인터프리터 실행 가능성을 확인하고, `.venv-ci`가 불능이면 실행 가능한 `.venv`를 선택한다. Pyright도 선택한 인터프리터를 사용한다. `pyrightconfig.json`의 특정 로컬 venv 고정을 제거했다. setup 스크립트는 오래된 인터프리터를 명확히 안내하며, 명시적 `-Recreate`의 삭제 경로를 검증한다.

이 로컬 환경의 cryptography는 46.0.3으로 저장소 요구 `>=50.0.2`를 만족하지 않는다. 요구 버전 설치는 시도했으나 Windows ARM64용 wheel이 없고 Python 3.15의 source build metadata 단계에서 maturin이 인터프리터를 인식하지 못했다. 기존 버전은 그대로 유지되며 요구 하한을 낮추거나 검사를 숨기지 않았다. 이 제한은 앱 로직 회귀와 분리해서 보고한다. [배포 파일 목록](https://pypi.org/pypi/cryptography/50.0.2/json)을 확인했다.

## 검증 결과

최종 실행은 테스트 격리 보완 후 Windows ARM64의 Qt offscreen 경로에서 수행했다. 실제 네이버의 모든 지역·APT/VL/PRE·월세 페이지를 대량 수집하거나 Windows x64/Linux/macOS/배포 EXE 전체를 검증했다는 의미는 아니다.

```text
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --disable-warnings -o faulthandler_timeout=45 tests
1 failed, 512 passed, 43 warnings, 39 subtests passed in 270.45s
```

유일한 실패는 `test_requirements_pins.py`의 cryptography 설치 버전 검사다. 나머지 코드·GUI·DB·수집 엔진 회귀는 통과했다. Qt signal disconnect 관련 기존 경고를 포함한 43건의 경고는 오류와 구분한다. 환경 설정은 `QT_QPA_PLATFORM=offscreen`, `PYTHONNOUSERSITE=1`, `NAVERLAND_SKIP_PLAYWRIGHT_BROWSER_CHECK=1`이며 실제 브라우저 기반 대량 수집 검증은 포함하지 않는다.

- 새 테스트는 임시 DB에서 필터·존재 갱신·소멸·일별 통계·rollback, PRE 캐시 격리, API 오류/상한, RSC/면적, UTC 경계를 검증한다.
- GUI 완료 handler도 중단/필터/부분 실행에서 기존 통계를 보존하는지 실제 Qt 객체로 검증한다.
- CI/로컬 테스트 목록 동기화, 기존 수집 락·예약/종료·백업/복원·export 회귀를 함께 확인한다.
- Pyright는 `.venv/Scripts/python.exe` 지정으로 **0 errors, 0 warnings**였다. `compileall`과 `git diff --check`, PowerShell 스크립트 구문 검사도 통과했다.
- 임시 `NAVERLAND_DATA_DIR`에서 `.venv/Scripts/python.exe app_entry.py --preflight`는 exit 0이었다. 브라우저 설치 검사는 명시적으로 skip했으므로 실제 사이트 수집/Chromium 기동 성공과 동일시하지 않는다.
- 기존 `data/complexes.db`의 크기·수정시각은 작업 전후 동일하다. 로컬 설정·최근 기록에 대해서는 아래 테스트 격리 사고를 별도로 기록한다.

아직 실행하지 못한 플랫폼·실서비스 조합은 검증 한계이며, 추정 사항을 해결된 production 버그로 표시하지 않는다.

## 테스트 격리 사고와 조치

전체 테스트 중 기존 경로 테스트가 paths 모듈과 환경 변수를 초기화한 뒤 UI 테스트가 기본 경로를 다시 사용하면서 `data/settings.json`과 `data/recently_viewed.json`을 갱신했다. 최초 runner에 임시 경로를 주입하는 것만으로 격리가 유지된다고 판단한 것이 잘못이었다. 수집 SQLite 파일은 크기·수정시각 기준 변경되지 않았다.

설정·최근 기록의 실행 전 원본 백업은 없어 정확하게 복원했다고 주장할 수 없다. 임의로 원래 값을 추측해 덮어쓰지 않았다. 발견 시점의 두 파일은 `%TEMP%/naverland-test-incident-91473c94a10b48369ec969036546b7e6/`에 복사해 보존했다. 이 복사본은 실행 전 원본이 아니라 사고 후 상태다.

재발 방지를 위해 `tests/conftest.py`에 collection 시점의 세션 sandbox와 테스트별 sandbox, 환경 변수·설정 singleton 초기화를 추가했다. 경로 초기화 테스트 다음에도 UI 테스트가 사용자 경로를 이어받지 않도록 했다. 격리 수정 후에는 위 세 로컬 파일의 SHA-256을 기준으로 추가 변경 여부를 확인한다.

격리 수정 후 최종 전체 테스트 실행 전후 세 파일의 SHA-256이 동일했다. 이는 수정 이후 추가 쓰기가 없었다는 검증이며, 사고 이전 원본으로 복원됐다는 뜻은 아니다.
