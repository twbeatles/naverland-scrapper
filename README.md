# Naverland Scrapper Pro Plus v15.0

네이버 부동산 매물 수집, 가격 이력 관리, 알림, 대시보드 분석을 제공하는 PyQt6 데스크톱 앱입니다. 현재 코드는 Playwright 수집 엔진과 SQLite 로컬 DB를 중심으로 구성되어 있으며, Selenium은 일반 단지 수집의 보조 fallback 경로로만 유지합니다.

## 현재 핵심 구조

- `app_entry.py`: GUI 실행, preflight, live smoke CLI 진입점
- `src/core/crawler.py`: 크롤러 스레드와 엔진 오케스트레이션 facade
- `src/core/engines/playwright_engine.py`: Playwright 엔진 facade
- `src/core/engines/playwright_parts/*_parts/`: 런타임, 단지 수집, 지도 수집 단계별 구현
- `src/core/database.py`: `ComplexDatabase` facade
- `src/core/database_parts/*_parts/`: schema, article history, price snapshot, disappeared/favorite DB 로직
- `src/ui/widgets/crawler_tab.py`: 수집 탭 facade
- `src/ui/widgets/crawler_tab_parts/*_parts/`: UI setup, crawl control, result render 세부 구현
- `src/utils/live_smoke.py`: live smoke facade
- `src/utils/live_smoke_parts/`: probe, helper, runner 구현

기존 import 경로는 유지하면서 내부 구현만 기능별 패키지로 나누는 facade 구조입니다.

## 주요 기능

- Playwright 기본 수집 엔진
- `/api/articles/{complex|house}/...` Article API fast path
- API 실패 시 기존 Playwright response-capture 경로로 fallback
- APT/VL 자산 구분 수집
- 지도 기반 geo sweep 수집
- 모바일 상세 페이지 기반 중개사/연락처/갭 분석 필드 보강
- SQLite connection pool, schema migration, backup/restore 안전장치
- `price_snapshots` bulk upsert 및 daily unique key
- 수집 완료 후 가격 스냅샷 비동기 저장
- 결과 테이블/compact/card view 렌더링 최적화
- dashboard lazy 초기화 및 현재 결과 범위 기반 통계
- live smoke, preflight, perf baseline 검증 명령 제공

## 설치

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
playwright install chromium
```

권장 Python 버전은 3.9 이상입니다.

## 실행

```powershell
python app_entry.py
```

빠른 환경 점검:

```powershell
python app_entry.py --preflight
```

실사이트 smoke:

```powershell
python app_entry.py --live-smoke --smoke-headless --live-smoke-detail-fields --smoke-json-log logs/live-smoke.json
```

성능 기준선:

```powershell
python scripts/perf_baseline.py
```

테스트:

```powershell
python -m pytest -q
```

## 주요 설정

- `crawl_engine`: 기본 `playwright`
- `playwright_navigation_timeout_ms`: Playwright page navigation timeout
- `playwright_article_api_fast_path`: Article API fast path 사용 여부
- `playwright_article_api_timeout_ms`: Article API 직접 호출 timeout
- `compact_duplicate_listings`: 중복 매물 compact 표시
- `lazy_load_dashboard`: dashboard 최초 진입 시점 생성

설정 UI에서도 Playwright/성능 관련 옵션을 조정할 수 있습니다.

## 패키징

```powershell
python -m PyInstaller --clean --noconfirm naverland-scrapper.spec
```

기본 배포는 `onedir + bundled Chromium`입니다.

- `NAVERLAND_ONEFILE=1`: onefile 빌드
- `NAVERLAND_BUNDLE_CHROMIUM=0`: Chromium 제외 slim 빌드
- `NAVERLAND_CONSOLE=1`: 콘솔 창 활성화

현재 구조 분리 작업은 Python source package 추가만 포함하며, 추가 PyInstaller hidden import나 data bundle은 필요하지 않습니다.

## 현재 검증 기준

최근 구조/성능 리팩토링 후 확인한 기준:

- `python -m pytest -q` -> `287 passed`
- `python scripts/perf_baseline.py` 통과
- `python app_entry.py --live-smoke --smoke-headless --live-smoke-detail-fields --smoke-json-log logs/live-smoke-after-structure.json` 통과

live smoke 기준 `[article-api]`, `[complex]`, `[detail]`, `[detail-fields]`, `[geo-marker]`, `[article-lookup]` probe가 모두 OK여야 합니다.
