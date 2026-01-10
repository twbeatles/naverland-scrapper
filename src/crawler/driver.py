import logging
import random
try:
    import undetected_chromedriver as uc
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False

from src.utils.logger import get_logger

def get_random_user_agent():
    """랜덤 User-Agent 반환 (v13.1)"""
    from src.config import USER_AGENTS
    return random.choice(USER_AGENTS)

def get_proxy():
    """프록시 반환 (설정된 경우) (v13.1)"""
    from src.config import PROXY_LIST, PROXY_ROTATION_ENABLED
    if PROXY_ROTATION_ENABLED and PROXY_LIST:
        return random.choice(PROXY_LIST)
    return None

def initialize_driver():
    """Chrome Driver 초기화 (v13.1 - User-Agent 로테이션, 프록시 지원)"""
    if not UC_AVAILABLE:
        raise ImportError("undetected-chromedriver가 설치되지 않았습니다.")
        
    logger = get_logger("Driver")
    logger.info("Chrome 드라이버 초기화 중...")
    
    # 랜덤 User-Agent 선택
    user_agent = get_random_user_agent()
    logger.debug(f"User-Agent: {user_agent[:50]}...")
    
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"--user-agent={user_agent}")
    options.add_argument("--log-level=3")
    
    # 프록시 설정 (활성화된 경우)
    proxy = get_proxy()
    if proxy:
        options.add_argument(f"--proxy-server={proxy}")
        logger.info(f"프록시 사용: {proxy}")
    
    try:
        driver = uc.Chrome(options=options, version_main=None)
        logger.info("Chrome 드라이버 초기화 성공")
        return driver
    except Exception as e:
        logger.warning(f"Headless 실패, 일반 모드 시도... ({e})")
        options2 = uc.ChromeOptions()
        options2.add_argument("--no-sandbox")
        options2.add_argument("--disable-dev-shm-usage")
        options2.add_argument("--disable-gpu")
        options2.add_argument("--window-size=1920,1080")
        options2.add_argument("--start-minimized")
        options2.add_argument(f"--user-agent={user_agent}")
        if proxy:
            options2.add_argument(f"--proxy-server={proxy}")
        try:
            driver = uc.Chrome(options=options2, version_main=None)
            logger.info("Chrome 드라이버 초기화 성공 (일반 모드)")
            return driver
        except Exception as e2:
            logger.error(f"드라이버 초기화 최종 실패: {e2}")
            raise e2

def setup_driver_settings(driver, page_load_timeout=30, implicit_wait=5):
    """드라이버 추가 설정"""
    driver.set_page_load_timeout(page_load_timeout)
    driver.implicitly_wait(implicit_wait)
    return driver

def cleanup_driver(driver, force_kill=True):
    """
    드라이버 안전 종료 (v13.1)
    - 정상 종료 시도 후 실패 시 프로세스 강제 종료
    """
    logger = get_logger("Driver")
    
    if driver is None:
        return True
    
    # 1. 정상 종료 시도
    try:
        driver.quit()
        logger.info("Chrome 드라이버 정상 종료 완료")
        return True
    except Exception as e:
        logger.warning(f"드라이버 정상 종료 실패: {e}")
    
    # 2. 강제 종료 시도 (Windows)
    if force_kill:
        try:
            import subprocess
            import sys
            
            if sys.platform == 'win32':
                # Chrome 및 ChromeDriver 프로세스 강제 종료
                subprocess.run(
                    ['taskkill', '/F', '/IM', 'chromedriver.exe', '/T'],
                    capture_output=True, timeout=5
                )
                # headless chrome 프로세스도 정리
                subprocess.run(
                    ['taskkill', '/F', '/IM', 'chrome.exe', '/FI', 'WINDOWTITLE eq ""', '/T'],
                    capture_output=True, timeout=5
                )
                logger.info("Chrome 관련 프로세스 강제 종료 완료")
                return True
            else:
                # Linux/Mac
                import os
                import signal
                if hasattr(driver, 'service') and driver.service.process:
                    os.kill(driver.service.process.pid, signal.SIGKILL)
                    logger.info("드라이버 프로세스 강제 종료 완료")
                    return True
        except Exception as e2:
            logger.error(f"강제 종료도 실패: {e2}")
    
    return False
