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
    parser.add_argument(
        "--live-smoke",
        action="store_true",
        help="Run a lightweight Playwright smoke probe against Naver Land entry pages and exit.",
    )
    parser.add_argument(
        "--smoke-url",
        action="append",
        default=[],
        help="Additional URL to probe in --live-smoke mode. Can be repeated.",
    )
    parser.add_argument(
        "--smoke-timeout-ms",
        type=int,
        default=12000,
        help="Per-page timeout in milliseconds for --live-smoke mode.",
    )
    parser.add_argument(
        "--smoke-headless",
        action="store_true",
        help="Use headless browser for --live-smoke. Default is headed.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.preflight:
        from src.utils.preflight import run_preflight_checks

        ok, errors = run_preflight_checks(profile="full")
        # In windowed builds prints are not visible, but exit code is still useful for CI.
        for msg in errors:
            print(msg)
        return 0 if ok else 1

    if args.live_smoke:
        from src.utils.live_smoke import default_live_smoke_urls, run_live_smoke

        urls = list(args.smoke_url or [])
        if not urls:
            urls = default_live_smoke_urls()
        ok, messages = run_live_smoke(
            urls,
            headless=bool(args.smoke_headless),
            timeout_ms=max(1000, int(args.smoke_timeout_ms or 12000)),
        )
        for msg in messages:
            print(msg)
        return 0 if ok else 1

    from src.main import main as gui_main

    return int(gui_main() or 0)


if __name__ == "__main__":
    raise SystemExit(main())

