import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_SCAN_ROOTS = (ROOT / "src", ROOT / "tests")
ROOT_TEXT_FILES = (
    ROOT / "app_entry.py",
    ROOT / "README.md",
    ROOT / "claude.md",
    ROOT / "gemini.md",
    ROOT / "update_history.md",
    ROOT / "naverland-scrapper.spec",
    ROOT / ".editorconfig",
    ROOT / "pyrightconfig.json",
    ROOT / ".vscode" / "settings.json",
    ROOT / ".github" / "workflows" / "ci.yml",
)
UTF8_BOM = b"\xef\xbb\xbf"


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


def _iter_tracked_text_files():
    seen = set()

    for path in ROOT_TEXT_FILES:
        if path.exists() and path not in seen:
            seen.add(path)
            yield path

    for root in PYTHON_SCAN_ROOTS:
        for path in root.rglob("*.py"):
            if path not in seen:
                seen.add(path)
                yield path


class TestMojibakeScan(unittest.TestCase):
    def test_tracked_text_files_decode_as_utf8_without_bom(self):
        findings = []

        for path in _iter_tracked_text_files():
            rel_path = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            if data.startswith(UTF8_BOM):
                findings.append(f"{rel_path}: UTF-8 BOM detected")
            try:
                data.decode("utf-8")
            except UnicodeDecodeError as exc:
                findings.append(f"{rel_path}: not valid UTF-8 ({exc})")

        self.maxDiff = None
        self.assertEqual(
            findings,
            [],
            "Encoding findings detected:\n" + "\n".join(findings),
        )

    def test_tracked_text_files_have_no_mojibake_indicators(self):
        findings = []

        for path in _iter_tracked_text_files():
            text = path.read_text(encoding="utf-8")
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
