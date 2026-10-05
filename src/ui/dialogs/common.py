from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton
from src.utils.constants import APP_VERSION
from src.ui.styles import COLORS

class AboutDialog(QDialog):
    def __init__(self, parent=None, theme="dark"):
        super().__init__(parent)
        self.setWindowTitle("프로그램 정보")
        self.setMinimumSize(520, 540)
        c = COLORS[theme]
        accent = c["accent"]
        success = c["success"]
        text_secondary = c["text_secondary"]
        from src.ui.fluent.design_tokens import tint

        accent_soft = tint(accent, 0.10)
        success_soft = tint(success, 0.10)
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
            <p style="color: {text_secondary}; font-size: 13px; margin-top: 8px;">네이버 부동산 매물을 모아 보고 가격 변화를 살피는 도구</p>
        </div>
        
        <div style="background: {accent_soft}; border-radius: 12px; padding: 14px 16px; margin: 8px 12px;">
            <h3 style="color: {accent}; margin: 0 0 8px 0; font-size: 14px;">{APP_VERSION} 하이라이트</h3>
            <ul style="margin: 0; padding-left: 18px; line-height: 1.7;">
                <li><b>쉬워진 화면</b> — 단지 찾기부터 수집·저장까지 한 흐름으로</li>
                <li><b>기본·고급 설정 분리</b> — 평소 쓰는 항목만 먼저</li>
                <li><b>대시보드</b> — 수집 결과를 한눈에 요약</li>
                <li><b>카드 보기 · 즐겨찾기</b> — 눈여겨볼 매물을 빠르게 확인</li>
                <li><b>안정성</b> — 실패하면 자동으로 다시 시도</li>
            </ul>
        </div>
        
        <div style="background: {success_soft}; border-radius: 12px; padding: 14px 16px; margin: 8px 12px;">
            <h3 style="color: {success}; margin: 0 0 8px 0; font-size: 14px;">핵심 기능</h3>
            <ul style="margin: 0; padding-left: 18px; line-height: 1.7;">
                <li>여러 단지 매물을 한 번에 수집</li>
                <li>평당가 계산 및 정렬</li>
                <li>매물 즐겨찾기 및 메모</li>
                <li>엑셀·CSV 파일로 저장</li>
                <li>신규 매물 및 가격 변동 표시</li>
                <li>시세 변동 추적 및 차트</li>
            </ul>
        </div>
        
        <table style="width: 80%; border-collapse: collapse; margin: 12px auto;">
            <tr style="background-color: {accent_soft};">
                <td style="padding: 6px 12px; border-radius: 4px; font-size: 12px;">Ctrl+R</td>
                <td style="padding: 6px 12px; font-size: 12px;">수집 시작</td>
            </tr>
            <tr>
                <td style="padding: 6px 12px; font-size: 12px;">Ctrl+S</td>
                <td style="padding: 6px 12px; font-size: 12px;">엑셀로 저장</td>
            </tr>
            <tr style="background-color: {accent_soft};">
                <td style="padding: 6px 12px; font-size: 12px;">Ctrl+T</td>
                <td style="padding: 6px 12px; font-size: 12px;">테마 바꾸기</td>
            </tr>
        </table>
        
        <p style="color: {text_secondary}; margin-top: 16px; text-align: center; font-size: 11px; letter-spacing: 0.5px;">
            Built with Claude &amp; Gemini AI
        </p>
        """)
        layout.addWidget(browser)
        btn = QPushButton("닫기")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
