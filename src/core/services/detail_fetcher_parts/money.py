from __future__ import annotations

import re


def parse_kr_money_to_won(text: str) -> int | None:
    if not text:
        return None
    src = str(text).strip().replace(" ", "").replace(",", "")
    has_won = "원" in src
    src = src.replace("원", "")
    total = 0
    man = 0

    match = re.search(r"(\d+(?:\.\d+)?)억", src)
    if match:
        try:
            total += int(float(match.group(1)) * 100_000_000)
        except (TypeError, ValueError):
            pass
        tail = src.split("억", 1)[1]
        man_match = re.search(r"(\d+)만", tail) or re.search(r"^(\d+)$", tail) or re.search(r"(\d+)천", tail)
        if man_match:
            try:
                man = int(man_match.group(1))
                if "천" in man_match.group(0):
                    man *= 1000
            except (TypeError, ValueError):
                man = 0
    elif re.fullmatch(r"\d+", src):
        return int(src) if has_won else int(src) * 10_000
    else:
        man_match = re.search(r"(\d+)만", src) or re.search(r"(\d+)천만?", src)
        if man_match:
            man = int(man_match.group(1))
            if "천" in man_match.group(0):
                man *= 1000

    return total + man * 10_000
