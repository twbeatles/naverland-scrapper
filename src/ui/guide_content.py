"""Theme-aware HTML for the in-app guide (QTextBrowser)."""

from __future__ import annotations


def build_guide_html(theme: str = "dark") -> str:
    """Return full HTML document with colors that work on dark and light surfaces."""
    is_dark = str(theme or "dark").strip().lower() != "light"
    if is_dark:
        body_bg = "#12121f"
        body_fg = "#e8e8ef"
        muted = "#a8a8b8"
        accent = "#fbbf24"
        accent_soft = "rgba(251, 191, 36, 0.12)"
        accent_border = "rgba(251, 191, 36, 0.35)"
        code_bg = "rgba(251, 191, 36, 0.16)"
        code_fg = "#fcd34d"
        step_bg = "rgba(251, 191, 36, 0.08)"
        kbd_bg = "rgba(255, 255, 255, 0.08)"
        kbd_border = "rgba(255, 255, 255, 0.22)"
        tip_bg = "rgba(34, 197, 94, 0.12)"
        link = "#60a5fa"
        table_border = "rgba(255, 255, 255, 0.1)"
        title_weight_fg = "#f5f5f7"
    else:
        body_bg = "#f8fafc"
        body_fg = "#1e293b"
        muted = "#64748b"
        accent = "#0284c7"
        accent_soft = "rgba(14, 165, 233, 0.12)"
        accent_border = "rgba(14, 165, 233, 0.35)"
        code_bg = "rgba(14, 165, 233, 0.12)"
        code_fg = "#0369a1"
        step_bg = "rgba(14, 165, 233, 0.06)"
        kbd_bg = "#f1f5f9"
        kbd_border = "#cbd5e1"
        tip_bg = "rgba(22, 163, 74, 0.08)"
        link = "#2563eb"
        table_border = "#e2e8f0"
        title_weight_fg = "#0f172a"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
body {{
    font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
    font-size: 13px;
    line-height: 1.7;
    color: {body_fg};
    background-color: {body_bg};
    padding: 16px 24px;
    max-width: 800px;
}}
h2 {{
    font-size: 18px;
    font-weight: 800;
    color: {accent};
    border-bottom: 2px solid {accent_border};
    padding-bottom: 8px;
    margin-top: 24px;
}}
h3 {{
    font-size: 13px;
    font-weight: 700;
    color: {muted};
    margin-top: 18px;
    margin-bottom: 6px;
}}
.step {{
    background: {step_bg};
    border: 1px solid {accent_border};
    border-radius: 10px;
    padding: 14px 16px;
    margin: 10px 0;
}}
.step-num {{
    background: {accent};
    color: #ffffff;
    border-radius: 50%;
    width: 22px;
    height: 22px;
    display: inline-block;
    text-align: center;
    font-weight: 800;
    font-size: 12px;
    line-height: 22px;
    margin-right: 10px;
}}
.step-title {{
    font-weight: 700;
    margin-bottom: 4px;
    color: {title_weight_fg};
}}
.step-desc {{
    font-size: 12px;
    color: {muted};
}}
b {{
    color: {title_weight_fg};
    font-weight: 700;
}}
code {{
    background: {code_bg};
    color: {code_fg};
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 12px;
}}
.shortcut-table {{
    width: 100%;
    border-collapse: collapse;
    margin: 8px 0;
}}
.shortcut-table th {{
    background: {accent_soft};
    color: {accent};
    padding: 7px 12px;
    text-align: left;
    font-size: 12px;
    font-weight: 700;
    border-bottom: 1px solid {accent_border};
}}
.shortcut-table td {{
    padding: 6px 12px;
    border-bottom: 1px solid {table_border};
    font-size: 12px;
    color: {body_fg};
}}
kbd {{
    background: {kbd_bg};
    border: 1px solid {kbd_border};
    border-radius: 4px;
    padding: 1px 6px;
    font-size: 11px;
    font-family: monospace;
    color: {body_fg};
}}
.tip {{
    background: {tip_bg};
    border-left: 3px solid #16a34a;
    padding: 8px 14px;
    border-radius: 0 6px 6px 0;
    margin: 8px 0;
    font-size: 12px;
    color: {muted};
}}
.warn {{
    background: {accent_soft};
    border-left: 3px solid {accent};
    padding: 8px 14px;
    border-radius: 0 6px 6px 0;
    margin: 8px 0;
    font-size: 12px;
    color: {muted};
}}
a {{ color: {link}; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
ul {{ padding-left: 20px; color: {muted}; }}
li {{ margin: 4px 0; color: {muted}; }}
</style>
</head>
<body>

<h2>빠른 시작 가이드</h2>

<div class="step">
    <span class="step-num">1</span>
    <span class="step-title">단지 ID 찾기</span><br>
    <span class="step-desc">
        네이버 부동산에서 단지를 연 뒤 현재 URL의 단지 식별자를 확인하세요.<br>
        보통 <code>/complexes/123456</code> 또는 <code>complexNo=123456</code> 형태의 숫자가 <b>단지 ID</b>입니다.<br>
        브라우저 URL family는 시점에 따라 달라질 수 있습니다.
    </span>
</div>

<div class="step">
    <span class="step-num">2</span>
    <span class="step-title">단지 목록에 추가</span><br>
    <span class="step-desc">
        좌측 네비의 <b>매물 수집</b> 화면에서<br>
        ① 단지 ID를 입력하고 추가 버튼을 클릭하세요.<br>
        ② 또는 네이버 URL을 붙여넣어 <b>URL</b> 버튼을 사용하세요.
    </span>
</div>

<div class="step">
    <span class="step-num">3</span>
    <span class="step-title">거래 유형 선택</span><br>
    <span class="step-desc">
        수집할 거래 유형(<b>매매/전세/월세</b>)을 체크하세요.<br>
        가격 필터를 설정하면 해당 범위의 매물만 수집합니다.
    </span>
</div>

<div class="step">
    <span class="step-num">4</span>
    <span class="step-title">수집 시작</span><br>
    <span class="step-desc">
        <b>수집 시작</b> 버튼을 클릭하세요.<br>
        수집 완료 후 <b>저장</b> 버튼으로 Excel/CSV로 내보내세요.
    </span>
</div>

<div class="warn">
    속도를 너무 빠르게 설정하면 서버에서 차단될 수 있습니다. '보통' 이상을 권장합니다.
</div>

<h2>수집·표시 옵션</h2>
<div class="step">
    <span class="step-title">설정 → 기본 / 고급</span><br>
    <span class="step-desc">
        · 일상 옵션은 <b>기본</b> 탭에 모았습니다. 엔진·타임아웃 등은 <b>고급</b>에 있습니다.<br>
        · <b>분양권(PRE)</b>: 기본 꺼짐. 켜면 목록이 늘어날 수 있습니다.<br>
        · <b>상세 보강</b>: 기본 켜짐. 끄면 중개·기전세 없이 더 빠르게 수집합니다.<br>
        · <b>표시 항목</b>(확인일·동·타입명 등): 기본 숨김. 결과 <b>더보기</b> 또는 설정→고급에서 켭니다.<br>
        · 자세한 사이트 조사: 저장소 <code>docs/NAVER_LAND_SURVEY_2026-08-04.md</code>
    </span>
</div>

<h2>단축키</h2>
<table class="shortcut-table">
    <tr><th>기능</th><th>단축키</th></tr>
    <tr><td>크롤링 시작</td><td><kbd>Ctrl</kbd>+<kbd>R</kbd></td></tr>
    <tr><td>크롤링 중지</td><td><kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>R</kbd></td></tr>
    <tr><td>Excel 저장</td><td><kbd>Ctrl</kbd>+<kbd>S</kbd></td></tr>
    <tr><td>CSV 저장</td><td><kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>S</kbd></td></tr>
    <tr><td>결과 검색</td><td><kbd>Ctrl</kbd>+<kbd>F</kbd></td></tr>
    <tr><td>설정</td><td><kbd>Ctrl</kbd>+<kbd>,</kbd></td></tr>
    <tr><td>테마 변경</td><td><kbd>Ctrl</kbd>+<kbd>T</kbd></td></tr>
    <tr><td>트레이 최소화</td><td><kbd>Ctrl</kbd>+<kbd>M</kbd></td></tr>
</table>

<h2>팁</h2>
<ul>
    <li>결과 테이블에서 <b>더블클릭</b>하면 해당 매물 페이지로 이동합니다</li>
    <li>좌측 패널 슬라이더로 <b>패널 넓이</b>를 조절할 수 있습니다</li>
    <li>예약 수집에는 먼저 <b>단지 묶음</b>에서 그룹을 만들어 두세요</li>
    <li><b>내 단지</b>에 저장한 뒤 다시 돌리면 신규/변동 매물을 추적할 수 있습니다</li>
    <li>대시보드에서 <b>상승/하락/사라진 매물</b>을 한눈에 볼 수 있습니다</li>
</ul>

<h2>화면 안내 (좌측 네비)</h2>
<div class="step">
    <span class="step-title">수집 · 매물 수집</span><br>
    <span class="step-desc">단지 번호를 직접 넣어 수집하는 기본 화면입니다. 단지 추가 → 거래 유형 선택 → 수집 시작 → 저장 순서입니다.</span>
</div>
<div class="step">
    <span class="step-title">수집 · 지도로 찾기</span><br>
    <span class="step-desc">위도·경도를 기준으로 주변 단지를 자동으로 찾습니다. 단지 번호를 모를 때 지역 단위로 훑기에 적합합니다.</span>
</div>
<div class="step">
    <span class="step-title">보관함 · 내 단지 / 단지 묶음 / 즐겨찾기</span><br>
    <span class="step-desc">내 단지는 저장 단지 관리, 단지 묶음은 예약용 목록, 즐겨찾기는 자주 보는 매물 재확인에 씁니다.</span>
</div>
<div class="step">
    <span class="step-title">분석 · 대시보드 / 가격 통계 / 수집 기록 · 자동화 · 예약 수집</span><br>
    <span class="step-desc">대시보드는 전체 요약, 가격 통계는 시세 추이, 수집 기록은 과거 실행 내역, 예약 수집은 자동 실행입니다.</span>
</div>

<h2>메뉴 안내</h2>
<ul>
    <li><b>파일</b>: DB 백업, DB 복원, 설정, 종료</li>
    <li><b>보기</b>: 최근 본 매물 확인, 테마 전환</li>
    <li><b>필터</b>: 현재 필터 저장, 프리셋 불러오기, 고급 결과 필터</li>
    <li><b>알림</b>: 조건 매물 알림 설정</li>
    <li><b>도움말</b>: 단축키와 프로그램 정보</li>
</ul>

</body>
</html>
"""
