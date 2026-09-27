# Project Audit — naverland-scrapper

> 합성 기준: 영역A(문서·진입점·시작종료·설정), 영역B(수집 엔진), 영역C(데이터·보안·업데이트), 영역D(UI 배선) 감사 결과만을 근거로 합성. 코드 수정 없음, 원본 소스 재열람 없음(영역 보고서의 인용 위치·반증 기록을 그대로 계승). 없는 증거를 새로 지어내지 않음. 중복은 병합, 과장 없음.

## 1 Executive Summary

- 진입점 흐름(`app_entry.py main` → `src/main.py main` → stdio→`bootstrap_runtime_paths`→logger→`run_preflight_checks(profile="startup")`→QApplication→`setup_app_theme`→`RealEstateApp()`→`app.exec()`)은 문서·구현 일치. `README` 시작법·`spec` 진입점·`ci.yml`↔`ci_check.ps1` subset 관계도 동기화됨.
- High-Risk 3건: (1) 손상된 `window_geometry`가 생성자 앞단 무검증 `setGeometry`에서 시작 크래시 (High/Confirmed), (2) 스레드 없는 탭의 `shutdown_crawl()`이 `release(None)`로 타 탭의 CrawlLock을 해제 (High/근거 강한 Likely), (3) 즐겨찾기 토글이 DB 실패 반환값을 무시하고 메모리·UI를 갱신 (High/Confirmed).
- 그 외 Medium 8건 내외(종료 정리 누락 후보, `UnicodeDecodeError` 복구 사각, 스냅샷 락-이후 생존, detail `pool.get()` 중지 지연, 스냅샷 rollback 누락 등)와 Low/정보성 다수가 확인됨. SQL 인젝션·업데이트 서명 우회·백업/복원 경로에서는 확정된 취약점 없음(강점 확인).
- 문서 불일치는 1건이 확정적: 신규설치 테마 AUTO 독스트링 vs 기본값 `"dark"`.

## 2 Project Understanding

관측된 흐름을 Entry→Handler→Core→DB/File/API→Result 형태로 정리한다.

- **Entry**: `app_entry.py main` → `src/main.py main`. stdio 설정 → `bootstrap_runtime_paths` → logger → `run_preflight_checks(profile="startup")` → `QApplication` → `setup_app_theme(app, settings.get("theme","dark"))` → `RealEstateApp()` → `app.exec()`.
- **Handler (UI 배선)**: 수집 `start_crawling`(검증/락/스레드 생성) → 워커 시그널(`items`/`stats`/`complex_finished`/`error_signal`/`alert`) → 슬롯(`_on_crawl_finished` → `data_collected.emit` → `_on_crawl_data_collected`(수집저장+stale+현재탭 새로고침), `_on_alert_triggered` → toast+plyer, 상태바 `showMessage`). 프리셋 로드·고급필터·URL 배치(`dialogs`→`batch`, generation 가드·cancel)·Excel 템플릿·차트/대시보드 lazy 배선은 정상으로 보고됨.
- **Core (수집 엔진)**: geo/complex 탭별 QThread + cross-tab 단일 `CrawlLock`(동일탭 `isRunning`, 예약작업 `is_held` 체크) + detail 페이지 풀(`pool.get`/`put`) + retry/backoff + drain(취소+재gather, 3s 상한) + 메모리 recycle(`_shutdown_async()+_ensure_started()`).
- **DB/File/API**: 수집 → `build_price_snapshot_rows` → bulk upsert(`ON CONFLICT DO UPDATE`) → 조회 → export(CSV/XLSX/JSON). 캐시는 `_dirty`+`write_back_interval_sec`(기본 2초)+`atomic_write_json`(tmp+`os.replace`+fsync). 백업/복원은 `sqlite backup` API+복원 전 `integrity_check`. 업데이트는 manifest Ed25519+HTTPS+size/expiry → 아티팩트 sha256 → 부모 종료 대기→`.bak`→`os.replace`→`--preflight` 스모크→실패 시 롤백→`last-update-result.json`.
- **Result**: 테이블 표시·통계/히스토리·즐겨찾기·알림 토스트·내보내기 파일. 실패 통지는 export(`ExportResult(ok=False)`→QMessageBox)에서는 정상이나, 수집 `error_signal`은 로그 append에만 연결된 것으로 보고됨.

## 3 Audit Coverage & Limitations

- **범위**: 4개 영역 보고서의 인용 위치·반증 시도만을 근거로 합성. 본 합성 단계에서 소스·테스트·설정·외부 문서 본문을 새로 열람하지 않았으므로, 위치 행번호·코드 인용의 정확성은 각 영역 감사의 직접 열람 기록에 의존한다.
- **CodeGraph 사용 여부**: 본 합성 작업에서는 CodeGraph(`codegraph_explore` 등)를 사용하지 않았다. 영역 보고서에도 CodeGraph 사용 기록이 명시되어 있지 않아, 호출 그래프 미확인 지점(아래)은 그대로 미해결로 이월한다.
- **확인 못한 환경·외부서비스**: 실제 OS 연동 테마(AUTO) 동작, 트레이 가용/비가용 실환경, 모니터 변경 시 오프스크린, 비-UTF8 손상 파일 실물, 디스크 가득/잠금 타임아웃 실물, 다중 인스턴스 동시 실행, qfluentwidgets 부재 환경의 InfoBar 폴백, 강제종료 사이 `.bak` 고아 조건은 재현하지 않았다. 외부 네트워크(네이버 랜드, 업데이트 서버) 대상 live 검증은 영역B의 live smoke가 별도 프로브 경로로 수집 락·DB 미사용임이 보고된 범위로만 이해한다.
- **분석 한계 및 미해결 증거 이월**(호출자 요구 `미해결 항목: []`에 따라 별도 미해결 리스트를 두지 않고 본 절에 이월):
  - B-F4 recycle 호출 지점(루프 내 위치) 미열람 → Speculative 유지.
  - C 미해결 1건: `PriceSnapshotSaveThread`(crawler_tab)와 `_save_price_snapshots`(finish 경로)의 이중 저장 가능성은 호출 그래프 재검색이 빈 결과로 끝나 미확인. finish 경로 저장 호출 1회성 여부는 소유자 확인 필요.
  - A-3 전체 스레드 인벤토리 미확보 → Likely 유지.
  - D-U1 `currentChanged→_refresh_tab` 자동 연결 코드 미발견 → Speculative(정보성)로 유지.
  - D-F3 크롤러 alert emit부 원본 미열람 → Likely로 한정.
  - C-4 종료 시 `flush()` 호출 여부 미확인.

## 4 High-Risk Issues

High-Risk 선정 기준(호출자 요구): Confirmed와 근거 강한 Likely만. 3건.

### ISSUE-001 — 윈도우 지오메트리 이중 적용, 앞단이 무검증 (High / Confirmed)

- **위치**: `src/ui/app_parts/lifecycle_parts/bootstrap.py:32-33` vs `:102-113`, `:90` / 저장 `shutdown.py:39`(`_shutdown`은 항상 4원소 list 저장).
- **우선순위**: P0 (시작 크래시 경로).
- **문제**: `__init__` 앞단에서 `if geo: self.setGeometry(*geo)`를 try 없이 호출. 길이≠4·비수치 저장값이면 `TypeError`가 생성자에서 그대로 전파. 뒤단 `_restore_window_geometry()`의 형식 검증은 앞단이 이미 실패한 뒤라 무용. 오프스크린 클램프도 없음.
- **발생조건**: `settings.json`의 `window_geometry`가 깨진 길이/타입으로 저장된 경우(수동 편집·구버전·부분 쓰기)마다.
- **영향**: 앱 시작 크래시. 모니터 변경 시에는 클램프 부재로 창 실종 가능.
- **근거**: 영역A가 해당 3개 위치 본문 직접 대조. 저장 경로는 정상(4원소 list)임을 확인.
- **반증확인**: `_shutdown` 정상 저장값은 안전. `set()`→`_save()` 원자쓰기라 부분쓰기 가능성은 낮음 → 현실성은 수동편집/구파일 중심. 그러나 로드 경로가 손상값을 가정하지 않으므로 외부 손상 시 확정.
- **호출영향범위**: 첫 실행 포함 모든 시작 경로. 손상값이 있는 설치체 전체.
- **수정방향**: 앞단 직접 `setGeometry` 제거하고 검증된 `_restore_window_geometry()` 단일 경로로 일원화(검증 실패 시 기본 지오메트리로 폴백+경고 로그). 오프스크린 클램프(가용 스크린과의 교집합 확인) 추가.
- **회귀테스트**: 손상값 행렬(길이 3/5, 문자열 혼합, None, 음수/초대형 좌표) 주입 시작 테스트. 정상값·부재값은 기존 동작 유지 확인.

### ISSUE-002 — 빈 스레드 종료 경로가 타 탭의 CrawlLock을 해제 (High / 근거 강한 Likely)

- **위치**: `src/ui/widgets/crawler_tab_parts/crawl_control_parts/start_stop.py:201-222`, `src/core/crawl_lock.py:22-29`, `src/ui/app_parts/lifecycle_parts/shutdown.py:12-34`.
- **우선순위**: P0 (cross-tab 중복 실행 가드 붕괴).
- **문제**: `_release_crawl_lock()`은 `self._crawl_lock_owner`(없으면 `None`)를 그대로 전달하고, `CrawlLock.release(None)`은 owner 무관 전체 해제. `shutdown_crawl()`의 `thread is None / not Running` 분기(217-222행)가 이 경로를 탄다.
- **발생조건**: complex 수집 실행 중(`owner="complex"`)에 geo 탭의 스레드-없는 `shutdown_crawl()`(앱 종료 시 `crawler_tab → geo_tab` 순차 호출, DB maintenance 경로) 호출 시 complex 락이 풀림.
- **영향**: cross-tab 중복 실행 가드가 깨짐(cross-tab 방지는 락이 유일 — 동일탭만 `isRunning` 체크, 예약작업은 `is_held` 체크). 중복 수집→DB 쓰기 중첩으로 파급 가능(B-F2와 결합 시 증폭).
- **근거**: 영역B가 위 3개 파일 본문 직접 열람.
- **반증확인**: 정상 finish 경로(`finish.py:115-120`)는 owner 보유 상태 해제라 안전. `force_release`는 종료 시 1회라 의도됨. 그러나 `release(None)`의 best-effort 의미가 종료-청소와 정상-해제를 구분하지 않아 오인 해제 가능 — 반증 실패. 근거가 강한 Likely로 High-Risk 포함.
- **호출영향범위**: 앱 종료·DB maintenance에서 탭 순차 종료를 호출하는 모든 경로.
- **수정방향**: `release(None)`의 의미를 종료-청소 전용으로 분리(예: 정상 해제 경로는 owner 필수, `None`은 `force_release` 명시 호출로만). 또는 shutdown 시 탭별 owner 보유 탭만 해제하도록 가드.
- **회귀테스트**: complex 실행 중 geo 빈-스레드 `shutdown_crawl()` 호출 후 `is_held`가 유지되는지 확인. 양 탭 idle 종료 시 락이 정상 해제되는지 확인.

### ISSUE-003 — 즐겨찾기 토글: DB 실패를 무시하고 메모리·UI를 갱신 (High / Confirmed)

- **위치**: `src/ui/app_parts/settings_preset.py:264-288` / DB `src/core/database_parts/article_parts/favorite_ops.py:20-54` / 연결 `notify.py:141`.
- **우선순위**: P0 (사용자 가시 상태 불일치).
- **문제**: `_on_favorite_toggled`이 `try/finally`로 `db.toggle_favorite()` 반환값(False=실패)을 검사 없이 `favorite_keys` 추가·제거 + 크롤러/지오 탭 상태 갱신. 예외 시에도 `finally`라 UI 갱신됨.
- **발생조건**: DB 락/디스크 오류 등 `toggle_favorite`가 False 반환 시 항상. production 도달 가능(카드·최근본매물 다이얼로그에서 직접 연결).
- **영향**: UI는 즐겨찾기로 보이나 재진입 시 사라지는 상태 불일치. 사용자가 저장됐다고 믿는 동작.
- **근거**: 영역D가 `settings_preset.py:268-279`, `favorite_ops.py:49-52` 직접 대조. 래퍼·트랜잭션 보정 없음 확인.
- **반증확인**: 호출부에 재시도/롤백 없음 확인. 반증 실패 → Confirmed.
- **호출영향범위**: 즐겨찾기 토글 진입점 전체(카드·최근본매물 다이얼로그).
- **수정방향**: 반환값 검사 후 실패 시 메모리·UI 갱신 건너뛰고 토스트/로그로 실패 통지. 예외 경로도 동일(갱신 전 DB 성공 확정 후 UI 반영).
- **회귀테스트**: `toggle_favorite` False 주입 시 `favorite_keys`·탭 상태 불변 + 실패 토스트 확인. True 시 기존 동작 유지.

## 5 Potential Functional Gaps

표기: (Confirmed) / (Likely) / (추정). High-Risk 3건과 중복 기재하지 않고 상호참조한다. 심각도는 영역 판정을 계승한다.

- **ISSUE-004 — 신규설치 테마 AUTO 문서와 기본값 "dark" 불일치 (Medium / Confirmed)**: `src/ui/fluent/theme.py:24-31`, `src/core/managers_parts/schedule_defaults.py:5`, `src/main.py:105`, `bootstrap.py:68`. `theme_from_settings` 독스트링 "미지정(신규 설치)은 OS 연동(AUTO)"이나 `DEFAULT_SETTINGS["theme"]="dark"`라 `settings.get("theme","dark")`→`"dark"` 전달로 AUTO 분기 도달 불가. `sanitize`에 theme 강제 없음(`settings_sanitize.py`에 theme 처리 없음) 확인. 기능 파손은 OS-연동 체감 불가에 한정. → §6에도 기재.
- **ISSUE-005 — 종료 시 정리 누락 후보, 타이머·업데이트 워커 (Medium / Likely)**: `shutdown.py:12-46`, `timers_events.py:12-15`, `updates.py:12-19`, `theme.py:96-112`. `_shutdown`은 crawl 탭×2·`schedule_timer`·DB·tray·crawl_lock만 처리. `UpdateController` 워커 join, 테마 watcher `QTimer`(app 부모라 종료까지 폴링 지속), 예약 실행 중 크롤 명시 대기 없음. `closeEvent`+`_quit_app` 모두 `_shutdown()` 게이트 경유라 무조건 종료되지는 않음. `_on_update_downloaded`는 `_shutdown()` 성공 후 `QApplication.quit()`라 워커 잔존 시 조용한 지연 가능.
- **ISSUE-006 — 손상 settings.json `UnicodeDecodeError` 복구 사각 (Medium / Likely)**: `src/utils/json_store.py:42-60`, `settings_manager.py:70-85`. `load_json_with_recovery`가 `(OSError, json.JSONDecodeError)`만 포착. 비-UTF8 바이트 손상은 `open().read()` 단계 `UnicodeDecodeError` → 포착漏れ로 시작 크래시, `.broken` 백업·기본값 복구 불가. 순수 JSON 문법 파손·파일 부재는 정상 복구 확인. 정상 쓰기는 utf-8만(`atomic_write_json`)이라 외부 손상 한정.
- **ISSUE-007 — 스냅샷 비동기 저장이 락 해제 이후까지 생존 (Medium / Likely)**: `crawl_control_parts/finish.py:93-120`, `snapshot_worker.py:13-43`. `_on_crawl_finished`는 `try`에서 `_save_price_snapshots()`(비동기 워커 시작 후 즉시 리턴) → `finally`에서 `_release_crawl_lock()`. 락 문서목적("DB writes never concurrent", `crawl_lock.py:1`)과 달리 워커의 `add_price_snapshots_bulk`는 다음 수집과 DB 쓰기 중첩 가능. WAL+`busy_timeout=30000`+lease로 파손 가능성은 낮음 → 불변식 위반 중심. ISSUE-002와 결합 시 증폭.
- **ISSUE-008 — detail 워커 `pool.get()` 무한 대기로 중지 지연 (Medium / Likely)**: `playwright_parts/runtime_parts/browser.py:240-274`, `complex_mode_parts/detail_enrichment.py:164-242`. `_fetch_one`은 acquire 전 `_should_stop` 미확인, `_acquire_detail_page`의 `await pool.get()`에 타임아웃/중단 체크 없음. `_worker` stop 체크는 큐 `get_nowait` 전에만 있어 풀 고갈 시 중지 요청이 페이지 반납까지 대기. 중지 후 1개 아이템 추가 수집 후 종료. 전원 교착은 아님(워커수==풀max라 반납으로 해소). retry backoff·abort는 정상 확인 → 지연 문제로 한정.
- **ISSUE-009 — 메모리 recycle이 진행 중 detail 페이지를 구 컨텍스트와 섞음 (Medium / 추정)**: `browser.py:139-158,276-307`. `_check_memory_and_recycle_if_needed`가 `_shutdown_async()+_ensure_started()`로 풀·컨텍스트 교체. 비행 중 워커가 쥔 구 페이지는 `close()`된 컨텍스트 소속인데 `_release_detail_page`가 해제 시점의 신규 풀에 `put`하여 혼합. 호출 지점 미열람이라 추정. 후속 `browser.close()`가 전부 닫아 누수는 bounded.
- **ISSUE-010 — 스냅샷 쓰기 실패 시 rollback 누락 (Medium / Likely)**: `crawl_snapshot_parts/price_snapshot_write_ops.py:47-53,158-162`. 단건·bulk 모두 예외 경로에 `conn.rollback()` 없이 `finally`에서 dirty 커넥션 반환. 다음 대여자에게 열린 실패 트랜잭션이 넘어갈 수 있음. 형제 코드(`crawl_history_ops.py:62-82`, `article_bulk_ops.py:170-190`, `complex_group_ops`의 `_rollback_write_transaction`)는 전부 rollback → 의도적 관례 아님. WAL+`busy_timeout` 하 흔한 잠금 실패는 재시도도 없어 단건 실패가 `0`/`False`로 끝남(해당 배치 국한).
- **ISSUE-011 — bulk 저장 건수 과대 보고 (Low / Confirmed)**: `price_snapshot_write_ops.py:137-157`. dedup 후 `executemany`는 dedup된 행으로 실행하면서 반환값은 `len(normalized_rows)`(dedup 전). `ON CONFLICT DO UPDATE` 멱등이라 데이터 손상 아님, 카운트 표시 문제로 한정. → §6 표시 불일치로도 참조.
- **ISSUE-012 — 캐시 내부 리스트 직접 반환, 별칭 (Low / Likely)**: `src/core/cache.py:211-215`. `get()`이 `entry["raw_items"]` 원본 반환 → 호출자 변경 시 캐시 오염 전파. 현 호출부(`snapshot_worker`, `PriceSnapshotSaveThread`)는 복사·재가공 후 사용해 현실 발현 제한적. `list(...)` 방어 복사로 제거 가능.
- **ISSUE-013 — 캐시 write-back 손실 창 (Low / 추정)**: `src/core/cache.py:19-24,155-160,285-289`. `_dirty`+`write_back_interval_sec`(기본 2초)라 비정상 종료 시 최대 2초치 미반영 분실 가능. 종료 시 `flush()` 호출 여부 미확인. `atomic_write_json` 자체는 찢긴 쓰기 없음. 프로세스-로컬 락이라 다중 인스턴스는 last-writer-wins(파일 손상은 아님).
- **ISSUE-014 — 내보내기 비원자적 저장 (Low / Likely)**: `src/core/export.py:264,279-280,310`. `wb.save`/CSV/JSON 모두 사용자 경로 직접 기록 → 크래시 시 반쪽 파일(기존본 덮어쓰기 시 기존본 손상). 실패 통지는 정상(`ExportResult(ok=False)`→QMessageBox, `io_actions.py:165-174`). 인코딩 양호(CSV `utf-8-sig`, JSON `utf-8`, 파일명 콜론 없음). 수식 인젝션 반증 완료(`_sanitize_spreadsheet_value`가 `=,+,-,@,tab,CR` 중화, 우회 특수컬럼은 내부 상수·숫자).
- **ISSUE-015 — `PRAGMA index_info(idx)` f-string (Low / 추정)**: `schema_parts/migrations.py:49,97,374`, `schema_normalize.py:92`. 이름 출처가 `PRAGMA index_list` 결과(자체 DB)라 외부 입력 도달 경로 없음. 악성 DB는 이미 동등 권한 위치 → 실제 공격면 아님. 식별자 쿼팅 권장 수준.
- **ISSUE-016 — 그룹 탭 새로고침 무보호 + 즐겨찾기 메모 저장 무보호 (Medium / Confirmed)**: `tab_setup.py:555-556`→`group_tab.py:130-135`, `tabs.py:143-168`. `_refresh_tab` GROUP 분기는 try/except 없이 `load_groups()`→`db.get_all_groups()` 무보호(통계 분기는 보호 있음과 비대칭). `FavoritesTab._edit_note`도 `db.update_article_note` 무보호 후 `refresh()`. `DatabaseTab.load_data(:118-142)`는 보호 보유 → 패턴 미적용 문제.
- **ISSUE-017 — 알림 슬롯 `area_pyeong:.1f` 포맷, 비수치 시 슬롯 예외 (Medium / Likely)**: `timers_events.py:23-26`, 시그널 `crawler_tab.py:147`, `crawler.py:61`. `f"{area_pyeong:.1f}"` — 크롤러가 None/문자열 emit 시 TypeError(UI 스레드). 시그널 float 선언이나 Python emit 강제 약함. 내부는 보호됨. 크롤러 emit부 원본 미열람이라 Likely.
- **ISSUE-018 — 탭 새로고침이 UI 스레드 동기 DB 조회 (Medium / Likely)**: `tab_setup.py:547-583`, `database_tab.py:118-142`, `group_tab.py:130-167`, `stats_history.py:43-86`. DB/GROUP은 stale 가드 없이 매 전환마다 동기 실행(history/stats/favorites/dashboard만 `_noncritical_loaded` 가드). 대량 행 `setItem` 루프가 이벤트루프 점유(최소 보호 `blockSignals/setUpdatesEnabled/sorting off`는 있음). 디바운스/상호배제 없음.
- **ISSUE-019 — 에러 시그널이 로그만, 버튼·데이터 stale (Low / Likely)**: `start_stop.py:185-186`, `finish.py:22-120`. `error_signal` 연결이 `append_log` 람다뿐. 복구는 `finished_signal→_on_crawl_finished` 도착에만 의존. 정상 경로는 finished 항상 emit(QThread run 종료) → 비정상(강제종료 등) 한정. Geo `_on_crawl_finished(:507-573)` 정상계열은 복구됨.
- **ISSUE-020 — Toast 폴백 위치 0-size 기준 + 중복제거 경합, 완화됨 (Low / Likely)**: `lifecycle_parts/notify.py:12-70`, `widgets/toast.py:158-169`, `fluent/notify.py:8-53`. InfoBar 우선 구조 양호. 폴백에서 show 전 `width()/height()`로 오배치 가능. 이중 제거 경로는 `in` 검사/예외 포착으로 완화. 부재 환경 연속 토스트 한정, 크래시 아님.
- **ISSUE-021 — 단축키 등록 딕셔너리 덮어쓰기 (Low / Confirmed)**: `lifecycle_parts/shortcuts_actions.py:12-27`. `_register_shortcut`이 `self._shortcuts[key]=shortcut` 저장. 중복 키 시 기존 QShortcut이 부모 보유로 잔존해 이중발화 가능. 기본 상수 충돌 없음(`constants.py:12`) → production 영향 낮음.
- **ISSUE-022 — `minimize_to_tray=True` 기본값, X가 종료가 아님 (Low / Confirmed, 의도된 동작)**: `schedule_defaults.py:5`, `shutdown.py:61-71`, `tray.py:12-22`. 기본 True+tray 가용 시 `closeEvent`는 `ignore()` 후 숨김, `confirm_before_close`도 건너뜀. tray 미가용 시 폴백 후 정상 종료(`tray.py:24-27`). README "트레이 백그라운드"와 정합. 사용자가 모르는 백그라운드 수집(스케줄 타이머 지속) 가능 → 문서 정합성 지적로 유지.
- **정보성 U1 — 탭 전환→`_refresh_tab` 자동 연결 증거 없음 (추정)**: `tab_setup.py:547`, `tab_bridge.py:101-109`, `bootstrap.py`. `currentChanged` 방출부와 `_on_switch→sync_nav_selection`은 확인, `_refresh_tab` 연결 코드는 열람 범위에서 미발견. 맞다면 `data_collected`의 `_mark_noncritical_stale`+강제 새로고침 의존. DB탭 삭제 후 히스토리/통계 stale 잔류 여지. §3으로 이월.

**반증되어 제외(문제 아님)**: detail abort 삼킴(다음 루프頭 stop 체크) / drain 타임아웃(취소+재gather, 3s 상한) / `start_crawling` 중복가드·검증순서 및 실패 분기 release / live smoke 별도 경로 / SQL 전부 `?` 바인드(`LIMIT ?` 포함) / 백업·복원(`integrity_check`+필수 테이블+사전 백업+`close_all` 실패 시 중단) / 풀(WAL/`busy_timeout=30000`/FK ON, closing 대여 차단) / 업데이트(Ed25519+HTTPS+size/expiry, sha256 후 staged 삭제, `_is_child`+`target==sys.executable`, `.bak`+preflight+롤백+결과 기록) / 자격증명 처리 코드 없음(공개키는 공개값) / export 인코딩·파일명·수식 중화. 경미 잔류: helper 교체~결과기록 사이 강제종료 시 `.bak` 고아(수동 복구 가능), ticket/result fsync 없음.

## 6 Documentation Mismatches

- **DOC-001 (ISSUE-004)**: 신규설치 테마 문서("미지정(신규 설치)은 OS 연동(AUTO)", `theme.py:24-31` 독스트링)와 기본값 `"dark"`(`schedule_defaults.py:5`, `main.py:105` `settings.get("theme","dark")`, `bootstrap.py:68`) 불일치. 없으면 없음이 아님 — 1건 확정.
- **DOC-002 (ISSUE-011 표시)**: bulk 저장 건수 표시가 dedup 전 기준이라 실제 upsert보다 크게 표시될 수 있음. 데이터 손상은 아니나 사용자 가시 수치 불일치.
- 명시적으로 불일치가 아닌 것: ISSUE-022 트레이 동작은 README "트레이 백그라운드"와 정합(의도된 동작). 진입점·시작법·CI subset 관계도 동기화됨.

## 7 Recommended Fix Plan

- **Phase 1 (High-Risk, P0)**: ISSUE-001(지오메트리 단일 검증 경로+클램프) → ISSUE-002(`release(None)` 분리·owner 필수화) → ISSUE-003(즐겨찾기 DB 성공 후 UI 반영+실패 통지). 셋 다 사용자 가시 파손(시작 크래시/중복 수집/상태 불일치)이라 최우선.
- **Phase 2 (무결성·종료, P1)**: ISSUE-010(rollback 추가, 형제 패턴 일치)+ISSUE-007(스냅샷 저장 동기화 또는 락 보유 연장)+ISSUE-005(워커 join·타이머 정리 인벤토리 확보)+ISSUE-006(`UnicodeDecodeError` 포착 확장)+ISSUE-008(`pool.get` 타임아웃/중단 체크)+ISSUE-016(그룹/메모 DB 보호, `DatabaseTab` 패턴 재사용)+ISSUE-017(포맷 전 수치 가드).
- **Phase 3 (표시· polish, P2)**: DOC-001(기본값 `null`/미지정 허용 또는 문서 수정 중 택1 — 둘 다 바꾸지 말 것)+DOC-002(반환값을 dedup 후 기준)+ISSUE-014(tmp+replace 원자 저장)+ISSUE-012(방어 복사)+ISSUE-018(디바운스/stale 가드 확대)+ISSUE-019(에러 시 토스트+버튼 복구)+ISSUE-020(폴백 지오메트리 show 후 계산)+ISSUE-021(중복 키 등록 시 기존 해제)+ISSUE-013/015/009(값비싼 변경 전 소유자 확인: flush 소유자, 인덱스 쿼팅, recycle 호출 지점).

## 8 Test Recommendations

- **T-001 (ISSUE-001)**: 입력 — `window_geometry`를 `[0,0,800]`(길이 3), `["a",0,800,600]`, `None`, 오프스크린 좌표로 각각 주입 후 시작. 기대 — 크래시 없이 기본 지오메트리 폴백+경고 로그, 오프스크린은 가시 영역으로 클램프.
- **T-002 (ISSUE-002)**: 입력 — complex 수집 실행 중 geo 탭 빈-스레드 `shutdown_crawl()` 호출. 기대 — `is_held` 유지(complex 락 보존). 양 탭 idle 종료 시 락 해제됨.
- **T-003 (ISSUE-003)**: 입력 — `toggle_favorite` False/예외 주입 후 토글. 기대 — `favorite_keys`·탭 상태 불변 + 실패 토스트/로그. True 시 기존 반영 유지.
- **T-004 (ISSUE-006)**: 입력 — `settings.json`에 비-UTF8 바이트 파일 배치 후 시작. 기대 — `.broken` 백업+기본값 시작(현 상태는 크래시).
- **T-005 (ISSUE-010)**: 입력 — bulk `executemany` 중간 실패 주입. 기대 — rollback 후 풀 반환, 다음 대여 트랜잭션 오염 없음.
- **T-006 (ISSUE-007)**: 입력 — 스냅샷 비동기 저장 중 다음 수집 시작. 기대 — DB 쓰기 중첩 없음(동기화 또는 락 연장 후 해제).
- **T-007 (ISSUE-008)**: 입력 — 풀 고갈 상태에서 중지 요청. 기대 — 유한 시간 내 워커 종료(무한 대기 없음).
- **T-008 (ISSUE-016/017)**: 입력 — 그룹 진입·메모 저장 중 DB 예외 주입 / alert에 `area_pyeong=None` emit. 기대 — 탭 전환 핸들러 예외 전파 없음(통지+기존 화면 유지) / 알림 슬롯 예외 없이 폴백 표시.
- **T-009 (DOC-001)**: 입력 — settings.json 없는 첫 실행. 기대 — 채택한 규격(코드·문서 중 하나)에 따라 AUTO 또는 dark 중 하나로 일치. 양쪽 동시 변경 금지.
- **T-010 (ISSUE-014/DOC-002)**: 입력 — 내보내기 중 크래시 주입 / 중복 포함 bulk 저장. 기대 — 기존본 손상 없는 완성 파일만 남음 / 표시 건수==실제 upsert 건수.

## 9 Final Assessment

| 항목 | 등급 | 근거 요약 |
|---|---|---|
| 시작·종료·설정 | Needs Work | 진입점·CI 동기화는 양호하나 시작 크래시 경로(ISSUE-001/006)와 종료 정리 공백(ISSUE-005)이 남음 |
| 수집 엔진 동시성 | High Risk | 타 탭 락 해제(ISSUE-002)가 가드 자체를 깨며 스냅샷 중첩(ISSUE-007)·중지 지연(ISSUE-008)이 겹침 |
| 데이터 무결성·표시 | Needs Work | rollback 누락(ISSUE-010)·건수 과대(ISSUE-011)·캐시 별칭(ISSUE-012) — 파손보다 불변식·표시 중심 |
| 보안·업데이트·백업 | Good | SQL 바인드·Ed25519+HTTPS·sha256·`.bak`+preflight+롤백·복원 전 검증 모두 확인, 확정 취약점 없음 |
| UI 배선 | Needs Work | 즐겨찾기 불일치(ISSUE-003, High) 외 그룹 무보호·동기 로드·알림 포맷 등 Medium 산재, 정상 배선 다수는 확인 |
| 문서 정합성 | Acceptable | 진입점·시작법·CI 정합하나 테마 AUTO 규격 불일치(DOC-001) 1건 확정 |

**먼저 수정할 3개**: ISSUE-001(시작 크래시) → ISSUE-002(락 가드 붕괴) → ISSUE-003(즐겨찾기 상태 불일치).
