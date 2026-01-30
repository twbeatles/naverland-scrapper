"""
Toast 알림 위젯 (v14.0)
- 페이드 인/아웃 애니메이션
- 슬라이드 효과
- 비침습적 알림
"""
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from src.utils.logger import get_logger

logger = get_logger("Toast")
from PyQt6.QtGui import QFont


class ToastWidget(QWidget):
    """v14.0: 비침습적 Toast 알림 위젯 (애니메이션 지원)"""
    
    TOAST_TYPES = {
        "success": {"bg": "rgba(34, 197, 94, 0.95)", "icon": "✅", "border": "#22c55e"},
        "error": {"bg": "rgba(239, 68, 68, 0.95)", "icon": "❌", "border": "#ef4444"},
        "warning": {"bg": "rgba(245, 158, 11, 0.95)", "icon": "⚠️", "border": "#f59e0b"},
        "info": {"bg": "rgba(59, 130, 246, 0.95)", "icon": "ℹ️", "border": "#3b82f6"},
    }
    
    def __init__(self, message: str, toast_type: str = "info", parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.Tool | 
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        self._type = toast_type
        self._message = message
        self._setup_ui()
        self._setup_animations()
    
    def _setup_ui(self):
        """UI 구성"""
        color_info = self.TOAST_TYPES.get(self._type, self.TOAST_TYPES["info"])
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(12)
        
        # 아이콘
        icon_label = QLabel(color_info["icon"])
        icon_label.setStyleSheet("font-size: 22px;")
        layout.addWidget(icon_label)
        
        # 메시지
        msg_label = QLabel(self._message)
        msg_label.setStyleSheet(
            "color: white; font-size: 13px; font-weight: 600; padding: 0;"
        )
        msg_label.setWordWrap(True)
        msg_label.setFont(QFont("Malgun Gothic", 10))
        layout.addWidget(msg_label, 1)
        
        # 스타일 적용
        self.setStyleSheet(f"""
            ToastWidget {{
                background-color: {color_info["bg"]};
                border-radius: 12px;
                border: 1px solid {color_info["border"]};
            }}
        """)
        
        self.setMinimumWidth(320)
        self.setMaximumWidth(500)
        self.adjustSize()
    
    def _setup_animations(self):
        """애니메이션 설정"""
        # 페이드 효과용 Opacity Effect
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0)  # 초기 투명
        
        # 페이드 인 애니메이션
        self.fade_in_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in_anim.setDuration(300)
        self.fade_in_anim.setStartValue(0)
        self.fade_in_anim.setEndValue(1)
        self.fade_in_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # 페이드 아웃 애니메이션
        self.fade_out_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out_anim.setDuration(400)
        self.fade_out_anim.setStartValue(1)
        self.fade_out_anim.setEndValue(0)
        self.fade_out_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self.fade_out_anim.finished.connect(self._on_fade_out_finished)
        
        # 슬라이드 인 애니메이션 (위치)
        self.slide_in_anim = QPropertyAnimation(self, b"pos")
        self.slide_in_anim.setDuration(300)
        self.slide_in_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # 자동 닫기 타이머
        self.auto_close_timer = QTimer(self)
        self.auto_close_timer.setSingleShot(True)
        self.auto_close_timer.timeout.connect(self.fade_out)
    
    def show_toast(self, duration: int = 3500):
        """Toast 표시 (애니메이션과 함께)"""
        # 초기 위치 설정 (약간 위에서 시작)
        final_pos = self.pos()
        start_pos = QPoint(final_pos.x(), final_pos.y() - 30)
        
        self.slide_in_anim.setStartValue(start_pos)
        self.slide_in_anim.setEndValue(final_pos)
        
        self.show()
        self.raise_()
        
        # 애니메이션 시작
        self.fade_in_anim.start()
        self.slide_in_anim.start()
        
        # 자동 닫기 타이머
        self.auto_close_timer.start(duration)
    
    def fade_out(self):
        """페이드 아웃"""
        self.auto_close_timer.stop()
        self.fade_out_anim.start()
    
    def _on_fade_out_finished(self):
        """페이드 아웃 완료 시"""
        self.close()
        if self.parent():
            try:
                self.parent().toast_widgets.remove(self)
                self.parent()._reposition_toasts()
            except (AttributeError, ValueError) as e:
                logger.debug(f"Toast 정리 실패 (무시): {e}")
        self.deleteLater()
    
    def enterEvent(self, event):
        """마우스 호버 시 타이머 일시 정지"""
        self.auto_close_timer.stop()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """마우스 떠날 시 타이머 재시작"""
        self.auto_close_timer.start(1500)  # 호버 후 1.5초 뒤 닫힘
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        """클릭 시 즉시 닫기"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.fade_out()
        super().mousePressEvent(event)
