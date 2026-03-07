# 🏠 네이버 부동산 매물 크롤러 Pro Plus (v15.0)

네이버 부동산의 아파트 매물 정보를 수집, 분석, 관리할 수 있는 강력한 데스크톱 애플리케이션입니다.  
다중 단지 동시 크롤링, 실시간 가격 변동 추적, 신규 매물 알림, 지도 기반 광역 탐색, 그리고 엑셀 내보내기 기능 등을 제공합니다.

Claude Opus 4.5, Gemini 3.0 Pro 를 이용하여 제작 및 지속 개선중입니다.

## **✨ 주요 기능**

### **v15.0 Anti-Bot / Geo 확장 업데이트**

* **🧠 Playwright 기본 엔진:** 기본 수집 엔진이 `Playwright`로 확장되었고, 기존 `Selenium` 엔진은 **일반 단지 수집(`complex` 모드) fallback 경로**로 유지됩니다. (`geo sweep`은 Playwright 전용)
* **🧭 지도 탐색 탭 추가:** 별도 `지도 탐색` 탭에서 위도/경도/줌 기준 `geo sweep` 수집을 실행할 수 있습니다.
* **🏘️ APT + VL 동시 수집:** 아파트(`APT`)와 빌라/연립/다세대(`VL`)를 모두 탐색 대상으로 지원합니다.
* **📡 응답 기반 목록 수집:** 목록 단계는 Playwright response interception 기반으로 수집해 속도와 유연성을 높였습니다.
* **📱 모바일 상세 병렬 수집:** 모바일 상세 페이지 워커 풀을 이용해 중개사/전화/기전세금/전세 이력을 확장 수집합니다.
* **💰 갭 분석 필드 확장:** `기전세금(원)`, `갭금액(원)`, `갭비율`, `자산유형`, `수집모드` 등이 UI/DB/export 전 구간에 반영됩니다.
* **🗂️ 자동 단지 등록:** 지도 탐색으로 발견한 단지는 DB에 자동 등록되어 이후 그룹/재수집에 재활용할 수 있습니다.
* **📦 PyInstaller Chromium 번들:** `naverland-scrapper.spec`가 Playwright Chromium 번들을 포함하도록 확장되었습니다.

### **v15.0 안정화 업데이트**

* **🛡️ DB 복원 안정성 강화:** SQLite online backup 기반 백업/복원, 무결성(`integrity_check`) 및 필수 테이블 검증을 추가했습니다.
* **🧰 유지보수 모드 복원 플로우:** DB 복원 중 스케줄/크롤링/UI 액션을 안전하게 차단하고, 종료 후 자동 복구합니다.
* **🔍 고급 필터 동선 복원:** 앱 메뉴(`🔍 필터`)에서 고급 필터 진입/해제 경로를 공식 지원합니다.
* **📉 가격변동 표기 정합성:** UI/CSV/Excel에서 가격 하락값이 부호(`-`) 포함 문자열로 일관 표시됩니다.
* **📊 차트 폰트 fallback 개선:** 한글 폰트 미지원 환경에서도 통계/대시보드 렌더 경고를 줄이도록 fallback을 적용했습니다.
* **🧵 중단/종료 반응성 강화:** 재시도 대기 및 크롤링 sleep 구간을 인터럽트 가능하게 변경해 종료 실패 가능성을 낮췄습니다.
* **🪟 URL 배치 등록 비동기화:** 단지명 조회를 worker thread로 분리하고 진행률/취소 버튼을 추가해 UI block을 제거했습니다.
* **🗃️ 데이터 정합성 강화:** 단지 삭제 시 그룹 매핑 orphan이 남지 않도록 정리 로직과 FK 정책을 보강했습니다.
* **🧠 검색/캐시 동작 개선:** 검색 이력 dedupe 키를 확장하고, Playwright 응답이 확인된 0건(`confirmed_empty`)만 negative cache로 저장합니다(응답 drain timeout 시 저장 건너뜀).
* **🧭 캐시 키 컨텍스트 분리:** 캐시 키는 `complex_id + trade_type` 기본 키에 `mode/asset_type/source_lat/source_lon/source_zoom/marker_id` 컨텍스트 네임스페이스를 추가해 `complex`/`geo_sweep` 간 메타데이터 오염을 방지합니다.
* **🔖 버전/저장 카운트 정밀화:** `APP_VERSION` 단일 소스(`v15.0`) 적용 및 DB 저장 결과를 `신규/기존/실패`로 분리 표시합니다.
* **🔒 DB 잠금/손상 대응 강화:** DB write 경로를 직렬화하고 lock 재시도/빠른 실패를 적용해 `database is locked`에 대한 UI 멈춤을 완화했습니다.
* **🧯 손상 감지 시 write 차단:** `database disk image is malformed` 감지 시 write circuit-breaker를 활성화해 수집은 유지하고 추가 손상을 방지합니다.

### **v10.0 신규 기능**

* **📉 가격 변동 그래프:** 이전 수집 기록과 비교하여 가격 상승/하락 내역을 그래프로 표시하고 추적합니다.
* **각종 버그 수정 및 리팩토링:** 세세한 사용성 버그등이 수정되었습니다.

### **v7.3 신규 기능**

* **📉 가격 변동 추적:** 이전 수집 기록과 비교하여 가격 상승/하락 내역을 추적하고 하이라이트 표시합니다.  
* **🆕 신규 매물 배지:** 새로 등록된 매물을 즉시 식별할 수 있도록 'NEW' 배지를 표시합니다.  
* **🔍 고급 필터링:** 가격 범위, 면적, 층수(저/중/고), 키워드 포함/제외 등 상세 조건 필터링을 지원합니다.  
* **📊 엑셀 템플릿:** 엑셀로 내보낼 때 원하는 컬럼만 선택하거나 순서를 변경하여 저장할 수 있습니다.  
* **🔗 URL 일괄 등록:** 네이버 부동산 URL이나 단지 ID 텍스트를 붙여넣어 여러 단지를 한 번에 등록합니다.  
* **📝 특징 파싱 개선:** 중개사 광고 멘트를 필터링하고 핵심 특징만 추출합니다.

### **핵심 기능**

* **다중 단지 수집:** 여러 아파트 단지를 등록하고 한 번에 크롤링할 수 있습니다.  
* **지도 기반 광역 탐색:** 좌표 기반으로 주변 단지/매물을 sweep하며 자동 등록과 즉시 상세 수집까지 수행합니다.
* **데이터베이스 관리:** 수집된 단지 정보와 매물 이력을 로컬 DB(sqlite3)에 안전하게 저장합니다.  
* **그룹 관리:** 관심 단지를 그룹별로 묶어 관리하고 예약 실행할 수 있습니다.  
* **시세 히스토리:** 단지별/평형별 시세 변화를 그래프 데이터로 축적합니다.  
* **알림 시스템:** 특정 가격이나 면적 조건에 맞는 매물이 발견되면 알림을 표시합니다.  
* **편의 기능:** 다크/라이트 모드, 트레이 최소화, 예상 소요 시간 표시, 결과 요약 대시보드.
* **중복 축약 표시:** 동일 단지/가격/평수/층 조건의 유사 매물을 `N건`으로 묶어 결과를 간결하게 볼 수 있습니다.
* **확장 상세 필드:** `부동산상호`, `중개사이름`, `전화1`, `전화2`, `기전세금(원)`, `갭금액(원)`, `갭비율`을 저장/내보내기할 수 있습니다.

### **⚡ 성능 최적화 (UI 반응성 중심)**

* **이력 DB 배치 반영:** 매물 이력 업데이트를 배치 업서트로 처리해 크롤링 중 DB 오버헤드를 감소시켰습니다.
* **결과 검색 최적화:** 행별 검색 캐시/hidden 상태 캐시 + 디바운스로 대량 결과 필터링 지연을 줄였습니다.
* **대량 렌더링 개선:** 결과 테이블 반영을 chunk 단위로 처리하여 UI 멈춤을 완화했습니다.
* **로그 렌더링 제한:** 최대 라인 수를 유지해 장시간 실행 시 로그 탭 성능 저하를 방지합니다.
* **지연 초기화 옵션:** 비핵심 탭 초기 로드를 지연해 시작 체감 속도를 개선할 수 있습니다.

### **⚙️ 설정 반영 정책 (v14.1)**

* **크롤링 속도 즉시 저장:** 속도 슬라이더 변경 시 `settings.json`의 `crawl_speed`가 즉시 갱신됩니다.
* **기본 정렬 적용:** `default_sort_column`/`default_sort_order`가 결과 테이블 정렬 기준에 실제 적용됩니다.
* **검색 디바운스 즉시 반영:** 설정창에서 `result_filter_debounce_ms` 변경 후 즉시 검색 반응 주기에 반영됩니다.
* **완료 알림음 반영:** `play_sound_on_complete=true`일 때 크롤링 완료 시 시스템 비프음이 재생됩니다.
* **알림 중복 방지:** 동일 규칙+매물은 하루 1회만 알림되며 DB(`article_alert_log`)에 기록됩니다.
* **소멸 판정 범위 제한:** 소멸 매물 처리는 이번 실행 대상 단지/거래유형 범위로 제한됩니다.

### **🧭 동작 변경점 (v15.0)**

* **고급 필터 경로 정리:** 고급 필터는 `수집 탭(CrawlerTab)`의 `🔍 고급필터` 버튼에서 직접 설정합니다.
* **월세 가격 정책 분리:** 월세 필터는 `보증금 범위`와 `월세 금액 범위`를 각각 입력하며, 두 조건을 모두 만족해야 통과합니다.
* **캐시 정확도 개선:** 캐시는 필터 통과 결과가 아니라 원본(raw) 매물 기준으로 저장하고, 조회 시 현재 필터로 재평가합니다.
* **종료 안전성 강화:** 앱 종료 시 크롤링 스레드 종료 타임아웃이 발생하면 DB를 닫지 않고 종료를 중단하며 재시도를 안내합니다.

## **🛠 설치 및 실행 방법**

### **1\. 필수 요구 사항**

* Python 3.9 이상  
* Google Chrome 브라우저 (Selenium fallback용)
* Playwright Chromium 브라우저

### **2\. 라이브러리 설치**

터미널(CMD)에서 아래 명령어를 입력하여 필수 라이브러리를 설치하세요.  
pip install -r requirements.txt

Playwright Chromium 브라우저도 함께 설치해야 합니다.  
playwright install chromium

### **3\. 프로그램 실행**

python -m src.main

또는

python src/main.py

프로그램 시작 시 필수 라이브러리/디렉토리/충돌 마커(preflight)를 자동 점검하며, Playwright Chromium 존재 여부도 함께 확인합니다.

### **4\. 배포 빌드 (PyInstaller)**

기본 배포 프로필은 `naverland-scrapper.spec` 기준 **onefile**입니다.

* 기본(onefile): `pyinstaller naverland-scrapper.spec`
* onedir 강제: PowerShell에서 `$env:NAVERLAND_ONEFILE='0'; pyinstaller naverland-scrapper.spec`
* onefile 복귀: PowerShell에서 `$env:NAVERLAND_ONEFILE='1'; pyinstaller naverland-scrapper.spec`

현재 spec은 Playwright hidden imports와 Chromium 번들 경로를 포함합니다.

빌드 산출물 이름은 모드에 따라 다릅니다.

* onefile: `dist/naverland_onefile.exe`
* onedir: `dist/naverland/`

## **📖 사용 가이드**

1. **수집 모드 선택**  
   * **데이터 수집 탭:** 기존 단지 ID/URL 기반 수집용입니다.
   * **지도 탐색 탭:** 위도/경도/줌 기준으로 주변 지역을 sweep하며 단지를 자동 등록합니다.
2. **단지 등록**  
   * **검색:** '단지 목록' 탭에서 단지명과 단지 ID(네이버 URL의 숫자 부분)를 입력하여 추가합니다.  
   * **일괄 등록:** 'URL등록' 버튼을 눌러 여러 URL을 붙여넣으면 자동으로 파싱하여 등록합니다.  
3. **조건 설정**  
   * 거래 유형(매매/전세/월세)을 선택합니다.  
   * 필요 시 가격 및 면적 필터를 활성화하여 범위를 지정합니다.  
   * 월세는 `보증금 범위`와 `월세 금액 범위`를 각각 설정하며, 두 조건을 모두 만족해야 결과에 포함됩니다.
   * 기본 엔진은 설정 또는 수집 탭에서 `playwright` / `selenium`을 선택할 수 있습니다.
   * 지도 탐색 탭에서는 `APT`, `VL`, 줌, 링 수, 그리드 간격, 지점 대기시간을 조정할 수 있습니다.
   * 지도 탐색(`geo sweep`) 모드는 Playwright 전용이며 Selenium fallback은 지원하지 않습니다.
   * 고급 필터가 필요하면 상단 메뉴 **`🔍 필터 > ⚙️ 고급 결과 필터`** 또는 수집 결과 영역의 **`⚙️ 고급필터`** 버튼으로 진입합니다.
   * 고급 필터 해제는 메뉴 **`🔍 필터 > 🧹 고급 필터 해제`** 또는 결과 영역 **`🧹 필터해제`** 버튼으로 수행합니다.
4. **크롤링 시작**  
   * ▶️ 크롤링 시작 버튼을 누르거나 단축키 Ctrl+R을 입력합니다.  
   * 진행 상황과 예상 남은 시간이 하단에 표시됩니다.  
5. **결과 확인 및 저장**  
   * 수집된 매물은 테이블에 표시되며, 더블 클릭 시 네이버 부동산 페이지로 이동합니다.  
   * 결과 테이블에는 `자산유형`, `기전세금`, `갭금액`, `갭비율`이 기본 표시됩니다.
   * 💾 저장 버튼을 눌러 엑셀(xlsx), CSV, JSON 형식으로 데이터를 내보낼 수 있습니다.

5. **DB 복원 시 주의**  
   * DB 복원 중에는 앱이 유지보수 모드로 전환되어 크롤링/일부 UI 동작이 일시 차단됩니다.
   * 진행 중 크롤링이 안전하게 종료되지 않으면 복원은 중단되며, 종료 후 다시 시도해야 합니다.

## **⌨️ 단축키 목록**

| 기능 | 단축키 | 설명 |
| :---- | :---- | :---- |
| **크롤링 시작** | Ctrl \+ R | 선택된 단지의 매물 수집을 시작합니다. |
| **크롤링 중지** | Ctrl \+ Shift \+ R | 진행 중인 작업을 중지합니다. |
| **Excel 저장** | Ctrl \+ S | 결과를 엑셀 파일로 저장합니다. |
| **CSV 저장** | Ctrl \+ Shift \+ S | 결과를 CSV 파일로 저장합니다. |
| **새로고침** | F5 | 현재 탭의 데이터를 새로고침합니다. |
| **검색** | Ctrl \+ F | 결과 내 검색창으로 포커스를 이동합니다. |
| **설정** | Ctrl \+ , | 설정 창을 엽니다. |
| **테마 변경** | Ctrl \+ T | 다크/라이트 모드를 전환합니다. |
| **트레이 최소화** | Ctrl \+ M | 프로그램을 시스템 트레이로 숨깁니다. |
| **종료** | Ctrl \+ Q | 프로그램을 종료합니다. |

## **📂 파일 구조**

프로그램 실행 시 자동으로 생성되는 디렉토리입니다.

* data/: 데이터베이스(complexes.db), 설정 파일(settings.json), 히스토리 등이 저장됩니다.  
* logs/: 날짜별 실행 로그 파일이 저장되어 오류 추적에 사용됩니다.

## **📦 빌드(.spec) 점검 메모**

* `naverland-scrapper.spec`는 `Playwright` hidden import, runtime hook, Chromium 번들 데이터 경로를 포함하도록 확장되었습니다.
* onefile/onedir 모두 Playwright Chromium 번들을 같이 싣는 구성을 전제로 합니다.

## **⚠️ 주의사항**

* 이 프로그램은 개인적인 학습 및 편의를 위해 제작되었습니다.  
* 과도한 속도로 크롤링을 시도할 경우 네이버 부동산의 접속이 일시 차단될 수 있으므로, '보통' 또는 '느림' 속도 사용을 권장합니다.  
* 수집된 데이터의 상업적 이용에 대한 책임은 사용자에게 있습니다.


## v15.0.1 Runtime Notes (2026-03-06)

- `playwright_response_drain_timeout_ms` 설정을 추가했습니다. 기본값은 `3000`이며, Settings에서 조정할 수 있습니다.
- `complex` 모드 캐시 컨텍스트는 엔진 공통으로 `mode=complex`, `asset_type=APT`, `marker_id=""`로 정규화됩니다.
- 과거 complex 캐시 키(예: marker 기반 키)는 읽기 호환만 유지하며, 적중 시 정규 키로 재저장됩니다.
- `geo_sweep` 모드는 계속 Playwright 전용이며 Selenium fallback은 지원하지 않습니다.
- Geo 실행 중 운영 통계(`geo_discovered_count`, `geo_dedup_count`, `response_drain_wait_count`, `response_drain_timeout_count`)를 로그/상태바에서 확인할 수 있습니다.

## v15.0.2 Consistency Notes (2026-03-06)

- `naverland-scrapper.spec`를 점검한 결과, 이번 기능 반영 범위에서는 추가 hidden import나 runtime hook 변경 없이 현재 설정으로 충분합니다.
- 빌드 정책은 기존과 동일합니다.
  - 기본: `pyinstaller naverland-scrapper.spec` (onefile)
  - 선택: `NAVERLAND_ONEFILE=0`로 onedir
- 문서 정합 기준을 다음으로 고정합니다.
  - Selenium fallback은 `complex` 모드에서만 지원
  - `geo_sweep`는 Playwright 전용
  - `complex` 캐시 컨텍스트 정규화(`mode=complex`, `asset_type=APT`, `marker_id=""`)
  - 레거시 complex 캐시 키는 읽기 호환만 유지

## v15.0.3 Reliability Notes (2026-03-07)

- `CrawlerThread`가 실행 단위 pair 큐를 추적하고, Playwright 실패 시 Selenium fallback은 미처리 pair만 이어서 수행합니다.
- 수집 결과 push 경로에 item dedupe를 추가해 `(complex_id, article_id, trade_type)` 기준 중복 반영을 차단합니다(`article_id` 없으면 dedupe skip).
- Playwright negative cache는 `response_seen=True` + `drain_timed_out=False`일 때만 저장하며, 캐시 payload에 `reason=confirmed_empty` 메타를 포함합니다.
- Playwright 경로에 메모리 워치독(500MB)을 추가해 임계치 초과 시 browser/context/page pool을 recycle하고 통계(`playwright_recycle_count`, `playwright_last_recycle_reason`)를 노출합니다.
- DB `complexes`는 `(asset_type, complex_id)` 복합 unique로 자동 마이그레이션되며, legacy row는 `asset_type='APT'`로 승격됩니다.
- DB 탭 삭제 UX에 확인 모달과 `관련 이력까지 삭제` 옵션(기본 off)을 추가했습니다.
- CI는 push 시 테스트 미실행 정책을 유지하고, `pull_request`, `workflow_dispatch`, nightly `schedule(UTC 18:00)`에서 테스트를 실행합니다.
- `naverland-scrapper.spec`은 이번 반영 범위에서 추가 수정 없이 현재 설정(Playwright hidden import/runtime hook/Chromium bundle)으로 유지합니다.

## v15.0.4 Crawling Audit Notes (2026-03-07)

- 크롤링/스크래핑 구현 리스크 감사 문서를 추가했습니다: `crawling_scraping_risk_audit_2026-03-07.md`.
- 핵심 점검 결론:
  - Selenium 경로의 0건 negative cache 저장 조건 강화 필요
  - 차단 감지 누적 기반 쿨다운(circuit breaker) 필요
  - Playwright 응답 매칭/상세 파싱 성공률 관측성 강화 필요
- `.spec` 점검 결과:
  - `naverland-scrapper.spec`는 현재 코드 구조(분할 리팩토링 포함)에서도 추가 수정 없이 유지 가능합니다.
