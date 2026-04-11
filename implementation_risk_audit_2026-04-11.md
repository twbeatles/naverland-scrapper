# 구현 리스크 점검 보고서 (2026-04-11)

## 상태 요약
- 2026-04-11 기준, 본 문서에서 지적했던 예약 실행/자산 스코프 리스크는 모두 코드에 반영되었습니다.
- `naverland-scrapper.spec`는 같은 날짜 기준으로 재점검했고, 이번 수정 범위에서는 추가 hidden import/runtime hook/data bundle 변경이 필요하지 않았습니다.
- 관련 문서 `README.md`, `claude.md`, `gemini.md`, `update_history.md`도 최신 계약으로 동기화했습니다.

## 반영 완료 항목

### 1. 예약 실행이 실제 시작 실패여도 slot을 소비하던 문제
- 조치:
  - `CrawlerTab.start_crawling()` / `GeoCrawlerTab.start_crawling()`을 `bool` 반환으로 통일했습니다.
  - 스케줄러는 반환값이 `True`일 때만 `schedule_config.last_run_slot`, `last_run_at`를 기록합니다.
- 현재 계약:
  - 유지보수 모드, 이미 실행 중, 타깃 없음, 거래유형 미선택, 시작 직전 validation 실패는 slot을 소비하지 않습니다.

### 2. `complex` 예약 실행 실패 시 수동 작업 목록이 사라질 수 있던 문제
- 조치:
  - 예약 실행 전에 기존 수동 task list와 선택 row를 snapshot합니다.
  - 예약 대상 적재 실패 또는 `start_crawling() == False`면 기존 목록을 즉시 복원합니다.
- 현재 계약:
  - 예약 실행 성공 시에만 예약 대상 목록이 유지됩니다.
  - 실패 시 사용자가 준비해 둔 수동 큐는 그대로 남습니다.

### 3. 런타임 결과 dedupe 키에 `asset_type`이 없어 APT/VL 혼합 결과가 충돌하던 문제
- 조치:
  - `_item_dedupe_key()`를 `(asset_type, complex_id, article_id, trade_type)`로 변경했습니다.
  - 빈 `asset_type`은 legacy 호환을 위해 `APT`로 정규화합니다.
- 현재 계약:
  - 동일 `complex_id/article_id/trade_type`라도 `APT`와 `VL`은 서로 다른 매물로 유지됩니다.

### 4. 회귀 테스트 부족
- 조치:
  - 예약 시작 실패 시 slot 미소비
  - 예약 no-target 시 수동 task 복원
  - scheduled geo start failure 시 slot 미소비
  - asset-scoped runtime dedupe / blank asset legacy 호환
  - 위 시나리오를 각각 테스트로 추가했습니다.

### 5. CI에서 테스트가 자동으로 실행되지 않던 문제
- 조치:
  - GitHub Actions에 `tests/test_ui_wiring.py`, `tests/test_geo_tab_wiring.py`, `tests/test_crawler_regressions.py` pytest subset을 추가했습니다.
  - UI 테스트용 `QT_QPA_PLATFORM=offscreen` 환경도 함께 고정했습니다.

## 검증 결과
- `python -m pytest -q` => `210 passed`
- `npx --yes pyright` => `0 errors, 0 warnings, 0 informations`
- `python -m src.utils.preflight` => pass (`plyer` optional warning only)

## 메모
- 이번 수정은 runtime/UI/test/documentation 레벨 변경으로 분류되며, frozen packaging 동작에는 직접적인 구조 변경이 없습니다.
- 현재 작업 트리 기준으로는 `naver_site_live_audit_2026-04-10.md` 삭제가 별도 변경으로 존재합니다.
