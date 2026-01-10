"""
UI 애니메이션 헬퍼 (v14.0)
재사용 가능한 애니메이션 유틸리티
"""

from PyQt6.QtCore import (
    QPropertyAnimation, QEasingCurve, QSequentialAnimationGroup,
    QParallelAnimationGroup, QTimer, QPoint, QRect
)
from PyQt6.QtWidgets import QWidget, QLabel, QGraphicsOpacityEffect


class AnimationHelper:
    """애니메이션 헬퍼 클래스"""
    
    @staticmethod
    def fade_in(widget: QWidget, duration: int = 300, start_opacity: float = 0.0, end_opacity: float = 1.0):
        """페이드 인 애니메이션"""
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
        
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(start_opacity)
        anim.setEndValue(end_opacity)
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        anim.start()
        
        # 애니메이션 객체 참조 유지
        widget._fade_anim = anim
        return anim
    
    @staticmethod
    def fade_out(widget: QWidget, duration: int = 300, delete_on_finish: bool = False):
        """페이드 아웃 애니메이션"""
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
        
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InQuad)
        
        if delete_on_finish:
            anim.finished.connect(widget.deleteLater)
        
        anim.start()
        widget._fade_anim = anim
        return anim
    
    @staticmethod
    def slide_in(widget: QWidget, direction: str = "right", distance: int = 50, duration: int = 350):
        """슬라이드 인 애니메이션
        
        Args:
            widget: 애니메이션 대상 위젯
            direction: 방향 ("left", "right", "up", "down")
            distance: 이동 거리 (픽셀)
            duration: 애니메이션 시간 (ms)
        """
        current_pos = widget.pos()
        
        # 시작 위치 계산
        if direction == "right":
            start = QPoint(current_pos.x() + distance, current_pos.y())
        elif direction == "left":
            start = QPoint(current_pos.x() - distance, current_pos.y())
        elif direction == "up":
            start = QPoint(current_pos.x(), current_pos.y() - distance)
        elif direction == "down":
            start = QPoint(current_pos.x(), current_pos.y() + distance)
        else:
            start = current_pos
        
        widget.move(start)
        
        anim = QPropertyAnimation(widget, b"pos")
        anim.setDuration(duration)
        anim.setStartValue(start)
        anim.setEndValue(current_pos)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        
        widget._slide_anim = anim
        return anim
    
    @staticmethod
    def slide_out(widget: QWidget, direction: str = "right", distance: int = 50, duration: int = 350, hide_on_finish: bool = True):
        """슬라이드 아웃 애니메이션"""
        current_pos = widget.pos()
        
        # 종료 위치 계산
        if direction == "right":
            end = QPoint(current_pos.x() + distance, current_pos.y())
        elif direction == "left":
            end = QPoint(current_pos.x() - distance, current_pos.y())
        elif direction == "up":
            end = QPoint(current_pos.x(), current_pos.y() - distance)
        elif direction == "down":
            end = QPoint(current_pos.x(), current_pos.y() + distance)
        else:
            end = current_pos
        
        anim = QPropertyAnimation(widget, b"pos")
        anim.setDuration(duration)
        anim.setStartValue(current_pos)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        
        if hide_on_finish:
            anim.finished.connect(widget.hide)
        
        anim.start()
        widget._slide_anim = anim
        return anim
    
    @staticmethod
    def count_up(label: QLabel, start: int, end: int, duration: int = 500, 
                 prefix: str = "", suffix: str = "", format_number: bool = True):
        """숫자 카운트업 애니메이션
        
        Args:
            label: QLabel 위젯
            start: 시작 값
            end: 종료 값
            duration: 애니메이션 시간 (ms)
            prefix: 접두사 (예: "₩")
            suffix: 접미사 (예: "건")
            format_number: 천 단위 구분자 사용 여부
        """
        steps = 30  # 프레임 수
        interval = max(1, duration // steps)
        step_value = (end - start) / steps
        current = [start]  # 클로저를 위해 리스트 사용
        
        timer = QTimer(label)
        
        def update():
            current[0] += step_value
            if (step_value > 0 and current[0] >= end) or (step_value < 0 and current[0] <= end):
                current[0] = end
                timer.stop()
            
            value = int(current[0])
            if format_number:
                text = f"{prefix}{value:,}{suffix}"
            else:
                text = f"{prefix}{value}{suffix}"
            label.setText(text)
        
        timer.timeout.connect(update)
        timer.start(interval)
        
        label._count_timer = timer
        return timer
    
    @staticmethod
    def pulse(widget: QWidget, scale_factor: float = 1.05, duration: int = 200, count: int = 2):
        """펄스 애니메이션 (확대/축소 반복)
        
        Note: QWidget의 geometry를 사용하여 크기 조정
        """
        original_rect = widget.geometry()
        
        # 확대된 크기 계산
        center = original_rect.center()
        scaled_width = int(original_rect.width() * scale_factor)
        scaled_height = int(original_rect.height() * scale_factor)
        
        scaled_rect = QRect(
            center.x() - scaled_width // 2,
            center.y() - scaled_height // 2,
            scaled_width,
            scaled_height
        )
        
        # 애니메이션 그룹 생성
        group = QSequentialAnimationGroup(widget)
        
        for _ in range(count):
            # 확대
            expand = QPropertyAnimation(widget, b"geometry")
            expand.setDuration(duration // 2)
            expand.setStartValue(original_rect)
            expand.setEndValue(scaled_rect)
            expand.setEasingCurve(QEasingCurve.Type.InOutQuad)
            group.addAnimation(expand)
            
            # 축소
            shrink = QPropertyAnimation(widget, b"geometry")
            shrink.setDuration(duration // 2)
            shrink.setStartValue(scaled_rect)
            shrink.setEndValue(original_rect)
            shrink.setEasingCurve(QEasingCurve.Type.InOutQuad)
            group.addAnimation(shrink)
        
        group.start()
        widget._pulse_anim = group
        return group
    
    @staticmethod
    def shake(widget: QWidget, amplitude: int = 10, duration: int = 500):
        """흔들기 애니메이션 (에러 표시용)"""
        original_pos = widget.pos()
        
        group = QSequentialAnimationGroup(widget)
        
        positions = [
            QPoint(original_pos.x() + amplitude, original_pos.y()),
            QPoint(original_pos.x() - amplitude, original_pos.y()),
            QPoint(original_pos.x() + amplitude // 2, original_pos.y()),
            QPoint(original_pos.x() - amplitude // 2, original_pos.y()),
            original_pos
        ]
        
        interval = duration // len(positions)
        
        current_pos = original_pos
        for target_pos in positions:
            anim = QPropertyAnimation(widget, b"pos")
            anim.setDuration(interval)
            anim.setStartValue(current_pos)
            anim.setEndValue(target_pos)
            anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
            group.addAnimation(anim)
            current_pos = target_pos
        
        group.start()
        widget._shake_anim = group
        return group
    
    @staticmethod
    def highlight(widget: QWidget, color: str = "#4a9eff", duration: int = 1000):
        """하이라이트 효과 (배경색 변화)
        
        Note: 스타일시트를 임시로 변경하므로 주의 필요
        """
        original_style = widget.styleSheet()
        
        # 하이라이트 스타일 적용
        widget.setStyleSheet(f"{original_style} background-color: {color}30;")
        
        # 일정 시간 후 복원
        def restore():
            widget.setStyleSheet(original_style)
        
        QTimer.singleShot(duration, restore)


class AnimatedValue:
    """애니메이션 가능한 값 래퍼"""
    
    def __init__(self, initial_value: float = 0.0):
        self._value = initial_value
        self._target = initial_value
        self._timer = None
    
    @property
    def value(self):
        return self._value
    
    def animate_to(self, target: float, duration: int = 300, on_update=None, on_complete=None):
        """값을 목표까지 애니메이션"""
        self._target = target
        steps = 30
        interval = max(1, duration // steps)
        step_value = (target - self._value) / steps
        
        if self._timer:
            self._timer.stop()
        
        self._timer = QTimer()
        
        def update():
            self._value += step_value
            if (step_value > 0 and self._value >= self._target) or (step_value < 0 and self._value <= self._target):
                self._value = self._target
                self._timer.stop()
                if on_complete:
                    on_complete()
            
            if on_update:
                on_update(self._value)
        
        self._timer.timeout.connect(update)
        self._timer.start(interval)
