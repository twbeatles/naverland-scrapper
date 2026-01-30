import time
import random
from typing import Optional
from urllib.error import URLError, HTTPError
from socket import timeout as SocketTimeout
from PyQt6.QtCore import QThread, QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication

from src.utils.logger import get_logger

class NetworkErrorHandler:
    """네트워크 오류 처리 (v13.0)"""
    
    RECOVERABLE_ERROR_TYPES = (
        ConnectionError, TimeoutError, ConnectionResetError,
        URLError, HTTPError, SocketTimeout
    )
    
    @classmethod
    def is_recoverable(cls, error: Exception) -> bool:
        """복구 가능한 오류인지 확인"""
        if isinstance(error, cls.RECOVERABLE_ERROR_TYPES):
            return True
        
        error_str = str(error).lower()
        recoverable_patterns = [
            "connection", "timeout", "network", "socket",
            "temporary", "unavailable", "서버", "연결"
        ]
        return any(pattern in error_str for pattern in recoverable_patterns)
    
    @classmethod
    def get_wait_time(cls, error: Exception, attempt: int) -> float:
        """오류 타입과 시도 횟수에 따른 대기 시간 계산 (지수 백오프)"""
        base_delay = 2.0
        max_delay = 60.0
        
        # 지수 백오프: 2^attempt * base_delay + 랜덤 jitter
        delay = min(base_delay * (2 ** attempt), max_delay)
        jitter = random.uniform(0, delay * 0.3)
        
        return delay + jitter

class RetryHandler:
    """크롤링 재시도 핸들러 (v13.0)"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 2.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self._logger = get_logger('RetryHandler')
    
    def execute_with_retry(self, func, *args, **kwargs):
        """지수 백오프로 재시도"""
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                
                if not NetworkErrorHandler.is_recoverable(e):
                    self._logger.error(f"복구 불가능한 오류: {e}")
                    raise
                
                if attempt < self.max_retries:
                    wait_time = NetworkErrorHandler.get_wait_time(e, attempt)
                    
                    if self.is_rate_limited(e):
                        wait_time = max(wait_time, 30)  # Rate limit시 최소 30초 대기
                        self._logger.warning(f"Rate limit 감지! {wait_time}초 대기 후 재시도...")
                    else:
                        self._logger.warning(f"오류 발생, {wait_time:.1f}초 후 재시도 ({attempt+1}/{self.max_retries}): {e}")
                    
                    # NON-BLOCKING WAIT FIX
                    app_instance = QApplication.instance()
                    if app_instance and QThread.currentThread() == app_instance.thread():
                        self._logger.debug(f"Main thread detected. Using QEventLoop for wait of {wait_time}s")
                        loop = QEventLoop()
                        QTimer.singleShot(int(wait_time * 1000), loop.quit)
                        loop.exec()
                    else:
                        time.sleep(wait_time)
        
        raise last_error if last_error else Exception("알 수 없는 오류")
    
    def is_rate_limited(self, error) -> bool:
        """Rate Limit 감지"""
        error_str = str(error).lower()
        rate_limit_indicators = [
            "429", "too many requests", "rate limit", 
            "접속이 차단", "일시적으로 사용", "잠시 후"
        ]
        return any(indicator in error_str for indicator in rate_limit_indicators)
