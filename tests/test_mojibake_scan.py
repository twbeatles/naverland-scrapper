import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (ROOT / "src", ROOT / "tests")


def _line_has_mojibake(line: str) -> bool:
    for ch in line:
        code = ord(ch)
        if ch == "\ufffd":
            return True
        if 0x3130 <= code <= 0x318F:
            return True
        if 0xF900 <= code <= 0xFAFF:
            return True
    return False


class TestMojibakeScan(unittest.TestCase):
    def test_python_sources_have_no_mojibake_indicators(self):
        findings = []

        for root in SCAN_ROOTS:
            for path in root.rglob("*.py"):
                text = path.read_text(encoding="utf-8-sig")
                for lineno, line in enumerate(text.splitlines(), start=1):
                    if _line_has_mojibake(line):
                        findings.append(
                            f"{path.relative_to(ROOT).as_posix()}:{lineno}: {line.strip()}"
                        )

        self.maxDiff = None
        self.assertEqual(
            findings,
            [],
            "Mojibake indicators found:\n" + "\n".join(findings),
        )


if __name__ == "__main__":
    unittest.main()
