import unittest
from unittest.mock import patch

import app_entry


class TestAppEntry(unittest.TestCase):
    def test_parse_args_supports_live_smoke_flags(self):
        args = app_entry._parse_args(
            [
                "--live-smoke",
                "--smoke-url",
                "https://example.com/a",
                "--smoke-url",
                "https://example.com/b",
                "--smoke-timeout-ms",
                "5000",
                "--smoke-headless",
            ]
        )

        self.assertTrue(args.live_smoke)
        self.assertEqual(args.smoke_url, ["https://example.com/a", "https://example.com/b"])
        self.assertEqual(args.smoke_timeout_ms, 5000)
        self.assertTrue(args.smoke_headless)

    def test_main_dispatches_live_smoke_runner(self):
        with patch("src.utils.live_smoke.run_live_smoke", return_value=(True, ["[ok] smoke"])) as mock_runner:
            exit_code = app_entry.main(
                [
                    "--live-smoke",
                    "--smoke-url",
                    "https://example.com/probe",
                    "--smoke-timeout-ms",
                    "7000",
                    "--smoke-headless",
                ]
            )

        self.assertEqual(exit_code, 0)
        mock_runner.assert_called_once_with(
            ["https://example.com/probe"],
            headless=True,
            timeout_ms=7000,
        )


if __name__ == "__main__":
    unittest.main()
