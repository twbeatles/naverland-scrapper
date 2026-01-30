<<<<<<< HEAD
import time
from src.utils.logger import get_logger
from src.utils.error_handler import NetworkErrorHandler

class RetryHandler:
    """크롤링 재시도 핸들러 (v14.0 - Selenium 예외 강화)"""
    
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
=======
import time
from src.utils.logger import get_logger
from src.utils.error_handler import NetworkErrorHandler

class RetryHandler:
    """크롤링 재시도 핸들러 (v14.0 - Selenium 예외 강화)"""
    
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
>>>>>>> d9c1bab01fe7f0174c099636906ac082e1c1c62b
