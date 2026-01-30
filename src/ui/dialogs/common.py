<<<<<<< HEAD
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton
from src.utils.constants import APP_VERSION

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ℹ️ 정보")
        self.setMinimumSize(500, 500)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(f"""
        <div style="text-align: center; padding: 20px;">
            <h1 style="color: #3b82f6; margin-bottom: 5px;">🏠 네이버 부동산 크롤러</h1>
            <h2 style="margin-top: 0;">Pro Plus {APP_VERSION}</h2>
            <p style="color: #64748b; font-size: 14px;">Analytics & Stability 업데이트</p>
        </div>
        
        <h3 style="color: #3b82f6; border-bottom: 2px solid #3b82f6; padding-bottom: 5px;">🆕 {APP_VERSION} 업데이트</h3>
        <ul>
            <li>📊 <b>시세 분석 대시보드</b> - 통계 카드, 차트, 트렌드 분석</li>
            <li>🃏 <b>카드 뷰 모드</b> - 시각적인 매물 카드 형태 조회</li>
            <li>⭐ <b>즐겨찾기 탭</b> - 관심 매물 별도 관리</li>
            <li>🔄 <b>안정성 강화</b> - 자동 재시도, Rate Limit 감지</li>
            <li>🕐 <b>최근 본 매물</b> - 조회 히스토리 자동 저장</li>
        </ul>
        
        <h3 style="color: #22c55e; border-bottom: 2px solid #22c55e; padding-bottom: 5px;">✨ 핵심 기능</h3>
        <ul>
            <li>📊 다중 단지 동시 크롤링</li>
            <li>💰 평당가 계산 및 정렬</li>
            <li>📝 매물 즐겨찾기 및 메모</li>
            <li>💾 Excel/CSV/JSON 내보내기</li>
            <li>🆕 신규 매물 및 가격 변동 표시</li>
            <li>📈 시세 변동 추적 및 차트</li>
        </ul>
        
        <h3 style="color: #8b5cf6; border-bottom: 2px solid #8b5cf6; padding-bottom: 5px;">⌨️ 단축키</h3>
        <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
            <tr style="background-color: rgba(59, 130, 246, 0.1);">
                <td style="padding: 8px; border: 1px solid #e2e8f0;">Ctrl+R</td>
                <td style="padding: 8px; border: 1px solid #e2e8f0;">크롤링 시작</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #e2e8f0;">Ctrl+S</td>
                <td style="padding: 8px; border: 1px solid #e2e8f0;">Excel 저장</td>
            </tr>
            <tr style="background-color: rgba(59, 130, 246, 0.1);">
                <td style="padding: 8px; border: 1px solid #e2e8f0;">Ctrl+T</td>
                <td style="padding: 8px; border: 1px solid #e2e8f0;">테마 변경</td>
            </tr>
        </table>
        
        <p style="color: #64748b; margin-top: 20px; text-align: center; font-size: 12px;">
            Made with ❤️ using Claude & Gemini AI
        </p>
        """)
        layout.addWidget(browser)
        btn = QPushButton("닫기")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
=======
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton
from src.utils.constants import APP_VERSION

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ℹ️ 정보")
        self.setMinimumSize(500, 500)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(f"""
        <div style="text-align: center; padding: 20px;">
            <h1 style="color: #3b82f6; margin-bottom: 5px;">🏠 네이버 부동산 크롤러</h1>
            <h2 style="margin-top: 0;">Pro Plus {APP_VERSION}</h2>
            <p style="color: #64748b; font-size: 14px;">Analytics & Stability 업데이트</p>
        </div>
        
        <h3 style="color: #3b82f6; border-bottom: 2px solid #3b82f6; padding-bottom: 5px;">🆕 v13.0 업데이트</h3>
        <ul>
            <li>📊 <b>시세 분석 대시보드</b> - 통계 카드, 차트, 트렌드 분석</li>
            <li>🃏 <b>카드 뷰 모드</b> - 시각적인 매물 카드 형태 조회</li>
            <li>⭐ <b>즐겨찾기 탭</b> - 관심 매물 별도 관리</li>
            <li>🔄 <b>안정성 강화</b> - 자동 재시도, Rate Limit 감지</li>
            <li>🕐 <b>최근 본 매물</b> - 조회 히스토리 자동 저장</li>
        </ul>
        
        <h3 style="color: #22c55e; border-bottom: 2px solid #22c55e; padding-bottom: 5px;">✨ 핵심 기능</h3>
        <ul>
            <li>📊 다중 단지 동시 크롤링</li>
            <li>💰 평당가 계산 및 정렬</li>
            <li>📝 매물 즐겨찾기 및 메모</li>
            <li>💾 Excel/CSV/JSON 내보내기</li>
            <li>🆕 신규 매물 및 가격 변동 표시</li>
            <li>📈 시세 변동 추적 및 차트</li>
        </ul>
        
        <h3 style="color: #8b5cf6; border-bottom: 2px solid #8b5cf6; padding-bottom: 5px;">⌨️ 단축키</h3>
        <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
            <tr style="background-color: rgba(59, 130, 246, 0.1);">
                <td style="padding: 8px; border: 1px solid #e2e8f0;">Ctrl+R</td>
                <td style="padding: 8px; border: 1px solid #e2e8f0;">크롤링 시작</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #e2e8f0;">Ctrl+S</td>
                <td style="padding: 8px; border: 1px solid #e2e8f0;">Excel 저장</td>
            </tr>
            <tr style="background-color: rgba(59, 130, 246, 0.1);">
                <td style="padding: 8px; border: 1px solid #e2e8f0;">Ctrl+T</td>
                <td style="padding: 8px; border: 1px solid #e2e8f0;">테마 변경</td>
            </tr>
        </table>
        
        <p style="color: #64748b; margin-top: 20px; text-align: center; font-size: 12px;">
            Made with ❤️ using Claude & Gemini AI
        </p>
        """)
        layout.addWidget(browser)
        btn = QPushButton("닫기")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
>>>>>>> d9c1bab01fe7f0174c099636906ac082e1c1c62b
