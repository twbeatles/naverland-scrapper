"""requirements.txt pins must exist and be satisfied by this environment.

Guards against un-installable pins (e.g. a version that was never published),
which break `pip install -r requirements.txt` and cascade into CI failures.
"""

import re
import unittest
from importlib import metadata
from pathlib import Path


def _parse_requirements():
    pattern = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*(>=|==|~=|>|<=|<)?\s*([^;\s]*)\s*(?:;.*)?$")
    entries = []
    text = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = pattern.match(line)
        assert match is not None, f"unparsable requirement line: {line!r}"
        entries.append((match.group(1), match.group(2) or "", match.group(3) or ""))
    return entries


def _version_tuple(value):
    parts = []
    for chunk in re.split(r"[.\-+]", value):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


class TestRequirementPins(unittest.TestCase):
    def test_pins_are_installed_and_satisfied(self):
        entries = _parse_requirements()
        self.assertGreater(len(entries), 0)
        for name, operator, wanted in entries:
            with self.subTest(package=name):
                try:
                    installed = metadata.version(name)
                except metadata.PackageNotFoundError:
                    self.fail(f"{name} is pinned in requirements.txt but not installed")
                if operator in (">=", "==") and wanted:
                    self.assertGreaterEqual(
                        _version_tuple(installed),
                        _version_tuple(wanted),
                        f"{name} installed {installed} does not satisfy {operator}{wanted}",
                    )


if __name__ == "__main__":
    unittest.main()
