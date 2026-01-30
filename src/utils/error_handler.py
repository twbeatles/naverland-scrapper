import random
from urllib.error import URLError, HTTPError
from socket import timeout as SocketTimeout

class NetworkErrorHandler:
    """네트워크 오류 처리 (v14.0)"""
    
    RECOVERABLE_ERROR_TYPES = (
        ConnectionError, TimeoutError, ConnectionResetError,
        URLError, HTTPError, SocketTimeout
    )
    
    # v14.0: Selenium 복구 가능 오류 패턴 추가
    RECOVERABLE_SELENIUM_PATTERNS = [
        "stale element", "no such element", "timeout",
        "session deleted", "target frame detached",
        "element not interactable", "element click intercepted"
    ]
    
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
        
        # Selenium 패턴도 확인
        all_patterns = recoverable_patterns + cls.RECOVERABLE_SELENIUM_PATTERNS
        return any(pattern in error_str for pattern in all_patterns)
    
    @classmethod
    def get_wait_time(cls, error: Exception, attempt: int) -> float:
        """오류 타입과 시도 횟수에 따른 대기 시간 계산 (지수 백오프)"""
        base_delay = 2.0
        max_delay = 60.0
        
        # 지수 백오프: 2^attempt * base_delay + 랜덤 jitter
        delay = min(base_delay * (2 ** attempt), max_delay)
        jitter = random.uniform(0, delay * 0.3)
        
        return delay + jitter
