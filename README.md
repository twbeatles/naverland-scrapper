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
* **📱 모바일 상세 선택 수집:** 모바일 상세 페이지 워커 풀은 가격/면적 필터를 통과한 매물에 우선 적용되어 중개사/전화/기전세금/전세 이력을 확장 수집합니다.
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

### **v15.0 Live-Site Sample Refresh (2026-05-11)**

* **🌐 현재 실사이트 샘플 갱신:** 기본 live smoke 샘플을 현재 매물 목록이 확인되는 `complex_id=3833`, `article_id=2625154515`로 갱신했습니다.
* **🔎 Smoke article 검증 강화:** complex probe는 `/api/articles/complex/{id}`의 HTTP 상태뿐 아니라 `article_count`와 `sample_article`도 출력하며, 0건 샘플은 실패로 분리합니다.
* **🔗 article-only 역조회 보강:** `fin.land` 상세 페이지의 현재 `complexNumber` payload와 browser response URL을 해석하고, live smoke의 article lookup은 Playwright async loop 밖에서 실행해 browser fallback 경로를 실제로 검증합니다. packaged 환경의 article browser fallback은 설치된 Chrome을 우선 사용하고, 없을 때 Playwright Chromium으로 돌아갑니다.
* **⚡ 단지명 조회 429 대응:** direct API가 `429`를 반환하면 browser fallback으로 단지명을 재확인하고, 성공 시 `(asset_type, complex_id)` 캐시에 저장합니다. browser fallback도 실패할 때만 `단지_{id}`를 반환합니다.
* **🧪 CI subset 보강:** GitHub Actions core pytest subset에 `test_app_entry`, `test_live_smoke`, `test_analysis`, `test_rebind_methods`를 추가해 이번 live smoke/분석/mixin 변경을 원격 검증에 포함했습니다.
* **✅ 2026-05-11 smoke 확인 결과:** headless 기준 `home/complex/detail/geo-marker/article-lookup` probe가 모두 성공했고, JSON 로그 저장까지 확인했습니다.

### **v15.0 Functional Risk Closure (2026-05-15)**

* **⚡ 단지명 429 cooldown 보정:** direct API cooldown 중에도 미캐시 단지는 browser fallback을 시도하며, fallback 성공명은 `(asset_type, complex_id)` 캐시에 저장합니다.
* **🚦 Live Smoke seed/effective 분리:** 기본 `--smoke-article-id`는 고정 검증 대상이 아니라 seed입니다. 기본 seed를 쓰면 complex probe의 현재 `sample_article`이 effective article ID가 될 수 있고, JSON 로그에는 requested/effective article ID, `runtime_source`, 실행 파일 경로, 데이터 경로가 함께 남습니다.
* **🔬 상세 필드 smoke 옵션:** `--live-smoke-detail-fields`를 추가해 모바일 상세 파서의 `detail_parse_state`, 핵심 필드 확보 수, 누락 필드 수를 실사이트 smoke에 포함할 수 있습니다.
* **🧭 Geo 자산 선택 안전장치:** 지도 탐색과 예약 Geo에서 APT/VL을 모두 해제한 상태는 전체 수집으로 확장하지 않고 경고 후 차단합니다.
* **🏷️ 수동 단지 자산 선택:** 직접 추가 입력 줄에서 `APT/VL`을 선택할 수 있으며 기본값은 기존 호환성을 위해 `APT`입니다.
* **📦 릴리스 검증 게이트:** 배포 전 검증은 source checks, PyInstaller onedir build, frozen preflight, frozen live-smoke 순서로 확인합니다.

### **v15.0 Functional Audit Hardening (2026-06-04)**

* **🧭 fallback 최종화 보정:** Playwright 부분 성공 후 Selenium fallback으로 넘어가도 이미 성공한 pair를 history, 완료 signal, 소멸 매물 최종화에 합산합니다.
* **🛡️ DB write rollback 보강:** 단지/그룹 삭제와 memo/group write 실패 시 pooled SQLite connection에 partial transaction이 남지 않도록 rollback을 보장합니다.
* **🔐 Export formula 방어:** CSV/XLSX 내보내기는 외부 수집 문자열의 spreadsheet formula prefix를 escape하고, 내부 계산 컬럼 표시 형식은 유지합니다.
* **🪟 URL batch race 방지:** URL 일괄 등록 worker는 generation guard로 오래된 progress/finished signal이 새 결과 테이블을 덮어쓰지 못하게 합니다.
* **⏱️ Playwright timeout 분리:** `playwright_navigation_timeout_ms` 설정(default `15000`)을 추가해 warmup/entry/detail page navigation에 명시 timeout을 적용합니다.
* **🧭 Geo 빈 자산 정책 통일:** APT/VL 미선택은 Settings/Geo/schedule 경로에서 전체 선택으로 확장하지 않고 경고 또는 실행 차단으로 처리합니다.
* **🧪 CodeGraph 산출물 ignore:** 로컬 `.codegraph/` 인덱스 디렉터리는 개발자 산출물로 무시합니다.

### **v15.0 Typing / Encoding / Smoke Consistency Pass (2026-03-25)**

* **🧪 Repo-wide Pyright 정리:** workspace 기준 `pyright` 오류를 다시 정리하고, 새 `live_smoke` CLI와 테스트 더블 monkeypatch까지 타입 시그니처를 맞췄습니다.
* **🔤 인코딩 가드 강화:** root `.md/.spec/.gitignore/.editorconfig/.vscode/settings.json/.github/workflows/ci.yml`까지 UTF-8/BOM/mojibake 스캔 대상으로 고정했습니다.
* **🧭 Pylance 설정 고정:** `.vscode/settings.json`에 `include/exclude/extraPaths/encoding` 기준을 명시해 로컬 Pylance가 repo 기준과 같은 범위로 진단하도록 맞췄습니다.
* **🚦 Live Smoke CLI 추가:** `python app_entry.py --live-smoke [--smoke-headless] [--smoke-url ...] [--smoke-complex-id ...] [--smoke-article-id ...] [--live-smoke-detail-fields] [--smoke-json-log smoke.json]`로 GUI 없이 Playwright 실제 접근, article-only 역조회, Geo marker 전환, 선택형 상세 필드 파싱 경로를 점검할 수 있습니다.
* **🌐 2026-03-25 smoke 확인 결과:** headless 기준 `fin.land` 200, `new.land` 200, `m.land`는 `fin.land` map 경로로 redirect 되는 현재 동작을 확인했습니다.

### **v15.0 Live-Site Reliability Patch (2026-04-10)**

* **🧩 상세 파서 실사이트 복구:** 모바일 상세 수집은 `front-api` 응답의 `brokerageName`, `brokerName`, `phone.{brokerage,mobile}`, `prevJeonse*`를 우선 해석하고, source 선택 기준도 body 길이 대신 `실제 필드 확보 점수`로 전환했습니다.
* **⚡ 단지명 조회 fast-fallback:** direct API가 `429`를 반환하면 프로세스 단위 5분 cooldown을 걸고 browser fallback을 시도합니다. fallback도 실패할 때만 `단지_{id}`를 반환하며, 성공 조회명은 메모리 캐시에 재사용합니다.
* **🔎 Live Smoke 확장:** 기본 smoke가 `home + complex + detail + article-only 역조회 + geo marker switch/API` probe를 수행하며, `--smoke-complex-id`, `--smoke-article-id`, `--smoke-json-log`로 운영 점검 값을 조정할 수 있습니다.
* **🪟 URL family 정합화:** URL 배치 등록과 Selenium complex fallback은 helper 기반 URL 생성으로 통일했고, 사용자 안내 문구는 `URL family는 시점에 따라 달라질 수 있음` 기준으로 정리했습니다.
* **🌐 2026-04-10 smoke 확인 결과:** headless 기준 `home/complex/detail` probe가 모두 성공했고, detail probe는 `front-api/v1/article/agent` 응답까지 확인했습니다.

### **v15.0 Schedule / Asset Scope / CI Reliability Patch (2026-04-11)**

* **⏰ 예약 실행 slot 소비 조건 보강:** `complex`와 `geo_sweep` 예약 실행은 이제 실제 `start_crawling()` 성공 시에만 `last_run_slot`을 기록합니다. validation early-return이나 시작 실패는 같은 window 안 재시도를 막지 않습니다.
* **🧾 예약 실패 시 수동 작업 목록 복원:** `complex` 예약 실행은 기존 수동 task list를 snapshot한 뒤 예약 대상을 적재하며, 예약 시작 실패 또는 실행 가능한 APT 대상이 없을 때는 기존 목록과 선택 상태를 즉시 복원합니다.
* **🏷️ 런타임 dedupe 자산 스코프 정합화:** `_item_dedupe_key()`는 이제 `(asset_type, complex_id, article_id, trade_type)` 기준을 사용하고, legacy blank `asset_type`은 `APT`로 정규화합니다.
* **🧪 CI 정책 조정:** GitHub Actions는 `compileall + 핵심 pytest subset + pyright + preflight`를 실행합니다. 전체 pytest는 로컬 검증 기준으로 유지합니다.
* **📦 2026-04-11 .spec 재점검:** 이번 변경은 runtime/test/documentation 레벨에 머물러 `naverland-scrapper.spec`의 hidden import/runtime hook/data bundle 수정은 추가로 필요하지 않았습니다.

### **v15.0 Asset Scope / Docs / Build Consistency Patch (2026-04-16)**

* **🏘️ complex 타깃 자산 보존:** URL 일괄 등록, DB/그룹/최근 검색 복원, 수동 task 목록이 이제 `APT/VL` 자산유형을 끝까지 유지합니다. 같은 숫자 `cid`라도 `APT`와 `VL`은 별도 task로 함께 다룰 수 있습니다.
* **🔗 VL houses URL 정합화:** `new.land.naver.com/houses/{id}` 계열 URL은 `VL` 스코프를 유지한 채 단지명 조회, task 등록, 단지 페이지 열기 경로로 연결됩니다.
* **🎭 엔진 제한 명확화:** Playwright `complex` 모드는 `APT`와 `VL`을 모두 처리하고, Selenium `complex` 모드는 현재 `APT`만 지원합니다. `VL` 대상은 Selenium 직접 시작과 fallback 모두 차단/건너뜀 처리됩니다.
* **📊 대시보드 범위 정합화:** 소멸 매물 카드는 DB 전체가 아니라 현재 화면에 잡힌 `(asset_type, complex_id, trade_type)` 범위만 집계합니다.
* **💸 월세 이력 기준 보정:** 월세 이력/가격변동/알림 비교는 `price_text`에 `보증금/월세`를 그대로 저장하면서, 비교 기준값은 `월세 금액`을 우선 사용합니다.
* **⭐ 즐겨찾기 UI 정리:** 비어 있던 `링크` 컬럼을 제거해 실제 동작하는 열만 남겼습니다.
* **🧪 CI 단순화:** GitHub Actions는 이제 `compileall + 핵심 pytest subset + pyright + preflight`를 실행합니다.
* **📦 2026-04-16 .spec 재점검:** 이번 패스도 runtime/UI/test/doc 레벨 변경에 머물러 `naverland-scrapper.spec`의 hidden import/runtime hook/data bundle 수정은 추가로 필요하지 않았습니다.

### **v15.0 Implementation Gap Closure (2026-04-27)**

* **⏰ 예약 complex 자산 정책 정합화:** Playwright 예약 complex는 그룹의 `APT/VL`을 모두 task에 등록하고, Selenium complex는 기존 제약대로 `VL`을 제외합니다.
* **🧾 예약 복원 자산 보존:** 예약 시작 실패 또는 실행 가능 대상 없음으로 수동 task를 복원할 때 `(name, cid, asset_type)`을 함께 유지합니다.
* **🔗 article-only URL 역조회:** URL 일괄 등록은 `fin.land`/`m.land` article-only URL도 백그라운드 worker에서 단지 ID와 자산유형으로 역조회한 뒤 등록 후보로 표시합니다. 역조회 실패 row는 미선택 상태로 남습니다.
* **💸 월세 UI 가격 기준 통일:** 결과 정렬, 고급 필터, 카드 필터, 대시보드 가격 분포가 월세 매물에서 `월세 금액`을 우선 가격값으로 사용합니다.
* **🧪 회귀 테스트 보강:** Selenium DOM 월세 fallback, article URL 역조회, 예약 APT/VL 정책, 월세 UI metric, mixin rebind meta-test를 추가했습니다.
* **🧪 CI 정책 유지:** GitHub Actions는 `compileall + 핵심 pytest subset + pyright + preflight`를 실행하며, 전체 pytest는 로컬 검증 기준으로 유지합니다.
* **📦 2026-04-27 .spec/.gitignore 재점검:** 이번 변경도 Python/runtime/test/doc 레벨에 머물러 PyInstaller hidden import/runtime hook/data bundle 및 ignore 패턴 추가는 필요하지 않았습니다.

### **v15.0 Functional Implementation Hardening (2026-05-03)**

* **자산 스코프 보강:** 레거시 article history 메서드도 선택적 `asset_type`을 받아 같은 `complex_id`의 `APT/VL` 통계, 정리, 소멸 처리가 섞이지 않습니다.
* **필터 제외 정책 고정:** 가격/면적 필터 밖 매물은 결과뿐 아니라 히스토리, 알림 로그, 가격변경 카운트에서도 제외하고 `filtered_out`만 증가시킵니다.
* **가격 스냅샷 최신값 정책:** 같은 날짜/자산/단지/거래유형/평형/가격지표 조건은 중복 insert 대신 최신 수집값으로 갱신하며, 과거 중복 row도 조회 시 최신 row만 대표로 사용합니다.
* **예약 설정 hydration 보호:** 초기 로드와 그룹 refresh 중에는 설정 저장을 막고, 저장된 그룹이 사라져도 임의로 다른 그룹 ID로 대체하지 않습니다.
* **실사이트 관측 보강:** article-only 역조회는 `urllib` 실패 후 browser fallback을 시도할 수 있고, live smoke는 geo marker switch/API 관측과 JSON 로그 저장 옵션을 제공합니다.
* **상세 메타 보존:** `detail_parse_state`, `missing_field_count`, `detail_source`를 UI payload와 export 선택 컬럼으로 유지합니다.
* **문서/CI/패키징 재점검:** GitHub Actions는 core pytest subset을 포함하며, `.gitattributes`로 UTF-8 텍스트 정책을 명시했습니다. `naverland-scrapper.spec`와 `.gitignore`는 추가 기능 변경 없이 현재 규칙으로 충분합니다.

### **v15.0 Implementation Review Closure (2026-05-04)**

* **Geo marker 전환 관측성 노출:** marker switch attempt/success/fail/last method 통계를 runtime stats, stats payload, Geo 상태 메시지, 완료 요약 로그에서 확인할 수 있습니다.
* **기본 CSV/Excel export 정책 정리:** template이 없을 때도 legacy 최소 컬럼 대신 `ExcelTemplate.DEFAULT_COLUMNS`의 true/false 기준을 사용합니다. `자산유형`, 가격/면적, 평당가, 갭 분석 필드는 기본 포함되고 상세 메타/ID/가격변동은 템플릿에서 선택할 수 있습니다.
* **confirmed-empty cache 보정:** Playwright complex 수집에서 앞선 plan의 parse 실패 후 다음 plan이 정상 empty capture를 확인하면 `confirmed_empty` negative cache로 저장할 수 있습니다.
* **예약/이력/runtime 정합성:** 이미 소비된 schedule slot은 실제 실행으로 표시하지 않고, article history runtime cache는 `(asset_type, complex_id, trade_type)` 기준으로 분리합니다.
* **article-only batch fallback 재사용:** URL 일괄 등록 worker는 `urllib` 실패 후 사용하는 browser fallback session을 batch 단위로 재사용하고 종료 시 close합니다.
* **CI/문서/패키징 재점검:** GitHub Actions core subset에 export/detail/gap/cache/mojibake/preflight 테스트를 추가했습니다. `naverland-scrapper.spec`와 `.gitignore`는 추가 기능 변경 없이 현재 규칙으로 충분하며, 임시 구현 점검 문서는 저장소 문서로 유지하지 않고 삭제 상태를 반영합니다.

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
* **대시보드 집계 캐시:** 대시보드 통계와 현재 결과 범위의 소멸 매물 집계를 캐시해 반복 새로고침 비용을 줄였습니다.
* **카드뷰 렌더 최적화:** 카드 스타일 캐시와 배치 렌더링으로 대량 카드 표시 시 체감 속도를 개선했습니다.
* **대시보드 지연 초기화:** 히스토리/통계/즐겨찾기/DB 탭은 즉시 로드하되, 대시보드는 첫 진입 시 생성해 시작 시간을 줄였습니다.
* **compact 중복 묶기 실시간 최적화:** compact 결과는 배치마다 전체 재렌더하지 않고 dirty row만 증분 갱신하며, 정렬은 사용자 액션이나 수집 완료 시점에 한 번만 다시 맞춥니다.
* **즐겨찾기 부분 갱신:** app-level favorite key 초기화는 경량 `(asset_type, article_id, complex_id)` 조회를 사용하고, 토글 시 전체 결과 재구성 대신 해당 카드/row 상태만 갱신합니다.
* **hidden-tab stale refresh:** history/stats/favorites/dashboard는 크롤링 완료 후 숨겨진 상태면 즉시 다시 불러오지 않고 stale로 표시한 뒤 다음 탭 진입 때 1회만 갱신합니다.

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

프로그램 시작 시에는 필수 라이브러리/디렉토리/충돌 마커와 effective crawl engine 기준 브라우저만 경량 preflight로 점검합니다.
전체 internal import smoke를 포함한 full preflight는 `app_entry.py --preflight` 또는 `python -m src.utils.preflight` 경로에서 실행합니다.
추가로 `data/settings.json` 기준의 `effective crawl_engine`를 계산해, `playwright`를 실제로 사용할 런타임에서만 Playwright Chromium 존재 여부를 시작 차단 조건으로 확인합니다.
실사이트 접근 확인은 `python app_entry.py --live-smoke --smoke-headless`로 수행할 수 있습니다. 기본적으로 `home + complex + detail + article-only 역조회 + geo marker switch/API` probe를 실행합니다. 현재 기본 샘플은 `complex_id=3833`, `article_id=2625154515`이지만, 기본 article ID는 고정 검증 대상이 아니라 seed입니다. 기본 seed를 사용하면 complex probe에서 얻은 현재 `sample_article`이 effective article ID로 교체될 수 있습니다. 필요 시 `--smoke-url`로 경로를 추가하고 `--smoke-complex-id` / `--smoke-article-id`로 샘플 ID를 덮어쓸 수 있습니다. 상세 필드 파싱 품질까지 확인하려면 `--live-smoke-detail-fields`를 추가합니다. 결과를 남길 때는 `--smoke-json-log logs/live-smoke.json`을 추가하며, JSON에는 requested/effective article ID와 runtime/data 경로가 포함됩니다.

PowerShell에서 한글 로그가 깨지면 실행 전에 아래처럼 UTF-8 출력을 고정하세요.

```powershell
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
```

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

릴리스 전 기본 검증 순서는 다음과 같습니다.

1. `python -m pytest -q`
2. `python -m compileall -q app_entry.py src tests`
3. `python -m src.utils.preflight`
4. `npx --yes pyright`
5. `python app_entry.py --live-smoke --smoke-headless --smoke-json-log logs/live-smoke-source.json`
6. `pyinstaller naverland-scrapper.spec`
7. `dist\naverland\naverland.exe --preflight`
8. `dist\naverland\naverland.exe --live-smoke --smoke-headless --smoke-json-log logs/live-smoke-frozen.json`

상세 필드 파싱까지 릴리스 게이트에 포함하려면 source/frozen live-smoke 명령에 각각 `--live-smoke-detail-fields`를 추가합니다.

## **📖 사용 가이드**

1. **수집 모드 선택**  
   * **데이터 수집 탭:** 기존 단지 ID/URL 기반 수집용입니다.
   * **지도 탐색 탭:** 위도/경도/줌 기준으로 주변 지역을 sweep하며 단지를 자동 등록합니다.
2. **단지 등록**  
   * **검색:** '단지 목록' 탭에서 단지명과 단지 ID(네이버 URL의 숫자 부분)를 입력하여 추가합니다.  
   * **일괄 등록:** 'URL등록' 버튼을 눌러 여러 URL을 붙여넣으면 자동으로 파싱하여 등록합니다. `new.land complex`, `new.land houses(VL)`, `land.naver.com complexNo`, `m.land`, `fin.land article` 계열을 지원하며, `houses` URL은 `VL` 스코프를 유지한 채 등록됩니다. article-only URL은 백그라운드에서 단지 ID를 역조회하며, 역조회 실패 항목은 미선택 상태로 남습니다. 단지명 direct lookup이 rate limit에 걸리면 browser fallback으로 단지명을 재확인하고, fallback도 실패할 때만 일시적으로 `단지_{id}` 이름으로 표시될 수 있습니다.
3. **조건 설정**  
   * 거래 유형(매매/전세/월세)을 선택합니다.  
   * 필요 시 가격 및 면적 필터를 활성화하여 범위를 지정합니다.  
   * 월세는 `보증금 범위`와 `월세 금액 범위`를 각각 설정하며, 두 조건을 모두 만족해야 결과에 포함됩니다.
   * 기본 엔진은 설정 또는 수집 탭에서 `playwright` / `selenium`을 선택할 수 있습니다. 현재 `Playwright complex`는 `APT/VL`을 모두 지원하고, `Selenium complex`는 `APT`만 지원합니다.
   * 지도 탐색 탭에서는 `APT`, `VL`, 줌, 링 수, 그리드 간격, 지점 대기시간을 조정할 수 있습니다. `APT`와 `VL`은 둘 중 하나 이상 선택해야 하며, 모두 해제된 상태에서는 시작하지 않습니다.
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
* 2026-04-10 실사이트 정합 재점검 기준으로 상세 파서 `front-api` 매핑, 단지명 429 cooldown, live smoke CLI 확장, helper 기반 URL family 정리는 모두 runtime/UI 레벨 변경이라 추가 PyInstaller 수정이 필요하지 않았습니다.
* 2026-04-11 예약/자산 스코프/CI 신뢰성 패스 기준으로도 schedule slot 소비 조건 보강, 예약 실패 시 task snapshot 복원, runtime item dedupe 자산 스코프 정렬, CI 정적 검사 기준 확인은 모두 runtime/test/doc 레벨 변경이라 추가 PyInstaller 수정이 필요하지 않았습니다.
* 2026-04-16 자산 스코프/월세 이력/대시보드/CI 정합 패스 기준으로도 VL houses URL 보존, complex task `(asset_type, cid)` dedupe, scoped disappeared count, 월세 rent 기준 비교, 로컬 pytest 검증 기준 확인은 모두 runtime/test/doc 레벨 변경이라 추가 PyInstaller 수정이 필요하지 않았습니다.
* 2026-04-27 구현 갭 클로저 기준으로도 예약 complex APT/VL 정책 정합화, article-only URL 역조회, 월세 UI 가격 기준 통일, Selenium 월세 DOM fallback, mixin rebind meta-test는 모두 Python/runtime/test/doc 레벨 변경이라 추가 PyInstaller 수정이 필요하지 않았습니다.
* 2026-05-03 기능 구현 하드닝 기준으로도 DB scope/upsert, schedule hydration guard, filtered-out policy, article fallback, detail meta/export, live smoke JSON, core pytest CI subset은 모두 Python/runtime/test/doc 레벨 변경이라 추가 PyInstaller 수정이 필요하지 않았습니다.
* 2026-05-04 구현 리뷰 클로저 기준으로도 Geo marker stats 노출, DEFAULT_COLUMNS 기반 export 기본값, confirmed-empty cache 보정, trade_type별 history cache, batch article browser fallback 재사용, 빠른 CI subset 확장은 모두 Python/runtime/test/doc 레벨 변경이라 추가 PyInstaller 수정이 필요하지 않았습니다.
* 2026-05-11 실사이트 샘플 갱신 및 기능 리스크 하드닝 기준으로도 ExportResult, live smoke article count/sample 검증, `complexNumber` parser 보강, browser-backed name lookup fallback, packaged article fallback의 local Chrome 우선 실행, DB close timeout 결과 객체, 분석 APT/VL scope 확장, mixin rebind meta-test는 모두 Python/runtime/test/doc 레벨 변경이라 추가 PyInstaller 수정이 필요하지 않았습니다.
* 2026-05-15 기능 리스크 클로저 기준으로도 direct API cooldown 중 browser fallback 유지, `--live-smoke-detail-fields`, smoke runtime metadata JSON, Geo 자산 미선택 차단, 수동 APT/VL 선택 UI는 모두 Python/runtime/UI/test/doc 레벨 변경이라 추가 PyInstaller hidden import/runtime hook/data bundle 수정이 필요하지 않았습니다.
* 2026-06-04 기능 감사 하드닝 기준으로도 Selenium fallback prefill 최종화, DB rollback guard, CSV/XLSX formula escape, URL batch generation guard, `playwright_navigation_timeout_ms`, 상세 task fanout 제한, Geo 빈 자산 정책 정합화는 모두 Python/runtime/UI/test/doc 레벨 변경이라 추가 PyInstaller hidden import/runtime hook/data bundle 수정이 필요하지 않았습니다.

## **⚠️ 주의사항**

* 이 프로그램은 개인적인 학습 및 편의를 위해 제작되었습니다.  
* 과도한 속도로 크롤링을 시도할 경우 네이버 부동산의 접속이 일시 차단될 수 있으므로, '보통' 또는 '느림' 속도 사용을 권장합니다.  
* 수집된 데이터의 상업적 이용에 대한 책임은 사용자에게 있습니다.


## v15.0.14 Docs/Spec/Gitignore Consistency Pass (2026-03-17)

- 코드베이스 재점검 기준:
  - 기본 PyInstaller 프로필은 `onedir + Chromium bundle`입니다.
  - `onefile`은 `NAVERLAND_ONEFILE=1`에서만 활성화됩니다.
  - 카드 뷰 위젯은 `src/ui/widgets/cards.py`, 대시보드 위젯은 `src/ui/widgets/dashboard.py`에 분리되어 있습니다.
  - `startup_lazy_noncritical_tabs`는 레거시 호환용 `False` 키로만 유지되며, 현재는 대시보드만 첫 진입 시 생성되고 history/stats/favorites는 hidden-tab stale refresh 정책으로 갱신됩니다.
- 성능 정합 메모:
  - 대시보드는 통계/소멸 집계 캐시와 지연 차트 캔버스 초기화, 첫 탭 진입 시 위젯 생성을 사용합니다.
  - Playwright 모바일 상세는 현재 가격/면적 필터를 통과한 매물에만 적용됩니다.
  - 필터 밖 매물은 히스토리/알림/가격변경 카운트에서도 제외하고 `filtered_out`만 증가시키는 정책으로 고정했습니다.
  - 결과 렌더링은 검색 캐시 사전 생성, 로그 block count 제한, 카드 스타일 캐시, compact dirty-row 갱신, hidden-tab stale refresh를 사용합니다.
- `.gitignore` 점검 결과:
  - 기존 build/log/data/Playwright 산출물 규칙은 유지하고, 개발 도구 캐시(`.mypy_cache/`, `.ruff_cache/`, `.nox/`, `node_modules/`, `coverage.xml`)를 예방적으로 추가했습니다.

## v15.0.16 Functional Consistency Pass (2026-03-19)

- 최근 본 매물 동선 정합화:
  - 매물 열기 경로를 app-level handler로 통합했습니다.
  - 결과 테이블 더블클릭, 카드뷰 클릭, 최근 본 매물 다이얼로그, 즐겨찾기 탭 열기 버튼이 모두 같은 최근 본 매물 기록 경로를 사용합니다.
  - `recently_viewed_count`가 실제 저장/표시 최대 개수에 반영되고, dedupe 키는 `(asset_type, complex_id, article_id)`로 고정됩니다.
- 예약 실행 안정화:
  - exact-minute match 대신 slot 기반 catch-up window(10분)로 동작합니다.
  - `schedule_config`에는 `last_run_slot`, `last_run_at` 내부 메타가 저장됩니다.
  - busy / no-target skip은 같은 window 안에서 재시도 가능하며, 실제 시작된 경우에만 slot을 소비합니다.
- 대시보드 / 설정 정합화:
  - 빈 데이터 진입 시 카드/차트/trend 문구를 명시적으로 clear 하도록 정리했습니다.
  - `show_trend_analysis`가 실제 trend frame visibility를 제어합니다.
  - trend 영역은 placeholder 대신 현재 집계 기반 summary를 표시합니다.
  - `result_tab_mode`는 deprecated key로 제거했고, `startup_lazy_noncritical_tabs`는 레거시 no-op 키로만 유지됩니다.
- Packaging / docs / ignore review:
  - `naverland-scrapper.spec`는 이번 범위에서도 추가 hidden import/runtime hook/data bundle 수정이 필요하지 않았습니다.
  - `.gitignore`는 현재 build/log/data/Playwright/runtime artifact 규칙으로 충분합니다. live-smoke JSON은 `logs/` 규칙에 포함되고, `.gitattributes`는 추적 대상으로 유지합니다.
  - GitHub CI는 parser/app_entry/live_smoke/analysis/database/ui wiring/runtime smoke/export/rebind 핵심 pytest subset과 정적 검사, preflight 점검을 수행합니다.
- Validation:
  - `python -m pytest -q` => `182 passed`
  - `npx pyright` => `0 errors`


## v15.0.1 Runtime Notes (2026-03-06)

- `playwright_response_drain_timeout_ms` 설정은 응답 drain 대기용이며 기본값은 `3000`입니다. `playwright_navigation_timeout_ms` 설정은 page navigation 대기용이며 기본값은 `15000`입니다. 둘 다 Settings에서 조정할 수 있습니다.
- `complex` 모드 캐시 컨텍스트는 현재 `mode=complex`, `asset_type=<target asset_type>`, `marker_id=""`로 정규화됩니다.
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
  - 현재 `complex` 캐시 컨텍스트 정규화(`mode=complex`, `asset_type=<target asset_type>`, `marker_id=""`)
  - 레거시 complex 캐시 키는 읽기 호환만 유지

## v15.0.3 Reliability Notes (2026-03-07)

- `CrawlerThread`가 실행 단위 pair 큐를 추적하고, Playwright 실패 시 Selenium fallback은 미처리 pair만 이어서 수행합니다.
- 수집 결과 push 경로에 item dedupe를 추가해 `(complex_id, article_id, trade_type)` 기준 중복 반영을 차단합니다(`article_id` 없으면 dedupe skip).
- Playwright negative cache는 `response_seen=True` + `drain_timed_out=False`일 때만 저장하며, 캐시 payload에 `reason=confirmed_empty` 메타를 포함합니다.
- Playwright 경로에 메모리 워치독(500MB)을 추가해 임계치 초과 시 browser/context/page pool을 recycle하고 통계(`playwright_recycle_count`, `playwright_last_recycle_reason`)를 노출합니다.
- DB `complexes`는 `(asset_type, complex_id)` 복합 unique로 자동 마이그레이션되며, legacy row는 `asset_type='APT'`로 승격됩니다.
- DB 탭 삭제 UX에 확인 모달과 `관련 이력까지 삭제` 옵션(기본 off)을 추가했습니다.
- GitHub CI는 핵심 pytest subset, 정적 검사, preflight 점검을 수행합니다.
- `naverland-scrapper.spec`은 이번 반영 범위에서 추가 수정 없이 현재 설정(Playwright hidden import/runtime hook/Chromium bundle)으로 유지합니다.

## v15.0.4 Crawling Audit Notes (2026-03-07)

- 당시 크롤링/스크래핑 구현 리스크 감사 문서를 추가했습니다(`crawling_scraping_risk_audit_2026-03-07.md`, 현재는 독립 루트 문서로 유지하지 않음).
- 이 독립 감사 문서는 현재 루트 문서로 유지하지 않으며, 관련 이력은 `update_history.md`와 AI 컨텍스트 문서에 흡수되어 있습니다.
- 핵심 점검 결론:
  - Selenium 경로의 0건 negative cache 저장 조건 강화 필요
  - 차단 감지 누적 기반 쿨다운(circuit breaker) 필요
  - Playwright 응답 매칭/상세 파싱 성공률 관측성 강화 필요
- `.spec` 점검 결과:
  - `naverland-scrapper.spec`는 현재 코드 구조(분할 리팩토링 포함)에서도 추가 수정 없이 유지 가능합니다.

## v15.0.5 Docs/Packaging Recheck (2026-03-07)

- `.spec` 재점검 결과: `src/core/*_parts`, `src/ui/*_parts` 분할 리팩토링 이후에도 `naverland-scrapper.spec`는 현재 hidden import/runtime hook 구성으로 충분하며 추가 수정이 필요하지 않습니다.
- 당시 감사 문서 상태 정합화: `crawling_scraping_risk_audit_2026-03-07.md`를 저장소 기준 문서로 유지했으며, 현재는 독립 루트 문서 삭제 상태를 반영하고 추적 정보만 `update_history.md`에 남깁니다.
- 현재 기준으로 해당 독립 감사 문서는 루트 문서에서 제거되었고, 필요한 추적 정보는 `update_history.md`에 남깁니다.
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
- complex 모드 작업 목록은 당시 `cid` 기준 dedupe였고, 현재는 `(asset_type, cid)` 기준으로 동작합니다.
  - 수동 추가, DB/그룹/최근 검색/URL/예약 실행이 모두 같은 dedupe 경로를 사용합니다.
  - 동일 `cid`가 다시 들어오면 첫 이름을 유지하고 중복은 스킵 로그/상태 메시지로 안내합니다.
  - `start_crawling()` 직전에도 최종 `target_list`를 다시 정규화합니다.
- item dedupe와 집계 수치를 일치시켰습니다.
  - `_push_item()`은 실제 push 성공 여부를 `bool`로 반환합니다.
  - raw item, Selenium cache hit, DOM parse 경로 모두 실제 push 성공 건만 `matched_count`와 완료 count에 반영합니다.
- crawl history 메타데이터와 stats UX를 보강했습니다.
  - 당시 `complex` 모드가 APT 중심 경로였기 때문에 이력도 `asset_type='APT'`를 명시 저장했습니다. 현재는 target 자산유형을 그대로 저장합니다.
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

## v15.0.15 Functional Reliability Update (2026-03-18)

- URL batch registration now accepts both `complexes/{complex_id}` and `houses/{complex_id}?articleId=...` style Naver URLs.
- `NaverURLParser` is the single parser used for URL batch/manual registration flows.
- Monthly price snapshots now persist two metrics for `월세`:
  - `price_metric=deposit`
  - `price_metric=rent`
- Monthly stats default to `월세 금액` and expose a metric selector for `보증금`.
- Legacy deposit-only monthly snapshot rows are preserved but hidden from default queries and stats screens.
- Scheduled `geo_sweep` runs now persist and replay a full geo profile:
  - `lat`, `lon`, `zoom`, `rings`, `step_px`, `dwell_ms`, `asset_types`
- Manual Geo tab runs remember the last user-entered coordinates via `geo_last_lat` / `geo_last_lon`.
- Scheduled geo runs do not overwrite the remembered manual coordinates.
- DB restore now stops both active crawl modes before replacement:
  - regular crawler
  - geo sweep crawler
- Runtime JSON state files now use atomic write + broken-file quarantine:
  - `settings.json`
  - `presets.json`
  - `search_history.json`
  - `recently_viewed.json`
  - `crawl_cache.json`
- Packaging / ignore review:
  - `naverland-scrapper.spec` was rechecked and still needs no extra hidden import/runtime hook/data bundle changes.
  - `.gitignore` now ignores `*.json.tmp` and `*.json.broken.*` runtime artifacts.
- Validation:
  - `pytest -q` => `176 passed`
