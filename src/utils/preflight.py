import importlib.util
import importlib
from pathlib import Path
from typing import Iterable, Optional

from src.utils.logger import get_logger
from src.utils.paths import DATA_DIR, LOG_DIR


REQUIRED_DEPENDENCIES = [
    "PyQt6",
    "bs4",
    "matplotlib",
    "selenium",
    "undetected_chromedriver",
]

OPTIONAL_DEPENDENCIES = [
    "psutil",
    "plyer",
    "openpyxl",
]

# Modules that must be importable for the app to start.
# This catches internal refactors (moved/renamed modules) early.
REQUIRED_INTERNAL_IMPORTS = [
    "src.ui.app",
]


def find_conflict_markers(
    base_dir: Path, target_dirs: Optional[Iterable[str]] = None
) -> list[str]:
    search_dirs = list(target_dirs) if target_dirs else ["src", "tests"]
    problematic_files: list[str] = []

    for target in search_dirs:
        root = base_dir / target
        if not root.exists():
            continue
        for file_path in root.rglob("*.py"):
            try:
                content = file_path.read_text(encoding="utf-8")
            except OSError:
                continue
            has_conflict = any(
                line.startswith("<<<<<<< ")
                or line == "======="
                or line.startswith(">>>>>>> ")
                for line in content.splitlines()
            )
            if has_conflict:
                problematic_files.append(file_path.relative_to(base_dir).as_posix())

    return problematic_files


def find_missing_dependencies(packages: Iterable[str]) -> list[str]:
    return [pkg for pkg in packages if importlib.util.find_spec(pkg) is None]


def find_internal_import_failures(modules: Iterable[str]) -> list[str]:
    failures: list[str] = []
    for name in modules:
        try:
            importlib.import_module(name)
        except Exception as e:
            failures.append(f"{name}: {type(e).__name__}: {e}")
    return failures


def run_preflight_checks(
    base_dir: Optional[Path] = None,
    data_dir: Optional[Path] = None,
    log_dir: Optional[Path] = None,
    logger=None,
) -> tuple[bool, list[str]]:
    base = base_dir or Path(__file__).resolve().parent.parent.parent
    data = data_dir or DATA_DIR
    logs = log_dir or LOG_DIR
    app_logger = logger or get_logger("Preflight")

    errors: list[str] = []

    conflict_files = find_conflict_markers(base)
    if conflict_files:
        errors.append("소스 코드에 미해결 머지 충돌 마커가 존재합니다.")
        app_logger.error("머지 충돌 마커 감지: %s", ", ".join(conflict_files))

    missing_required = find_missing_dependencies(REQUIRED_DEPENDENCIES)
    if missing_required:
        errors.append(
            "필수 라이브러리가 누락되었습니다: " + ", ".join(missing_required)
        )
        app_logger.error("필수 라이브러리 누락: %s", ", ".join(missing_required))

    if not missing_required:
        internal_failures = find_internal_import_failures(REQUIRED_INTERNAL_IMPORTS)
        if internal_failures:
            errors.append(
                "내부 모듈 import 스모크 테스트에 실패했습니다: " + "; ".join(internal_failures)
            )
            app_logger.error("내부 모듈 import 실패: %s", "; ".join(internal_failures))

    missing_optional = find_missing_dependencies(OPTIONAL_DEPENDENCIES)
    if missing_optional:
        app_logger.warning(
            "선택 라이브러리 누락(기능 제한 가능): %s", ", ".join(missing_optional)
        )

    for directory in [data, logs]:
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            errors.append(f"디렉토리 생성 실패: {directory} ({e})")
            app_logger.error("디렉토리 생성 실패: %s (%s)", directory, e)

    return len(errors) == 0, errors


def main() -> int:
    ok, errors = run_preflight_checks()
    if ok:
        return 0
    for message in errors:
        print(message)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
