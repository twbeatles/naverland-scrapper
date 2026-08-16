# Project Audit

> Remediation update (2026-08-16): signed update keys are configured; the installer now validates staged paths/tickets, waits for application shutdown, runs preflight after replacement, rolls back on failure, reports results on next start, and has focused tests. Remaining entries below are the original audit snapshot or future hardening work.

## 1. Executive Summary

전체 위험도는 **High**다. 수집 기능은 전역 크롤링 락, 작업 종료 대기, SQLite 연결 풀, JSON 손상 복구를 갖추고 있으며 CodeGraph상 UI·수집·DB 테스트 연결점도 다수 확인됐다. 반면 새 GitHub Release 업데이트는 현재 공개키가 비어 있어 비활성 상태이고, 실제 EXE 교체·재시작·롤백 경로에 테스트가 없다.

가장 큰 위험은 새 EXE를 교체한 뒤 실행 가능성을 확인하지 않고 기존 백업을 삭제하는 점이다. 또한 헬퍼를 먼저 시작한 뒤 앱 종료를 시도하므로, 크롤링 종료가 실패하면 업데이트는 고아 상태로 실패하며 사용자에게 결과가 전달되지 않는다.

## 2. Project Understanding

`CLAUDE.md`는 루트에 없다. README에 따르면 프로젝트는 Naver Land 매물 수집, 가격 이력, 알림, 대시보드를 제공하는 Windows 데스크톱 앱이다. PyQt6/Fluent UI, Playwright 중심 수집과 Selenium fallback, SQLite 및 JSON 설정·캐시를 사용한다.

CodeGraph 분석상 실행은 `app_entry.main` → `src.main.main` → `RealEstateApp`으로 이어진다. `CrawlerTab.start_crawling`과 지도 수집은 process-wide `CrawlLock`으로 상호 배제되고, 앱 종료는 각 수집 스레드의 `shutdown_crawl`을 기다린다. SQLite 연결 풀은 WAL 연결을 대여·반납하고 종료 시 새 대여를 중단한다. JSON은 `atomic_write_json`과 `load_json_with_recovery`로 처리한다.

업데이트 흐름은 `UpdateController` worker thread → signed manifest 검증 → EXE 해시/크기 검증 다운로드 → helper EXE → 부모 종료 대기 → 교체/재시작 순서다. CodeGraph의 blast radius에서 `RealEstateApp`은 42개 호출 지점 및 UI smoke/wiring 테스트에 연결되지만, `apply_update`, `UpdateController.apply`, `download_release_manifest`에는 전용 테스트 연결점이 없다.

## 3. High-Risk Issues

### 업데이트 채널이 기본값에서 비활성 상태

* 위치: `src/utils/version.py:5-6`, `src/utils/update_controller.py:26-33`, `.github/workflows/release.yml`
* 문제: `UPDATE_PUBLIC_KEY_B64`가 빈 문자열이다. controller는 공개키와 URL이 모두 있어야 동작하고 workflow도 공개키가 비어 있으면 실패한다.
* 영향: 현재 저장소 상태만으로는 자동 업데이트를 배포하거나 사용할 수 없다.
* 근거: CodeGraph에서 URL의 유일한 소비자는 `UpdateController`이며 `configured`가 빈 공개키를 거부한다.
* 권장 수정 방향: 공개키를 소스에 고정하고, 대응 개인키만 `NAVERLAND_UPDATE_PRIVATE_KEY_B64` GitHub Secret으로 설정한 뒤 테스트 태그로 검증한다.
* 우선순위: High

### 교체 후 실행 검증과 지속 가능한 롤백이 없음

* 위치: `src/utils/update_installer.py:69-79`
* 문제: 기존 EXE를 백업하고 새 EXE를 교체한 뒤 `Popen`만 성공하면 백업을 삭제한다. 프로세스 생성은 preflight·GUI 초기화 성공을 뜻하지 않는다.
* 영향: 새 빌드가 즉시 크래시하거나 필수 파일이 누락되면 사용 가능한 이전 버전까지 잃을 수 있다.
* 근거: `apply_update`는 새 프로세스의 결과를 기다리지 않고 `backup.unlink()`한다. CodeGraph도 이 함수에 테스트가 없음을 표시한다.
* 권장 수정 방향: helper가 새 EXE의 `--preflight`/smoke 성공을 확인한 뒤에만 백업을 제거하고, 실패 시 원자적 롤백 및 다음 실행 시 결과 알림을 제공한다.
* 우선순위: Critical

### 종료 실패 시 업데이트 헬퍼가 고아 작업이 되고 결과가 통지되지 않음

* 위치: `src/ui/app_parts/lifecycle.py`의 `_on_update_downloaded`, `_quit_app`, `_shutdown`; `src/utils/update_installer.py:45-48, 63-68`
* 문제: UI가 helper를 먼저 시작하고 `_quit_app`을 호출한다. `_shutdown`은 수집 스레드가 8초 안에 끝나지 않으면 종료를 취소하지만, helper는 이미 부모 PID를 45초 기다리다가 실패한다. 결과 파일·IPC·다음 시작 알림이 없다.
* 영향: 사용자는 설치를 승인했지만 앱은 계속 실행되고 설치도 조용히 실패할 수 있다. helper/staging 파일도 남는다.
* 근거: CodeGraph가 `_shutdown`의 timeout 반환과 helper의 PID polling timeout을 확인했다.
* 권장 수정 방향: 모든 종료 조건을 먼저 만족시킨 뒤 helper를 시작한다. 실패·롤백 결과를 파일로 남기고 다음 기동 시 표시하며 staging을 정리한다.
* 우선순위: High

### 업데이트 설치 진입점의 경로 신뢰 경계가 약함

* 위치: `app_entry.py:20-25, 90-94`, `src/utils/update_installer.py:51-62`
* 문제: 숨겨진 `--apply-update`는 호출자가 제공한 target/staged 경로와 해시를 사용한다. EXE 확장자·존재 여부만 검사하며 staging root, 현재 설치 EXE, 사전 검증 작업 토큰을 확인하지 않는다.
* 영향: 동일 사용자 권한의 로컬 프로세스가 이를 임의의 사용자 쓰기 가능 EXE 교체 도구로 사용할 수 있다. 권한 상승은 아니지만 업데이트 신뢰 경계가 넓다.
* 근거: argparse 입력이 직접 `apply_update`로 전달되며 경로 소속 검증이 없다.
* 권장 수정 방향: staged를 앱 전용 updates 디렉터리로, target을 기록된 설치 경로로 제한하고, 검증 완료 작업의 난수 토큰·해시·크기를 helper가 재검증하게 한다.
* 우선순위: Medium

### 업데이트 상태가 UI 이벤트 큐와 분리되어 중복 실행 가능

* 위치: `src/utils/update_controller.py:23-24, 34-48, 55-63`
* 문제: worker가 Qt signal을 emit한 직후 `_busy=False`가 된다. UI가 queued signal을 처리하기 전에 사용자가 다시 확인할 수 있고, action 비활성화·operation id·취소 상태가 없다.
* 영향: 중복 확인/대화상자 또는 복수 staging 파일이 생길 수 있다.
* 근거: `_busy`는 worker 실행 기간만 보호하며 사용자 confirmation/download/apply 상태를 보유하지 않는다.
* 권장 수정 방향: `idle/checking/available/downloading/applying` 상태 머신, UI disable, operation id로 오래된 signal 무시를 구현한다.
* 우선순위: Medium

### JSON 원자 저장이 동시 저장을 보장하지 않음

* 위치: `src/utils/json_store.py:22-28`, `src/core/managers.py:248-278`
* 문제: 모든 저장이 고정 `<name>.json.tmp`를 사용하고 `SettingsManager.set/update`는 저장 시 락으로 보호되지 않는다.
* 영향: 같은 파일을 동시에 저장할 경우 임시 파일 충돌이나 마지막 변경 유실이 가능하다. 손상 복구는 기본값 복원이라 설정 손실로 이어질 수 있다.
* 근거: CodeGraph가 `atomic_write_json`의 7개 호출자와 무잠금 settings write path를 확인했다. 동시 호출이 항상 발생한다는 뜻은 아니다.
* 권장 수정 방향: 파일별 lock, UUID 임시 파일, 단일 저장 큐를 사용한다.
* 우선순위: Medium

### 사용자 문서 인코딩이 깨져 있음

* 위치: `README.md`, 기존 `PROJECT_AUDIT.md`
* 문제: raw bytes를 UTF-8로 디코드하면 한글이 mojibake로 표시됐고 CP949/EUC-KR로도 유효하게 디코드되지 않았다.
* 영향: 설치·실행·릴리즈 절차를 신뢰성 있게 전달할 수 없다.
* 근거: 감사 과정에서 바이트 단위로 확인했다.
* 권장 수정 방향: 원문을 복구해 UTF-8로 저장하고 CI에 인코딩/모지바케 검사를 추가한다.
* 우선순위: Medium

## 4. Potential Functional Gaps

* **추정:** 시작 시 비대화형 업데이트 확인 정책이 없다. 제품 요구사항이면 빈도 제한, 실패 무시, “나중에” 버전 기록이 필요하다.
* **추정:** 개발 실행에서도 업데이트 발견 대화상자 뒤에야 자동 설치 불가 오류가 난다. 발견 단계에서 개발 모드 안내 또는 릴리즈 페이지 제공이 더 일관적이다.
* 실패한 staging/helper/backup을 다음 실행에서 정리·복구·표시하는 기능은 코드상 없다.
* release workflow는 build와 `--preflight`만 수행하며, 실제 구버전 → helper → 교체 → 재시작/롤백 e2e를 실행하지 않는다.
* README는 새 업데이트 동작·키 설정을 링크하지 않는다. `docs/RELEASE_UPDATES.md`에는 설명이 있으나 README와 연결되지 않는다.

## 5. Recommended Fix Plan

### 1단계: 즉시 수정

1. 공개키/Secret을 설정하고 테스트 태그로 workflow를 검증한다.
2. 새 EXE smoke 성공 전 백업을 보존하고 실패 시 자동 롤백한다.
3. 앱 종료 성공 뒤에만 helper를 시작하고 결과를 다음 시작에 통지한다.

### 2단계: 안정성 개선

1. 업데이트 상태 머신·operation id·UI disable을 추가한다.
2. staging/helper/backup 보존 정책과 시작 시 정리·복구를 구현한다.
3. `--apply-update`를 앱 전용 staging root, 기록된 target, 작업 토큰으로 제한한다.
4. JSON 저장에 파일별 lock과 고유 임시 파일을 적용한다.

### 3단계: 구조 개선

1. 업데이트 확인·다운로드·설치·결과 표시를 순수 서비스와 Qt adapter로 분리한다.
2. 릴리즈 artifact, manifest, 키 검증, rollback을 하나의 release verification 스크립트로 통합한다.
3. README 및 문서를 정상 UTF-8로 복원하고 문서 검사 CI를 추가한다.

## 6. Test Recommendations

* `apply_update` 통합 테스트: 부모 종료 대기, 정상 교체/재시작, 새 EXE smoke 실패 롤백, `Popen` 실패 롤백.
* UI 테스트: 종료 실패 시 helper 미시작, 취소 시 staged 제거, 다음 실행의 성공/실패 알림.
* `UpdateController` 테스트: 빠른 연속 click, 늦은 signal, 중복 staging 및 취소.
* 보안 입력 테스트: target/staged 경로 탈출, 작업 토큰·해시·크기 불일치 거부.
* 매니페스트 테스트: 만료, 대형 payload, HTTPS downgrade redirect, 잘못된 base64/키 길이, 버전 비교 경계.
* one-file release e2e: 구 버전 fixture에서 helper 교체·재시작·rollback을 CI에서 실행.
* JSON 동시 저장 테스트 및 README/docs UTF-8·대표 한글 문구 검사.
