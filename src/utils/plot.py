import platform
from matplotlib import font_manager, rc
from src.utils.logger import get_logger

logger = get_logger("Plot")

def setup_korean_font():
    """Matplotlib 한국어 폰트 설정"""
    try:
        system_name = platform.system()
        
        if system_name == "Windows":
            # 윈도우: 맑은 고딕
            font_name = "Malgun Gothic"
        elif system_name == "Darwin":
            # 맥: 애플고딕
            font_name = "AppleGothic"
        else:
            # 리눅스: 나눔고딕 (설치 필요)
            font_name = "NanumGothic"
            
        # 폰트 설정
        rc('font', family=font_name)
        
        # 마이너스 기호 깨짐 방지
        rc('axes', unicode_minus=False)
        
        logger.info(f"Matplotlib Font set to: {font_name}")
        
    except Exception as e:
        logger.warning(f"Font setup failed: {e}")
