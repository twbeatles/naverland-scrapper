# Project Audit

## 1. Executive Summary

Naverland Scrapper Pro Plus v15.0은 PyQt6 + Playwright 기반 네이버 부동산(`new.land.naver.com`) 수집 데스크톱 앱입니다. 287개 단위 테스트와 live-smoke 게이트가 있어 **기본 자동화 기반은 양호**하지만, Superpowers(TDD·환경 격리·에이전트 자율 개발) 관점에서 **중간~높은 위험** 요소가 존재했습니다.

핵심 발견:

| 영역 | 위험도 | 요약 |
|------|--------|------|
| Naver Article API 페이지네이션 | **High** | Fast path가 `page=1`만 요청해 대형 단지 매물 누락 가능 |
| Frozen 런타임 경로 (비-Windows) | **High** | `LOCALAPPDATA` 전용 → Linux/macOS PyInstaller 샌드박스 실패 |
| 모듈 import 시점 경로 고정 | **Medium** | `BASE_DIR`/`DATA_DIR` 모듈 상수가 worktree 격리를 어렵게 함 |
| SettingsManager 싱글톤 | **Medium** | 테스트 간 상태 오염 가능(일부 테스트에서 수동 reset) |
| Response-capture fallback | **Medium** | 브라우저 캡처 경로도 단일 응답만 소비, 페이지네이션 미지원 |
| 광범위 `except Exception` | **Medium** | 자동화 시 실패 원인 은폐(다만 fallback 설계 의도 있음) |

**조치 상태**: 1~2단계 핵심 항목 반영 완료 — Article API 페이지네이션(사전 필터 `list_count`, 부분 페이지 보존), response-capture fallback 보충 페이지(`_supplement_article_api_pages`), `configure_paths`/`reset_configured_paths`, `SettingsManager.reset_for_tests`, live-smoke `build_article_api_url` 통합. pytest **301 passed**.

**분석 방법**: CodeGraph MCP는 현재 harness에서 사용 불가하여, `grep`·파일 직접 열람·호출 경로 추적·Naver 공개 스크래퍼 문서([chongjae/naver_land](https://github.com/chongjae/naver_land), [jissp/naver-land-crawler](https://github.com/jissp/naver-land-crawler)) 및 live-smoke 프로브 URL을 교차 검증했습니다.

---

## 2. Project Understanding

### 아키텍처

```
app_entry.py
  └─ --preflight / --live-smoke / GUI
       └─ src/main.py → src/ui/app.py (PyQt6)
            └─ CrawlerTab / GeoCrawlerTab
                 └─ CrawlerThread (QThread)
                      └─ PlaywrightCrawlerEngine (facade)
                           ├─ runtime_parts/   (browser, contexts, navigation)
                           ├─ complex_mode_parts/
                           │    ├─ loop.py          단지 수집 루프
                           │    ├─ article_api.py    Article API fast path
                           │    ├─ response_capture.py  Playwright 응답 캡처 fallback
                           │    └─ detail_enrichment.py
                           └─ geo_mode_parts/    지도 마커 스캔
```

- **DB**: `ComplexDatabase` facade → `database_parts/*` (SQLite, migration 보존)
- **설정**: `SettingsManager` 싱글톤 → `data/settings.json`
- **경로**: `src/utils/paths.py` → `BASE_DIR`, `DATA_DIR`, `DB_PATH`

### Naver Land API 정렬 (실제 구조)

| 엔드포인트 | 용도 | 주요 파라미터 |
|-----------|------|--------------|
| `GET /api/articles/complex/{cid}` | 단지 매물 목록 | `realEstateType`, `tradeType`, `page`, `type=list`, `order=rank` |
| `GET /api/articles/house/{cid}` | 빌라/주택 | 동일 |
| `GET /api/complexes/single-markers` | 지도 마커 | geo 스캔 |
| `m.land.naver.com/article/...` | 상세 보강 | `detail_fetcher.py` |

응답 페이로드: `articleList[]` 항목에 `articleNo`/`atclNo`, `dealOrWarrantPrc`, `area1`/`area2`, `tradeTypeCode`, `floorInfo` 등. 페이지네이션: `page` 쿼리 + 응답 `isMoreData`(공개 스크래퍼 관례).

### 주요 실행 흐름 (단지 수집)

```
_run_complex_mode (loop.py)
  → _crawl_target_with_cache (cache_flow.py)
    → _collect_target_raw_items (response_capture mixin)
      → _fetch_article_api_fast_path (article_api.py)  [auth header 필요]
         실패 시 → Playwright page navigation + response handler
      → normalize_article_payload (response_capture.py)
      → detail enrichment (detail_fetcher.py)
  → ComplexDatabase bulk upsert
```

### Superpowers 적합성 요약

- **TDD**: `normalize_*`, `detail_fetcher`, `paths`, `managers` 등 순수 함수/모듈 테스트 존재. Playwright 엔진은 stub 기반 async 테스트로 Red-Green 가능.
- **환경 격리**: `tempfile` + `patch(CACHE_PATH)` 패턴 있음. `BASE_DIR` 모듈 상수와 Settings 싱글톤이 격리를 제한.
- **자동화 게이트**: `compileall`, `pytest`, `perf_baseline.py`, `--live-smoke`가 Claude.md에 문서화됨.

---

## 3. High-Risk Issues

### H-1. Article API fast path — page=1 고정 (매물 누락)

* **위치**: `src/core/engines/playwright_parts/complex_mode_parts/article_api.py` — `_build_article_api_url`, `_fetch_article_api_fast_path` (기존 L66 `page=1`, 단일 GET)
* **문제**: Naver `/api/articles/complex/{cid}`는 `page` 파라미터로 페이지네이션하며, 대형 단지는 20건 이상 매물이 존재. Fast path가 1페이지만 수집하면 나머지 매물이 누락됨.
* **영향**: 수집 건수 과소, 가격 스냅샷/소멸 추적 오류, 에이전트가 “수집 완료”로 잘못 판단.
* **근거**: Naver URL 예시 `page=2` ([chongjae/naver_land README](https://github.com/chongjae/naver_land)); jissp crawler는 `page: currentPage++` 루프. 코드: `"page": "1"` 하드코딩, `_fetch_article_api_fast_path` 단일 `request_context.get`.
* **권장 수정 방향**: `page` 파라미터화 + `isMoreData`/페이지 크기 기반 루프, 순수 함수 `build_article_api_url`/`article_api_has_more_pages` 분리 및 단위 테스트.
* **우선순위**: **Critical** → **수정 완료** (`src/core/services/article_api.py` 추가, fast path 페이지 루프)

### H-2. Frozen 런타임 데이터 경로 — Windows 전용

* **위치**: `src/utils/paths.py` — `_local_appdata_root`, `get_base_dir` (기존)
* **문제**: PyInstaller frozen 모드가 `LOCALAPPDATA`/`AppData/Local`만 사용. Linux CI/샌드박스/macOS에서 데이터 디렉터리 생성 실패 가능.
* **영향**: 자동화 빌드·headless smoke·에이전트 worktree에서 앱 기동 실패.
* **근거**: `get_base_dir()` → `_local_appdata_root() / FROZEN_APP_DIR_NAME`; 비-Windows fallback이 `~/AppData/Local` (Windows 경로).
* **권장 수정 방향**: `sys.platform`별 표준 경로 (Windows LOCALAPPDATA, macOS Application Support, Linux XDG_DATA_HOME).
* **우선순위**: **High** → **수정 완료** (`_frozen_runtime_data_root`)

### H-3. Response-capture fallback — 단일 응답만 처리

* **위치**: `src/core/engines/playwright_parts/complex_mode_parts/response_capture.py` — `_collect_target_raw_items` 내 `_consume` (L90–137)
* **문제**: Playwright response handler가 첫 매칭 API 응답의 `articleList`만 병합. UI 스크롤/추가 페이지 요청을 트리거하지 않음.
* **영향**: Fast path 실패 시 fallback도 대형 단지에서 불완전 수집 가능 (Claude.md: “안정성 > fast path” 원칙과 충돌).
* **근거**: `_consume`이 `response.json()` 1회만 처리; `page` 증가 로직 없음.
* **권장 수정 방향**: Fallback에서도 auth header 확보 후 programmatic pagination, 또는 페이지 UI 인터랙션으로 추가 API 응답 drain.
* **우선순위**: **High** → **수정 완료** (`_supplement_article_api_pages` after browser capture)

### H-4. 모듈 import 시점 `BASE_DIR` 고정

* **위치**: `src/utils/paths.py` L52–59 `BASE_DIR = get_base_dir()`
* **문제**: import 시 한 번 계산되어 `reload` 없이는 worktree/환경 변수 변경 반영 불가.
* **영향**: 병렬 에이전트·격리 테스트에서 데이터 경로 충돌; `importlib.reload` 패턴 필요.
* **근거**: `managers.py`가 `DATA_DIR`/`SETTINGS_PATH`를 import 시 바인딩; `test_paths_runtime.py`는 `reload`로 우회.
* **권장 수정 방향**: lazy accessor 또는 `configure_paths(base_dir)` 주입 API (facade 호환 유지).
* **우선순위**: **Medium**

### H-5. SettingsManager 싱글톤 + 파일 경로 결합

* **위치**: `src/core/managers.py` — `SettingsManager` (`_instance`, `SETTINGS_PATH`)
* **문제**: 프로세스 전역 단일 인스턴스; 테스트는 `SettingsManager._instance = None` 수동 reset.
* **영향**: 테스트 순서 의존, 에이전트 병렬 실행 시 설정 오염 **(추정)**.
* **근거**: `__new__` double-checked locking; `test_managers_cache.py` tearDown에서 reset.
* **권장 수정 방향**: `SettingsManager.for_path(path)` 팩토리 또는 테스트 전용 reset 공개 API.
* **우선순위**: **Medium**

### H-6. Article API fast path — auth 없으면 즉시 fallback

* **위치**: `article_api.py` L184–185
* **문제**: `_article_api_auth_header` 없으면 fast path 스킵. 정상이나, cold start에서 항상 느린 경로.
* **영향**: 성능·차단 위험 증가; 자동화 smoke는 페이지 방문으로 auth 캡처 (`probes.py` L82–119).
* **근거**: `if not str(getattr(self, "_article_api_auth_header", "") or "").strip(): return None`
* **권장 수정 방향**: 문서화 유지; preflight/smoke가 auth 캡처 성공을 게이트로 사용 (현행 적절).
* **우선순위**: **Low**

---

## 4. Potential Functional Gaps

1. **Response-capture 페이지네이션 부재** (확실): H-3과 동일. 대형 단지 fallback 시 불완전.
2. **`isMoreData` 필드 미처리** (확실, 수정됨): Fast path에 `article_api_has_more_pages` 추가.
3. **VL(house) 경로 페이지네이션** (추정): `houses` base_kind에도 동일 API 구조 적용됨 — fast path 수정으로 커버.
4. **Geo marker API rate limit** (추정): `geo_mode_parts/scan.py` 연속 스윕 시 차단 가능; 쿨다운은 complex loop에만 존재.
5. **문서 vs 구현 — pytest 카운트**: Claude.md “287 passed” — 현재 baseline 일치. 신규 테스트 추가 시 문서 갱신 필요.
6. **README Python 버전**: “3.9 이상” 명시; 코드베이스는 3.13 `__pycache__` 존재 — 3.9 호환 테스트(`test_python39_annotation_compat.py`)로 완화.
7. **멱등성 — QThread 중복 시작** (추정): `crawl_control_parts/start_stop.py`에서 stop 후 restart 패턴; 전용 mutex 테스트 부족.
8. **인코딩**: JSON 저장은 `atomic_write_json` 사용; SQLite/text는 UTF-8 전제 — Windows 콘솔 인코딩 이슈는 live-smoke JSON 로그로 우회.

---

## 5. Recommended Fix Plan

### 1단계 (즉시 수정) — **완료**

- [x] Article API URL 빌더·페이지네이션 순수 함수 추출 (`src/core/services/article_api.py`)
- [x] Fast path 다중 페이지 루프 (`MAX_ARTICLE_API_PAGES` 안전 상한)
- [x] Frozen 런타임 크로스 플랫폼 데이터 루트
- [x] 단위 테스트: `tests/test_article_api.py`, pagination/async stub, Linux XDG path

### 2단계 (안정성 개선)

- Response-capture fallback programmatic pagination (auth header 재사용)
- `SettingsManager.reset_for_tests()` 공개 API
- `paths.configure(base_dir)` 주입으로 worktree 격리 개선
- 광범위 `except Exception` → 구체 예외 + 구조화 로그 (자동화 실패 분류)

### 3단계 (구조 및 TDD 개선)

- `article_api` 파라미터를 live-smoke `probes.py`와 단일 모듈로 통합 (DRY)
- Geo sweep 통합 테스트 (marker handler + dedup)
- Claude.md / README 검증 명령·테스트 수 동기화 자동화

---

## 6. Test Recommendations

| 시나리오 | 목적 | 상태 |
|---------|------|------|
| `build_article_api_url(..., page=N)` 파라미터 검증 | Naver URL 계약 | **추가됨** |
| `article_api_has_more_pages` — `isMoreData` true/false | 페이지 루프 종료 | **추가됨** |
| Fast path 2페이지 stub (`_FakeRequestContext` 2응답) | 실제 엔진 pagination | **추가됨** |
| Frozen Linux `XDG_DATA_HOME` | 샌드박스 경로 | **추가됨** |
| Fallback multi-page (mock page.request) | H-3 회귀 방지 | 권장 |
| `SettingsManager` 병렬 temp dir 2인스턴스 | 싱글톤 격리 | 권장 |
| Live-smoke `complex/3833` 20건 초과 시 total 비교 | 실네트워크 회귀 | CI 선택 |
| `normalize_article_payload` — `atclNo`/`dealOrWarrantPrc`/`area1` | Naver 필드 매핑 | 기존 + 유지 |

### Red-Green-Refactor 루프 가이드 (에이전트용)

1. **Red**: `tests/test_article_api.py` 또는 stabilization 테스트 먼저 작성
2. **Green**: `src/core/services/article_api.py` 또는 mixin 최소 수정
3. **Refactor**: URL 빌더 중복 제거 (`probes.py` → shared builder, 3단계)
4. **Gate**: `python -m compileall -q app_entry.py src tests` → `pytest -q` → `perf_baseline.py` → `--live-smoke`