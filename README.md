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
* **📦 PyInstaller 경량/번들 선택:** 기본 배포는 Chromium 번들을 포함하며, 필요 시 환경변수로 slim 빌드로 전환할 수 있습니다.

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
* **대시보드 집계 캐시:** 대시보드 통계와 소멸 매물 집계를 캐시해 반복 새로고침 비용을 줄였습니다.
* **카드뷰 렌더 최적화:** 카드 스타일 캐시와 배치 렌더링으로 대량 카드 표시 시 체감 속도를 개선했습니다.
* **즉시 탭 초기화 유지:** 히스토리/통계/즐겨찾기/DB 탭은 현재 lazy loading 없이 시작 시 즉시 로드됩니다.

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

기본 설정(`crawl_engine=playwright`)을 유지할 경우 소스 실행에는 로컬 Playwright Chromium이 필요하고, frozen 빌드는 기본 번들 Chromium으로 바로 실행됩니다.
`crawl_engine=selenium`으로 전환한 환경에서는 Playwright browser 미설치가 warning으로만 처리됩니다.

### **3\. 프로그램 실행**

python -m src.main

또는

python src/main.py

프로그램 시작 시 필수 라이브러리/디렉토리/충돌 마커(preflight)를 자동 점검합니다.
추가로 `data/settings.json` 기준의 `effective crawl_engine`를 계산해, `playwright`를 실제로 사용할 런타임에서만 Playwright Chromium 존재 여부를 시작 차단 조건으로 확인합니다.

### **4\. 배포 빌드 (PyInstaller)**

기본 배포 프로필은 `naverland-scrapper.spec` 기준 **onedir(Chromium 번들 포함)**입니다.

* 기본(onedir, Chromium 번들 포함): `pyinstaller naverland-scrapper.spec`
* onefile 강제: PowerShell에서 `$env:NAVERLAND_ONEFILE='1'; pyinstaller naverland-scrapper.spec`
* onedir 명시: PowerShell에서 `$env:NAVERLAND_ONEFILE='0'; pyinstaller naverland-scrapper.spec`
* slim(현재 프로필 유지): PowerShell에서 `$env:NAVERLAND_BUNDLE_CHROMIUM='0'; pyinstaller naverland-scrapper.spec`
* 콘솔 디버깅 빌드(현재 프로필 유지): PowerShell에서 `$env:NAVERLAND_CONSOLE='1'; pyinstaller naverland-scrapper.spec`

현재 spec은 Playwright hidden imports를 포함하며, 기본 빌드에 Chromium 번들을 포함합니다.  
`NAVERLAND_CONSOLE=1`을 주면 GUI 빌드에서도 콘솔 창을 띄워 시작 실패 로그를 직접 확인할 수 있습니다.

빌드 산출물 이름은 모드에 따라 다릅니다.

* onedir(Chromium 번들 포함, 기본): `dist/naverland/`
* onedir(slim): `dist/naverland_slim/`
* onefile(Chromium 번들 포함): `dist/naverland_onefile.exe`
* onefile(slim): `dist/naverland_onefile_slim.exe`

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

* `naverland-scrapper.spec`는 `Playwright` hidden import/runtime hook을 포함합니다.
* 기본 빌드는 `onedir + Chromium 번들 포함` 프로필이며, 필요 시 `NAVERLAND_ONEFILE=1`로 onefile, `NAVERLAND_BUNDLE_CHROMIUM=0`으로 slim 빌드를 생성할 수 있습니다.
* 카드뷰 위젯은 `src/ui/widgets/cards.py`, 대시보드 위젯은 `src/ui/widgets/dashboard.py`로 분리되어 있으며 이번 정합성 패스에서도 추가 hidden import 수정은 필요하지 않았습니다.

## **⚠️ 주의사항**

* 이 프로그램은 개인적인 학습 및 편의를 위해 제작되었습니다.  
* 과도한 속도로 크롤링을 시도할 경우 네이버 부동산의 접속이 일시 차단될 수 있으므로, '보통' 또는 '느림' 속도 사용을 권장합니다.  
* 수집된 데이터의 상업적 이용에 대한 책임은 사용자에게 있습니다.


## v15.0.14 Docs/Spec/Gitignore Consistency Pass (2026-03-17)

- 코드베이스 재점검 기준:
  - 기본 PyInstaller 프로필은 `onedir + Chromium bundle`입니다.
  - `onefile`은 `NAVERLAND_ONEFILE=1`에서만 활성화됩니다.
  - 카드 뷰 위젯은 `src/ui/widgets/cards.py`, 대시보드 위젯은 `src/ui/widgets/dashboard.py`에 분리되어 있습니다.
  - 비핵심 탭 lazy loading은 제거되었고 관련 설정 키는 레거시 호환용으로만 남아 있습니다.
- 성능 정합 메모:
  - 대시보드는 통계/소멸 집계 캐시와 지연 차트 캔버스 초기화를 사용합니다.
  - 결과 렌더링은 검색 캐시 사전 생성, 로그 block count 제한, 카드 스타일 캐시를 사용합니다.
- `.gitignore` 점검 결과:
  - 기존 build/log/data/Playwright 산출물 규칙은 유지하고, 개발 도구 캐시(`.mypy_cache/`, `.ruff_cache/`, `.nox/`, `node_modules/`, `coverage.xml`)를 예방적으로 추가했습니다.


## v15.0.1 Runtime Notes (2026-03-06)

- `playwright_response_drain_timeout_ms` 설정을 추가했습니다. 기본값은 `3000`이며, Settings에서 조정할 수 있습니다.
- `complex` 모드 캐시 컨텍스트는 엔진 공통으로 `mode=complex`, `asset_type=APT`, `marker_id=""`로 정규화됩니다.
- 과거 complex 캐시 키(예: marker 기반 키)는 읽기 호환만 유지하며, 적중 시 정규 키로 재저장됩니다.
- `geo_sweep` 모드는 계속 Playwright 전용이며 Selenium fallback은 지원하지 않습니다.
- Geo 실행 중 운영 통계(`geo_discovered_count`, `geo_dedup_count`, `response_drain_wait_count`, `response_drain_timeout_count`)를 로그/상태바에서 확인할 수 있습니다.

## v15.0.2 Consistency Notes (2026-03-06)

- `naverland-scrapper.spec`를 점검한 결과, 이번 기능 반영 범위에서는 추가 hidden import나 runtime hook 변경 없이 현재 설정으로 충분합니다.
- 빌드 정책은 기존과 동일합니다.
  - 기본: `pyinstaller naverland-scrapper.spec` (onedir)
  - 선택: `NAVERLAND_ONEFILE=1`로 onefile
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

## v15.0.5 Docs/Packaging Recheck (2026-03-07)

- `.spec` 재점검 결과: `src/core/*_parts`, `src/ui/*_parts` 분할 리팩토링 이후에도 `naverland-scrapper.spec`는 현재 hidden import/runtime hook 구성으로 충분하며 추가 수정이 필요하지 않습니다.
- 감사 문서 상태 정합화: `crawling_scraping_risk_audit_2026-03-07.md`를 저장소 기준 문서로 유지하고, 문서 내부에 정합성 추적 메모를 추가했습니다.
- 문서 정합성 동기화: `README.md`, `claude.md`, `gemini.md`, `update_history.md`의 fallback 정책(`complex`만 Selenium fallback), `geo_sweep` 정책(Playwright 전용), 분할 리팩토링 경로 표기를 동일 기준으로 맞췄습니다.
- `.gitignore` 재확인 결과: 현재 빌드/로그/백업/Playwright 산출물 무시 규칙으로 충분하며 추가 패턴은 필요하지 않습니다.

## v15.0.6 UI/Typing/Packaging Stabilization (2026-03-08)

- UI 사용성 정합화:
  - 검색 조건 좌/우 패널 + 내부 조건 섹션을 스플리터로 조절하고, 분할 비율을 설정에 저장/복원합니다.
  - 입력 위젯 전역 wheel-guard를 도입해 `QSpinBox/QDoubleSpinBox/QComboBox`에서 휠 오입력 변경을 방지합니다(콤보는 팝업 열린 경우만 휠 허용).
  - 라이트/다크 테마별 드롭다운 팝업 가독성을 보정했습니다(`QComboBox QAbstractItemView` 상태별 색상 분리).
- 타입 안정화:
  - `npx pyright src` 기준 `0 errors`를 달성하도록 `src/` 전역 타입 오류를 정리했습니다.
- 패키징 점검:
  - `.spec`에서 Matplotlib Qt backend hidden import를 `backend_qtagg` 기준으로 정리했습니다.
  - `NAVERLAND_CONSOLE=1` 빌드 스위치를 추가해 GUI 실행 실패 시 콘솔 로그 확인 경로를 열었습니다.
  - Chromium 번들 탐지 실패(`NAVERLAND_BUNDLE_CHROMIUM=1`)가 조용히 묻히지 않도록 spec 단계 경고 메시지를 출력합니다.

## v15.0.7 Reliability/Risk Plan Applied (2026-03-11)

- F-01: Selenium parse metadata(`response_seen`, `parse_success`, `empty_confirmed`, `blocked_detected`)를 표준화하고, `confirmed_empty` 조건에서만 negative cache를 기록합니다.
- F-02: Geo 탭도 일반 탭과 동일하게 `retry_on_error=False`면 `max_retry_count=0`을 강제합니다.
- F-03: `mark_disappeared_articles_for_targets`를 대량 타깃에서도 안전한 chunk update 방식으로 변경했습니다.
- F-04: `add_complex`에 write lock + lock retry(`database is locked`) + rollback 경로를 추가했습니다.
- F-05: 차단 대응은 하이브리드 회로차단기(페어 2회/90초 cooldown, 전역 5회 중단)로 고정 적용했습니다.
- F-06: stats용 complex 목록은 충돌 CID에만 `asset:cid` 복합키를 사용하고, UI는 plain/compound 키를 모두 해석합니다.
- F-07: Geo 모드에서 `complex_trade_types`가 비어 있으면 crawl history 저장을 스킵합니다.
- F-08: `playwright_parts/complex_mode.py`, `playwright_parts/geo_mode.py`의 깨진 로그/예외 문자열을 정리했습니다.
- F-09: stats payload에 `response_seen_count`, `parse_success_count`, `parse_fail_count`, `detail_success_count`, `detail_fail_count`, `blocked_page_count`를 추가했습니다.
- Verification: `pytest -q` 전체 실행 기준 `112 passed`.

## v15.0.9 Functional Consistency Notes (2026-03-14)

- 알림 스코프를 `asset_type` 기준으로 분리했습니다.
  - `alert_settings.asset_type`, `article_alert_log.asset_type`를 추가하고 legacy/blank 값은 `ALL`로 backfill 합니다.
  - 알림 조회는 `requested asset_type + ALL` 규칙만 반환하며, 동일 `alert_id/article_id/complex_id/notified_on`이라도 자산유형이 다르면 별도 dedupe 합니다.
  - 알림 설정 UI는 `단지명 (APT:cid)` / `단지명 (VL:cid)`를 표시하고, `공통 적용(APT/VL)` 체크 시 `ALL` 범위 규칙을 저장합니다.
- complex 모드 작업 목록은 `cid` 기준 dedupe로 고정했습니다.
  - 수동 추가, DB/그룹/최근 검색/URL/예약 실행이 모두 같은 dedupe 경로를 사용합니다.
  - 동일 `cid`가 다시 들어오면 첫 이름을 유지하고 중복은 스킵 로그/상태 메시지로 안내합니다.
  - `start_crawling()` 직전에도 최종 `target_list`를 다시 정규화합니다.
- item dedupe와 집계 수치를 일치시켰습니다.
  - `_push_item()`은 실제 push 성공 여부를 `bool`로 반환합니다.
  - raw item, Selenium cache hit, DOM parse 경로 모두 실제 push 성공 건만 `matched_count`와 완료 count에 반영합니다.
- crawl history 메타데이터와 stats UX를 보강했습니다.
  - `complex` 모드 이력도 `asset_type='APT'`를 명시 저장합니다.
  - 히스토리 탭은 `단지명 / 단지ID / 자산 / 엔진 / 모드 / 거래유형 / 수집건수 / 수집시각`을 표시합니다.
  - 통계 차트는 단일 `(trade_type, pyeong)` 시리즈일 때만 렌더하고, 다중 시리즈면 `차트를 보려면 거래유형과 평형을 하나로 좁혀주세요.` 메시지를 보여줍니다.
- `.spec` 재점검 결과:
  - `naverland-scrapper.spec`는 이번 변경 범위에서도 추가 hidden import/runtime hook 수정이 필요하지 않았습니다.
- `.gitignore` 재점검 결과:
  - 현재 build/log/data/Playwright 산출물 무시 규칙으로 충분하며 이번 범위에서 추가 수정은 필요하지 않았습니다.

## v15.0.10 Functional Follow-up (2026-03-15)

- `article_history`, `article_favorites`는 이제 `(asset_type, article_id, complex_id)` 기준으로 분리 관리됩니다.
  - 앱 시작 시 자산 스코프 마이그레이션이 필요하면 사전 DB 백업을 만든 뒤 스키마를 재구성합니다.
  - legacy blank `asset_type` 값은 `APT`로 정규화합니다.
- disappeared / purge 정합성을 자산 스코프 기준으로 맞췄습니다.
  - disappeared 대상 계산은 내부적으로 `(asset_type, complex_id, trade_type)` triple만 사용합니다.
  - purge/delete는 `article_history`, `crawl_history`, `price_snapshots`, `alert_settings`, `article_favorites`, `article_alert_log`를 자산 스코프 predicate로 정리합니다.
- 저장 메뉴를 `화면 기준 저장`과 `원본 저장`으로 분리했습니다.
  - 화면 기준 저장은 현재 검색어, 고급 필터, compact duplicate 상태, 현재 정렬 순서를 반영한 가시 결과만 저장합니다.
  - 원본 저장은 기존처럼 `collected_data` 전체를 그대로 저장합니다.
- 예약 실행은 `complex`와 `geo_sweep`를 모두 지원합니다.
  - `complex`는 기존 그룹 기반 예약을 유지합니다.
  - `geo_sweep`는 위도/경도 예약 실행을 지원하고, zoom/rings/step/dwell/asset_types는 저장된 geo 기본값을 사용합니다.
- Geo 운영 통계는 실행 중에도 실시간으로 반영됩니다.
  - `geo_discovered_count`, `geo_dedup_count`가 marker 처리 시점마다 상태바/로그에 즉시 반영됩니다.
- 즐겨찾기 동기화는 자산 스코프 기준으로 통일되었습니다.
  - 카드뷰, 즐겨찾기 탭, 최근 본 매물, 결과 재렌더가 모두 `(asset_type, article_id, complex_id)` 키를 공유합니다.
- `.spec` / `.gitignore` 재점검:
  - `naverland-scrapper.spec`는 이번 범위에서도 추가 hidden import/runtime hook 수정이 필요하지 않았습니다.
  - `.gitignore`는 현재 build/log/data/backup/Playwright 산출물 무시 규칙으로 충분해 추가 수정이 없었습니다.
- 검증:
  - `python -m pytest -q` => `137 passed`

## v15.0.11 Typing/Encoding Consistency Pass (2026-03-16)

- Typing baseline:
  - workspace 기준 `pyrightconfig.json`을 추가해 검사 범위를 `app_entry.py + src + tests`로 고정했습니다.
  - 현재 기준 검증 명령은 `npx pyright`이며 결과는 `0 errors`입니다.
  - Pylance/Pyright 오탐이 나던 믹스인/동적 속성/테스트 더블 타입을 정리했습니다.
- Encoding baseline:
  - `.editorconfig`와 `.vscode/settings.json`을 추가해 UTF-8 저장과 workspace type checking 기준을 고정했습니다.
  - Python/문서 파일에 남아 있던 UTF-8 BOM을 제거했고, 깨진 주석/문자열을 정리했습니다.
- `.spec` / `.gitignore` review:
  - `naverland-scrapper.spec`는 이번 패스에서도 추가 hidden import/runtime hook/data bundle 수정이 필요하지 않았습니다.
  - `.gitignore`는 기존 산출물 무시 규칙은 유지하고, 새로 추가한 `pyrightconfig.json`과 `.vscode/settings.json`만 추적 가능하도록 예외를 보강했습니다.
- Validation:
  - `npx pyright` => `0 errors`
  - `python -m pytest -q` => `137 passed`

## v15.0.12 Runtime Safety / Packaging Recheck (2026-03-16)

- Preflight / runtime safety:
  - `preflight`는 `data/settings.json`을 직접 읽어 `effective crawl_engine`를 계산합니다.
  - Playwright Chromium 미설치는 `effective crawl_engine=playwright`일 때만 시작 차단으로 처리하고, `selenium`일 때는 warning-only로 처리합니다.
  - `geo_incomplete_safety_mode` 기본값은 `true`이며, geo incomplete 런에서는 자동 단지 등록 / crawl history 저장 / disappeared marking을 보수적으로 skip합니다.
- Geo / history contract:
  - `crawl_history`에 `run_status`(`success|partial|failed|incomplete`) 컬럼이 추가되었고, History 탭은 `mode` 다음에 `status` 컬럼을 표시합니다.
  - geo marker 정규화는 `complex_id`와 `marker_id`를 분리해 저장합니다.
  - 성공적으로 검증된 pair가 0개인 런에서는 disappeared marking을 수행하지 않습니다.
- `.spec` / `.gitignore` review:
  - `naverland-scrapper.spec`는 hidden import/runtime hook/data bundle 규칙 변경 없이 유지 가능합니다.
  - slim 배포에서는 `playwright` 사용 시 로컬 Chromium 또는 번들 포함 기본 빌드가 필요합니다.
  - `.gitignore`는 현재 build/log/data/backup/Playwright 산출물 기준으로 추가 수정이 필요하지 않았습니다.
- Validation:
  - `pytest -q` => `149 passed`
