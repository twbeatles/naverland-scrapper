import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.preflight import (
    find_conflict_markers,
    find_missing_dependencies,
    run_preflight_checks,
)


class TestPreflight(unittest.TestCase):
    def test_find_conflict_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src_dir = base / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            ok_file = src_dir / "ok.py"
            bad_file = src_dir / "bad.py"

            ok_file.write_text("print(1)\n", encoding="utf-8")
            bad_file.write_text(
                "<<<<<<< HEAD\nprint(1)\n=======\nprint(2)\n>>>>>>> x\n",
                encoding="utf-8",
            )

            found = find_conflict_markers(base, ["src"])
            self.assertEqual(found, ["src/bad.py"])

    def test_find_missing_dependencies(self):
        missing = find_missing_dependencies(["json", "package_that_does_not_exist_123"])
        self.assertIn("package_that_does_not_exist_123", missing)
        self.assertNotIn("json", missing)

    def test_run_preflight_checks_failure_on_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src_dir = base / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            (src_dir / "bad.py").write_text(
                "<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n",
                encoding="utf-8",
            )

            ok, errors = run_preflight_checks(
                base_dir=base,
                data_dir=base / "data",
                log_dir=base / "logs",
            )
            self.assertFalse(ok)
            self.assertTrue(any("머지 충돌" in err for err in errors))


if __name__ == "__main__":
    unittest.main()
