import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logger(name="realestate_crawler", log_dir=None):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    if logger.handlers:
        return logger
        
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    
    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    # File Handler
    if log_dir:
        log_dir = Path(log_dir)
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            fh = RotatingFileHandler(
                log_dir / f"{name}.log",
                maxBytes=10*1024*1024,
                backupCount=5,
                encoding='utf-8'
            )
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(formatter)
            logger.addHandler(fh)
        except Exception as e:
            print(f"[WARN] 로그 파일 설정 실패: {e}")
            
    return logger

def get_logger(name=None):
    return logging.getLogger(name if name else "realestate_crawler")
