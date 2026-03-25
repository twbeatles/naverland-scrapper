import re
from datetime import datetime
from pathlib import Path
import os
import winreg


def _normalize_asset_type(asset_type: str) -> str:
    token = str(asset_type or "APT").strip().upper()
    return token if token in {"APT", "VL"} else "APT"


def build_complex_url(complex_id, *, asset_type="APT", preferred_family="new"):
    """단지 URL 생성."""
    cid = str(complex_id or "").strip()
    if not cid:
        return ""

    family = str(preferred_family or "new").strip().lower()
    normalized_asset = _normalize_asset_type(asset_type)
    path = "houses" if normalized_asset == "VL" else "complexes"

    if family == "m":
        return f"https://m.land.naver.com/{path}/{cid}"
    return f"https://new.land.naver.com/{path}/{cid}"


def build_article_url(
    article_id,
    *,
    complex_id=None,
    asset_type="APT",
    preferred_family="fin",
):
    """매물상세 URL 생성."""
    aid = str(article_id or "").strip()
    if not aid:
        return ""

    family = str(preferred_family or "fin").strip().lower()
    normalized_asset = _normalize_asset_type(asset_type)
    if family == "m":
        return f"https://m.land.naver.com/article/info/{aid}"
    if family == "new":
        cid = str(complex_id or "").strip()
        if not cid:
            return ""
        path = "houses" if normalized_asset == "VL" else "complexes"
        return f"https://new.land.naver.com/{path}/{cid}?articleId={aid}"
    return f"https://fin.land.naver.com/articles/{aid}"

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

    @staticmethod
    def to_signed_string(price_int: int, zero_text: str = "") -> str:
        try:
            value = int(price_int)
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            return f"+{PriceConverter.to_string(value)}"
        if value < 0:
            return f"-{PriceConverter.to_string(abs(value))}"
        return zero_text

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

def get_complex_url(complex_id, asset_type="APT", preferred_family="new"):
    """호환용 단지 URL 생성."""
    return build_complex_url(
        complex_id,
        asset_type=asset_type,
        preferred_family=preferred_family,
    )


def get_article_url(complex_id, article_id, asset_type="APT", preferred_family="fin"):
    """호환용 매물상세 URL 생성."""
    return build_article_url(
        article_id,
        complex_id=complex_id,
        asset_type=asset_type,
        preferred_family=preferred_family,
    )

class ChromeParamHelper:
    @staticmethod
    def _iter_registry_app_paths():
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                key = winreg.OpenKey(root, key_path)
                try:
                    value, _ = winreg.QueryValueEx(key, "")
                finally:
                    winreg.CloseKey(key)
                if value:
                    yield str(value)
            except FileNotFoundError:
                continue
            except Exception:
                continue

    @staticmethod
    def _iter_candidate_paths():
        seen = set()
        for candidate in ChromeParamHelper._iter_registry_app_paths():
            token = str(candidate or "").strip()
            if token and token not in seen:
                seen.add(token)
                yield token

        roots = [
            os.environ.get("PROGRAMFILES", ""),
            os.environ.get("PROGRAMFILES(X86)", ""),
            os.environ.get("LOCALAPPDATA", ""),
        ]
        suffixes = [
            Path("Google/Chrome/Application/chrome.exe"),
            Path("Google/Chrome Beta/Application/chrome.exe"),
            Path("Google/Chrome SxS/Application/chrome.exe"),
        ]
        for root in roots:
            if not root:
                continue
            for suffix in suffixes:
                candidate = str(Path(root) / suffix)
                if candidate not in seen:
                    seen.add(candidate)
                    yield candidate

        for candidate in (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ):
            if candidate not in seen:
                seen.add(candidate)
                yield candidate

    @staticmethod
    def get_chrome_executable_path():
        """설치된 Chrome 실행 파일 경로를 반환합니다."""
        for candidate in ChromeParamHelper._iter_candidate_paths():
            try:
                if Path(candidate).exists():
                    return str(Path(candidate))
            except OSError:
                continue
        return ""

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

