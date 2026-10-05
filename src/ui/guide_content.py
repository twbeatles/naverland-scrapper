"""Theme-aware HTML for the in-app guide (QTextBrowser).

Qt의 rich text 엔진은 border-radius, div padding, inline-block 등을 지원하지
않는다. 그래서 모든 배치는 표(table)와 셀 padding·bgcolor·border-bottom처럼
Qt가 확실히 그리는 속성만으로 만든다.
"""

from __future__ import annotations

from html import escape

#: (제목, 설명 HTML) — 빠른 시작 4단계
_QUICK_START = (
    (
        "수집할 단지 추가",
        "<b>매물 수집</b> 화면에서 <b>단지 찾기</b>를 눌러 단지 이름(예: 래미안, 반포자이)을 검색하고, "
        "원하는 단지를 체크해 추가합니다.<br>"
        "네이버 부동산 주소를 알고 있다면 <b>불러오기 → 네이버 부동산 주소 붙여넣기</b>로도 추가할 수 있습니다.",
    ),
    (
        "거래 종류 선택",
        "<b>매매 · 전세 · 월세</b> 중 수집할 종류를 체크합니다.<br>"
        "면적이나 가격 범위를 좁히고 싶을 때만 <b>조건·속도 설정</b>을 펼쳐 켜면 됩니다.",
    ),
    (
        "수집 시작",
        "<b>수집 시작</b>을 누르면 오른쪽에 매물이 바로 쌓입니다.<br>"
        "표의 매물을 두 번 누르면 네이버 부동산 매물 페이지가 열립니다.",
    ),
    (
        "결과 저장",
        "<b>결과 저장</b>으로 엑셀 파일에 담을 수 있습니다.<br>"
        "자주 보는 단지는 <b>내 단지에 저장</b>해 두면 다음부터 <b>불러오기</b>로 바로 가져옵니다.",
    ),
)

_RESULT_TIPS = (
    "<b>정렬·필터</b>에서 가격·면적 순으로 정렬하거나, 층·가격·단어로 결과를 좁혀 볼 수 있습니다.",
    "<b>카드로 보기</b>로 바꾸면 카드의 별(☆)을 눌러 <b>즐겨찾기</b>에 담을 수 있습니다.",
    "같은 단지를 여러 번 수집하면 <b>신규 · 가격 상승 · 가격 하락</b>이 표시됩니다.",
    "수집이 잘 안 될 때는 <b>진행 기록</b> 탭에서 어떤 일이 있었는지 볼 수 있습니다.",
)

_SETTINGS_NOTES = (
    ("기본 / 고급", "평소 쓰는 항목은 <b>기본</b> 탭에 있습니다. <b>고급</b>은 수집이 자주 실패할 때만 조정하세요."),
    ("분양권 매물", "기본은 꺼져 있습니다. 켜면 목록이 늘어납니다."),
    ("상세 정보 가져오기", "끄면 중개소·기존 전세금 없이 더 빠르게 수집합니다."),
    ("표에 보일 항목", "확인일·동·타입명 등은 결과의 <b>정렬·필터</b> 또는 설정 → 고급에서 켭니다."),
)

_SHORTCUTS = (
    ("수집 시작", "Ctrl + R"),
    ("수집 중지", "Ctrl + Shift + R"),
    ("엑셀로 저장", "Ctrl + S"),
    ("CSV로 저장", "Ctrl + Shift + S"),
    ("결과에서 찾기", "Ctrl + F"),
    ("설정", "Ctrl + ,"),
    ("어두운/밝은 테마 바꾸기", "Ctrl + T"),
    ("트레이로 숨기기", "Ctrl + M"),
)

_SCREENS = (
    ("매물 수집", "단지를 골라 매물을 수집하는 기본 화면입니다. 단지 추가 → 거래 종류 선택 → 수집 시작 → 결과 저장 순서입니다."),
    ("지도로 찾기", "지역을 고르면 그 주변의 단지와 매물을 자동으로 찾습니다."),
    ("내 단지", "저장해 둔 단지 목록입니다. 수집할 때 불러오기로 바로 가져옵니다."),
    ("단지 묶음", "함께 수집할 단지 모음입니다. 한 번에 불러오거나 예약 수집에 씁니다."),
    ("즐겨찾기", "눈여겨볼 매물을 모아 두고 메모를 남깁니다."),
    ("대시보드", "방금 수집한 결과를 한눈에 요약합니다."),
    ("가격 통계", "단지별 최저·최고·평균 가격을 날짜별로 봅니다."),
    ("수집 기록", "지금까지 언제 어떤 단지를 수집했는지 보여 줍니다."),
    ("예약 수집", "매일 정한 시간에 자동으로 수집합니다. 앱이 켜져 있어야 합니다(트레이에 두어도 됩니다)."),
)

_MENUS = (
    ("파일", "데이터 백업, 백업에서 복원, 설정, 종료"),
    ("보기", "최근 본 매물, 테마 바꾸기"),
    ("수집 조건", "지금 조건 저장·불러오기, 결과 상세 필터"),
    ("알림", "원하는 가격·면적의 매물이 나오면 알려 주는 가격 알림"),
    ("도움말", "단축키와 프로그램 정보"),
)


def _palette(theme: str) -> dict[str, str]:
    is_dark = str(theme or "dark").strip().lower() != "light"
    if is_dark:
        return {
            "bg": "#0f0f1a",
            "fg": "#e8e8ef",
            "strong": "#f5f5f7",
            "muted": "#b0b0c0",
            "accent": "#fbbf24",
            "line": "#2a2a3a",
            "panel": "#1a1a26",
            "note_bg": "#241f12",
            "key_bg": "#262636",
        }
    return {
        "bg": "#f8fafc",
        "fg": "#1e293b",
        "strong": "#0f172a",
        "muted": "#64748b",
        "accent": "#0284c7",
        "line": "#e2e8f0",
        "panel": "#ffffff",
        "note_bg": "#eff6ff",
        "key_bg": "#f1f5f9",
    }


def _section(title: str) -> str:
    return f'<h2>{escape(title)}</h2>'


def _steps(c: dict[str, str]) -> str:
    rows = []
    for index, (title, desc) in enumerate(_QUICK_START, start=1):
        rows.append(
            "<tr>"
            f'<td width="44" valign="top" style="padding: 14px 0 14px 4px; border-bottom: 1px solid {c["line"]};'
            f' font-size: 24px; font-weight: 700; color: {c["accent"]};">{index}</td>'
            f'<td valign="top" style="padding: 14px 8px 14px 0; border-bottom: 1px solid {c["line"]};">'
            f'<span style="font-size: 14px; font-weight: 700; color: {c["strong"]};">{escape(title)}</span><br>'
            f'<span style="color: {c["muted"]};">{desc}</span>'
            "</td></tr>"
        )
    return f'<table width="100%" cellspacing="0" cellpadding="0">{"".join(rows)}</table>'


def _note(c: dict[str, str], html: str) -> str:
    return (
        f'<table width="100%" cellspacing="0" cellpadding="12" bgcolor="{c["note_bg"]}" style="margin-top: 12px;">'
        f'<tr><td style="color: {c["fg"]};">{html}</td></tr></table>'
    )


def _two_column(c: dict[str, str], rows, *, first_width: int, key_style: bool = False) -> str:
    out = []
    for left, right in rows:
        if key_style:
            right_html = (
                f'<span style="background-color: {c["key_bg"]}; color: {c["strong"]};'
                f' font-family: Consolas, monospace;">&nbsp;{escape(right)}&nbsp;</span>'
            )
            left_html = f'<span style="color: {c["fg"]};">{escape(left)}</span>'
        else:
            left_html = f'<span style="font-weight: 700; color: {c["strong"]};">{escape(left)}</span>'
            right_html = f'<span style="color: {c["muted"]};">{right}</span>'
        out.append(
            "<tr>"
            f'<td width="{first_width}" valign="top" style="padding: 9px 12px 9px 4px;'
            f' border-bottom: 1px solid {c["line"]};">{left_html}</td>'
            f'<td valign="top" style="padding: 9px 4px; border-bottom: 1px solid {c["line"]};">{right_html}</td>'
            "</tr>"
        )
    return f'<table width="100%" cellspacing="0" cellpadding="0">{"".join(out)}</table>'


def _bullets(c: dict[str, str], items) -> str:
    rows = "".join(
        "<tr>"
        f'<td width="20" valign="top" style="padding: 5px 0 5px 4px; color: {c["accent"]};">•</td>'
        f'<td valign="top" style="padding: 5px 4px; color: {c["muted"]};">{item}</td>'
        "</tr>"
        for item in items
    )
    return f'<table width="100%" cellspacing="0" cellpadding="0">{rows}</table>'


def build_guide_html(theme: str = "dark") -> str:
    """Return full HTML document with colors that work on dark and light surfaces."""
    c = _palette(theme)
    body = "".join(
        (
            f'<p style="color: {c["muted"]}; margin-top: 0;">'
            "처음이라면 아래 네 단계만 따라 하면 됩니다. 나머지는 필요할 때 찾아보세요.</p>",
            _section("빠른 시작 가이드"),
            _steps(c),
            _note(
                c,
                "수집 속도를 너무 빠르게 하면 네이버에서 잠시 접속을 막을 수 있습니다. "
                "<b>보통</b> 또는 그보다 느리게 쓰는 것을 권장합니다.",
            ),
            _section("지역 단위로 찾기"),
            f'<p style="color: {c["muted"]};">단지 이름을 몰라도 됩니다. <b>지도로 찾기</b> 화면의 '
            "<b>지역 찾기</b>에서 동·구 이름을 고르고 <b>탐색 시작</b>을 누르면 그 주변의 단지와 매물을 찾아 줍니다. "
            "<b>주변까지 넓히기</b> 단계를 올리면 더 넓은 범위를 훑지만 시간이 더 걸립니다.</p>",
            _section("결과 살펴보기"),
            _bullets(c, _RESULT_TIPS),
            _section("설정"),
            _two_column(c, _SETTINGS_NOTES, first_width=150),
            _section("단축키"),
            _two_column(c, _SHORTCUTS, first_width=220, key_style=True),
            _section("화면 안내 (왼쪽 메뉴)"),
            _two_column(c, _SCREENS, first_width=110),
            _section("메뉴 안내"),
            _two_column(c, _MENUS, first_width=110),
        )
    )
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
body {{
    font-family: 'Pretendard', 'Segoe UI', 'Malgun Gothic', sans-serif;
    font-size: 13px;
    color: {c['fg']};
    background-color: {c['bg']};
}}
h2 {{
    font-size: 16px;
    font-weight: 700;
    color: {c['strong']};
    margin-top: 28px;
    margin-bottom: 8px;
}}
p {{ margin-top: 6px; margin-bottom: 6px; }}
b {{ color: {c['strong']}; font-weight: 700; }}
</style>
</head>
<body>
<table width="760" cellspacing="0" cellpadding="0"><tr><td>
{body}
</td></tr></table>
</body>
</html>
"""
