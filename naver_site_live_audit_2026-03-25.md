# 네이버 실사이트 연동 감사 리포트 (2026-03-25)

## 요약

- 이 문서는 `README.md`, `claude.md`, 실제 수집 코드, 그리고 2026-03-25 기준 라이브 사이트 검증 결과를 함께 근거로 작성한 최신 독립 감사 문서다.
- 이번 범위는 코드 수정이 아니라 `감사 + 우선순위 + 권장 보강안` 정리다.
- 핵심 결론은 `네이버 부동산 사이트가 사라졌다`가 아니라 `브라우저 수동 접근과 자동화 접근의 결과가 달라질 수 있고, 현재 코드는 그 차이를 충분히 흡수하지 못한다`이다.
- 사용자 관측으로는 일반 브라우저 직접 접근에는 큰 문제가 없고, Playwright 실행 시 차단되는 것으로 보인다. 본 환경에서는 GUI 수동 검증을 직접 재현하지 못했으므로 이 항목은 사용자 제보로 취급한다.
- 본 환경에서 확인한 자동화 결과는 `automation-specific block/redirect`, `도메인/경로 drift`, `응답 매칭 고정 의존`, `상세 파싱 취약성`을 동시에 시사한다.
- `README.md`, `claude.md`에서 언급된 과거 감사 문서(`crawling_scraping_risk_audit_2026-03-07.md`)는 현재 루트에서 확인되지 않았으므로, 이 문서는 독립형 최신 감사본으로 본다.

## 검증 범위와 기준

- 문서 기준
  - `README.md`
  - `claude.md`
- 핵심 코드 기준
  - `src/core/engines/playwright_parts/complex_mode.py`
  - `src/core/engines/playwright_parts/geo_mode.py`
  - `src/core/engines/playwright_parts/runtime.py`
  - `src/core/services/detail_fetcher.py`
  - `src/core/parser.py`
  - `src/utils/helpers.py`
  - `src/ui/dialogs/batch.py`
  - `src/ui/widgets/crawler_tab_parts/crawl_control.py`
  - `src/ui/widgets/crawler_tab_parts/ui_setup.py`
  - `src/ui/app_parts/tab_setup.py`
- 라이브 검증 기준
  - PowerShell `Invoke-WebRequest`로 `new.land`, `m.land`, `fin.land` 응답을 직접 확인
  - Playwright ad-hoc 스크립트로 `new.land` 단지/목록 경로 접근 시 최종 URL과 네트워크 응답 패턴 확인
  - 공개 검색 결과 기준으로 현재 공개 매물 상세 경로에 `fin.land.naver.com/articles/{articleId}`가 노출되는지 확인

## 라이브 관측 결과

### 사실로 확인된 항목

- 2026-03-25 기준 `https://new.land.naver.com/api/complexes/102378?sameAddressGroup=false` 직접 호출은 아래 응답으로 종료됐다.

```text
{"success":false,"code":"TOO_MANY_REQUESTS","message":"Rate limit exceeded"}
```

- 2026-03-25 기준 `https://m.land.naver.com/article/info/2513105556` 초기 HTML은 Next.js 기반 셸 형태였고, 초기 본문에서 `실거래가`는 확인됐지만 `중개소`, `공인중개사`, `기전세금`, `전화`, `전세`는 확인되지 않았다.
- 2026-03-25 기준 `https://fin.land.naver.com/` 역시 Next.js 기반 초기 HTML로 응답했다.
- 2026-03-25 기준 `https://fin.land.naver.com/articles/2529610450`, `https://fin.land.naver.com/articles/2535545147` 초기 HTML에는 `실거래가`만 확인됐고 `기전세금`, `중개소`, `전화`, `매물번호`, `공인중개사`는 확인되지 않았다.
- 2026-03-25 기준 Playwright Chromium으로 `https://new.land.naver.com/complexes/...` 및 `https://new.land.naver.com/complexes?ms=...` 계열에 접근했을 때 최종 URL이 `https://new.land.naver.com/404`로 수렴했고, 기대하던 `/api/articles/...` 또는 `single-markers` 응답을 관측하지 못했다.

### 추론으로 해석한 항목

- 위 결과만으로 `new.land`가 전체 서비스에서 폐기됐다고 단정할 수는 없다.
- 사용자 제보상 일반 브라우저 접근은 된다고 하므로, 현재 더 강한 가설은 `자동화 경로 식별`, `세션/쿠키/헤더 조건 차이`, `도메인/라우팅 drift`의 복합 문제다.
- 특히 본 환경의 Playwright 검증은 ad-hoc headless Chromium 기준이다. 앱 기본 설정은 `playwright_headless=False`지만, 현재 런타임도 Playwright 고유 fingerprint를 충분히 숨기지 못하므로 headed로도 유사 리스크가 남는다.

## 우선순위 요약

| ID | 항목 | 우선순위 | 이유 |
| --- | --- | --- | --- |
| F-01 | Playwright 차단 리스크 | P1 | 현재 기본 엔진이 Playwright이고, `geo_sweep`는 Playwright 전용이라 차단 시 핵심 기능이 직접 멈춘다. |
| F-02 | 도메인/URL drift | P1 | `new.land` 고정 전제가 URL 생성, 단지명 조회, 입력 파싱, 상세 열기까지 전 영역에 퍼져 있다. |
| F-03 | 응답 캡처 취약성과 조용한 빈 결과 | P1 | 응답 URL 패턴이 조금만 바뀌어도 예외 없이 `0건`으로 끝날 수 있다. |
| F-04 | 상세 파싱 취약성 | P1 | 중개사/전화/기전세금/갭 계산이 이 경로에 달려 있어 데이터 품질이 급락할 수 있다. |
| F-05 | 사용자 진입 경로 불일치 | P2 | 입력 예시, 도움말, 링크 열기, 테스트 fixture가 실제 현행 경로와 어긋나 운영 혼선을 만든다. |

## Findings

### F-01. Playwright 차단 리스크

**문제**

- 현재 기본 수집 엔진은 Playwright이며, `geo_sweep`는 Playwright 전용이다. `README.md`, `claude.md` 모두 이 전제를 문서화하고 있다.
- `src/core/engines/playwright_parts/runtime.py`는 Playwright 기본 Chromium을 사용해 브라우저를 띄우고, desktop/mobile context 모두 `navigator.webdriver`를 `undefined`로 덮는 정도의 제한적 stealth만 적용한다.
- 같은 파일에서 desktop context는 고정 UA를 쓰고, mobile context는 iPhone 14 Pro Max preset과 고정 `referer`를 사용한다. 세션은 비영속이며 쿠키/스토리지가 누적되지 않는다.
- `src/core/engines/playwright_parts/runtime.py`의 `block_heavy_resources`는 기본적으로 이미지/미디어/폰트를 차단한다. 이 설정은 성능에는 유리하지만 fingerprint와 렌더 타이밍을 일반 사용자 브라우저와 다르게 만들 수 있다.
- Selenium 쪽에는 차단 페이지 감지(`BlockedPageError`)가 있지만, Playwright 경로에는 최종 URL 404, 방어 페이지, 응답 0건을 명시적으로 차단으로 승격하는 로직이 없다.

**실제 사이트 근거**

- 2026-03-25 기준 ad-hoc Playwright Chromium 접근에서 `new.land` 단지/목록 경로는 최종적으로 `/404`로 이동했고, 기대한 API 응답을 잡지 못했다.
- 같은 날 사용자 제보상 일반 브라우저 직접 접근은 가능하다고 하므로, `site down`보다는 `automation-specific block/redirect` 가능성이 더 높다.

**영향 범위**

- 일반 단지 수집 `complex`
- 지도 기반 `geo_sweep`
- Playwright 기반 목록 응답 가로채기
- Playwright 기반 모바일 상세 워커 풀

**발생 가능 시나리오**

- Playwright Chromium fingerprint가 차단되어 `new.land`가 404 또는 방어 페이지로 리다이렉트된다.
- headless 여부와 무관하게 고정 UA, 비영속 세션, 제한적 stealth, 리소스 차단 패턴이 자동화 식별 신호로 작동한다.
- `geo_sweep`는 Playwright 전용이라 Selenium fallback으로도 복구되지 않는다.

**우선순위**

- P1

**권장 보강안**

- Playwright 경로에 `final_url`, `http_status`, `title`, `block_reason`, `response_match_count` 계측을 추가해 `0건`과 `차단`을 분리해야 한다.
- Playwright 런타임에 `persistent context`, session reuse, UA/locale/viewport/profile 전략, 추가 stealth 계층을 검토해야 한다.
- `playwright_block_heavy_resources`는 anti-bot 모드에서 자동 완화하거나, 최소한 탐지 시 재시도 프로필을 다르게 주는 전략이 필요하다.
- `goto()` 후 `/404`, 방어 타이틀, 응답 0건이 반복되면 명시적 block signal로 승격해야 한다.
- 수동 브라우저는 되고 Playwright만 막히는 현재 전제를 기준으로, `headless 여부`보다 `Playwright fingerprint` 자체를 우선 진단 대상으로 둬야 한다.

### F-02. 도메인/URL drift

**문제**

- `src/utils/helpers.py`의 `get_complex_url()`, `get_article_url()`는 모두 `https://new.land.naver.com/...`를 반환한다.
- `src/core/parser.py`의 `NaverURLParser.PATTERNS`는 `new.land`, `land.naver.com`, `m.land`만 처리하고 `fin.land.naver.com/articles/{articleId}` 패턴을 전혀 인식하지 못한다.
- 같은 파일의 `_fetch_name_impl()`은 단지명 조회를 `https://new.land.naver.com/api/complexes/{complex_id}?sameAddressGroup=false`에 직접 의존한다.
- `src/core/services/detail_fetcher.py`는 현재 URL이 `fin.land.naver.com`일 때만 `m.land`로 우회하지만, 애초에 상세 진입 자체를 `fin.land` 기준으로 설계하지는 않았다.
- `src/ui/widgets/crawler_tab_parts/crawl_control.py`의 `_open_complex_url()`은 더블클릭 시 무조건 `new.land.naver.com/complexes/{id}`를 연다.

**실제 사이트 근거**

- 2026-03-25 기준 직접 HTTP 확인에서는 `fin.land.naver.com`이 활성 HTML을 반환했고, 공개 검색 결과로도 `fin.land.naver.com/articles/{articleId}` 상세 경로가 노출됐다.
- 같은 시점에 `new.land` API 직접 호출은 rate limit에 걸렸고, Playwright 기준 `new.land` 진입은 `/404`로 수렴했다.

**영향 범위**

- 단지명 조회
- 사용자 URL 입력 파싱
- 결과 더블클릭 시 외부 브라우저 열기
- 기사/상세 URL 생성
- 향후 라우팅 변경 대응성 전반

**발생 가능 시나리오**

- 사용자가 현재 실제 서비스 URL인 `fin.land` 상세 링크를 붙여넣어도 단지 추출이 실패한다.
- 링크 열기가 낡은 `new.land` 경로를 열어 사용자가 실제 브라우저에서는 다른 경로로 재탐색해야 한다.
- 단지명 조회 API가 차단되면 UI에는 `단지_{id}` 같은 fallback만 남아 운영성이 떨어진다.

**우선순위**

- P1

**권장 보강안**

- `base domain/url builder`를 추상화해 `new.land`, `m.land`, `fin.land`를 전략적으로 선택하도록 바꿔야 한다.
- `NaverURLParser`는 `fin.land.naver.com/articles/{articleId}`와 향후 라우팅 패턴을 수용하도록 확장해야 한다.
- 단지명 조회는 단일 `new.land` API 고정이 아니라 다중 source fallback 또는 브라우저 런타임 내부 조회 전략이 필요하다.
- 외부 브라우저 열기와 UI 예시 문자열은 현재 운영 경로에 맞게 재정렬해야 한다.

### F-03. 응답 캡처 취약성과 조용한 빈 결과

**문제**

- `src/core/engines/playwright_parts/complex_mode.py`는 목록 응답을 `"/api/articles/complex/{cid}"` 또는 `"/api/articles/house/{cid}"` substring으로 정확히 매칭한다.
- 같은 파일의 `_candidate_paths()`는 `complexes`/`houses`만 순회한다. 경로가 versioned API, 다른 hostname, query-only route, GraphQL, batch endpoint로 바뀌면 수집이 전부 비게 된다.
- `src/core/engines/playwright_parts/geo_mode.py`는 `complexes/single-markers`, `houses/single-markers`에만 반응한다.
- 현재 Playwright 경로는 응답이 전혀 안 잡혀도 강한 예외로 처리하지 않고 `0건`으로 종료될 수 있다.
- Selenium 경로는 최소한 차단 페이지 감지를 갖고 있지만, Playwright는 `response_seen=False`와 `redirected 404`를 차단 사유로 승격하지 않는다.

**실제 사이트 근거**

- 2026-03-25 Playwright 접근에서는 실제로 기대한 `/api/articles/...`와 `single-markers` 응답을 잡지 못했다.
- 같은 시점 `new.land` 직접 API는 rate limit에 걸렸다. 즉, API endpoint가 살아 있더라도 현재 클라이언트 접근 방식이 안정적이지 않다.

**영향 범위**

- 목록 수집 정확도
- `geo_sweep` 단지 발견
- cache hit/miss 해석
- 수집 완료 로그와 통계의 신뢰도

**발생 가능 시나리오**

- 사이트가 다른 응답 경로나 proxy를 사용하기 시작했는데 코드가 substring 매칭만 유지한다.
- 방어/리다이렉트로 본문은 404 셸인데, 코드가 이를 block이 아닌 `빈 결과`로 기록한다.
- 결과적으로 운영자는 `진짜 매물이 없음`과 `응답 매칭 실패`를 구분하지 못한다.

**우선순위**

- P1

**권장 보강안**

- 응답 매칭을 단일 substring에서 `host + pathname family + payload schema` 기준으로 넓혀야 한다.
- Playwright path에 `final_url`, `response_seen`, `response_match_count`, `raw_response_url_samples`를 저장해야 한다.
- `response_seen=False`이면서 DOM도 비정상일 경우 `confirmed_empty`가 아니라 `capture_failed`로 분류해야 한다.
- `geo_sweep`도 동일하게 marker endpoint가 비어 있을 때 page state를 함께 관찰해야 한다.

### F-04. 상세 파싱 취약성

**문제**

- `src/core/services/detail_fetcher.py`는 상세 수집을 `m.land.naver.com/article/info/{article_no}`와 `article/view/{article_no}`에 우선 의존한다.
- 이 함수는 `body` 전체 텍스트에서 `기전세금`, `중개소`, `공인중개사`, 전화번호를 정규식으로 찾는다.
- 실거래/전세 내역은 `text=실거래가` 클릭 후 `text=전세` 클릭에 의존한다.
- 페이지 이동 후 대기시간이 `300ms`, 클릭 후 `200ms`, `250ms` 수준으로 짧아, client-side hydration이나 느린 네트워크에 취약하다.
- 초기 HTML이나 DOM에서 필요한 텍스트가 즉시 노출되지 않으면, 관련 필드가 빈 문자열 또는 0으로 조용히 채워진다.

**실제 사이트 근거**

- 2026-03-25 기준 `m.land`와 `fin.land` 상세의 초기 HTML에서는 `실거래가`만 보였고, `기전세금`, `중개소`, `전화`, `공인중개사` 같은 텍스트는 확인되지 않았다.
- 이는 현재 상세 파서가 기대하는 텍스트가 초기 응답 HTML에 없거나, hydration 이후에만 나타날 수 있음을 의미한다.

**영향 범위**

- `부동산상호`
- `중개사이름`
- `전화1`, `전화2`
- `기전세금(원)`
- `갭금액(원)`, `갭비율`
- 상세 필드 export 품질 전반

**발생 가능 시나리오**

- 페이지가 Next.js/CSR 구조로 바뀌어 초기 HTML에는 핵심 텍스트가 없다.
- 버튼 레이블이나 탭 텍스트가 바뀌어 `text=실거래가`, `text=전세` 클릭이 실패한다.
- broker/contact 정보가 비동기 API로만 주어지면 현재 regex 파서는 영구적으로 빈 필드를 만든다.

**우선순위**

- P1

**권장 보강안**

- `article detail source`를 전략화해 `m.land`, `fin.land`, 향후 신규 경로를 분리된 source로 다뤄야 한다.
- DOM 텍스트만 보지 말고 hydration 이후 DOM, inline JSON, network response를 함께 보는 다중 수집 경로가 필요하다.
- 상세 파서 실패를 단순 빈 필드로 삼키지 말고 `detail_source`, `detail_parse_state`, `detail_missing_fields`를 남겨야 한다.
- 대기시간은 고정 `sleep` 중심이 아니라 selector/state 기반으로 전환해야 한다.

### F-05. 사용자 진입 경로 불일치

**문제**

- `src/ui/dialogs/batch.py`의 URL 입력 예시는 `https://new.land.naver.com/complexes/...` 중심이다.
- `src/ui/widgets/crawler_tab_parts/ui_setup.py`의 툴팁도 `new.land.naver.com/complexes/12345 -> ID: 12345`를 안내한다.
- `src/ui/app_parts/tab_setup.py`의 빠른 시작 가이드도 `new.land.naver.com`에서 단지 ID를 찾으라고 안내한다.
- `src/core/parser.py`는 `fin.land` URL을 인식하지 못한다.
- `tests/test_parser_module.py`, `tests/test_playwright_engine_stabilization.py` 등도 대부분 `new.land` 패턴을 고정 fixture로 사용한다.

**실제 사이트 근거**

- 2026-03-25 기준 공개 검색 노출은 `fin.land` 상세 경로를 보여주고 있고, 자동화 검증에서 `new.land`는 취약한 진입점으로 관찰됐다.
- 즉, 운영자/사용자가 실제로 보는 현재 서비스 경로와 앱의 안내 문구가 분리될 가능성이 높다.

**영향 범위**

- URL 일괄 등록
- 도움말/가이드 신뢰도
- 단지 링크 열기 UX
- 테스트가 잡아내는 회귀 범위

**발생 가능 시나리오**

- 사용자가 현재 서비스에서 복사한 URL을 붙여넣었는데 파싱이 실패한다.
- 가이드대로 `new.land` URL을 찾으려다 실제 브라우저 경로와 어긋나 혼선을 겪는다.
- 테스트는 계속 통과하지만 실제 운영 경로와 점점 멀어진다.

**우선순위**

- P2

**권장 보강안**

- 도움말, 툴팁, URL 예시, 외부 링크 열기 동작을 실제 운영 경로 기준으로 갱신해야 한다.
- parser test fixture는 `new.land` 단독이 아니라 `new.land`, `m.land`, `fin.land`를 모두 포함해야 한다.
- URL 등록 UI는 `article URL -> complex/article 분해` 경로도 고려해야 한다.

## 후속 인터페이스 변경 제안

이번 단계에서는 구현하지 않지만, 다음 변경 없이는 안정적인 복구가 어렵다.

- `base domain/url builder` 추상화
  - `complex`, `article`, `search`, `api`별로 `new.land`, `m.land`, `fin.land`를 선택할 수 있는 resolver가 필요하다.
- `article detail source` 전략 분리
  - `MlandDetailSource`
  - `FinlandDetailSource`
  - 향후 추가 source
- observability 필드 추가
  - `final_url`
  - `http_status`
  - `block_reason`
  - `response_match_count`
  - `detail_parse_state`
  - `detail_source`

## 검증 시나리오와 현재 해석

### 1. 수동 브라우저는 되지만 Playwright에서는 `new.land`가 404/차단되는가

- 관측 결과
  - 사용자 제보상 일반 브라우저 접근은 가능하다.
  - 본 환경의 ad-hoc Playwright Chromium 접근은 `new.land`에서 `/404`로 수렴했다.
- 현재 코드 반응
  - Playwright 경로는 이를 명시적 차단으로 판정하지 못할 수 있다.
- 잠재 회귀
  - 운영자는 실제 차단을 `매물 0건`으로 오해할 수 있다.
- 권장 계측
  - `final_url`, `title`, `block_reason`, `redirect_count`

### 2. `new.land` API 직접 호출이 rate limit에 걸릴 때 현재 로직이 이를 빈 결과와 구분하는가

- 관측 결과
  - `new.land/api/complexes/{id}` 직접 호출은 `TOO_MANY_REQUESTS`를 반환했다.
- 현재 코드 반응
  - `NaverURLParser.fetch_complex_name()`는 실패 시 예외를 삼키고 `단지_{id}`로 fallback한다.
- 잠재 회귀
  - 운영자가 rate limit을 사이트 구조 변경이나 잘못된 ID로 오인할 수 있다.
- 권장 계측
  - `name_lookup_status`, `http_status`, `error_code`, `source_domain`

### 3. `fin.land` 공개 매물 상세가 실제 경로일 때 현재 상세 파서가 직접 다루는가

- 관측 결과
  - 공개 검색 결과로 `fin.land.naver.com/articles/{articleId}`가 노출된다.
- 현재 코드 반응
  - 상세 파서는 `m.land` 우선이며, `fin.land`는 현재 URL이 그쪽일 때만 우회적으로 감지한다.
- 잠재 회귀
  - 현행 사용자 경로와 코드 내부 상세 source가 계속 벌어진다.
- 권장 계측
  - `detail_source`, `resolved_detail_url`, `detail_redirect_chain`

### 4. 초기 HTML에 상세 정보가 거의 없고 렌더 후 텍스트에 의존하는가

- 관측 결과
  - `m.land`, `fin.land` 초기 HTML에서는 `실거래가` 외 핵심 텍스트가 거의 보이지 않았다.
- 현재 코드 반응
  - `body` 텍스트 regex와 짧은 wait에 강하게 의존한다.
- 잠재 회귀
  - 중개사/전화/기전세금/갭 필드가 빈 값으로 누락된다.
- 권장 계측
  - `detail_body_length`, `detail_missing_fields`, `hydration_wait_ms`, `selector_found`

### 5. UI/문서/테스트의 URL 예시가 실제 현행 경로와 어긋나는가

- 관측 결과
  - 현재 코드와 문서는 `new.land` 중심이며 `fin.land`는 입력 경로로 거의 고려되지 않는다.
- 현재 코드 반응
  - URL 예시와 파서 fixture가 기존 경로를 강화한다.
- 잠재 회귀
  - 운영자가 올바른 URL을 넣어도 등록 실패, 또는 stale 링크로 이동한다.
- 권장 계측
  - `input_url_family`, `parser_match_family`, `open_url_family`

## 결론

- 2026-03-25 기준 가장 큰 위험은 `사이트 종료`가 아니라 `자동화 접근 차단 + 도메인/경로 drift + 관측성 부족`의 조합이다.
- 현재 구조는 `new.land`와 `m.land` 전제 위에서 만들어졌고, `fin.land`는 부분 대응만 들어가 있다.
- 특히 Playwright 경로는 기본 엔진이면서도 차단/404/응답 미포착을 강한 실패로 올리지 못해, 실제 장애가 `빈 결과`로 보일 위험이 크다.
- 다음 구현은 selector 미세 조정보다 먼저 `경로 추상화`, `상세 source 전략 분리`, `observability 보강` 순서로 가는 것이 맞다.

## Repo Sync Note (2026-03-25)

- 코드베이스에는 GUI 없이 실제 접근 경로를 확인하는 `app_entry.py --live-smoke [--smoke-headless]` 경로가 추가되었다.
- 2026-03-25 headless smoke 기준:
  - `https://fin.land.naver.com/` -> 200
  - `https://new.land.naver.com/` -> 200
  - `https://m.land.naver.com/` -> `fin.land` map 경로로 redirect
- repo-wide typing/encoding consistency pass 이후 `pyright` 기준은 `0 errors`이며, root `.md/.spec/.gitignore/.editorconfig/.vscode/settings.json/.github/workflows/ci.yml`까지 UTF-8/mojibake 검사 대상에 포함된다.
