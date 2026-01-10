import sys
import os
from pathlib import Path

def get_base_dir():
    """실행 파일의 디렉토리를 안정적으로 반환 (데이터 저장용)"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(os.path.dirname(os.path.abspath(__file__))).parent.parent

def get_resource_path(relative_path):
    """번들된 리소스 파일의 경로를 반환 (onefile 패키징 지원)"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def ensure_directories(data_dir, log_dir):
    """필수 디렉토리 생성"""
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        print(f"[FATAL] 디렉토리 생성 실패: {e}")
        return False
