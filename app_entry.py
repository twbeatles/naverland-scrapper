"""
Build entrypoint for PyInstaller.

- Keeps import resolution stable by running from project root (so `import src...` works).
- Provides a headless smoke-test mode: `--preflight` exits quickly without starting the GUI.
"""

from __future__ import annotations

import argparse


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Run dependency/import/fs checks and exit without starting the GUI.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.preflight:
        from src.utils.preflight import run_preflight_checks

        ok, errors = run_preflight_checks()
        # In windowed builds prints are not visible, but exit code is still useful for CI.
        for msg in errors:
            print(msg)
        return 0 if ok else 1

    from src.main import main as gui_main

    return int(gui_main() or 0)


if __name__ == "__main__":
    raise SystemExit(main())

