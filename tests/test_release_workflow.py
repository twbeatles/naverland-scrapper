"""Release workflow must survive `python -I` (isolated mode).

Regression test for the v15.5 Release failure: `python -I` drops the current
directory from `sys.path`, so `python -I -c "from src..."` dies with
`ModuleNotFoundError: No module named 'src'` before any real check runs.
Every isolated (`-I`) inline snippet that imports `src.*` must therefore
insert the repo root into `sys.path` before the first `src` import.
"""

import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_YML = REPO_ROOT / ".github" / "workflows" / "release.yml"

# Files allowed to run `python -I -c "..."` snippets against src/*.
ISOLATED_SNIPPET_FILES = (
    RELEASE_YML,
    REPO_ROOT / "scripts" / "setup_build_env.ps1",
    REPO_ROOT / "scripts" / "build_local.ps1",
)

_ISOLATED_INLINE = re.compile(r"-I\s+-c\s+\"(?P<payload>[^\"]+)\"")
_SRC_IMPORT = re.compile(r"(?:^|[;\s])from\s+src\.|(?:^|[;\s])import\s+src\.")


def _isolated_payloads(path):
    return [
        match.group("payload")
        for match in _ISOLATED_INLINE.finditer(path.read_text(encoding="utf-8"))
    ]


class TestReleaseWorkflow(unittest.TestCase):
    def test_isolated_snippets_set_sys_path_before_src_import(self):
        for path in ISOLATED_SNIPPET_FILES:
            with self.subTest(file=path.name):
                self.assertTrue(path.is_file(), f"{path} is missing")
                payloads = [p for p in _isolated_payloads(path) if _SRC_IMPORT.search(p)]
                self.assertGreater(
                    len(payloads),
                    0,
                    f"{path} has no isolated src-check snippet to guard",
                )
                for payload in payloads:
                    anchor = payload.find("sys.path.insert")
                    first_src = _SRC_IMPORT.search(payload)
                    assert first_src is not None  # filtered by _SRC_IMPORT above
                    self.assertGreaterEqual(
                        anchor,
                        0,
                        f"{path} runs `python -I -c` importing src without "
                        "sys.path.insert; isolated mode drops cwd from "
                        "sys.path (ModuleNotFoundError: No module named 'src')",
                    )
                    self.assertLess(
                        anchor,
                        first_src.start(),
                        f"{path} inserts sys.path after the first src import",
                    )

    def test_release_binding_check_runs_in_isolated_mode(self):
        payloads = [
            payload
            for payload in _isolated_payloads(RELEASE_YML)
            if "find_qfluentwidgets_binding_mismatch" in payload
        ]
        self.assertEqual(
            len(payloads),
            1,
            "release.yml must keep exactly one isolated Qt binding check",
        )
        completed = subprocess.run(
            [sys.executable, "-I", "-c", payloads[0]],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertNotIn(
            "No module named 'src'",
            completed.stderr,
            "release.yml binding check cannot import src in isolated mode",
        )
        self.assertEqual(
            completed.returncode,
            0,
            f"release.yml binding check failed in isolated mode: {completed.stderr.strip()}",
        )
        self.assertIn("qfluentwidgets", completed.stdout)


if __name__ == "__main__":
    unittest.main()
