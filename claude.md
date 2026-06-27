# AI Context

현재 코드베이스 기준의 작업 메모입니다. 과거 변경 이력은 `update_history.md`에 짧게 남기고, 이 파일은 구조와 운영 기준만 유지합니다.

## 요약

Naverland Scrapper Pro Plus v15.0은 PyQt6 기반 데스크톱 크롤러입니다. Playwright가 기본 수집 엔진이며, SQLite에 단지/매물/가격 스냅샷/알림 데이터를 저장합니다.

## 중요 원칙

- 기존 공개 import 경로를 깨지 않습니다.
- facade 파일은 조립과 재수출을 담당합니다.
- 실제 구현은 기능별 `*_parts/` 패키지에 둡니다.
- 새 mixin 메서드는 `src/utils/mixin_rebind.py`의 MRO 기반 rebinding 경로에 포함되어야 합니다.
- 수집 안정성은 fast path보다 우선입니다. Article API 실패 시 기존 Playwright response-capture fallback을 유지합니다.
- DB migration은 기존 데이터 보존을 기본으로 합니다.

## 주요 모듈

- `src/core/database.py`: `ComplexDatabase` facade
- `src/core/database_parts/schema_parts/`: tables, migrations, indexes, cleanup
- `src/core/database_parts/crawl_snapshot_parts/`: crawl history, price snapshot write/query, filters
- `src/core/database_parts/article_parts/`: article history, bulk upsert, favorites, disappeared
- `src/core/engines/playwright_engine.py`: `PlaywrightCrawlerEngine` facade
- `src/core/engines/playwright_parts/complex_mode_parts/`: loop, cache flow, article API, response capture, detail enrichment, paths
- `src/core/engines/playwright_parts/runtime_parts/`: browser, contexts, navigation, blocking, response tasks
- `src/core/engines/playwright_parts/geo_mode_parts/`: scan, markers, map controls
- `src/ui/widgets/crawler_tab_parts/`: UI setup, crawl control, result render 하위 패키지
- `src/utils/live_smoke_parts/`: live smoke helper/probe/runner

## 검증

기능 변경 또는 구조 이동 후 기본 검증:

```powershell
python -m compileall -q app_entry.py src tests
python -m pytest -q
python scripts/perf_baseline.py
python app_entry.py --live-smoke --smoke-headless --live-smoke-detail-fields --smoke-json-log logs/live-smoke-after-structure.json
```

최근 확인:

- pytest 전체 통과: `296 passed`
- perf baseline 통과
- live smoke `[article-api]`, `[complex]`, `[detail]`, `[detail-fields]`, `[geo-marker]`, `[article-lookup]` OK

## 패키징

`naverland-scrapper.spec`는 현재 구조와 맞습니다. 새 분리 모듈은 정적 import되는 Python source이므로 추가 hidden import나 data bundle은 필요하지 않습니다.
