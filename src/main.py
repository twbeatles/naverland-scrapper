import locale
import os
import sys
from pathlib import Path

# Add project root to sys.path to allow running this script directly.
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.utils.logger import cleanup_old_logs, get_logger, setup_logger
from src.utils.paths import ensure_directories
from src.utils.preflight import run_preflight_checks


def _configure_stdio_encoding() -> None:
    """Align stdout/stderr encoding with the current terminal on Windows."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue

        encoding = None
        try:
            fileno = stream.fileno()
            encoding = os.device_encoding(fileno)
        except Exception:
            encoding = None

        if not encoding:
            encoding = locale.getpreferredencoding(False) or "utf-8"

        try:
            stream.reconfigure(encoding=encoding, errors="replace")
        except Exception:
            continue


def _configure_qt_font_dir() -> None:
    """Point Qt to a real font directory in packaged Windows environments."""
    if os.name != "nt":
        return
    if os.environ.get("QT_QPA_FONTDIR"):
        return

    candidates = [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
        Path("C:/Windows/Fonts"),
    ]
    for candidate in candidates:
        if candidate.exists():
            os.environ["QT_QPA_FONTDIR"] = str(candidate)
            return


def _apply_default_app_font(app) -> None:
    from PyQt6.QtGui import QFont

    font = QFont("Malgun Gothic", 10)
    if font.pointSize() <= 0 and font.pixelSize() <= 0:
        font.setPointSize(10)
    app.setFont(font)


def main():
    _configure_stdio_encoding()
    _configure_qt_font_dir()

    ensure_directories()
    setup_logger()
    logger = get_logger("Main")
    cleanup_old_logs()
    logger.info("애플리케이션 시작")

    ok, errors = run_preflight_checks(logger=logger, profile="startup")
    if not ok:
        for error in errors:
            logger.error(error)
        return 1

    def _excepthook(exc_type, exc, tb):
        logger.error("Unhandled exception", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _excepthook

    from PyQt6.QtWidgets import QApplication
    from src.ui.app import RealEstateApp

    app = QApplication(sys.argv)
    _apply_default_app_font(app)

    window = RealEstateApp()
    window.show()

    try:
        sys.exit(app.exec())
    except Exception as e:
        logger.error(f"애플리케이션 종료 중 오류 발생: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
