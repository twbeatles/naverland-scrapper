
import sys
import io
import traceback
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

from src.ui.window import RealEstateApp
from src.utils.logger import setup_logger, get_logger
from src.utils.helpers import DateTimeHelper
from src.config import APP_TITLE, BASE_DIR, DATA_DIR, DB_PATH, LOG_DIR

def main():
    """메인 진입점 (v13.1 - 로깅 개선)"""
    import multiprocessing
    multiprocessing.freeze_support()
    
    # Windows Console UTF-8 Encoding
    if sys.platform == 'win32':
        try:
            if hasattr(sys.stdout, 'buffer'):
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            if hasattr(sys.stderr, 'buffer'):
                sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
        except (AttributeError, OSError):
            pass
    
    # 필수 디렉토리 생성
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    # 로거 초기화 (파일 로깅 포함)
    logger = setup_logger(log_dir=LOG_DIR)
    
    logger.info("=" * 60)
    logger.info(f"  {APP_TITLE}")
    logger.info("=" * 60)
    logger.info(f"시작 시간: {DateTimeHelper.now_string()}")
    logger.info(f"기본 디렉토리: {BASE_DIR}")
    logger.info(f"데이터 디렉토리: {DATA_DIR}")
    logger.info(f"DB 파일: {DB_PATH}")
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    font = QFont("Malgun Gothic", 9)
    app.setFont(font)
    
    app.setQuitOnLastWindowClosed(False)
    
    try:
        logger.info("메인 윈도우 생성 중...")
        window = RealEstateApp()
        logger.info("메인 윈도우 생성 완료")
        window.show()
        logger.info("윈도우 표시 완료")
    except Exception as e:
        logger.critical(f"메인 윈도우 생성 실패: {e}")
        logger.critical(traceback.format_exc())
        sys.exit(1)
    
    code = app.exec()
    logger.info(f"=== 종료 (code: {code}) ===")
    sys.exit(code)

if __name__ == "__main__":
    main()

