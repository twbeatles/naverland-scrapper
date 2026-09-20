from __future__ import annotations


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
    return payload if isinstance(payload, dict) else {}
