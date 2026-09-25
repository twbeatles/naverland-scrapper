import os
import re
import sys
import unittest
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

REPO_ROOT = Path(__file__).resolve().parents[1]
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
CI_CHECK_PS1 = REPO_ROOT / "scripts" / "ci_check.ps1"

# Regression tests that must run in CI; if one is missing from either list,
# the safety net it provides silently stops running.
REQUIRED_IN_CI = {
    "tests/test_browser_pool_guard.py",
    "tests/test_ci_subset_sync.py",
}

_TEST_PATTERN = re.compile(r"tests/test_[A-Za-z0-9_]+\.py")


def _listed_tests(path):
    return set(_TEST_PATTERN.findall(path.read_text(encoding="utf-8")))


class TestCiSubsetSync(unittest.TestCase):
    def test_ci_workflow_and_local_check_list_same_tests(self):
        yml_tests = _listed_tests(CI_YML)
        ps1_tests = _listed_tests(CI_CHECK_PS1)
        self.assertEqual(
            ps1_tests,
            yml_tests,
            "scripts/ci_check.ps1 pytest list drifted from .github/workflows/ci.yml; "
            f"only in ci.yml: {sorted(yml_tests - ps1_tests)}, "
            f"only in ci_check.ps1: {sorted(ps1_tests - yml_tests)}",
        )

    def test_guard_tests_run_in_ci(self):
        yml_tests = _listed_tests(CI_YML)
        ps1_tests = _listed_tests(CI_CHECK_PS1)
        for required in sorted(REQUIRED_IN_CI):
            self.assertIn(required, yml_tests, f"{required} is missing from ci.yml")
            self.assertIn(required, ps1_tests, f"{required} is missing from ci_check.ps1")


if __name__ == "__main__":
    unittest.main()
