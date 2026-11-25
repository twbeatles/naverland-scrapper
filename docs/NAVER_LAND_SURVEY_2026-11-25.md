# 네이버 부동산 사이트 재조사 (2026-11-25) — 10-22 이후 변경 확인

이전 문서: [`NAVER_LAND_SURVEY_2026-10-22.md`](./NAVER_LAND_SURVEY_2026-10-22.md) · 계획: [`FIN_LAND_MIGRATION_PLAN_2026-10-22.md`](./FIN_LAND_MIGRATION_PLAN_2026-10-22.md)

10-22 전면 전환 대응 이후 사이트 변경이 있는지, 앱 연결부(`site_contract`·fin API·검색·상세·지도·DOM 폴백)가
현재 사이트와 어긋난 곳이 있는지 실측했다. 결론은 **계약 변경 없음, 전 경로 정상**이며, 예방 차원의 UA 갱신 1건만 반영했다.

## 1. 조사 방법

- `python app_entry.py --live-smoke --smoke-headless` 실사이트 10개 프로브 (UA 변경 전·후 각 1회, 전부 `[ok]`)
- 직접 HTTP 프로브 4건: fin `robots.txt`, fin autocomplete, new `/api/search`, m.land(리다이렉트 추적)
- 코드 대조: `site_contract.py`, `fin_article_api.py`, `fin_land_codec.py`, `keyword_search.py`,
  `detail_fetcher_parts/*`, `playwright_parts/{complex_mode_parts/fin_api.py,geo_mode_parts/fin_markers.py,runtime_parts/*}`,
  `crawler_parts/dom_scroll_parse.py`, `core/item_parser.py`, `parser.py`

로그: [`logs/live-smoke-2026-11-25.json`](../logs/live-smoke-2026-11-25.json)

## 2. 현재 상태 (10-22 대비)

| 항목 | 10-22 | 11-25 실측 | 판정 |
|------|-------|-----------|------|
| fin 지도 SPA (`/map?layer=`) | 정상 | 200, `/articles/{id}` → map 레이어로 307 정상 | 변경 없음 |
| fin `robots.txt` | 가벼운 오리진 페이지로 사용 | 200. `Disallow: /front-api/v1/` 추가됨 — 크롤러 예절 고지일 뿐 인페이지 `fetch`와 무관 | 앱 영향 없음 |
| fin front-api 브라우저 밖 직접 호출 | 429 | autocomplete·`/api/search` 직접 호출 모두 429 재현 | 계약 유지 (인페이지 fetch 필수) |
| `HeadlessChrome` UA | front-api 429 | 코드 전 경로 `DESKTOP_USER_AGENT`로 통일 유지, 테스트로 강제 중 | 유지 |
| m.land | JS 리다이렉트(`location.replace(DOMAINS.FIN…)`) | 이번에는 서버 측 리다이렉트로 fin map에 도달 (home 프로브 200) | fin행 동일, 코드에 m.land 진입 없음 |
| new.land 홈·Article API·단지 페이지 | 동작 (폴백 경로) | home·`single-markers`·article list 모두 200, `article-api` 프로브 200 (2페이지 40건) | 폴백 유효 |
| new.land `ms=` base62 | 숫자·base62 혼용 | home이 숫자 `ms=`를 base62로 다시 씀 (`2ALiac,3zhF96,15`) | `fin_land_codec` 해석 정상 |
| fin 매물 목록/검색/구역 API 스키마 | `parse_*` 파서와 일치 | `fin-contract` 프로브 파싱 성공 (articles 73~79, geo 30) | 변경 없음 |
| 매물 상세 | API 우선 + 화면 폴백, 전화1=중개사 | `detail` 프로브 `agent_api=200 agent_source=in_page` | 변경 없음 |
| fin 타이틀 | 네이버페이 부동산 | `Npay 부동산` (브랜드 표기 변경) | 앱 문자열에 네이버페이 언급 없음, 영향 없음 |

## 3. DOM 관련 대조 결과

- **주 수집 경로는 DOM을 타지 않는다.** fin 목록 파서(`fin_article_api.py`)는 JSON 스키마 기반이며
  `fin-contract` 실측으로 유효함을 확인했다.
- **DOM 폴백 경로**(new.land 무응답 시 `dom_scroll_parse` + `ItemParser`)는 선택자가 클래스명 패턴
  매칭(`[class*='ArticleItem']` 등) + 텍스트 정규식 폴백으로 구성되어 있어 단일 클래스명 변경에 내성이 있다.
  이번에는 폴백이 발동하지 않아 실측 검증은 못 했으나, 발동 조건·판정(`CollectionResult`) 로직은 그대로다.
- **상세 화면 클릭**(`text=실거래가` → `text=전세`)은 실패해도 예외를 삼키고(`except: pass`) API 필드가 우선이라
  라벨 변경 시에도 수집이 깨지지 않는다. 이번 실측에서 API 경로로 200을 받았다.
- **하이드레이션 읽기**(`__NEXT_DATA__`·`__next_f` RSC 프레임)는 키가 없어도 빈 dict로 끝나고
  `corpus_text` 조합에만 기여하므로 SPA 구조 변경에 관대하다.

## 4. 반영한 수정 (2건)

1. `src/core/services/site_contract.py` — `DESKTOP_USER_AGENT`를 `Chrome/141.0.0.0` → `Chrome/158.0.0.0`으로 갱신.
   근거: 실측 머신의 현행 stable이 158.0.8127.89이며, 사이트가 `NAVIGATOR_USER_AGENT`를 텔레메트리로 수집한다.
   실제 브라우저(158)가 141을 자칭하는 불일치를 두는 것보다 추적하는 쪽이 bot 신호가 적다.
   (141에서도 200이 나오던 상태라 긴급 수정이 아니라 예방 차원이다.)
2. `src/core/engines/playwright_parts/runtime_parts/contexts.py` — 웜업 주석의 낡은 서술
   ("fin/m HTML often 404s")을 현재 상태(heavy SPA라서 가벼운 new.land 홈을 쓴다)로 수정. 동작 변경 없음.

수정 불필요 판정: m.land 정규식(`parser.py`)은 붙여넣은 옛 링크 해석용이라 유지.
`FIN_API_ORIGIN_PAGE`(robots.txt)·커서 페이지네이션·`boundedComplexes` 바디·상세 API 순서는 실측과 일치.

## 5. 검증

- 단위: `test_fin_land`·`test_site_contract`·`test_playwright_engine_globals`·`test_keyword_search*` 104 passed,
  `test_live_smoke`·`test_crawl_preflight`·`test_preflight`·`test_crawler_regressions` 59 passed
- 실사이트: UA 변경 후 live-smoke 10개 프로브 전부 `[ok]` (fin-contract articles=73, geo=30,
  detail agent 200, article-lookup fin 역조회 정상)

## 6. 실제 수집 종단 검증 (같은 날 추가)

`CrawlerThread`를 임시 DB로 실사이트 실행 (사용자 DB 미사용, headless local Chrome):

| 실행 | 결과 |
|------|------|
| 헬리오시티(111515, APT) 매매, 상세 3건 | complete, **2,025건**, detail 3/3 성공, 429 없음 |
| 골든빌(615902, VL) 매매, 상세 3건 | complete, **47건**, villa 엔드포인트 정상, detail 3/3 성공 |
| 헬리오시티 전세 (상세 off) | complete, **719건**, 보증금 파싱 정상 |
| 골든빌 전세 | complete, **0건** — 동일 경로 200·파싱 성공이라 실제 매물 없음으로 판정 (APT 전세 719건으로 B1 분기 정상 확인) |

DB 품질: 가격·면적·층·중개소 100% 기입, 중복 키 0, 전부 `active`. 중개소명 괄호 표기(`(버들414-9400)공인중개사사무소` 등)는
목록 `brokerageName` 원문 그대로이며 앱 가공 오류가 아니다. 전화1은 상세 보강분에만 존재(상세 cap에 따른 설계).

## 7. 수집 병목 측정·개선 (같은 날 추가)

- 오프라인 파이프라인(파싱→정규화→이력→스냅샷→소멸): 합성 2,700건 0.3초 — 병목 아님
- 실측 병목: 3개 쌍 wall 30.7초 중 쌍 사이 수면 12.2초(40%). 보통 속도 3~5초/쌍이 fin fast-path에서도 그대로 적용되던 것이 원인
- 개선: 깨끗한 fast-path 쌍은 1초로 단축, 레거시/DOM·실패 쌍은 기존 속도 유지 → 동일 3개 쌍 19.9초(35% 단축), 수집량·429·폴백 동일. 상세: `update_history.md` 2026-11-25 항목

## 8. 다음 점검 포인트

- `DESKTOP_USER_AGENT`는 Chrome stable이 크게 오를 때마다 갱신 (실측 머신 버전과 대조).
- new.land가 내려가면 레거시 폴백(`article_api`·`response_capture`·DOM 스크롤)은 제거 대상으로 전환. 현재는 모두 200이라 유지.
- fin 목록에 신규 필드(관리비·가격변동 이력 등)가 필요해지면 DB 컬럼 설계부터 (10-22 비범위 항목 유지).

*작성: 2026-11-25 (실측: 같은 날 KST, headless local Chrome 158)*
