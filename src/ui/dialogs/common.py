from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton
from src.utils.constants import APP_VERSION
from src.ui.styles import COLORS

class AboutDialog(QDialog):
    def __init__(self, parent=None, theme="dark"):
        super().__init__(parent)
        self.setWindowTitle("정보")
        self.setMinimumSize(520, 540)
        c = COLORS[theme]
        accent = c["accent"]
        success = c["success"]
        text_secondary = c["text_secondary"]
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(f"""
        <div style="text-align: center; padding: 24px 20px 10px 20px;">
            <h1 style="color: {accent}; margin-bottom: 4px; font-size: 26px;">네이버 부동산 크롤러</h1>
            <p style="margin-top: 4px;">
                <span style="background-color: {accent}; color: white; padding: 4px 14px; border-radius: 999px; font-size: 13px; font-weight: 700;">
                    Pro Plus {APP_VERSION}
                </span>
            </p>
            <p style="color: {text_secondary}; font-size: 13px; margin-top: 8px;">Fluent UI · Analytics &amp; Stability</p>
        </div>
        
        <div style="background: {accent}14; border-radius: 12px; padding: 14px 16px; margin: 8px 12px;">
            <h3 style="color: {accent}; margin: 0 0 8px 0; font-size: 14px;">{APP_VERSION} 하이라이트</h3>
            <ul style="margin: 0; padding-left: 18px; line-height: 1.7;">
                <li><b>Fluent 네비게이션</b> — 수집 / 보관함 / 분석 / 자동화</li>
                <li><b>기본·고급 설정 분리</b> — 일상 옵션만 먼저 노출</li>
                <li><b>시세 분석 대시보드</b> — 통계 카드, 차트, 트렌드</li>
                <li><b>카드 뷰 · 즐겨찾기</b> — 관심 매물 빠른 확인</li>
                <li><b>안정성</b> — 자동 재시도, Rate Limit 감지</li>
            </ul>
        </div>
        
        <div style="background: {success}14; border-radius: 12px; padding: 14px 16px; margin: 8px 12px;">
            <h3 style="color: {success}; margin: 0 0 8px 0; font-size: 14px;">✨ 핵심 기능</h3>
            <ul style="margin: 0; padding-left: 18px; line-height: 1.7;">
                <li>📊 다중 단지 동시 크롤링</li>
                <li>💰 평당가 계산 및 정렬</li>
                <li>📝 매물 즐겨찾기 및 메모</li>
                <li>💾 Excel/CSV/JSON 내보내기</li>
                <li>🆕 신규 매물 및 가격 변동 표시</li>
                <li>📈 시세 변동 추적 및 차트</li>
            </ul>
        </div>
        
        <table style="width: 80%; border-collapse: collapse; margin: 12px auto;">
            <tr style="background-color: {accent}14;">
                <td style="padding: 6px 12px; border-radius: 4px; font-size: 12px;">Ctrl+R</td>
                <td style="padding: 6px 12px; font-size: 12px;">크롤링 시작</td>
            </tr>
            <tr>
                <td style="padding: 6px 12px; font-size: 12px;">Ctrl+S</td>
                <td style="padding: 6px 12px; font-size: 12px;">Excel 저장</td>
            </tr>
            <tr style="background-color: {accent}14;">
                <td style="padding: 6px 12px; font-size: 12px;">Ctrl+T</td>
                <td style="padding: 6px 12px; font-size: 12px;">테마 변경</td>
            </tr>
        </table>
        
        <p style="color: {text_secondary}; margin-top: 16px; text-align: center; font-size: 11px; letter-spacing: 0.5px;">
            Built with ❤️ using Claude &amp; Gemini AI
        </p>
        """)
        layout.addWidget(browser)
        btn = QPushButton("닫기")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
