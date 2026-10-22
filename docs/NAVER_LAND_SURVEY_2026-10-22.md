# 네이버 부동산 사이트 조사 (2026-10-22) — fin.land 전면 전환 대비

이전 문서: [`NAVER_LAND_SURVEY_2026-08-12.md`](./NAVER_LAND_SURVEY_2026-08-12.md) · 개선 계획: [`FIN_LAND_MIGRATION_PLAN_2026-10-22.md`](./FIN_LAND_MIGRATION_PLAN_2026-10-22.md)

네이버페이 부동산이 `https://fin.land.naver.com/map?layer=...` 지도 화면으로 전면 전환될 예정이라는 전제로, 2026-10-22에 실제 브라우저(Playwright Chromium 156, headless/headed)로 화면을 열고 네트워크 요청을 기록했다. 응답 스키마는 같은 브라우저 세션 안에서 직접 호출해 확인했고, 요청 파라미터는 사이트 JS 번들(`property.pstatic.net/property-web/_next/static/chunks/*.js`)의 API 정의와 대조했다.

## 1. 결론 요약

| 항목 | 08-12 | 10-22 실측 |
|------|-------|-----------|
| `fin.land` 지도/HTML | pstatic 404 다발 | **정상.** `/map?layer=...` 단일 SPA(Next.js). `/complexes/{id}`, `/articles/{id}`, `/search?keyword=`는 모두 307로 `map` 레이어에 들어감 |
| `fin.land` front-api | 세션 없으면 429 | **브라우저 내부 `fetch`는 쿠키 없이도 200.** 브라우저 밖 요청(curl, urllib, Playwright `APIRequestContext`)은 UA가 정상이어도 429 |
| HeadlessChrome UA | 확인 안 됨 | **`HeadlessChrome/...` UA는 front-api가 즉시 429**, SPA는 429를 받으면 `/404`·`/500` 오류 페이지로 이동 |
| `new.land` | 핵심 호스트 | 정상 Chrome UA에서는 아직 동작. HeadlessChrome/curl은 `/404`. **`ms=`가 base62로 바뀜** (`ms=2AJ9Kw,3zn5fO,16`) |
| `m.land` | fin 합류 | **홈과 `/article/info/{id}`가 fin으로 리다이렉트** (독립 소스로 사용할 수 없음) |
| 단지 매물 목록 | `new.land /api/articles/complex/{id}` | fin `POST /front-api/v1/complex/article/list` (커서 페이지네이션, 동일매물 묶음) |
| 키워드 검색 | `new.land /api/search` | fin `GET /front-api/v1/search/autocomplete/{complexes,legalDivisions,...}` |

이 결과로 보면 수집 엔진의 기본 경로를 fin front-api로 옮겨야 한다. 앱 기존 UA(`...AppleWebKit/537.36`, `Chrome/126.0`)는 HeadlessChrome 토큰이 없어 front-api에서 200을 받았다.

## 2. URL 계약

### 2.1 `layer` 파라미터

`layer`는 레이어 스택 JSON을 [lz-string](https://github.com/pieroxy/lz-string) `compressToEncodedURIComponent`로 압축한 값이다(번들 모듈 `443324`가 lz-string 원본).

| 화면 | 디코딩 결과 |
|------|-------------|
| 홈 | `[{"id":"home","searchParams":{}}]` |
| 단지 | `[{"id":"complex_detail","params":{"complexId":111515},"searchParams":{"tab":"article"}}]` |
| 매물 | `[{"id":"article_detail","params":{"articleId":"2550000000"},"searchParams":{}}]` |

- 단지 `tab` 값: `article`, `transaction` 등. 빌라 단지는 `isVilla=true`
- 공유용 정식 링크: `https://fin.land.naver.com/complexes/{id}?tab=article` (307 → 레이어 URL)

### 2.2 지도 좌표

- fin: `center=<lon>-<lat>&zoom=15`. 각 좌표는 base62(`0-9a-zA-Z`)이고 값 = `(n - 2e9) / 1e7`. 예시 `center=3zhF48-2AM354` → 경도 126.9779692, 위도 37.566535
- new.land: `ms=<lat>,<lon>,<zoom>`. 같은 base62 형식으로 바뀌었다. 예시 `ms=2AJ9Kw,3zn5fO,16` → 37.4976, 127.1072. 숫자형 `ms=37.5,127.0,16` 입력도 여전히 받아 base62로 다시 씀
- 필터 쿼리: `tradeTypes=A1-B1&realEstateTypes=A01-A04-B01`

### 2.3 코드표 (번들 zod 스키마)

- 거래유형: `A1` 매매, `B1` 전세, `B2` 월세, `B3` 단기임대
- 부동산유형: `A01` 아파트, `A02` 오피스텔, `A04` 재건축, `A05` 타운하우스, `A06` 다세대, `A07` 도시형생활주택, `B01` 아파트 분양권, `C02` 빌라·연립 등
- 정렬 `articleSortType`: `RANKING_DESC`, `DATE_DESC`, `PRICE_ASC/DESC`, `SPACE_ASC/DESC`
- 페이지 크기 `size`: 최대 30 (`ARTICLE_PAGINATION_SIZE=30`)

## 3. front-api 실측 (`https://fin.land.naver.com/front-api/v1`)

공통 envelope은 `{"isSuccess":true,"detailCode":"success","message":"","result":...}`이다. 오류는 `{"detailCode":"TOO_MANY_REQUESTS"}`(429) 또는 `FST_ERR_VALIDATION`(400)으로 온다.

### 3.1 검색

| 요청 | 결과 |
|------|------|
| `GET /search/autocomplete/complexes?keyword=헬리오시티&size=10&page=0` | `result.list[]`: `complexNumber`, `complexName`, `type`(A01), `legalDivisionName`("서울시 송파구 가락동"), `legalDivisionNumber`, `coordinates{xCoordinate,yCoordinate}`, `hasVrTour` / `hasNextPage`, `totalCount` |
| 같은 API, `keyword=래미안` | `totalCount=303`, `page`는 0부터 시작 |
| `GET /search/autocomplete/legalDivisions?keyword=반포동` | `legalDivisionNumber`(10자리 = 기존 cortarNo), `legalDivisionName`, `legalDivisionLevelType`(EUP 등), `coordinates` |
| `GET /search/autocomplete/subwayStations?keyword=잠실` | `stationName`, `coordinates` |
| 전체 주소(`서울특별시 송파구 가락동`, `서울특별시 서초구 반포동`) | **0건.** 동/구 이름 꼬리로 다시 검색해야 함(기존 address variant 로직 재사용 가능) |
| `GET /search/complexes/address?address=...` | 지번 주소 입력 시 `result: []` |

`apartmentComplexes` 엔드포인트도 같은 응답을 준다. 사이트 홈 검색은 `complexes`·`legalDivisions`·`subwayStations`·`presales`·`redevelopmentAreas`·`elementarySchool`을 병렬로 호출한다.

### 3.2 단지

- `GET /complex?complexNumber=111515` → `name`, `type`, `address{legalDivisionNumber, city, division, sector, jibun, roadName, zipCode}`, `coordinates`, `totalHouseholdNumber`(9510), `dongCount`, `useApprovalDate`, `constructionCompany`, `parkingInfo`, `buildingRatioInfo` 등
- `GET /complex/article/stats?complexNumber=` → `count{dealCount, leaseDepositCount, leaseMonthlyCount, leaseShortTerm}`, `price{dealMin/MaxPrice, ...}`
- `GET /complex/pyeongList?complexNumber=` → 평형 목록(`number`, `name`, 평면도)

### 3.3 단지 매물 목록 (수집 핵심)

```
POST /complex/article/list
{"size":30,"complexNumber":"111515","tradeTypes":["A1"],"userChannelType":"PC",
 "articleSortType":"RANKING_DESC","lastInfo":[]}
```

- 응답 `result`: `seed`, `lastInfo`(커서 배열), `hasNextPage`, `totalCount`, `list[]`
- 다음 페이지 요청에는 직전 응답의 `lastInfo`와 `seed`를 그대로 넣는다(사이트 `withSeed`)
- 선택 필터: `pyeongTypes`, `dongNumbers`, `minDealPrice/maxDealPrice`, `minWarrantyPrice/maxWarrantyPrice`, `minRentPrice/maxRentPrice`
- 빌라 단지는 `/complex/villa/article/list`(같은 형식)

`list[]`는 **동일매물 묶음**이다.

```
{ "representativeArticleInfo": {...대표 광고...},
  "duplicatedArticleInfo": {
     "representativePriceInfo": {"dealPrice":{"minPrice","maxPrice"}, "warrantyPrice":{...}, "rentPrice":{...}},
     "realtorCount": 3, "directTradeCount": 0,
     "articleInfoList": [ {...광고...}, ... ] } }
```

광고 객체 필드:

| 필드 | 예시 | 앱 매핑 |
|------|------|---------|
| `articleNumber` | "2656920495" | 매물ID |
| `complexNumber`, `complexName`, `dongName` | 111515, 헬리오시티, "106" | 단지ID·동 |
| `tradeType`, `realEstateType` | A1, A01 | 거래유형·자산유형 |
| `priceInfo.dealPrice / warrantyPrice / rentPrice` | 3100000000 / 0 / 0 (**원**) | 매매가·보증금·월세(만원 문자열로 변환) |
| `priceInfo.managementFeeAmount`, `priceChangeHistories[]` | 300000 | (신규) 관리비·가격변동 |
| `spaceInfo.supplySpace / exclusiveSpace / supplySpaceName` | 110.17 / 84.95 / "110F" | 공급·전용면적·타입명 |
| `articleDetail.floorInfo`, `direction` | "33/35", "WS" | 층/방향 (방향은 코드 → 남서향 등 변환) |
| `articleDetail.articleFeatureDescription`, `directTrade` | | 타입/특징·직거래 |
| `verificationInfo.verificationType`, `articleConfirmDate` | OWNER, 2026-10-22 | 확인유형·확인일 |
| `brokerInfo.brokerageName`, `cpId` | 송파로얄공인중개사사무소, bizmk | 부동산상호·정보제공 |
| `address.coordinates` | x=경도, y=위도 | 위도·경도 |

헬리오시티 매매 전 페이지 실측: **31페이지, 묶음 905개(`totalCount`=905 ≈ stats `dealCount` 906), 펼친 광고 1,977건(고유 매물번호).** 즉 `totalCount`는 묶음 수다. 기존 앱은 new.land `sameAddressGroup=false`로 광고 단위를 수집했으므로, 묶음의 `articleInfoList`를 펼쳐야 같은 의미가 된다. 동일주소건수는 묶음 크기, 동일주소최고/최저가는 `representativePriceInfo`로 채운다.

### 3.4 매물 상세

| 요청 | 결과 |
|------|------|
| `GET /article/agent?articleNumber=` | `brokerageName`, `brokerName`, `address`, `businessRegistrationNumber`, `phone{brokerage, mobile}` |
| `GET /article/basicInfo?articleNumber=&realEstateType=A01&tradeType=A1` | `priceInfo`(매매는 `previousDeposit` = 기전세금, 원 단위), `detailInfo.articleDetailInfo`(설명), `spaceInfo`(방·욕실 수), `sizeInfo`(`pyeongArea`). **유형 코드가 매물과 다르면 `{"isSuccess":false}`** (빌라에 A01, 전세에 A1 등) |
| `GET /article/basicInfo?articleId=` (앱 기존) | **400 `FST_ERR_VALIDATION`** → 수정 필요 |
| `GET /article/key?articleNumber=` | `complexNumber`, `pyeongTypeNumber`, `buildingNumber`, `realEstateType`, `tradeType` |
| `GET /search/articles?articleNumber=&userChannelType=PC` | 목록과 같은 광고 객체 1건(매물번호 → 단지 역조회) |
| `GET /article/maintenanceFee?articleNumber=`, `/article/tax`, `/article/agentFee` | 관리비·세금·중개보수 |

### 3.5 지도(지오 모드)

- `POST /complex/complexClusters` — body `{"filter":{"tradeTypes":[...],"realEstateTypes":[...],...},"boundingBox":{"left","right","top","bottom"},"precision":15,"userChannelType":"PC"}` → `clusters[]`(`complexNumber`, `coordinates`, `totalHouseholdNumber`, ...). 이름이 없고 빌라는 묶여서(3,603곳 → 101 클러스터) 탐색용으로 부적합
- `POST /complex/boundedComplexes` — 위 body에 `complexPagingRequest:{size:30, complexSortType, lastInfo, seed}` 추가 → 단지명·주소·좌표·세대수·거래유형별 매물수(`articleCountInfoDto`)·가격범위. **앱 지도 탐색이 이 API를 사용**
  - 필터는 `{"tradeTypes":["A1"],"realEstateTypes":[...],"hasArticle":true}`만으로 충분(나머지 키 생략 가능). `hasArticle:true`면 매물 있는 단지만(공덕 일대 512 → 263곳)
  - 정렬 `complexSortType`: `POPULARITY_DESC`(인기), `HOUSEHOLD_NUMBER_DESC`, `USE_APPROVAL_DATE_DESC`, `ARTICLE_COUNT_DESC`(매물 많은 순, 앱 사용)
  - 항목 `type`: 아파트 `COMPLEX` → `complex.complexInfo`, 빌라 `VILLA` → `villa.villaInfo`
  - 빌라 `realEstateTypes` = `A05`(연립)·`A06`(다세대)·`A07`(도시형생활주택)·`C02`(빌라·연립) (번들 `VILLA_REAL_ESTATE_TYPES`)
- `POST /complex/legalDivisionComplexList` — 법정동 단위 단지 목록
- `GET /legalDivision/searchByCoordinate?longitude=&latitude=&type=EUP` — 좌표 → `legalDivisionNumber`, `legalDivisionName`("서울시 동대문구 답십리동")

### 3.6 빌라

- 목록: `POST /complex/villa/article/list` (아파트와 같은 body·응답 형식, 묶음 구조 동일)
- 정보: `GET /complex/villa?complexNumber=` (이름·주소·좌표·세대수)
- 링크: `/complexes/{id}?tab=article&isVilla=true` → 레이어 `searchParams.isVilla=true`
- **번호 체계가 new.land와 다름**: fin 빌라 번호(예: 골든빌 615902)는 new.land `/api/houses/{id}`에서 404. 또 new.land 빌라 지도(`/houses`)는 이미 단지 마커(`houses/single-markers`)를 쓰지 않고 법정동 단위 매물 클러스터(`/api/articles/clusters?cortarNo=`)로 바뀌어, 앱의 기존 빌라 경로는 실제로 동작하지 않았다
- 없는 번호: 정보 API는 `result` 없는 성공 응답, 목록 API는 빈 목록 → 앱은 "빈 첫 페이지 + 정보 없음"이면 미존재로 보고 예전 경로로 넘긴다

## 4. 차단·레이트리밋 관측

1. 짧은 시간에 홈을 반복해서 열자(프로브 6~7회, 회당 front-api 20여 건) 모든 front-api가 429를 받고 SPA는 `financial.pstatic.net/404.html` 또는 `/500`으로 이동했다
2. 같은 IP에서 일반 Chrome UA로 새로 열자 즉시 200을 받았다. 차단은 **IP가 아니라 HeadlessChrome UA + 브라우저 밖 요청 신호** 기준이다. 같은 headless 브라우저에서 UA만 바꾸면 200, 기본 UA는 429로 재현됨
3. 사이트는 `POST /front-api/v1/telemetry {"signals":["NAVIGATOR_USER_AGENT"]}`를 보낸다(UA 기반 봇 신호 수집)
4. 정상 UA에서 1~1.3초 간격으로 매물 목록 31페이지를 연속 호출해도 429는 없었다

운영 규칙: HeadlessChrome UA를 쓰지 않는다, front-api는 fin 오리진 페이지 안에서 `fetch`로 호출한다, 429는 즉시 재시도하지 않는다(기존 정책 유지).

## 5. 앱 영향 정리

| 기능 | 현재 코드 | 판정 |
|------|-----------|------|
| 단지 매물 수집 | new.land Article API + response capture | 동작하지만 전환 시 중단 → **fin 목록 API를 기본 경로로** |
| 키워드 검색 | new.land `/api/search` (세션 페이지가 new.land 홈) | 전환 시 중단 → **fin autocomplete로 교체**, new.land는 폴백 |
| 상세 front-api 보강 | `APIRequestContext.get` | **현재도 429** → fin 페이지 내부 fetch로 교체, `basicInfo` 파라미터 수정 |
| 지도 링크 붙여넣기 | `ms=위도,경도` 숫자만 해석, fin `layer`/`center`는 해석 불가 | **base62·layer 해석 추가** |
| m.land 진입/워밍업 계획 | 옵션(기본 off) | m.land가 fin으로 리다이렉트 → **제거** |
| 지도(지오) 모드 마커 | new.land `single-markers/2.0` + 지도 드래그 | 드래그 좌표 해석(`ms=`)이 base62 변경으로 이미 고장 → **fin `boundedComplexes` 구역 조회로 교체**(2차) |
| 빌라(VL) 목록 | new.land `/api/articles/house` | new.land 빌라 지도 구조 변경으로 이미 고장 → **fin `/complex/villa/article/list`로 교체**(2차) |
| 단지명 조회 | new.land overview (urllib) | 브라우저 밖 요청이라 429 가능 → 검색 세션에서 fin `/complex` 우선 |

## 6. 앱 반영 결과 (같은 날 실사이트 검증)

계획 문서의 1~6단계를 반영했다. 실사이트 확인 결과:

| 검증 | 결과 |
|------|------|
| 엔진 fin 경로, 헬리오시티(111515) 매매 | complete, 31페이지, **1,977행**(고유 매물번호 1,977), 15.6초 |
| 같은 단지 전세 / 월세 | complete, 665행(17페이지) / 789행(18페이지) |
| 반포자이(22853) 매매 | complete, 980행 |
| new.land 폴백 호출 | 0회 (`article_api_fast_path_*` 카운터 0, `fin_api_hit_count`=4) |
| 검색 `헬리오시티` / `래미안` / `반포동` | 2건 / 10건(+더 보기, 2페이지 정상) / 단지 10건 + 지역 `1165010700` |
| 검색 `서울특별시 송파구 가락동` | fin은 전체 주소 0건 → 변형 `송파구 가락동`으로 적중, 지역 `1171010700` |
| 검색 `경기도 성남시 분당구 정자동 123` | 번지 제거 변형으로 적중, 지역 `4113510300` |
| 링크 단지 확인 (fin `/complex`) | 헬리오시티, 서울시 송파구 가락동 913, 9,510세대 |
| 매물번호 → 단지 (fin `/search/articles`) | 2656920495 → 111515 |
| `app_entry.py --live-smoke --smoke-headless --live-smoke-detail-fields` | 11단계 모두 `[ok]` (`fin-contract` articles=87, `detail` agent 200 in-page, `article-lookup` fin 경로) |

로그: `logs/live-smoke-fin-2026-10-22.json`

## 7. 2차 반영: 지도 탐색·빌라·상세 (같은 날)

### 실제 앱 수집 스레드로 종단 검증

`CrawlerThread`를 임시 데이터 폴더(별도 SQLite)로 실제 실행했다. 사용자 DB는 건드리지 않았다.

| 실행 | 결과 |
|------|------|
| 단지 수집 1차: 헬리오시티·반포자이(아파트), 골든빌(빌라) × 매매·전세, 상세 단지당 3건 | 6개 조합 모두 complete, **4,069건** 저장, 오류·경고 0, 92초 |
| 단지 수집 2차(같은 DB 재실행) | 신규 **0건**(1차 매물을 동일 매물로 인식), 이력 4,069건 유지(중복 없음) |
| 지도 탐색: 공덕 일대(37.5440, 126.9510) 줌 16, 아파트+빌라, 매매 | fin 구역 조회 11회로 **단지 320곳**(아파트 117·빌라 203) 발견, 320곳 모두 complete, 5,772건, 단지 DB 등록 320 |
| 상세 방식 비교(같은 56건) | 상세 화면 열기 **101초** vs fin API만 **14.4초**, 필드 동일(화면 방식은 전화2에 같은 번호 중복 기록) |
| 상세 대량(기본 설정 = API 우선, 단지당 100건) | 매물 4,087건 + 상세 426건 **84.7초**, 6개 조합 complete, 429 없음 |

### 발견해서 고친 문제

- **중개사 전화 칸에 관리사무소 번호:** 상세 화면이 함께 받는 단지 정보(`/complex?complexNumber=`의 `managementOfficeContact`)가 먼저 병합되어 `전화1`에 들어갔다(예: 헬리오시티 02-403-8330). 중개사 API(`/article/agent`) 값을 우선하고, 단지 단위 응답은 중개 정보 추출에서 제외했다
- **상세 비용:** 상세 화면(SPA) 대신 fin API(`agent` → `article/key` → 매매만 `basicInfo`)를 먼저 쓰고, 그것으로 못 받은 매물만 화면을 연다
- **지도 탐색 드래그 고장:** `ms=`가 base62가 되어 `_get_ms()`가 좌표를 못 읽었다. fin 구역 조회로 대체했고, 예전 경로도 base62를 읽도록 고쳤다

## 8. 재현 방법

조사 스크립트는 저장소에 넣지 않았다(scratchpad 사용). 재현 절차:

1. 일반 Chrome UA로 Chromium을 띄우고 `https://fin.land.naver.com/robots.txt`를 연다(가벼운 동일 출처 페이지)
2. `page.evaluate(fetch('/front-api/v1/...'))`로 위 표의 요청을 1초 이상 간격으로 보낸다
3. `python app_entry.py --live-smoke --smoke-headless`의 `fin-contract` 단계가 같은 검사를 수행한다(본 라운드에서 추가)

*작성: 2026-10-22 (실측: 같은 날 KST 10:00–11:00)*
