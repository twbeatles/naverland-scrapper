from __future__ import annotations

import json
import re


def _decode_rsc_frames(frames) -> list:
    """Read JSON records from Flight text frames without evaluating JavaScript."""
    if not isinstance(frames, list):
        return []
    chunks = []
    size = 0
    for frame in frames[:2000]:
        if not isinstance(frame, list) or len(frame) < 2 or frame[0] != 1 or not isinstance(frame[1], str):
            continue
        size += len(frame[1])
        if size > 2_000_000:
            break
        chunks.append(frame[1])
    records = []
    for line in "".join(chunks).splitlines():
        match = re.match(r"^[0-9a-fA-F]+:(?:[A-Z])?([\[{].*)$", line)
        if not match:
            continue
        try:
            records.append(json.loads(match.group(1)))
        except (ValueError, RecursionError):
            continue
    return records


async def _read_hydration_state(detail_page) -> dict:
    script = """
    () => {
      const pick = (value) => {
        if (!value || typeof value === "function") {
          return null;
        }
        try {
          return JSON.parse(JSON.stringify(value));
        } catch (error) {
          return null;
        }
      };
      const keys = [
        "__NEXT_DATA__",
        "__NUXT__",
        "__INITIAL_STATE__",
        "__PRELOADED_STATE__",
        "__APOLLO_STATE__",
        "__STATE__",
        "__REDUX_STATE__",
        "__next_f",
      ];
      const payload = {};
      for (const key of keys) {
        const value = pick(window[key]);
        if (value) {
          payload[key] = value;
        }
      }
      return payload;
    }
    """
    try:
        payload = await detail_page.evaluate(script)
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        return {}
    records = _decode_rsc_frames(payload.get("__next_f"))
    if records:
        payload["__next_f_decoded"] = records
    return payload
