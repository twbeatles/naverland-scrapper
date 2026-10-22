# fin.land 전면 전환 대응 개선 계획 (2026-10-22)

근거 실측: [`NAVER_LAND_SURVEY_2026-10-22.md`](./NAVER_LAND_SURVEY_2026-10-22.md)

## 목표

1. `new.land`가 내려가도 **단지 매물 수집과 키워드 검색이 계속 동작**하게 한다
2. 이미 동작하지 않는 경로(m.land 진입, `APIRequestContext` front-api, `basicInfo?articleId=`)를 고치거나 지운다
3. 아파트 단지 검색을 fin 검색 API 기준으로 개선한다(정확한 단지번호·좌표·법정동, 링크 붙여넣기 해석)
4. 수집 안정성은 유지한다. new.land 경로는 살아 있는 동안 폴백으로 남기고, 결과 완료성 판정(`CollectionResult`)은 그대로 쓴다

## 설계 원칙

- **front-api는 fin 오리진 페이지 안에서 `fetch`로 호출한다.** `https://fin.land.naver.com/robots.txt`를 연 페이지를 호출 전용으로 쓴다. 지도 SPA를 띄우지 않으므로 부가 요청 20여 건이 생기지 않는다
- **HeadlessChrome UA를 쓰지 않는다.** 데스크톱 컨텍스트 UA를 완전한 Chrome UA 상수(`site_contract.DESKTOP_USER_AGENT`)로 통일한다
- **광고 단위 의미를 유지한다.** fin 목록의 동일매물 묶음을 펼쳐 기존 `sameAddressGroup=false`와 같은 행 단위를 만든다
- fin 광고는 기존 new.land 필드 모양으로 변환한 뒤 `normalize_article_payload`를 그대로 통과시킨다. DB·UI·export 계약이 바뀌지 않는다
- 캐시 fingerprint 버전을 올려(`COLLECTION_SCHEMA_VERSION` 2→3) 소스가 바뀐 결과가 예전 캐시와 섞이지 않게 한다

## 작업 단계

### 1단계 — 계약·코덱 (서비스 계층)

- `site_contract.py`: fin front-api 상수와 URL/body 빌더 추가(`build_fin_article_list_body`, 검색·단지·상세 URL, `DESKTOP_USER_AGENT`, `FIN_API_ORIGIN_PAGE`). `build_front_api_basic_info_url`을 `articleNumber` + `realEstateType` + `tradeType` 형식으로 수정
- 신규 `services/fin_land_codec.py`: lz-string `decompressFromEncodedURIComponent`, base62 좌표 encode/decode, fin/new 지도 URL 해석(`parse_map_link`)
- 신규 `services/fin_article_api.py`: 목록 응답 파싱(묶음 펼침, 커서), 가격(원→만원 문자열)·방향 코드 변환, 광고 → 레거시 모양 변환

### 2단계 — 수집 엔진

- 신규 mixin `complex_mode_parts/fin_api.py`(`PlaywrightFinApiMixin`): fin 호출용 페이지 lazy 생성, `fetch` 래퍼, 커서 페이지네이션, 429/HTTP 오류/잘못된 payload 처리(기존 Article API와 같은 partial/failed 규칙)
- `_collect_target_raw_items` 첫 단계에서 APT 단지는 fin 목록을 먼저 시도한다. 실패하면 기존 new.land Article API → response capture 순서로 폴백한다
- 데스크톱 UA 상수 적용
- m.land/fin HTML 레거시 진입 계획(`playwright_allow_fin_m_entry_plans`) 제거

### 3단계 — 상세 보강

- `detail_fetcher_parts/front_api.py`: 상세 페이지가 fin 오리진이면 페이지 내부 `fetch`로 agent/basicInfo를 호출. 세션 워밍 대상을 new.land 홈에서 fin `robots.txt`로 변경
- agent 응답(`phone.brokerage/mobile`, `brokerName`) 매핑 확인

### 4단계 — 검색·링크

- `keyword_search.py`: fin autocomplete(단지 + 법정동) 기반 `fetch_fin_suggestions`·`fetch_fin_search_page`, fin 실패(429 제외) 시 new.land `/api/search` 폴백(`fetch_complex_search_page`). 페이지 번호 변환(앱 1-base ↔ fin 0-base). `KeywordBrowserSession`은 fin `robots.txt`에서 시작
- 검색 결과에 법정동 주소·좌표를 채우고, 붙여넣은 단지 링크는 fin `/complex` API로 이름·주소를 확인
- `NaverURLParser`: fin `map?layer=`(complex_detail/article_detail) 해석, `extract_map_center`가 base62 `ms=`와 fin `center=`를 해석
- 검색 다이얼로그 안내 문구 갱신(“fin 지도 링크는 해석 불가” 문구 제거)

### 5단계 — 링크 생성·정리

- `build_complex_url` 기본 family를 fin으로 변경(`/complexes/{id}?tab=article`, 빌라는 `isVilla=true`). new 링크는 `preferred_family="new"`로 계속 생성 가능
- 오래된 주석·문서 갱신(site_contract docstring, CLAUDE.md, update_history)

### 6단계 — 검증

- 단위 테스트: 코덱, 목록 파서(묶음 펼침·커서·오류 envelope), 가격/방향 변환, 검색 파서·폴백, 링크 해석, UA 상수, 엔진 fin 경로(가짜 페이지)
- 기존 스위트 + `scripts/ci_check.ps1`
- 실사이트 검증: 엔진 fin 경로로 헬리오시티 매매 수집, 검색 세션으로 “헬리오시티/래미안/반포동” 검색, live-smoke `fin-contract` 프로브

## 2차 라운드 (같은 날 완료)

1차에서 후속으로 미뤘던 두 항목은 실측 결과 **이미 동작하지 않던 경로**였으므로 같은 날 이관했다.

| 항목 | 반영 내용 | 상태 |
|------|-----------|------|
| 지도 탐색 마커 → fin | `geo_mode_parts/fin_markers.py`: 격자 각 지점을 화면 크기 bbox로 바꿔 `boundedComplexes`(매물 있는 단지만, 매물 많은 순, 커서 페이지)로 조회. 지도 드래그 불필요. 첫 조회가 실패하면 new.land 지도로 폴백. 구역당 상한 10페이지(300곳) | 완료 |
| 빌라 목록 → fin | APT는 `/complex/article/list`, VL은 `/complex/villa/article/list`. 빈 첫 페이지면 `/complex(/villa)` 정보 API로 존재 확인 후, 없는 번호만 예전 경로로 폴백 | 완료 |
| 상세 API 우선 | `agent` → `article/key` → 매매만 `basicInfo`. 화면은 API로 못 받은 매물만 엶. 관리사무소 번호가 중개사 전화로 들어가던 문제 수정 | 완료 |
| 예전 지도 경로 좌표 | `_get_ms()`가 base62 `ms=`를 읽도록 수정 | 완료 |
| UI 문구 | 지도 탐색 "구역 간격/구역마다 쉬는 시간"(쉬는 시간은 fin 구역 사이 간격으로 사용), 상세 설정 문구, 단지 번호 입력 힌트, 지도 위치 링크에 법정동 이름 표시 | 완료 |

## 남은 비범위

| 항목 | 이유 | 후속 방향 |
|------|------|-----------|
| 관리비·가격변동 이력 등 신규 필드의 DB 컬럼화 | 기존 additive migration 원칙상 별도 설계 필요 | 화면 표시 요구가 확정되면 추가 |
| 지하철역·학교 검색 | 단지 수집과 직접 관련 없음 | 지역 검색 탭 확장 시 |
| 예전 new.land 빌라 번호 이전 | new.land house 번호와 fin 빌라 번호가 달라 자동 대응 불가 | 저장된 빌라는 「지역 찾기/지도로 찾기」로 다시 추가 안내 |
| 전세 3년 최고·최저(상세 화면 실거래 탭) | API 우선 경로에서는 받지 않음 | 필요하면 `complex/pyeong/realPrice` 연동 |

## 위험과 대응

- **front-api 계약 변경:** 파서는 envelope 검증 실패 시 `None`을 반환하고 new.land 폴백으로 넘어간다. 폴백까지 실패하면 기존 failed/partial 판정을 따른다
- **429:** 같은 페이지 자동 연속 재시도 금지 정책을 유지한다. 페이지 간 지연 기본 150ms에서 fin 경로는 최소 400ms
- **묶음 펼침 건수 증가:** 광고 단위라 묶음 수보다 행이 많다(헬리오시티 매매 905묶음 → 1,977행). 기존 new.land `sameAddressGroup=false`와 같은 의미다
