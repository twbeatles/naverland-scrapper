# AI Context

이 문서는 코드 작업용 현재 컨텍스트입니다. 오래된 누적 변경 내역보다 현재 코드베이스 구조와 검증 기준을 우선합니다.

## 프로젝트

- 이름: Naverland Scrapper Pro Plus v15.0
- 목적: 네이버 부동산 매물 수집, 상세 정보 보강, 가격 이력 저장, 알림, 대시보드 분석
- GUI: PyQt6
- 수집: Playwright 기본, Selenium은 제한적 fallback
- 저장소: SQLite + JSON 설정 파일
- 패키징: PyInstaller `naverland-scrapper.spec`

## 현재 아키텍처

공개 facade 파일은 기존 import 호환을 유지합니다.

- `src/core/database.py`
  - `database_parts/schema_parts/`
  - `database_parts/crawl_snapshot_parts/`
  - `database_parts/article_parts/`
- `src/core/engines/playwright_engine.py`
  - `playwright_parts/runtime_parts/`
  - `playwright_parts/complex_mode_parts/`
  - `playwright_parts/geo_mode_parts/`
- `src/ui/widgets/crawler_tab.py`
  - `crawler_tab_parts/ui_setup_parts/`
  - `crawler_tab_parts/crawl_control_parts/`
  - `crawler_tab_parts/result_render_parts/`
- `src/core/parser.py`
  - `parser_parts/`
- `src/utils/live_smoke.py`
  - `live_smoke_parts/`
- `src/ui/widgets/dashboard.py`
  - `dashboard_parts/`
- `src/ui/styles.py`
  - `styles_parts/`

Mixin 메서드 rebinding은 `src/utils/mixin_rebind.py`를 사용합니다. 새 하위 mixin을 추가하면 MRO 기반 테스트가 최종 런타임 클래스에 메서드가 붙는지 확인합니다.

## 성능/수집 포인트

- Article API fast path를 먼저 시도하고 실패 시 response-capture로 fallback합니다.
- API 200 + 빈 목록은 확정 empty로 처리합니다.
- response-capture는 API 응답을 감지하면 조기 종료합니다.
- `price_snapshots`는 daily unique key와 bulk upsert를 사용합니다.
- 수집 완료 UI 처리는 가격 스냅샷 저장보다 먼저 진행되며, snapshot 저장은 worker로 넘깁니다.

## 검증 명령

```powershell
python -m pytest -q
python scripts/perf_baseline.py
python app_entry.py --live-smoke --smoke-headless --live-smoke-detail-fields --smoke-json-log logs/live-smoke-after-structure.json
```

현재 기준:

- 전체 pytest: `287 passed`
- perf baseline 통과
- live smoke probe 전체 OK

## 패키징/ignore 기준

- 구조 분리로 추가된 파일은 모두 Python source package입니다.
- `naverland-scrapper.spec`의 hidden import/data bundle 변경은 필요 없습니다.
- generated artifact는 기존 `.gitignore`의 `logs/`, `build/`, `dist/`, `data/`, cache/bytecode 규칙으로 처리됩니다.
