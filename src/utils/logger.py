import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
# from src.utils.paths import LOG_DIR  <-- Removed to fix circular import

def setup_logger(name="realestate_crawler"):
    from src.utils.paths import LOG_DIR
    logger = logging.getLogger(name)
    if logger.handlers: return logger
    logger.setLevel(logging.DEBUG)
    
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))
    logger.addHandler(ch)
    
    # LOG_DIR should have been created by ensure_directories called in main
    log_file = LOG_DIR / f"crawler_{datetime.now().strftime('%Y%m%d')}.log"
    
    try:
        fh = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s'))
        logger.addHandler(fh)
    except Exception as e:
        logger.error(f"로그 파일 핸들러 생성 실패: {e}")
        
    return logger

def get_logger(name=None):
    return logging.getLogger(f"realestate_crawler.{name}" if name else "realestate_crawler")

def cleanup_old_logs(days=30):
    """지정 일수 이상 오래된 로그 파일 정리"""
    log_cleanup_logger = get_logger("LogCleanup")
    from src.utils.paths import LOG_DIR
    try:
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        removed_count = 0
        if not LOG_DIR.exists():
            return

        for log_file in LOG_DIR.glob("crawler_*.log*"):
            try:
                # crawler_20240101.log
                file_date_str = log_file.stem.replace("crawler_", "").split(".")[0]
                # Handle cases where log file name might be slightly different or rotated
                if not file_date_str.isdigit():
                    continue
                    
                file_date = datetime.strptime(file_date_str, "%Y%m%d")
                if file_date < cutoff_date:
                    log_file.unlink()
                    removed_count += 1
            except (ValueError, OSError) as e:
                continue  # 파싱 실패 시 무시
        if removed_count > 0:
            log_cleanup_logger.info(f"오래된 로그 파일 {removed_count}개 삭제")
    except Exception as e:
        log_cleanup_logger.warning(f"로그 정리 중 오류: {e}")
