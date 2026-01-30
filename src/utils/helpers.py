<<<<<<< HEAD
from datetime import datetime
import winreg
import re

class PriceConverter:
    @staticmethod
    def to_int(price_str):
        if not price_str: return 0
        price_str = str(price_str).replace(",", "").replace(" ", "").strip()
        total = 0
        if "억" in price_str:
            parts = price_str.split("억")
            try: total += int(float(parts[0])) * 10000
            except (ValueError, TypeError): pass
            if len(parts) > 1 and parts[1]:
                remain = parts[1].replace("만", "").strip()
                if remain:
                    try: total += int(float(remain))
                    except (ValueError, TypeError): pass
        elif "만" in price_str:
            try: total = int(float(price_str.replace("만", "").strip()))
            except (ValueError, TypeError): pass
        else:
            try: total = int(float(price_str))
            except (ValueError, TypeError): pass
        return total
    
    @staticmethod
    def to_string(price_int):
        if price_int >= 10000:
            uk, man = price_int // 10000, price_int % 10000
            return f"{uk}억 {man:,}만" if man else f"{uk}억"
        elif price_int > 0:
            return f"{price_int:,}만"
        return "0"

class AreaConverter:
    PYEONG_RATIO = 0.3025
    @classmethod
    def sqm_to_pyeong(cls, sqm): return round(sqm * cls.PYEONG_RATIO, 1)
    @classmethod
    def pyeong_to_sqm(cls, pyeong): return round(pyeong / cls.PYEONG_RATIO, 2)

class DateTimeHelper:
    @staticmethod
    def now_string(fmt="%Y-%m-%d %H:%M:%S"): return datetime.now().strftime(fmt)
    @staticmethod
    def file_timestamp(): return datetime.now().strftime("%Y%m%d_%H%M%S")

class PricePerPyeongCalculator:
    """평당가 계산기 (v12.0)"""
    
    @staticmethod
    def calculate(price_int: int, pyeong: float) -> int:
        """평당가 계산 (만원 단위)"""
        if pyeong <= 0 or price_int <= 0:
            return 0
        return int(price_int / pyeong)
    
    @staticmethod
    def format(price_per_pyeong: int) -> str:
        """평당가 문자열 포맷팅"""
        if price_per_pyeong <= 0:
            return "-"
        return PriceConverter.to_string(price_per_pyeong) + "/평"

def get_complex_url(complex_id):
    """단지 URL 생성"""
    return f"https://new.land.naver.com/complexes/{complex_id}"

def get_article_url(complex_id, article_id):
    """매물상세 URL 생성"""
    return f"https://new.land.naver.com/complexes/{complex_id}?articleId={article_id}"

class ChromeParamHelper:
    @staticmethod
    def get_chrome_major_version():
        """레지스트리에서 설치된 Chrome의 메이저 버전을 가져옵니다."""
        try:
            # 윈도우 레지스트리 경로
            key_path = r"SOFTWARE\Google\Chrome\BLBeacon"
            
            # 레지스트리 열기 (HKEY_CURRENT_USER 우선 확인)
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
            except FileNotFoundError:
                # 없으면 HKEY_LOCAL_MACHINE 확인
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            
            # 버전 값 읽기
            version, _ = winreg.QueryValueEx(key, "version")
            winreg.CloseKey(key)
            
            # 메이저 버전 추출
            major_version = int(version.split('.')[0])
            return major_version
        except Exception as e:
            # 실패 시 로그 출력 또는 None 반환 (호출 측에서 처리)
            # print(f"Chrome version detection failed: {e}")
            return None

=======
from datetime import datetime
import winreg
import re

class PriceConverter:
    @staticmethod
    def to_int(price_str):
        if not price_str: return 0
        price_str = str(price_str).replace(",", "").replace(" ", "").strip()
        total = 0
        if "억" in price_str:
            parts = price_str.split("억")
            try: total += int(float(parts[0])) * 10000
            except (ValueError, TypeError): pass
            if len(parts) > 1 and parts[1]:
                remain = parts[1].replace("만", "").strip()
                if remain:
                    try: total += int(float(remain))
                    except (ValueError, TypeError): pass
        elif "만" in price_str:
            try: total = int(float(price_str.replace("만", "").strip()))
            except (ValueError, TypeError): pass
        else:
            try: total = int(float(price_str))
            except (ValueError, TypeError): pass
        return total
    
    @staticmethod
    def to_string(price_int):
        if price_int >= 10000:
            uk, man = price_int // 10000, price_int % 10000
            return f"{uk}억 {man:,}만" if man else f"{uk}억"
        elif price_int > 0:
            return f"{price_int:,}만"
        return "0"

class AreaConverter:
    PYEONG_RATIO = 0.3025
    @classmethod
    def sqm_to_pyeong(cls, sqm): return round(sqm * cls.PYEONG_RATIO, 1)
    @classmethod
    def pyeong_to_sqm(cls, pyeong): return round(pyeong / cls.PYEONG_RATIO, 2)

class DateTimeHelper:
    @staticmethod
    def now_string(fmt="%Y-%m-%d %H:%M:%S"): return datetime.now().strftime(fmt)
    @staticmethod
    def file_timestamp(): return datetime.now().strftime("%Y%m%d_%H%M%S")

class PricePerPyeongCalculator:
    """평당가 계산기 (v12.0)"""
    
    @staticmethod
    def calculate(price_int: int, pyeong: float) -> int:
        """평당가 계산 (만원 단위)"""
        if pyeong <= 0 or price_int <= 0:
            return 0
        return int(price_int / pyeong)
    
    @staticmethod
    def format(price_per_pyeong: int) -> str:
        """평당가 문자열 포맷팅"""
        if price_per_pyeong <= 0:
            return "-"
        return PriceConverter.to_string(price_per_pyeong) + "/평"

def get_complex_url(complex_id):
    """단지 URL 생성"""
    return f"https://new.land.naver.com/complexes/{complex_id}"

def get_article_url(complex_id, article_id):
    """매물상세 URL 생성"""
    return f"https://new.land.naver.com/complexes/{complex_id}?articleId={article_id}"

class ChromeParamHelper:
    @staticmethod
    def get_chrome_major_version():
        """레지스트리에서 설치된 Chrome의 메이저 버전을 가져옵니다."""
        try:
            # 윈도우 레지스트리 경로
            key_path = r"SOFTWARE\Google\Chrome\BLBeacon"
            
            # 레지스트리 열기 (HKEY_CURRENT_USER 우선 확인)
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
            except FileNotFoundError:
                # 없으면 HKEY_LOCAL_MACHINE 확인
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            
            # 버전 값 읽기
            version, _ = winreg.QueryValueEx(key, "version")
            winreg.CloseKey(key)
            
            # 메이저 버전 추출
            major_version = int(version.split('.')[0])
            return major_version
        except Exception as e:
            # 실패 시 로그 출력 또는 None 반환 (호출 측에서 처리)
            # print(f"Chrome version detection failed: {e}")
            return None

>>>>>>> d9c1bab01fe7f0174c099636906ac082e1c1c62b
