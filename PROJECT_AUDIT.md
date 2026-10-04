# Project Audit — naverland-scrapper

> One-shot functional audit (2026-10-04, current tree including v15.2 keyword
> search / filter / marker changes). 코드 수정 없음. 루트에 기존
> `PROJECT_AUDIT.md`(이전 다영역 감사 합성본)가 있었으나, 본 보고서는 현 소스를
> 직접 검증(CodeGraph + 원문 열람 + 테스트 실행)한 독립 결과이며 이전 보고서의
> 결론을 계승하지 않는다. 이전 보고서가 지적한 4건(지오메트리·락 해제·즐겨찾기·
> 에러 시그널)은 현 코드에서 수정 완료를 확인했고 §4 말미에 기록한다.

## 1. Executive Summary

- 프로젝트 전체 상태: 네이버 부동산 매물 수집 Windows 데스크톱 앱(PyQt6 +
  Playwright/Selenium). 핵심 경로(수집·DB·백업/복원·업데이트 서명)에 방어 로직이
  촘촘하고, 이전 감사 지적이 실제로 수정되어 있다. 전체 위험도는 **관리 가능**
  수준이며 Critical은 발견하지 못했다.
- 전체 위험도: Medium (아래 2건이 상한).
- 가장 중요한 문제 2개:
  1. 키워드 검색 세션 생성 실패 시 브라우저/드라이버 프로세스 누수 (Medium / Confirmed).
  2. 가격 스냅샷 백그라운드 저장이 종료 대기 없이 앱 종료와 경합 (Medium / Likely).
- 데이터 손상/유실 가능성: 확정적 경로 없음. 복원(롤백+검증), 원자 쓰기,
  upsert 멱등, 풀 종료 규율이 갖춰져 있다. 유실 가능성은 파생 스냅샷 1배치
  수준(§4 ISSUE-002)에 한정된다.
- 가장 먼저 수정해야 할 영역: `KeywordSearchDialog` 워커의 세션 수명주기
  (생성 실패 경로에 `close()` 보장).

## 2. Project Understanding

- 프로젝트 목적: 네이버 부동산(APT/VL) 매물 수집·가격 추적·예약 수집·Excel/CSV
  내보내기를 지원하는 Windows 데스크톱 Fluent UI 앱.
- 주요 entrypoint: `app_entry.py::main` → `src/main.py::main`
  (stdio 인코딩 → 폰트dir → `bootstrap_runtime_paths` → logger →
  `run_preflight_checks(profile="startup")` → QApplication → 테마 →
  `RealEstateApp()` → `app.exec()`).
- 핵심 모듈: `src/core/crawler.py`(QThread) + `crawler_parts/*`(상태·이력·IO),
  `engines/playwright_*`(complex/geo/detail/marker), `engines/*selenium*`
  (폴백), `core/parser*`(URL/ID/단지명 역조회), `services/*`(site_contract,
  keyword_search, detail_fetcher, response_capture, export 아님),
  `core/database*`(ConnectionPool + 도메인 믹스인), `core/managers*`(settings·
  cache), `utils/update_*`(manifest Ed25519·installer), `ui/app_parts/*`
  (탭·스케줄·DB관리·종료), `ui/widgets/crawler_tab_parts/*`(수집 컨트롤·렌더·필터).
- 데이터 저장 방식: SQLite(WAL, busy_timeout 30s, FK ON) + ConnectionPool(5) +
  도메인별 get/return 규율. 설정·캐시·이력은 `atomic_write_json`(tmp+fsync+
  os.replace) + 손상 시 백업 후 기본값 복구. 백업은 sqlite backup API+검증,
  복원은 사전 백업→풀 종료→copy→교체→재검증→실패 시 롤백.
- 외부 의존성: 네이버 랜드(new/fin/m) + `raw.githubusercontent.com` 업데이트
  manifest, 로컬 Chrome 또는 Playwright Chromium, openpyxl/matplotlib 등.
- 핵심 실행 흐름:
  - 수집: `start_crawling`(검증→CrawlLock→스레드) → 엔진(수집→detail 보강→
    _push_item→배치 시그널) → `_on_crawl_finished`(캐시 flush→스냅샷 동기 저장→
    data_collected→`_on_crawl_data_collected` 저장+새로고침) → Result.
  - 지도: 좌표 입력 → `apply_geo_profile` → sweep(마커 API→DOM 캡처 보조→
    discovered 등록→매물 수집) → Result.
  - 키워드: 입력(디바운스) → `/api/autocomplete` 제안 → `/api/search`(단지/
    지역) → 체크 추가 또는 지역→지도 탭 → Result.
  - 종료: `closeEvent` → tray/confirm 분기 → `_shutdown`(크롤 종료 대기→락 강제
    해제→업데이트 워커 대기→지오메트리 저장→DB close) → Result.

## 3. Audit Coverage & Limitations

- 실제 확인한 주요 모듈: 진입점·preflight·설정/캐시·DB 풀/복원/즐겨찾기·스케줄·
  종료·업데이트 manifest/installer·export 원자쓰기·재시도·detail 풀·마커 폴백·
  키워드 서비스/다이얼로그·필터·가이드/단축키.
- CodeGraph로 분석한 호출 관계(6회 explore): 진입점·종료 수명주기, 크롤러
  스레드/엔진/차단감지, DB 풀·bulk·즐겨찾기·마이그레이션, 업데이트·종료·즐겨찾기
  배선, geo 스윕·폴백·detail·재시도, 설정/캐시/스케줄, 키워드 세션/워커/종료·
  export. 동적 디스패치 2곳(시그널 emit)은 발신점으로 추적 종료.
- 실행한 테스트(모두 본 감사 중 직접 실행, 통과): audit/DB/managers/retry/
  preflight/export/parser/crawler 164개, 신규 키워드·필터·마커·계약 50개+,
  UI smoke 17개, finish/regression/wiring 83개, pyright 266파일 0 errors,
  compileall. 총 300+ 통과.
- 확인하지 못한 환경/외부 서비스: 실제 네이버 대상 live 수집(본 감사는
  오프라인; 네트워크 검증은 별도 선행 프로브 범위), 패키징 exe·업데이트 실서버,
  Linux/macOS·트레이 미지원·다중 인스턴스·강제종료·디스크 가득 실물.
- 분석 한계: 정적+오프라인 테스트 중심이므로 타이밍 의존 race는 코드 흐름
  확정 수준이며, 장시간 실수집에서의 429·차단挙動은 재현하지 않았다. CodeGraph는
  정적 호출을 반환하므로 시그널 런타임 연결·스레드 인터리빙은 수동 추적했다.
- 테스트 실행 기록의 정직성: UI 3종 일괄 1회차에 Windows 임시 DB 파일 잠금
  (`PermissionError`, WinError 32)으로 56 실패가 났으나 재실행에서 83개 전부
  통과해 환경성으로 판단한다. 실행하지 않은 테스트를 통과로 기재하지 않았다.

## 4. High-Risk Issues

### [ISSUE-001] 키워드 세션 생성 실패 시 브라우저/드라이버 프로세스 누수

- **위치:** `src/ui/dialogs/search.py::_KeywordWorker._ensure_session` (35),
  `src/core/services/keyword_search.py::KeywordBrowserSession.__enter__` (181~209)
- **우선순위:** Medium
- **신뢰도:** Confirmed (코드 흐름 확정; 별도 런타임 재현 불필요한 결정적 경로)
- **문제:** `_ensure_session`에서 `session_factory().__enter__()`가 예외를 던지면
  세션이 `self._session`에 저장되지 않는다. `close_session`은 저장된 세션만
  닫으므로, 이미 `start()`한 playwright 드라이버와 `launch()`한 Chromium이
  영원히 남는다. `_shutdown_worker`의 `thread.wait(3000)` 뒤 `close_session()`
  호출도 저장된 게 없어 no-op이다.
- **발생 조건:** Chrome 미설치·Playwright 브라우저 부재·네트워크 차단·
  `goto("new.land...")` 실패 등 세션 수립이 실패하는 환경에서 제안/검색 시도
  때마다 1건씩. `_session`이 계속 None이므로 실패할 때마다 반복 누수된다.
- **영향:** 좀비 `chrome.exe`+드라이버 누적(메모리/CPU 점유, 사용자 PC에서 확인
  가능). 데이터 손상은 없다.
- **근거:** 위 두 함수의 원문 대조. 성공 경로·cancel 경로는 정리되나,
  `__enter__` 예외 경로만 정리가 없다.
- **반증 확인:** 유사한 기존 경로(`ArticleLookupBrowserFallbackSession`)는
  `finally: session.close()`로 보장되어 있어 반대로 본 경로의 누락이
  확정된다. Qt 시그널 정리는 삭제된 다이얼로그에 안전하므로 그쪽은 문제없다.
- **호출/영향 범위:** CodeGraph 기준 `KeywordBrowserSession` 호출자는
  `dialogs/search.py` 1곳, `fetch_suggestions` 6곳(동일 다이얼로그). 영향은
  키워드 다이얼로그 사용 세션에 한정.
- **권장 수정 방향:** `_ensure_session`에서 `__enter__` 실패 시 이미 시작된
  자원을 닫도록 `try/except` 안에서 `session.__exit__`을 호출하거나,
  `KeywordBrowserSession`에 생성-실패 정리(부분 초기화 롤백)를 둔다.
- **필요한 회귀 테스트:** `session_factory`가 `__enter__`에서 예외를 던지는
  스텁으로 제안/검색을 호출한 뒤, `close_session` 호출 여부와 무관하게 스텁의
  `__exit__`이 호출됐음을 단언. 성공 케이스는 기존
  `tests/test_keyword_search_dialog.py`가 커버한다.

### [ISSUE-002] 스냅샷 백그라운드 저장 스레드가 종료 대기에 없음

- **위치:** `src/ui/widgets/crawler_tab_parts/crawl_control_parts/snapshot_worker.py`
  (전체), `src/ui/app_parts/lifecycle_parts/shutdown.py::_shutdown` (12~66)
- **우선순위:** Medium
- **신뢰도:** Likely (경로 명확, 타이밍 윈도우 의존)
- **문제:** 수동 저장의 비동기 경로(`_start_price_snapshot_worker`)로 뜬
  `PriceSnapshotSaveThread`(부모=탭)는 어디에서도 join/wait되지 않는다.
  `_shutdown`은 크롤러 스레드·업데이트 워커만 대기한다. 저장 중 앱 종료 시
  (a) 탭과 함께 실행 중 스레드가 파괴되어 Qt abort 가능,
  (b) bulk 트랜잭션 중단 시 해당 배치 스냅샷이 롤백된다.
- **발생 조건:** [저장] 클릭 직후(수천 건 bulk 쓰기 중) 즉시 앱 종료.
  윈도우는 보통 수 ms~수 초 윈도우.
- **영향:** 최악 앱 비정상 종료 + 당회 파생 스냅샷(batch) 유실. 원본
  `article_history`는 별도 경로로 보존되므로 재수집·재생성 가능(유실 한정).
- **근거:** `_price_snapshot_worker` 참조가 `snapshot_worker.py` 5곳에만 있고
  종료·join 호출이 전수 검색 0건. `finish.py`의 완료 경로는 동기 저장이라
  해당 없음(범위 한정).
- **반증 확인:** `upsert`가 `ON CONFLICT DO UPDATE` 멱등이라 중복 저장은
  안전함을 확인(중복 실행 가설 기각). 그러나 실행 중 파괴는 멱등으로 막지
  못한다. DB `close()`는 풀만 닫고 스레드를 기다리지 않는다.
- **호출/영향 범위:** 수동 저장 버튼 경로만. 완료 시점 자동 저장은 동기라
  영향 없음.
- **권장 수정 방향:** `_shutdown`에 스냅샷 워커 대기(예: 5s 상한 후 진행)를
  추가하거나, 종료 시작 시점에 저장을 동기로 전환한다.
- **필요한 회귀 테스트:** 느린 DB 스텁(수 초 sleep) + 저장 개시 직후
  `shutdown_crawl`/`_shutdown` 호출 시 워커 완료 후 종료됨을 단언. 기존
  `tests/test_finish_summary.py`는 동기 경로만 커버한다.

### 이전 감사 지적의 현 상태 (재검증 완료, 수정됨)

| 이전 지적 | 현 코드 | 판정 |
|---|---|---|
| window_geometry 무검증 setGeometry 시작 크래시 | `bootstrap.py:100~176` 검증+클램프 단일 경로, 손상값 폴백 | 수정됨 |
| 빈 스레드 종료가 타 탭 CrawlLock 해제 | `start_stop.py:232~242` owner 보유 시만 해제 | 수정됨 |
| 즐겨찾기 DB 실패 무시하고 UI 갱신 | `settings_preset.py:274~312` 실패 시 keys 미갱신+토스트 | 수정됨(단, 카드 별 즉시 반영은 §5 잔여) |
| 에러 시그널 로그 전용·버튼 stale | `start_stop.py:201~230` 토스트+버튼 복구 | 수정됨 |
| 완료 시 스냅샷 비동기-락 해제 경합 | `finish.py:93~98` 락 보유 중 동기 저장 | 수정됨 |

### 본 감사 지적의 수정 상태 (2026-10-04 검증 완료)

| 지적 | 수정 내용 | 회귀 테스트 | 판정 |
|---|---|---|---|
| ISSUE-001 세션 생성 실패 누수 | `_ensure_session`이 `__enter__` 실패 시 `session.__exit__` 호출로 드라이버/브라우저 정리 | `tests/test_keyword_search_dialog.py::TestKeywordWorkerSessionCleanup` | 수정됨 |
| ISSUE-002 스냅샷 워커 종료 미대기 | `_wait_for_snapshot_worker(timeout 5s)` 추가 후 `shutdown_crawl`에서 호출, 탭 캐시 `flush()` 병행 | `tests/test_ui_wiring.py::test_snapshot_worker_wait_*`, `test_shutdown_flushes_tab_caches` | 수정됨 |
| 카드 별 실패 롤백 (구 §5 잔여) | DB 실패/False 시 `_revert_favorite_key_visual`로 양 탭 낙관적 상태 롤백, Duck-typed 호스트 대비 호출부 `try/except` 가드 | `tests/test_ui_wiring.py::test_favorite_*_reverts_visual_state`, 기존 `tests/test_audit_fixes.py::TestIssue003FavoriteToggle` 전수 통과 | 수정됨 |
| 키워드 429/쿨다운/재시도 | 전송 오류를 `KeywordSearchError`로 승격, 429 단일 재시도+30s 쿨다운, `failed(str,int,str)` kind 가드 | `tests/test_keyword_search.py::TestKeywordWorkerResilience` | 수정됨 |
| 테스트 픽스처 모지바케 | `tests/test_keyword_search*.py`의 한글 호환 자모 반복이 들어간 테스트 키워드를 `empty-query-zzz`로 교체 (자사 `test_mojibake_scan` 게이트 위반) | `tests/test_mojibake_scan.py` 통과 | 수정됨 |

게이트: `pytest tests/` 479 passed + 19 subtests, `pyright` errors+warnings 0, CI subset(`test_ui_wiring`, `test_mojibake_scan` 포함) 통과. `ruff`는 프로젝트 설정·CI 게이트가 없어 미적용(기본 룰셋 기준 전역 1387건 중 다수 선재, 신규 라인은 리포 관행 `except Exception` 일치·신규 I001 3건 정리).

## 5. Potential Functional Gaps

- **카드 별 낙관적 반영 미롤백 (Confirmed Gap, Low):** `cards.py:260~266`은
  클릭 즉시 별을 뒤집고 emit한다. DB 실패 시 `_on_favorite_toggled`이 토스트로
  알리지만 카드 별은 되돌리지 않는다(다음 새로고침에 정정, `favorite_keys`·DB는
  정확). 실패가 통지되므로 영향은 일시적 혼선에 한정.
- **키워드 429 단일 시도 후 침묵 (Likely Gap, Medium):** 세션 내 요청은
  상태 != 200이면 `[]` 반환(`keyword_search.py:140`, `151`) 후 제안 목록이
  비어 실패와 "결과 없음"을 구분 못 한다. 세션 단위로 쿨다운·재시도가 없어
  제한 상태에서 다이얼로그를 닫았다 열기 전에는 계속 빈 결과다.
- **제안 실패의 generation 미가드 (Likely, Low):** `_on_worker_failed`가
  generation을 무시하고 `_set_busy(False)`한다. 검색 실행 중 제안 실패가
  겹치면 버튼이 중간에 풀려 중복 페이지 요청→결과 중복 append 가능.
  (`_run_search`·`_load_more`의 busy 가드와 결합된 좁은 윈도우.)
- **Selenium 폴백의 VL 제외 (Logged limitation, Likely Gap):** `loop.py:89~93`
  에서 VL은 로그 후 건너뛴다. 예약 수집은 사전에 VL을 제외하고 고지하므로
  정합이나, 수동 수집의 VL 타깃은 폴백 없이 유실(로그 한 줄)된다.
- **종료 시 캐시 미flush (Confirmed, Low):** `crawl_cache.flush()` 호출자는
  `finish.py:91`뿐이라 2초 write-back 윈도우 내 종료 시 캐시 일부가 소실된다.
  캐시는 성능 용도라 재수집으로 복구 가능, DB 정합 영향 없음.
- **사망 코드 `src/utils/retry.py` (Confirmed dead, hygiene):** 전수 검색에서
  production import 0건. 현행은 cancel 지원 `retry_handler.py`를 사용한다.
  오용 방지 차원의 정리 대상(동작 영향 없음).
- **Chrome 없는 환경의 키워드 UX (Likely Gap):** 세션 수립 불가 시 제안·검색
  모두 빈 결과로만 보인다. preflight는 브라우저 부재를 경고하지만 다이얼로그
  진입점에는 capability 안내가 없다.

## 6. Documentation Mismatches

- **README 배지 v15.1 vs `APP_VERSION = "v15.2"** (`src/utils/version.py:1`,
  `README.md:6`): 릴리스 후 배지 미갱신. 기능 영향 없음.
- **README에 키워드 검색(v15.2) 미기재:** `guide_content.py`에는 🔍 버튼 안내가
  있으나 README 사용법(①~⑥)에는 ID·URL 방식만 있다. 신규 핵심 기능의 문서 누락.
- 명시적으로 불일치 아님: README의 "실시간 검색 (`Ctrl+F`)"는
  `SHORTCUTS["search"]="Ctrl+F"`(`constants.py:15`) + `_init_shortcuts` 등록으로
  실재한다. 고급필터 "동·중개업소" 검색 주장도 P1 blob 확장으로 현재 참이다.

## 7. Recommended Fix Plan

### Phase 1 — Immediate

1. ISSUE-001 세션 생성 실패 정리 보장 + 회귀 테스트(실패 스텁의 `__exit__`
   호출 단언). 영향이 현재 코드 2곳으로 국한된다.
2. ISSUE-002 종료 시 스냅샷 워커 대기(상한 5s) + 느린 DB 회귀 테스트.

### Phase 2 — Stability

3. 키워드 429/실패의 상태 구분(빈 결과 vs 오류 문구) + 세션 쿨다운·재시도 1회.
4. `_on_worker_failed` generation 가드 + 제안 클릭 후 디바운스 취소(불필요 요청 제거).
5. 카드 별 실패 시 롤백(또는 실패 시 즉시 해당 카드만 상태 복원).
6. 종료 시 캐시 flush(크롤러 탭·지도 탭) — 2줄 수준.
7. 사망 `retry.py` 제거 또는 `_deprecated` 명시.

### Phase 3 — Structural

8. VL Selenium 폴백 정책 결정(지원 추가 vs UI에서 사전 차단·고지 일원화).
9. 종료·워커 수명주기 통합(스냅샷·키워드·업데이트 워커의 단일 join 지점).
10. README 버전 배지·키워드 검색 문서화.

실제 코드는 수정하지 않는다(본 감사 범위).

## 8. Test Recommendations

- Unit: 세션 생성 실패 시 `__exit__` 호출(ISSUE-001); `close_all` 타임아웃+
  `force_after_timeout=False` 중단 경로(기존 커버 확인 후 부족분);
  `_is_default_advanced_filter(None/{})` 경계(기존 `test_result_filters.py` 확장).
- Integration: 느린 DB에서 저장→즉시 종료 시 스냅샷 워커 완료(ISSUE-002);
  복원 실패→롤백 후 `integrity_check`+필수 테이블 단언(이미 일부 존재,
  `still_leased` 중단 케이스 추가); DB 삭제 시 관련 6종 테이블 purge 단언.
- End-to-End: 키워드→추가→수집→스냅샷→export 한 사이클(가짜 세션+가짜 엔진),
  예약 geo 실행→좌표 적용→시작 실패 시 작업 복원.
- Concurrency: 풀 고갈(10s 타임아웃) 후 fallback 연결 생성·반납; 스냅샷 워커
  실행 중 탭 파괴 금지(또는 대기) 검증; 제안-검색 인터리브 중복 append 금지.
- Regression: 손상 `window_geometry` 행렬 시작 테스트(이미 수정됨, 고정용);
  owner 없는 `release` 금지(기존 `test_audit_fixes.py` 패턴 유지);
  즐겨찾기 실패 시 keys 불변 + 카드 별 복원.
- Platform-specific: `QT_QPA_FONTDIR` 없는 Windows 패키징 폰트, 트레이 미지원
  Linux의 `closeEvent` 분기, macOS 경로 길이·대소문자 DB 파일.

## 9. Final Assessment

- Functional Correctness: **Acceptable** — 핵심 수집·DB·복원·업데이트 경로가
  방어적으로 구현되어 있고, 과거 지적이 수정되어 있다. 신규 키워드 경로의
  실패 처리가 가장 약한 고리다.
- Runtime Stability: **Acceptable** — 스레드 종료 규율·재시도·상세 풀의
  stop 반응이 갖춰져 있다. 스냅샷 워커와 키워드 세션의 수명주기가 예외다.
- Data Integrity: **Good** — 원자 쓰기·upsert 멱등·복원 롤백+검증·삭제 시
  관련 purge·FK ON으로 손상 경로가 보이지 않는다.
- Error Resilience: **Acceptable** — 재시도·쿨다운·폴백·토스트가 있으나,
  키워드 경로의 침묵 실패와 제안/검색 경합이 약점이다.
- Cross-platform Robustness: **Needs Work** — Windows 중심(경로·트레이·폰트
  분기 존재)이나 Linux/macOS 실검증 흔적이 없고, Chrome 의존 경로의 대체
  안내가 부족하다.
- Test Confidence: **Acceptable** — 300+ 통과·회귀 고정 테스트가 있으나 live
  수집 E2E와 종료 경합 테스트가 비어 있다.

**실제로 먼저 수정할 문제 3개:**

1. ISSUE-001 키워드 세션 생성 실패 정리 (Medium/Confirmed).
2. ISSUE-002 스냅샷 워커 종료 대기 (Medium/Likely).
3. 키워드 429/실패 상태 구분 + 재시도 (Medium/Likely Gap) — 1번과 같은 파일이라
   묶음 수정이 효율적이다.
