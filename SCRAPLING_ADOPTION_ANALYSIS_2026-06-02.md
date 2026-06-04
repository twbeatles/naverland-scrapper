# Scrapling 적용 검토 분석 (2026-06-02)

## 결론

`D4Vinci/Scrapling`을 이 저장소의 스크래핑 계층에 적용하는 것은 **전면 교체보다 제한적 PoC가 적절**하다.

현재 `naverland-scrapper`는 이미 Playwright를 기본 엔진으로 사용하며, 네이버 부동산의 DOM이 아니라 `/api/articles/...`, `single-markers`, 모바일 상세 응답을 직접 관측해 정규화하는 구조다. Scrapling의 장점인 `DynamicFetcher`/`StealthyFetcher`, XHR 캡처, 세션 유지, adaptive selector는 유용할 수 있지만, 이 프로젝트의 핵심 안정성은 이미 `response` 이벤트 기반 수집, cache/history 정책, Geo incomplete safety, PyInstaller Chromium 번들 정책에 묶여 있다.

### 2026-06-04 정합성 메모

기능 감사 하드닝(v15.0.27)은 Selenium fallback prefill 최종화, DB rollback guard, CSV/XLSX formula escape, URL batch generation guard, Playwright navigation timeout, 상세 task fanout 제한, Geo 빈 자산 정책 정합화를 적용했다. 이 변경은 모두 기존 Playwright/Selenium/SQLite/export/UI 경계 안에서 처리되었고 Scrapling runtime dependency, optional adapter, PyInstaller hidden import/data, `lxml` exclude 정책은 변경하지 않았다.

따라서 이 문서의 결론은 유지된다. Scrapling은 여전히 전면 교체 대상이 아니라 article-only 역조회 또는 모바일 상세 fallback용 optional PoC 후보이며, 실제 도입 전에는 별도 dependency/spec/frozen smoke 검증이 필요하다.

따라서 추천 방향은 다음과 같다.

1. **단기 도입 후보:** article-only URL 역조회 fallback 또는 모바일 상세 상세필드 fallback에 Scrapling 세션을 실험적으로 붙인다.
2. **중기 후보:** `ScraplingCrawlerEngine`을 별도 실험 엔진으로 추가해 `crawl_engine=scrapling` 플래그 뒤에서 live smoke 비교를 수행한다.
3. **비추천:** 기존 `PlaywrightCrawlerEngine`을 Scrapling으로 즉시 교체하거나 Scrapling Spider API로 앱 전체 크롤링 오케스트레이션을 재작성한다.

## 외부 라이브러리 기준

Scrapling 0.4.8 기준 확인 사항:

- PyPI 최신 릴리스는 `0.4.8`, 2026-05-11 공개이며 Python `>=3.10`을 요구한다.
- GitHub `pyproject.toml` 기준 core dependency는 `lxml`, `cssselect`, `orjson`, `tld`, `w3lib`, `typing_extensions`이고, `fetchers` extra는 `curl_cffi`, `playwright==1.59.0`, `patchright==1.59.1`, `browserforge`, `apify-fingerprint-datapoints`, `msgspec`, `anyio`, `protego` 등을 추가한다.
- 기본 설치 `pip install scrapling`은 parser 중심이며, fetcher/browser 기능은 `pip install "scrapling[fetchers]"`와 `scrapling install`이 필요하다.
- Scrapling fetcher 계층은 `Fetcher`, `DynamicFetcher`, `StealthyFetcher`로 나뉜다. `DynamicFetcher`는 Playwright 기반 브라우저 자동화와 `capture_xhr`를 지원하고, `StealthyFetcher`는 더 강한 anti-bot 옵션을 제공한다.
- adaptive scraping은 selector가 깨졌을 때 저장된 요소 특성을 기반으로 유사 요소를 다시 찾는 기능이다. 단, 현재 이 앱의 목록 수집 핵심은 DOM selector보다 네트워크 JSON 응답이므로 adaptive selector의 직접 효과는 제한적이다.

출처:

- Scrapling GitHub: https://github.com/D4Vinci/Scrapling
- Scrapling PyPI: https://pypi.org/project/scrapling/
- 설치 문서: https://scrapling.readthedocs.io/en/latest/#installation
- Fetchers basics: https://scrapling.readthedocs.io/en/latest/fetching/choosing.html
- Dynamic websites: https://scrapling.readthedocs.io/en/latest/fetching/dynamic.html
- Stealthy fetcher: https://scrapling.readthedocs.io/en/latest/fetching/stealthy.html
- Adaptive scraping: https://scrapling.readthedocs.io/en/latest/parsing/adaptive.html

## 현재 저장소 구조와 맞물리는 지점

### 현재 엔진 구조

- `CrawlerThread`는 `PlaywrightCrawlerEngine` 또는 `SeleniumCrawlerEngine`을 선택하는 오케스트레이션 계층이다.
- `PlaywrightCrawlerEngine`은 `src/core/engines/playwright_parts/runtime.py`, `complex_mode.py`, `geo_mode.py`로 분리되어 있다.
- `complex` 모드는 `page.on("response", ...)`로 `/api/articles/complex/{cid}` 또는 `/api/articles/house/{cid}` 응답을 포착하고 `normalize_article_payload()`로 표준 item을 만든다.
- `geo_sweep` 모드는 `single-markers` 응답을 포착하고, 지도 marker 전환/drag/wheel을 직접 수행한 뒤 발견 단지별 상세 수집으로 이어진다.
- 모바일 상세는 `src/core/services/detail_fetcher.py`에서 `fin.land`, `m.land` 상세 URL을 순회하며 body/html/hydration/network response를 합쳐 broker/contact/기전세금 필드를 복구한다.
- URL batch article-only 역조회는 `src/core/parser.py`의 `ArticleLookupBrowserFallbackSession`이 sync Playwright session을 재사용하는 구조다.

### Scrapling이 들어갈 수 있는 위치

1. `NaverURLParser` article-only browser fallback 대체/보강

   현재 sync Playwright fallback은 article URL을 열고 body/content/response URL 일부에서 `complexNumber`, `hscpNo`, `bildNo`, `houseNo` 등을 추출한다. Scrapling `DynamicSession` 또는 `StealthySession`은 세션 재사용과 XHR 캡처를 제공하므로 가장 작은 표면으로 실험할 수 있다.

2. `fetch_mobile_article_detail()`의 보조 상세 fetcher

   상세 페이지는 DOM text, hydration blob, network response를 모두 합쳐 필드를 복구한다. Scrapling의 `capture_xhr`와 `Response.captured_xhr`가 현재 `responses` artifact와 유사한 역할을 할 수 있다. 다만 현재 함수는 기존 Playwright page pool을 받아 쓰므로, Scrapling 세션을 새로 띄우면 메모리/속도/쿠키 상태가 달라질 수 있다.

3. 별도 `ScraplingCrawlerEngine`

   `CrawlerEngine` 인터페이스가 단순하므로 실험 엔진 추가는 가능하다. 하지만 `geo_sweep`의 drag/wheel, marker 전환, response drain timeout, incomplete safety, disappeared marking까지 같은 수준으로 구현하려면 기존 Playwright mixin 상당 부분을 다시 연결해야 한다.

4. Parser-only 도입

   Scrapling `Selector`/adaptive parser만 도입해 Selenium DOM fallback 또는 상세 HTML 파싱 보조로 쓰는 방식도 가능하다. 그러나 이 프로젝트의 주요 데이터 소스는 네이버 API JSON이므로 우선순위는 낮다.

## 장점

- **세션 기반 fetcher 추상화:** Scrapling session class는 브라우저를 요청마다 새로 띄우지 않고 유지할 수 있어 현재 article lookup fallback처럼 반복 호출되는 경로에 맞는다.
- **XHR 캡처 API:** `capture_xhr`가 현재 직접 구현한 `page.on("response")` 패턴 일부를 단순화할 수 있다.
- **Stealth 옵션 실험:** 네이버가 headless/automation fingerprint에 더 민감해질 경우 비교군으로 둘 가치가 있다. 다만 Scrapling의 anti-bot 강점은 Cloudflare 계열 보호에 대한 설명이 중심이라 네이버 부동산에서의 효과는 실사이트 smoke로 증명해야 한다.
- **Parser 편의성:** CSS/XPath/텍스트 기반 탐색과 adaptive selector는 Selenium DOM fallback, 상세 body fallback 유지보수에 도움이 될 수 있다.
- **비교 실험이 쉬운 후보:** 기존 live smoke와 통계(`response_seen_count`, `response_match_count`, `detail_parse_state`, `missing_field_count`)가 있어 Playwright 현행 대비 효과를 수치로 볼 수 있다.

## 주요 리스크

### Python 버전 정책 충돌

현재 README/AI 문서는 Python 3.9+를 기준으로 한다. Scrapling은 Python 3.10+가 필요하다. Scrapling을 runtime dependency로 올리면 이 저장소의 Python 3.9 호환 정책을 포기하거나, Scrapling 경로를 optional dependency로 완전히 격리해야 한다.

권장:

- 전면 dependency 추가 전 Python 지원 정책을 먼저 결정한다.
- 3.9 유지가 필요하면 `extras` 또는 lazy import로 Scrapling 기능을 선택 기능화한다.

### Playwright 버전 및 브라우저 설치 충돌

현재 `requirements.txt`는 `playwright>=1.50`이다. Scrapling `fetchers` extra는 `playwright==1.59.0`과 `patchright==1.59.1`을 요구한다. 의존성 해석 결과에 따라 기존 Playwright 동작, 브라우저 설치 경로, PyInstaller Chromium bundle 검출이 바뀔 수 있다.

권장:

- PoC는 별도 venv에서 시작한다.
- 본선 도입 시 `requirements.txt`, preflight, PyInstaller spec, runtime hook을 함께 수정한다.

### PyInstaller 패키징 영향

현재 `naverland-scrapper.spec`는 `collect_submodules("playwright")`와 Chromium bundle 수집을 포함하지만, `lxml`, `html5lib`는 제외 목록에 있다. Scrapling core는 `lxml`에 의존하므로 parser까지 사용하면 현 spec의 `lxml` exclude는 충돌한다. `patchright`, `browserforge`, fingerprint data, `curl_cffi` 등 fetcher extra도 hidden import/data 수집 검증이 필요하다.

권장:

- Scrapling 도입은 항상 source smoke와 frozen smoke를 분리 검증한다.
- spec 변경 없이 `pip install scrapling[fetchers]`만 추가하는 방식은 배포판에서 실패할 가능성이 높다.

### 현재 네트워크 중심 수집 정책과의 불일치

현행 Playwright 엔진은 response handler를 직접 붙이고, pending response task를 drain하며, drain timeout이면 negative cache를 저장하지 않는다. Scrapling의 `capture_xhr`는 fetch 완료 후 `Response.captured_xhr`로 접근하는 API라서 다음 동작을 그대로 대체할 수 있는지 검증이 필요하다.

- `/api/articles/...` 응답이 여러 entry plan에서 안정적으로 잡히는지
- `single-markers`가 지도 drag/wheel 이후에도 누락 없이 잡히는지
- 응답 지연/parse failure/drain timeout을 현행 stats와 같은 방식으로 분류할 수 있는지
- 0건 응답을 `confirmed_empty` negative cache로 저장해도 되는지

### Anti-bot 적용의 운영 리스크

Scrapling의 stealth 기능이 접속 성공률을 높일 수도 있지만, 대상 사이트의 이용 조건과 차단 정책을 더 직접적으로 건드릴 수 있다. 이 앱은 이미 속도 preset, retry, cooldown, block detection, live smoke 중심으로 안정성을 관리하고 있으므로, stealth 옵션은 무제한 우회 수단이 아니라 실패율 비교용 실험 옵션으로만 취급하는 편이 안전하다.

## 권장 PoC 설계

### PoC 1: article-only 역조회 fallback

목표:

- `NaverURLParser.resolve_article_complex()`의 browser fallback 경로에 Scrapling 기반 session을 추가하고 기존 Playwright fallback과 비교한다.

범위:

- `fin.land.naver.com/articles/{article_id}`
- `m.land.naver.com/article/info/{article_id}`
- `m.land.naver.com/article/view/{article_id}`

성공 기준:

- 기존 테스트 `test_resolve_article_complex_*`, `test_name_lookup_worker_reuses_article_browser_fallback_session`와 동등한 동작
- live smoke article lookup pass
- source/frozen 모두에서 browser fallback이 local Chrome/Chromium 경로를 깨지 않음

도입 방식:

- `src/core/parser.py`에 바로 결합하지 말고 `src/core/services/scrapling_fetch.py` 같은 optional adapter를 둔다.
- import 실패 시 기존 Playwright fallback으로 즉시 돌아간다.
- stats/log에는 `source=scrapling_browser_fallback`처럼 분리된 source를 남긴다.

### PoC 2: 모바일 상세 보조 fetcher

목표:

- `fetch_mobile_article_detail()`에서 기존 Playwright page pool 결과가 `failed` 또는 핵심 필드 0개일 때 Scrapling fallback을 한 번만 시도한다.

성공 기준:

- `detail_parse_state`, `missing_field_count`, `detail_network_response_count`, `detail_hydration_hit`가 기존보다 개선되는지 측정
- 필터 통과 매물에만 상세 fetch를 수행하는 현행 정책 유지
- 중단 요청 시 pending 작업이 취소되는 현행 테스트 계약 유지

주의:

- 현재 상세 수집은 Playwright page pool을 공유한다. Scrapling이 별도 browser/session을 띄우면 worker 수만큼 브라우저가 늘 수 있으므로 pool 크기와 메모리 watch dog 기준을 별도로 둬야 한다.

### PoC 3: 별도 Scrapling 엔진

목표:

- `crawl_engine=scrapling` 실험 엔진을 추가해 complex mode만 비교한다.

범위:

- 1차는 `complex` APT/VL 목록 수집만 수행한다.
- Geo sweep은 1차 범위에서 제외한다.
- Selenium fallback과 disappeared marking은 기존 정책을 재사용한다.

성공 기준:

- 같은 sample complex에서 `response_match_count`, raw item count, normalized item count가 Playwright와 같거나 더 안정적
- `capture_failed`, `block_like_redirect`, `parse_fail_count`가 악화되지 않음
- `python -m pytest tests/test_playwright_engine_stabilization.py tests/test_parser_module.py tests/test_live_smoke.py -q`에 대응하는 Scrapling 전용 테스트 추가

## 비교 측정 항목

PoC는 감으로 판단하지 말고 다음 값을 현행 Playwright와 나란히 기록해야 한다.

- complex/article 응답 포착률: `response_seen_count`, `response_match_count`, `capture_failed_count`
- parsing 품질: `parse_success_count`, `parse_fail_count`
- 상세 품질: `detail_parse_state`, `missing_field_count`, `detail_network_response_count`, `detail_hydration_hit`
- Geo 품질: `geo_discovered_count`, `geo_dedup_count`, `geo_incomplete_count`, marker switch stats
- 안정성: block-like redirect 횟수, retry exhaust, headed fallback 발생 여부
- 성능: 단지/거래유형 pair당 소요 시간, 메모리 RSS, browser recycle 횟수
- 배포: PyInstaller onedir 크기, frozen preflight, frozen live smoke

## 구현 시 체크리스트

1. dependency 정책 결정
   - Python 3.9 유지 여부 결정
   - `requirements.txt`에 바로 넣을지, optional extra 문서화로 둘지 결정

2. optional adapter 작성
   - `scrapling` import는 함수 내부 lazy import
   - import 실패/런타임 실패 시 기존 Playwright 경로 fallback
   - session close 보장

3. 설정 추가
   - `scrapling_enabled`
   - `scrapling_mode=off|article_lookup|detail_fallback|engine`
   - 필요 시 timeout, capture regex, headless 옵션 분리

4. 테스트 추가
   - Scrapling 미설치 상태에서도 전체 테스트 pass
   - 설치 상태에서 adapter unit test
   - parser/detail/live smoke 비교 테스트

5. packaging 재점검
   - `lxml` exclude 제거 또는 조건화
   - `scrapling`, `patchright`, `browserforge`, `curl_cffi` hidden import/data 확인
   - `python -m src.utils.preflight`
   - `pyinstaller naverland-scrapper.spec`
   - `dist\naverland\naverland.exe --preflight`
   - source/frozen `--live-smoke --live-smoke-detail-fields`

## 최종 판단

Scrapling은 이 프로젝트에 **가치 있는 비교군**이다. 특히 article-only 역조회와 상세 fallback처럼 실패 시 보조 경로가 필요한 곳에는 적용해볼 만하다.

다만 이 저장소의 핵심 수집 안정성은 이미 네이버 API 응답 이벤트, 캐시 쓰기 조건, Geo incomplete safety, live smoke, PyInstaller Chromium 번들 정책에 깊게 연결되어 있다. Scrapling이 제공하는 추상화가 이 계약을 자동으로 보존하지는 않는다.

따라서 당장 할 일은 “Scrapling으로 갈아타기”가 아니라, **optional Scrapling adapter를 만들고 기존 Playwright 엔진 대비 실사이트 smoke 수치로 이기는지 확인하는 것**이다. 첫 PoC는 `article-only URL 역조회 fallback`이 가장 작고, 실패해도 기존 동작을 깨뜨릴 가능성이 낮다.
