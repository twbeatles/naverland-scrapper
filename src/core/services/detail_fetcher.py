from __future__ import annotations

import re

from src.core.services.gap_analysis import enrich_gap_fields


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


async def fetch_mobile_article_detail(detail_page, article_no: str) -> dict:
    async def _goto(url: str):
        await detail_page.goto(url, wait_until="domcontentloaded")
        await detail_page.wait_for_timeout(300)
        if "fin.land.naver.com" in detail_page.url:
            await detail_page.goto(
                f"https://m.land.naver.com/article/info/{article_no}",
                wait_until="domcontentloaded",
            )
            await detail_page.wait_for_timeout(300)

    if not article_no:
        return {}

    await _goto(f"https://m.land.naver.com/article/info/{article_no}")
    try:
        body_text = await detail_page.inner_text("body")
    except Exception:
        body_text = ""

    if ("요청하신 페이지를 찾을 수 없어요" in body_text) or (len(body_text.strip()) < 50):
        await _goto(f"https://m.land.naver.com/article/view/{article_no}")
        try:
            body_text = await detail_page.inner_text("body")
        except Exception:
            body_text = ""

    def grab(regex: str, flags: int = 0) -> str:
        match = re.search(regex, body_text, flags)
        return match.group(1).strip() if match else ""

    prev_jeonse_text = grab(r"기전세금\s*([\d,억\s만]+)")
    prev_jeonse = parse_kr_money_to_won(prev_jeonse_text) if prev_jeonse_text else 0

    try:
        await detail_page.locator("text=실거래가").first.click()
        await detail_page.wait_for_timeout(200)
        await detail_page.locator("text=전세").first.click()
        await detail_page.wait_for_timeout(250)
        body_text = await detail_page.inner_text("body")
    except Exception:
        pass

    lines = [line.strip() for line in body_text.splitlines() if line.strip()]
    agent_name = ""
    office = ""
    candidate_idx = -1

    for idx, line in enumerate(lines):
        if re.fullmatch(r"[가-힣]{2,4}", line) and line not in ("이미지", "상세보기", "중개사", "중개소"):
            context = "\n".join(lines[max(0, idx - 3): idx + 2])
            if ("중개사" in context) or ("프로필" in context) or ("중개소" in context):
                agent_name = line
                candidate_idx = idx
                break

    office_pattern = re.compile(r"(공인중개사|부동산)")
    if candidate_idx >= 0:
        for line in lines[candidate_idx + 1: candidate_idx + 6]:
            if office_pattern.search(line) and ("상세보기" not in line) and ("전화" not in line):
                office = line
                break
    if not office:
        office_match = re.search(r"중개소\s+([^\n]+)", body_text)
        if office_match:
            office = office_match.group(1).strip()

    max_match = re.search(r"(\d+)\s*년\s*내\s*최고\s*([\d,억\s만]+)", body_text)
    min_match = re.search(r"(\d+)\s*년\s*내\s*최저\s*([\d,억\s만]+)", body_text)
    period_years = int(max_match.group(1)) if max_match else (int(min_match.group(1)) if min_match else 0)
    jeonse_max = parse_kr_money_to_won(max_match.group(2)) if max_match else 0
    jeonse_min = parse_kr_money_to_won(min_match.group(2)) if min_match else 0

    phones = re.findall(r"(0\d{1,2}-\d{3,4}-\d{4})", body_text)
    return {
        "부동산상호": office,
        "중개사이름": agent_name,
        "전화1": phones[0] if len(phones) >= 1 else "",
        "전화2": phones[1] if len(phones) >= 2 else "",
        "전세_기간(년)": period_years,
        "전세_기간내_최고(원)": jeonse_max or 0,
        "전세_기간내_최저(원)": jeonse_min or 0,
        "기전세금(원)": prev_jeonse or 0,
    }


def apply_mobile_detail(item: dict, detail: dict | None) -> dict:
    if not isinstance(item, dict):
        return {}
    if isinstance(detail, dict):
        item.update(detail)
    return enrich_gap_fields(item)
