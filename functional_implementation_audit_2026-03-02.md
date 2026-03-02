# 기능 구현 점검 리포트 (2026-03-02)

## 범위
- 참조 문서: `README.md`, `claude.md`, `update_history.md`
- 점검 대상: `src/core`, `src/ui`, `src/utils`, `tests`
- 실행 검증:
  - 점검 시점: `PYTHONPATH=. pytest -q` (68 passed)
  - 반영 완료 후: `PYTHONPATH=. pytest -q` (77 passed)

## 핵심 점검 결과 (우선순위 순)

### 1) 종료/복구 시 크롤러 중단 실패 가능성 (High)
- 근거 코드:
  - `src/ui/widgets/crawler_tab.py:904` (`shutdown_crawl(timeout_ms=8000)`)
  - `src/ui/widgets/crawler_tab.py:917` (`thread.wait(wait_ms)`)
  - `src/utils/retry_handler.py:17-40` (재시도 루프 + `time.sleep(wait_time)`)
  - `src/core/crawler.py:481`, `src/core/crawler.py:764` (크롤링 중 고정 sleep)
- 리스크:
  - 재시도/대기 구간이 인터럽트 불가라서 8초 내 종료가 자주 실패할 수 있습니다.
  - `DB 복구`, `앱 종료` 시 “스레드 종료 대기 초과”가 발생하면 사용자 동작이 차단됩니다.
- 권장 보완:
  - `RetryHandler`에 cancellation/event 주입.
  - sleep을 100~200ms 단위로 쪼개고 중간에 stop 플래그 확인.
  - 종료 경로에서는 retry/wait 정책을 더 짧게 override.

### 2) 단지 삭제 시 그룹 매핑 고아 데이터 발생 (Medium)
- 근거 코드:
  - `src/core/database.py:277` (`group_complexes` 생성)
  - `src/core/database.py:530` (`DELETE FROM complexes WHERE id = ?`)
  - `src/core/database.py:547` (bulk delete도 동일)
- 관찰:
  - 단지 삭제 시 `group_complexes` 정리 로직이 없어 고아 row가 남습니다.
  - 실제 재현: 그룹-단지 연결 1건 생성 후 단지 삭제 시 `group_complexes` row는 유지됨.
- 리스크:
  - DB 정합성 저하, 장기적으로 불필요 데이터 누적.
- 권장 보완:
  - `PRAGMA foreign_keys=ON` + `ON DELETE CASCADE` 적용 또는
  - `delete_complex`, `delete_complexes_bulk`에서 `group_complexes` 정리 쿼리 추가.

### 3) URL 배치 분석이 UI 스레드에서 네트워크 호출 (Medium)
- 근거 코드:
  - `src/ui/dialogs/batch.py:73-110` (`_parse_urls` 루프)
  - `src/ui/dialogs/batch.py:95` (`NaverURLParser.fetch_complex_name` 직접 호출)
  - `src/core/parser.py:96-101` (`urlopen(timeout=10)`)
- 리스크:
  - URL/ID 입력량이 많거나 네트워크 지연 시 다이얼로그가 체감상 멈춘 것처럼 보일 수 있습니다.
- 권장 보완:
  - 이름 조회를 worker thread로 분리.
  - 취소 버튼/타임아웃 표시/진행률 표시 추가.

### 4) `analysis.py` 동일 클래스 중복 정의 (Medium)
- 근거 코드:
  - `src/core/analysis.py:4` (`class MarketAnalyzer`)
  - `src/core/analysis.py:138` (`class MarketAnalyzer` 재정의)
  - `src/core/analysis.py:114`, `src/core/analysis.py:248` (`ComplexComparator`도 중복)
- 리스크:
  - 후반 정의가 앞선 정의를 덮어써서 수정 누락/오해를 유발합니다.
- 권장 보완:
  - 중복 블록 제거 후 단일 정의만 유지.
  - 해당 파일에 대한 회귀 테스트 1~2개 추가.

### 5) 예약 실행이 현재 목록을 먼저 비우는 동작 (Medium)
- 근거 코드:
  - `src/ui/app.py:522` (`_run_scheduled`)
  - `src/ui/app.py:530` (`self.crawler_tab.clear_tasks()`)
  - `src/ui/app.py:535` (`start_crawling()` 호출)
  - `src/ui/widgets/crawler_tab.py:783-787` (이미 실행 중이면 시작 거부)
- 리스크:
  - 크롤링 실행 중 예약 트리거가 오면 시작은 거부되지만, 목록은 이미 덮어써질 수 있습니다.
- 권장 보완:
  - `isRunning()` 체크를 `_run_scheduled` 초기에 수행해 실행 중이면 목록 변경 없이 skip.

### 6) 최근 검색 히스토리 dedupe 기준이 단지 목록만 포함 (Low)
- 근거 코드:
  - `src/core/managers.py:127` (`complexes`만 비교해 중복 제거)
- 리스크:
  - 같은 단지라도 거래유형/필터가 다른 검색 이력이 덮어써져 사용자 맥락이 손실됩니다.
- 권장 보완:
  - dedupe key에 `trade_types`(+필요시 필터 fingerprint) 포함.

### 7) 빈 결과에 대한 캐시 미저장으로 불필요 재요청 가능 (Low)
- 근거 코드:
  - `src/core/crawler.py:527` (`if cached_items:`)
  - `src/core/crawler.py:564-565` (raw_items가 있을 때만 cache set)
- 리스크:
  - 특정 단지/유형이 자주 0건일 때 반복 네트워크 요청이 발생합니다.
- 권장 보완:
  - `0건`도 short TTL로 negative cache 저장 옵션 제공.

### 8) 버전 메타데이터 불일치 (Low)
- 근거 코드/문서:
  - `src/utils/constants.py:2` (`APP_VERSION = "v14.0"`)
  - `README.md:1` (`v14.2`)
  - `claude.md:1` (`v15.0`)
- 리스크:
  - 사용자/운영/이슈 대응 시 버전 혼동.
- 권장 보완:
  - 단일 버전 소스(`pyproject`/`version.py`)로 통합.

### 9) DB 저장 완료 카운트가 실제 insert와 불일치 가능 (Low)
- 근거 코드:
  - `src/core/database.py:440-452` (중복도 `True` 반환)
  - `src/ui/widgets/crawler_tab.py:564-573` (반환값 `True`면 저장 카운트 증가)
- 리스크:
  - 사용자에게 실제 신규 저장 수보다 큰 숫자가 표시될 수 있습니다.
- 권장 보완:
  - `add_complex` 반환을 `inserted/existing/error`로 분리.

### 10) 수동 입력 단지 ID 검증 부재 (Low)
- 근거 코드:
  - `src/ui/widgets/crawler_tab.py:536-543` (`_add_complex`)
- 리스크:
  - 비정상 ID가 그대로 대상 목록에 들어가 크롤링 실패/소음 로그 증가.
- 권장 보완:
  - 숫자 형식 검증 및 사용자 피드백.

## 테스트 보강 제안
- `shutdown_crawl`이 retry/sleep 구간에서도 일정 시간 내 종료되는지 테스트.
- `delete_complex` 후 `group_complexes` 정리 여부 테스트.
- `_run_scheduled`가 실행 중 크롤러 상태에서 목록을 보존하는지 테스트.
- URL 배치 분석에서 다건 입력 시 UI non-blocking 동작 테스트(또는 worker unit test).
- `analysis.py` 중복 제거 후 회귀 테스트.

## 우선 적용 추천 순서
1. 종료 경로 취소 가능화(High)
2. 그룹 매핑 정합성 보장(Medium)
3. URL 배치 비동기화(Medium)
4. `analysis.py` 중복 제거(Medium)
5. 예약 실행 덮어쓰기 방지(Medium)

## 구현 반영 현황 (2026-03-02)
- 상태: 계획 항목 10/10 반영 완료
- 버전: `v15.0` 기준으로 문서/코드 메타데이터 정렬
- 검증:
  - 명령: `PYTHONPATH=. pytest -q`
  - 결과: `77 passed`
- 추가 점검:
  - `naverland-scrapper.spec` 재점검 결과 추가 hidden import 수정 불필요
  - `.gitignore` 재점검 결과 신규 ignore 규칙 추가 필요 없음
