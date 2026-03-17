import importlib.util
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Iterable, Optional

from src.utils.logger import get_logger
from src.utils.paths import DATA_DIR, LOG_DIR, SETTINGS_PATH


REQUIRED_DEPENDENCIES = [
    "PyQt6",
    "bs4",
    "matplotlib",
    "playwright",
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


def _is_truthy_env(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def should_skip_playwright_browser_check() -> bool:
    return _is_truthy_env(os.environ.get("NAVERLAND_SKIP_PLAYWRIGHT_BROWSER_CHECK"))


def should_require_playwright_browser() -> bool:
    return _is_truthy_env(os.environ.get("NAVERLAND_REQUIRE_PLAYWRIGHT_BROWSER"))


def is_frozen_runtime() -> bool:
    return bool(getattr(sys, "frozen", False))


def should_run_source_integrity_checks() -> bool:
    if is_frozen_runtime():
        return False
    return not _is_truthy_env(os.environ.get("NAVERLAND_SKIP_SOURCE_INTEGRITY_CHECKS"))


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


def _iter_playwright_browser_path_candidates() -> list[Path]:
    candidates: list[Path] = []

    configured = str(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "") or "").strip()
    if configured:
        candidates.append(Path(configured))

    local_app_data = str(os.environ.get("LOCALAPPDATA", "") or "").strip()
    if local_app_data:
        candidates.append(Path(local_app_data) / "ms-playwright")

    if is_frozen_runtime():
        executable_dir = Path(sys.executable).resolve().parent
        base_path = Path(getattr(sys, "_MEIPASS", executable_dir))
        candidates.extend(
            [
                base_path / "ms-playwright",
                base_path / "_internal" / "ms-playwright",
                executable_dir / "ms-playwright",
                executable_dir / "_internal" / "ms-playwright",
            ]
        )

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _find_browser_executable_under(root: Path) -> str:
    if not root.exists():
        return ""

    direct_candidates = [
        root / "chrome-win64" / "chrome.exe",
        root / "chrome-linux" / "chrome",
        root / "chrome-mac" / "Chromium.app" / "Contents" / "MacOS" / "Chromium",
    ]
    for candidate in direct_candidates:
        if candidate.exists():
            return str(candidate)

    try:
        for pattern in ("*/chrome-win64/chrome.exe", "*/chrome-linux/chrome", "*/chrome-mac/Chromium.app/Contents/MacOS/Chromium"):
            match = next(root.glob(pattern), None)
            if match is not None and match.exists():
                return str(match)
    except OSError:
        return ""
    return ""


def find_missing_playwright_browser() -> str:
    if importlib.util.find_spec("playwright") is None:
        return "playwright"
    for candidate in _iter_playwright_browser_path_candidates():
        executable = _find_browser_executable_under(candidate)
        if executable:
            return ""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            executable = Path(p.chromium.executable_path)
        if not executable.exists():
            return str(executable)
        return ""
    except Exception as e:
        return f"playwright browser unavailable: {e}"


def get_effective_crawl_engine(settings_path: Optional[Path] = None) -> str:
    path = settings_path or SETTINGS_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return "playwright"
    if not isinstance(payload, dict):
        return "playwright"
    engine = str(payload.get("crawl_engine", "playwright") or "playwright").strip().lower()
    if engine not in {"playwright", "selenium"}:
        return "playwright"
    return engine


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
    settings_path = data / "settings.json"

    errors: list[str] = []

    if should_run_source_integrity_checks():
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
    elif not should_skip_playwright_browser_check():
        missing_browser = find_missing_playwright_browser()
        if missing_browser:
            message = "Playwright Chromium 브라우저가 준비되지 않았습니다: " + missing_browser
            if should_require_playwright_browser():
                errors.append(message)
                app_logger.error("Playwright Chromium 누락: %s", missing_browser)
            elif get_effective_crawl_engine(settings_path) == "playwright":
                errors.append(message)
                app_logger.error(
                    "Playwright Chromium required for effective crawl_engine=playwright: %s",
                    missing_browser,
                )
            else:
                app_logger.warning("%s", message)

    if not missing_required and should_run_source_integrity_checks():
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
