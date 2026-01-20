import sys
import os

# Add project root to sys.path to allow running this script directly
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

import logging
from PyQt6.QtWidgets import QApplication
from src.ui.app import RealEstateApp
from src.utils.logger import get_logger
from src.utils.plot import setup_korean_font

def main():
    # 로깅 설정
    logger = get_logger("Main")
    from src.utils.logger import cleanup_old_logs
    cleanup_old_logs()
    logger.info("애플리케이션 시작")
    
    # Matplotlib 폰트 설정
    setup_korean_font()
    
    app = QApplication(sys.argv)
    
    # 폰트 설정 (옵션)
    from PyQt6.QtGui import QFont
    font = QFont("Malgun Gothic", 10)
    app.setFont(font)
    
    window = RealEstateApp()
    window.show()
    
    try:
        sys.exit(app.exec())
    except Exception as e:
        logger.error(f"애플리케이션 종료 중 오류 발생: {e}")

if __name__ == "__main__":
    main()
