# Desktop Qt UI Design Rules
## PySide6 / PyQt6 공통 에이전트 지시서

> 목적: 모든 Qt 데스크톱 앱에서 `ktrain`과 유사한 수준의 일관되고 절제된 Fluent 스타일을 유지한다.
>
> 이 문서는 UI 신규 구현, UI 리팩터링, 신규 페이지 추가, 기존 위젯 교체 작업 시 공통 규칙으로 사용한다.

---

## 0. 최우선 원칙

에이전트는 UI를 "예쁘게 꾸미는 것"보다 **일관성, 가독성, 정보 구조, 상태 표현, 유지보수성**을 우선한다.

다음 우선순위를 따른다.

1. 기존 기능과 동작을 깨뜨리지 않는다.
2. 기존 프로젝트의 Qt 바인딩(PySide6/PyQt6)을 존중한다.
3. `ktrain`의 Fluent UI 구조와 밀도를 기본 참고 스타일로 삼는다.
4. 화면마다 임의 스타일을 추가하지 않고 공통 컴포넌트와 토큰을 재사용한다.
5. 다크/라이트 테마에서 모두 정상 동작해야 한다.
6. 기능 추가보다 UI 규칙 통일이 우선이다.
7. 과도한 장식보다 업무용 데스크톱 앱의 명료성을 우선한다.

`ktrain`의 특정 도메인 색상(SRT/KTX 등)은 복제하지 않는다.  
참고해야 할 것은 **레이아웃 밀도, Fluent 컴포넌트 사용 방식, Navigation 구조, InfoBar 기반 피드백, OS 테마 연동, 공통 theme 처리 방식**이다.

---

# 1. 기술 스택 원칙

## 1.1 Qt 바인딩

기존 프로젝트가 다음 중 하나를 사용하면 그대로 유지한다.

- PySide6
- PyQt6

UI 개선만을 목적으로 PyQt6 ↔ PySide6 전체 전환을 하지 않는다.

단, 신규 프로젝트이거나 전면 재구축 작업에서 별도 제약이 없다면 다음을 우선 검토한다.

```text
PySide6
+ PySide6-Fluent-Widgets
+ 필요 시 superqt
```

### 금지

한 프로젝트에서 다음을 혼합하지 않는다.

```text
PyQt6 + PySide6
PyQt6-Fluent-Widgets + PySide6-Fluent-Widgets
```

`qfluentwidgets` 패키지는 Qt binding별 배포판이 동일 import namespace를 사용하므로 환경 충돌 가능성을 항상 확인한다.

---

# 2. 기본 UI 방향

기본 스타일은 다음 키워드를 따른다.

```text
Fluent
Clean
Compact
Native-like
Low visual noise
Information first
Consistent spacing
Clear hierarchy
```

다음 스타일은 피한다.

```text
과도한 gradient
과도한 shadow
glassmorphism 남용
neon color
큰 radius 남발
모든 영역을 card로 감싸는 구성
모든 버튼에 accent color 사용
emoji를 UI icon으로 사용
웹 대시보드처럼 지나치게 넓은 여백
```

Qt 데스크톱 앱은 웹 페이지가 아니다.

화면 공간을 효율적으로 사용하면서도 답답하지 않은 밀도를 유지한다.

---

# 3. Main Window 구조

가능하면 `ktrain`과 유사한 구조를 사용한다.

PySide6 + QFluentWidgets 기준:

```python
class MainWindow(MSFluentWindow):
    ...
```

또는 프로젝트 상황에 따라:

```python
class MainWindow(FluentWindow):
    ...
```

주요 화면은 `addSubInterface()` 기반 Navigation을 우선한다.

예:

```python
self.addSubInterface(
    self.home_page,
    FIF.HOME,
    "홈",
)

self.addSubInterface(
    self.settings_page,
    FIF.SETTING,
    "설정",
    position=NavigationItemPosition.BOTTOM,
)
```

### Navigation 원칙

상단/주요 기능:

```text
홈
검색
변환
처리
결과
내역
```

하단/보조 기능:

```text
설정
업데이트
정보
```

페이지가 3개 이상이면 임의의 버튼 묶음보다 NavigationInterface 계열 사용을 우선 검토한다.

---

# 4. 프로젝트 UI 디렉터리 구조

UI 코드가 커지면 최소한 다음 구조로 분리한다.

```text
src/
└─ ui/
   ├─ main_window.py
   ├─ theme.py
   ├─ components/
   │  ├─ __init__.py
   │  ├─ cards.py
   │  ├─ dialogs.py
   │  ├─ empty_state.py
   │  └─ status.py
   │
   ├─ pages/
   │  ├─ home_page.py
   │  ├─ settings_page.py
   │  └─ ...
   │
   └─ resources/
```

규모가 더 크면:

```text
ui/
├─ design_tokens.py
├─ theme.py
├─ components/
├─ pages/
├─ dialogs/
└─ icons/
```

### 책임 분리

`MainWindow`는 다음 역할만 가진다.

- 페이지 구성
- Navigation
- 전역 UI 상태
- tray/window lifecycle
- page 간 coordination

`MainWindow` 안에 다음을 직접 넣지 않는다.

- 대규모 비즈니스 로직
- 네트워크 요청 구현
- 파일 파싱 구현
- DB 처리
- 복잡한 worker 내부 로직
- 수백 줄짜리 개별 페이지 UI

---

# 5. Design Token 규칙

UI에서 임의의 숫자와 색상을 반복해서 쓰지 않는다.

공통 토큰을 정의한다.

예:

```python
SPACE_XXS = 4
SPACE_XS = 8
SPACE_SM = 12
SPACE_MD = 16
SPACE_LG = 24
SPACE_XL = 32

CONTROL_HEIGHT_SM = 32
CONTROL_HEIGHT_MD = 36
CONTROL_HEIGHT_LG = 40

PAGE_MARGIN = 24
SECTION_GAP = 24
CARD_RADIUS = 8
```

## 간격 기준

기본 spacing scale:

```text
4
8
12
16
24
32
```

가능하면 이 값 외의 임의 spacing을 만들지 않는다.

### 권장값

| 용도 | 값 |
|---|---:|
| 아이콘 ↔ 텍스트 | 8px |
| 작은 control 간 | 8px |
| form row 간 | 12px |
| 관련 control group 간 | 16px |
| section 간 | 24px |
| page 좌우 margin | 24px |
| 대형 section 구분 | 32px |

---

# 6. Typography

폰트 크기는 화면별로 임의 생성하지 않는다.

권장 계층:

```text
Page Title      22~24px / Semibold
Section Title   16~18px / Semibold
Body            13~14px / Regular
Secondary       12~13px / Regular
Caption         11~12px / Regular
```

### 규칙

- 한 페이지에서 제목 크기를 여러 종류로 난립시키지 않는다.
- 굵기는 강조에만 사용한다.
- 설명 텍스트는 primary text보다 한 단계 낮은 명도로 표현한다.
- 버튼 텍스트에 불필요한 bold를 남발하지 않는다.
- 긴 설명은 QLabel 하나에 길게 넣기보다 title + secondary text 형태를 우선한다.

폰트 family는 OS 친화적인 fallback을 사용한다.

예:

```text
Pretendard
Segoe UI
Apple SD Gothic Neo
Malgun Gothic
sans-serif
```

단, 특정 폰트를 앱에 강제로 포함하지 않아도 된다.

---

# 7. Color 규칙

색상은 의미 기반 semantic token으로 관리한다.

```text
primary
background
surface
surface_alt
border
text_primary
text_secondary
success
warning
error
```

## 금지

다음과 같은 코드를 페이지마다 반복하지 않는다.

```python
button.setStyleSheet("background: #3874f2; ...")
label.setStyleSheet("color: #aaa;")
```

대신 theme 또는 component 계층에서 정의한다.

### Accent

한 화면에서 기본 accent는 하나만 사용한다.

예외:

- success
- warning
- error
- 도메인 상태 표현

Brand color가 있다면 primary accent로 사용할 수 있지만, 모든 요소를 해당 색으로 칠하지 않는다.

---

# 8. Light / Dark Theme

가능하면 OS 테마와 연동한다.

QFluentWidgets 사용 시 기본 방향:

```python
setTheme(Theme.AUTO)
```

필요하면 `darkdetect` 또는 Qt의 `colorSchemeChanged`를 이용해 동기화한다.

`ktrain`과 같이 theme 동기화 코드는 별도 모듈로 둔다.

```text
ui/theme.py
```

### 필수 확인

다크 모드에서:

- text contrast
- disabled text
- table header
- input border
- selected row
- checkbox
- list widget
- error/warning status

라이트 모드에서도 동일하게 확인한다.

---

# 9. QSS 사용 규칙

QSS는 **최후의 보정 수단**이다.

QFluentWidgets가 제공하는 component를 QSS로 다시 그리지 않는다.

## 허용

- Qt 기본 위젯과 Fluent 위젯 사이의 시각적 차이 보정
- 특정 native widget의 dark mode 대비 보정
- 라이브러리에서 제공하지 않는 최소한의 상태 표현
- 프로젝트 전체에 적용되는 공통 token 기반 스타일

## 금지

페이지마다 다음과 같은 방식:

```python
widget.setStyleSheet(...)
button.setStyleSheet(...)
label.setStyleSheet(...)
```

특히 조건문에 따라 inline QSS 문자열을 계속 생성하지 않는다.

불가피하다면 공통 helper로 이동한다.

---

# 10. Component 선택 원칙

가능하면 Fluent component를 우선 사용한다.

예:

```text
PushButton
PrimaryPushButton
ToolButton
LineEdit
SearchLineEdit
ComboBox
SpinBox
SwitchButton
CheckBox
ProgressBar
ProgressRing
InfoBar
MessageBox
CardWidget
SimpleCardWidget
SettingCard
HeaderCardWidget
```

기본 Qt widget을 써야 할 이유가 없다면 직접 `QPushButton` 등을 꾸며 재구현하지 않는다.

---

# 11. Button 규칙

버튼은 중요도에 따라 구분한다.

## Primary

화면의 핵심 행동.

예:

```text
검색
변환 시작
저장
실행
적용
```

한 화면 또는 한 section에서 primary action은 원칙적으로 하나만 둔다.

## Secondary

보조 행동.

```text
취소
폴더 열기
초기화
새로고침
추가 설정
```

## Destructive

삭제, 초기화, 데이터 제거 등.

일반 primary 색상을 사용하지 않는다.

필요하면 확인 절차를 둔다.

### 금지

한 줄에 다음처럼 모든 버튼이 동일 강조도를 갖게 하지 않는다.

```text
[검색] [저장] [복사] [초기화] [삭제] [폴더열기]
```

---

# 12. Form 규칙

Form은 정렬이 가장 중요하다.

권장:

```text
Label              Input
설명                 helper text
```

또는 좁은 화면에서는:

```text
Label
Input
helper text
```

### 규칙

- 같은 그룹의 label 폭을 통일한다.
- input 높이를 통일한다.
- 동일 종류 input 폭을 가급적 통일한다.
- placeholder를 label 대용으로 사용하지 않는다.
- 단위를 input 밖에 명확하게 표시한다.
- 숫자값은 가능하면 SpinBox 계열을 사용한다.
- 경로 입력은 LineEdit + Browse button 패턴을 사용한다.

---

# 13. Card 사용 규칙

Card는 관련 기능을 묶을 때만 사용한다.

좋은 예:

```text
[검색 조건]
출발역
도착역
날짜
인원
```

나쁜 예:

```text
카드
 └─ 카드
     └─ 카드
         └─ 버튼
```

페이지 전체를 여러 개의 떠 있는 card로 쪼개지 않는다.

### Card 판단 기준

다음 중 하나에 해당할 때 사용:

- 하나의 설정 그룹
- 명확한 독립 기능
- 별도 상태를 가진 작업 영역
- 요약 정보

단순한 section 제목과 2~3개 control뿐이면 card 없이 section layout을 우선한다.

---

# 14. Table / List

업무용 앱에서는 테이블 가독성이 매우 중요하다.

### 기본 규칙

- row height 통일
- header 정렬 통일
- 필요 없는 vertical grid 최소화
- 핵심 열만 강조
- 숫자는 우측 정렬 고려
- 상태 열은 icon/badge/text 조합 사용
- action button을 모든 셀에 과도하게 넣지 않는다

빈 테이블에는 빈 공간만 보여주지 않는다.

예:

```text
검색 결과가 없습니다.
조건을 변경한 뒤 다시 검색해 주세요.
```

Empty state component 사용을 우선한다.

---

# 15. Feedback / Notification

## 성공 / 경고 / 오류

일반적인 작업 결과는 `InfoBar` 사용을 우선한다.

예:

```python
InfoBar.success(...)
InfoBar.warning(...)
InfoBar.error(...)
InfoBar.info(...)
```

Modal dialog는 사용자의 작업을 반드시 차단해야 하는 경우만 사용한다.

### MessageBox 적합

- 저장하지 않고 종료
- 진행 중 작업 취소
- 데이터 삭제
- 되돌릴 수 없는 작업
- 반드시 선택이 필요한 상황

### InfoBar 적합

- 저장 완료
- 복사 완료
- 검색 실패
- 네트워크 오류
- 업데이트 완료
- 설정 적용 완료

---

# 16. Loading / Busy State

시간이 걸리는 작업은 반드시 상태를 표현한다.

필요에 따라:

```text
ProgressBar
ProgressRing
버튼 disabled
취소 버튼
상태 설명
```

작업 중 UI 전체를 무조건 disable 하지 않는다.

정말 필요한 영역만 잠근다.

### 긴 작업

UI thread에서 실행하지 않는다.

```text
QThread
QObject worker
Qt signal/slot
```

등 기존 프로젝트 패턴을 따른다.

---

# 17. 페이지 상태 설계

모든 주요 페이지는 최소한 다음 상태를 고려한다.

```text
initial
loading
populated
empty
error
busy
disabled
```

예:

```text
검색 페이지

initial
→ 검색 조건 입력

loading
→ ProgressRing + "검색 중"

populated
→ 결과 테이블

empty
→ EmptyState

error
→ InfoBar + 재시도 가능 상태
```

정상 성공 화면만 구현하고 나머지를 방치하지 않는다.

---

# 18. Dialog 규칙

Dialog는 최대한 짧고 목적이 명확해야 한다.

구조:

```text
Title

설명

content

Cancel | Primary Action
```

### 금지

- Dialog 안에 또 Dialog를 여는 구조
- 모든 설정을 modal에 몰아넣기
- 긴 로그를 MessageBox에 출력
- 단순 알림을 modal로 표시

---

# 19. Icon 규칙

QFluentWidgets의 `FluentIcon`을 우선한다.

```python
from qfluentwidgets import FluentIcon as FIF
```

예:

```text
FIF.HOME
FIF.SEARCH
FIF.SETTING
FIF.UPDATE
FIF.FOLDER
FIF.SAVE
FIF.DELETE
```

### 금지

```text
🔍
⚙️
📁
✅
❌
```

emoji를 앱의 정식 UI icon으로 사용하지 않는다.

텍스트 문맥에서 보조적으로 쓰는 것은 별개다.

---

# 20. Responsive Window

고정 해상도를 전제로 하지 않는다.

`ktrain`처럼 화면 가용 영역에 맞춰 초기 창 크기를 결정하는 패턴을 권장한다.

예:

```python
screen = QGuiApplication.primaryScreen()
available = screen.availableGeometry()
```

### 최소 요구

- 100% scaling
- 125%
- 150%

에서 UI가 깨지지 않아야 한다.

가능하면 1920×1080 이하 환경에서도 사용할 수 있어야 한다.

절대 좌표 기반 배치를 사용하지 않는다.

---

# 21. Layout 규칙

다음 순서로 사용을 우선한다.

```text
QVBoxLayout
QHBoxLayout
QGridLayout
QFormLayout
```

절대 위치:

```python
widget.move(...)
widget.setGeometry(...)
```

는 특별한 UI가 아니라면 사용하지 않는다.

### stretch 활용

빈 공간을 임의 margin으로 채우지 말고:

```python
layout.addStretch()
```

를 적절히 사용한다.

---

# 22. Scroll

페이지 내용이 창보다 길어질 가능성이 있으면 ScrollArea를 고려한다.

설정 화면, 긴 Form, 다수 Section에서는 특히 중요하다.

단, table 자체와 page scroll을 중첩해서 사용해 UX를 악화시키지 않는다.

---

# 23. Settings 페이지

설정은 일반 form보다 `SettingCard` 계열을 우선 검토한다.

예:

```text
일반
 ├─ 자동 업데이트
 ├─ 시작 시 실행
 └─ 기본 폴더

화면
 ├─ 테마
 └─ 언어

고급
 └─ 로그 설정
```

카테고리를 나눠 한 화면에 모든 설정을 평면 배치하지 않는다.

---

# 24. 재사용 컴포넌트

다음 패턴이 2회 이상 등장하면 공통 component화를 검토한다.

```text
파일 선택 row
폴더 선택 row
상태 badge
empty state
section header
progress panel
log viewer
path input
search toolbar
result toolbar
confirmation dialog
```

### 원칙

"코드를 줄이기 위한 추상화"보다  
"디자인과 동작을 동일하게 유지하기 위한 추상화"를 우선한다.

---

# 25. 비즈니스 로직과 UI 분리

페이지 class는 비즈니스 로직을 최소화한다.

좋은 구조:

```text
UI
↓ signal
Controller / Service
↓
Core
↓
result
↓ signal
UI
```

UI 파일이 API 호출, scraping, DB query, 파일 parsing까지 직접 수행하면 분리를 검토한다.

단순 앱에서는 불필요한 MVC/MVVM 과설계를 하지 않는다.

---

# 26. 기존 UI 리팩터링 절차

기존 UI를 개선할 때 무작정 전체 파일을 다시 작성하지 않는다.

다음 순서로 진행한다.

## Phase 1 — Audit

먼저 확인:

```text
현재 MainWindow
Navigation 방식
페이지 목록
중복 widget
inline QSS
custom color
custom button
dialog
table
loading state
dark/light 처리
window size
DPI 처리
```

## Phase 2 — Design Map

기존 기능을 다음과 같이 매핑한다.

```text
현재 UI
→ 유지
→ Fluent component로 교체
→ 공통 component화
→ 제거
```

## Phase 3 — Foundation

먼저 구축:

```text
theme
design tokens
MainWindow
Navigation
공통 component
```

## Phase 4 — Page Migration

페이지 단위로 변경한다.

한 번에 모든 화면을 전면 변경하지 않는다.

## Phase 5 — Cleanup

마지막에:

```text
unused QSS
unused widget
legacy component
duplicate color
duplicate spacing
dead code
```

를 정리한다.

---

# 27. ktrain 스타일을 참고할 때 유지할 요소

다음 특징을 우선 참고한다.

## 27.1 Fluent Navigation

`MSFluentWindow` / `FluentWindow` 기반 navigation.

## 27.2 단순한 페이지 구성

각 주요 기능을 별도 page로 분리한다.

## 27.3 시스템 테마 연동

다크/라이트를 앱에서 임의 강제하지 않는다.

## 27.4 InfoBar

작업 결과 알림은 화면 흐름을 깨지 않는 방식으로 제공한다.

## 27.5 Theme 모듈 분리

```text
theme.py
```

에서 공통 테마 로직을 관리한다.

## 27.6 최소 QSS

Fluent component가 이미 제공하는 스타일을 다시 CSS처럼 덮어쓰지 않는다.

## 27.7 Desktop density

웹앱처럼 과도하게 큰 padding을 적용하지 않는다.

---

# 28. 절대 금지 패턴

다음 패턴을 새로 만들지 않는다.

```python
button.setStyleSheet(...)
button2.setStyleSheet(...)
button3.setStyleSheet(...)
```

```python
widget.setGeometry(20, 30, 300, 50)
```

```text
화면마다 다른 button height
화면마다 다른 border radius
임의 hex color 반복
emoji icon
모든 기능을 하나의 거대한 MainWindow.py에 구현
UI thread에서 긴 작업
성공 메시지를 전부 QMessageBox로 표시
빈 결과를 빈 테이블로만 표현
hover animation 과다
shadow 과다
card nesting
```

---

# 29. 에이전트 작업 전 필수 확인

UI 작업을 시작하기 전에 다음 파일을 먼저 확인한다.

```text
README
requirements / pyproject
main entry
MainWindow
현재 theme
현재 UI components
대상 page
worker/service 구조
tests
packaging 설정
```

프로젝트 전체 구조를 파악하기 전에 UI 파일 하나만 보고 전면 재작성하지 않는다.

---

# 30. 에이전트 구현 규칙

에이전트는 작업 시 다음 순서를 따른다.

```text
1. 현재 UI 구조 분석
2. 기존 기능 목록 작성
3. 변경할 UI 영역 정의
4. 공통 component 재사용 가능성 확인
5. theme/token 적용
6. page 단위 구현
7. signal/slot 연결 검증
8. loading/error/empty 상태 검증
9. dark/light 검증
10. DPI/window resize 검증
11. 테스트 실행
12. dead UI code 제거
```

---

# 31. 기능 보존 원칙

UI 리팩터링 중 다음을 임의 변경하지 않는다.

```text
파일 처리 결과
API 요청 방식
DB schema
업데이트 로직
저장 형식
사용자 설정 key
CLI interface
worker 동작
기존 단축키
```

UI 개선 작업과 기능 변경을 분리한다.

기능 변경이 필요하면 이유를 명시하고 별도 변경으로 취급한다.

---

# 32. 테스트 기준

가능하면 다음을 확인한다.

## Startup

```text
앱 실행 성공
MainWindow 표시
Navigation 정상
기본 페이지 정상
```

## Interaction

```text
버튼 동작
입력
파일 선택
dialog
page 이동
```

## State

```text
loading
success
empty
error
cancel
```

## Theme

```text
light
dark
```

## Window

```text
resize
minimum size
high DPI
```

---

# 33. UI 완료 조건

다음 조건을 만족해야 UI 작업 완료로 판단한다.

- [ ] 기존 핵심 기능이 유지된다.
- [ ] Navigation 구조가 일관된다.
- [ ] spacing scale이 통일되어 있다.
- [ ] button hierarchy가 명확하다.
- [ ] inline `setStyleSheet()` 남용이 없다.
- [ ] 임의 hex color가 페이지 코드에 흩어져 있지 않다.
- [ ] dark/light mode가 정상이다.
- [ ] loading 상태가 존재한다.
- [ ] empty 상태가 존재한다.
- [ ] error 상태가 존재한다.
- [ ] 긴 작업이 UI thread를 막지 않는다.
- [ ] dialog와 InfoBar 용도가 구분되어 있다.
- [ ] 주요 화면에서 resize 시 layout이 깨지지 않는다.
- [ ] 125~150% DPI에서도 사용 가능하다.
- [ ] 중복 UI component가 정리되어 있다.
- [ ] legacy QSS와 dead UI code가 제거되었다.
- [ ] 테스트 또는 smoke test를 통과한다.

---

# 34. Agent용 최종 지시

UI 작업 요청을 받으면 다음 원칙을 기본값으로 적용하라.

```text
이 프로젝트의 UI는 ktrain 스타일의 절제된 Fluent 데스크톱 UI를 기준으로 한다.

기존 Qt binding은 유지하되 가능한 경우 QFluentWidgets의 표준 component를 우선 사용한다.

화면별 임시 QSS, 임의 색상, 임의 spacing, custom button 생성을 피하고
theme / design token / reusable component 기반으로 구현한다.

MainWindow는 Navigation과 page coordination에 집중하고,
각 기능 화면은 독립 page로 분리한다.

성공/경고/오류 등 비차단 알림은 InfoBar를 우선 사용하며,
Modal dialog는 사용자의 선택을 반드시 요구하는 경우에만 사용한다.

다크/라이트 테마, 창 크기 변경, DPI scaling,
loading / empty / error / busy 상태를 모두 고려한다.

UI 리팩터링 과정에서 기존 기능, 데이터 처리 방식, 저장 형식,
worker/service 동작을 임의로 변경하지 않는다.

새로운 스타일을 만들기 전에 기존 공통 component와 theme을 먼저 재사용한다.

구현 후에는 UI 중복, inline QSS, 임의 색상, dead code를 정리하고
최종적으로 이 문서의 UI 완료 조건을 기준으로 self-review한다.
```

---

# 35. 변경 결과 보고 형식

에이전트는 작업 완료 후 최소한 다음 형식으로 보고한다.

```markdown
## UI 변경 요약

### 변경한 화면
- ...

### 공통 컴포넌트
- ...

### Theme / Style 변경
- ...

### 기존 기능 보존 여부
- ...

### 제거한 Legacy UI
- ...

### 테스트
- ...

### 남은 UI 개선 후보
- ...
```

---

## 적용 원칙 요약

```text
ktrain = 스타일 기준점
QFluentWidgets = 기본 컴포넌트
Theme = 중앙 관리
Spacing = 4/8/12/16/24/32
Navigation = 일관되게
Primary action = 제한적으로
InfoBar > 단순 MessageBox
QSS = 최소화
UI와 Core = 분리
상태 설계 = initial/loading/empty/error/success
Dark/Light/DPI = 기본 요구사항
```

이 규칙을 프로젝트 전체 UI의 기본 설계 계약(Design Contract)으로 간주한다.
