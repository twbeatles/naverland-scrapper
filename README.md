# 🏠 네이버 부동산 크롤러 Pro Plus v12.0

네이버 부동산에서 아파트 매물 정보를 자동으로 수집하는 데스크톱 애플리케이션입니다.

## ✨ 주요 기능

### 🔍 데이터 수집
- 네이버 부동산 아파트 매물 크롤링
- 매매/전세/월세 거래유형별 수집
- 가격, 면적, 층수, 방향 등 상세 정보
- 스마트 스크롤링으로 전체 매물 수집

### 📊 v12.0 신규 기능
- **평당가 계산**: 매물별 평당가 자동 계산 및 정렬
- **크롤링 캐시**: TTL 기반 결과 캐싱 (반복 검색 속도 향상)
- **즐겨찾기/메모**: 관심 매물 저장 및 메모 기능 (DB 준비됨)
- **매물 소멸 추적**: 사라진 매물 감지 (DB 준비됨)

### 💾 데이터 관리
- SQLite 기반 단지 DB 관리
- 그룹별 단지 분류
- 가격 변동 추적 및 히스토리
- Excel/CSV/JSON 내보내기

### 🎨 UI/UX
- 다크/라이트 테마
- HiDPI 디스플레이 지원
- Toast 알림 시스템
- 반응형 레이아웃

## 📦 설치

### 요구사항
```
Python 3.9+
Chrome 브라우저
```

### 의존성 설치
```bash
pip install PyQt6 beautifulsoup4 undetected-chromedriver openpyxl plyer
```

### 선택적 의존성
```bash
# 차트 기능
pip install matplotlib

# 시스템 알림
pip install plyer
```

## 🚀 사용법

### 실행
```bash
python "부동산 매물 크롤러 v12.0.py"
```

### 기본 워크플로우
1. **단지 추가**: 네이버 부동산 URL 또는 단지 ID 입력
2. **거래유형 선택**: 매매, 전세, 월세 중 선택
3. **크롤링 시작**: ▶️ 버튼 클릭
4. **결과 확인**: 평당가, 가격변동 등 확인
5. **저장**: Excel/CSV/JSON으로 내보내기

### 단축키
| 기능 | 단축키 |
|------|--------|
| 크롤링 시작 | `Ctrl+R` |
| 크롤링 중지 | `Ctrl+Shift+R` |
| Excel 저장 | `Ctrl+S` |
| 설정 | `Ctrl+,` |
| 테마 전환 | `Ctrl+T` |

## 📁 파일 구조
```
naverland-scrapper/
├── 부동산 매물 크롤러 v12.0.py   # 메인 프로그램
├── data/
│   ├── complexes.db             # 단지 DB
│   ├── settings.json            # 설정
│   ├── presets.json             # 필터 프리셋
│   └── crawl_cache.json         # 크롤링 캐시
└── logs/
    └── crawler_YYYYMMDD.log     # 로그 파일
```

## ⚙️ 설정 옵션

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `theme` | dark | 테마 (dark/light) |
| `crawl_speed` | 보통 | 크롤링 속도 |
| `cache_enabled` | true | 캐시 사용 여부 |
| `cache_ttl_minutes` | 30 | 캐시 유효 시간 (분) |
| `show_price_per_pyeong` | true | 평당가 표시 |
| `track_disappeared` | true | 매물 소멸 추적 |

## 🔧 빌드

### PyInstaller로 단일 실행파일 생성
```bash
pip install pyinstaller
pyinstaller realestate_crawler.spec
```

## ⚠️ 주의사항
- 네이버 이용약관을 준수하여 사용하세요
- 과도한 크롤링은 IP 차단의 원인이 될 수 있습니다
- "느림" 또는 "매우 느림" 속도 권장

## 📝 버전 히스토리

### v12.0 (2025-12)
- 평당가 계산 및 정렬 기능
- 크롤링 결과 캐싱 시스템
- 즐겨찾기/메모 DB 인프라
- 매물 소멸 추적 기능

### v11.0
- HiDPI 디스플레이 지원
- Toast 알림 시스템
- 코드 품질 개선

### v10.5
- Glassmorphism UI 테마
- 다크/라이트 모드

## 📄 라이선스
MIT License

---
Made with ❤️ using Python & PyQt6
