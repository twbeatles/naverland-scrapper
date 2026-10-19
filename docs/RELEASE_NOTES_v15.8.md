## Search crash fix

- Fixed the app terminating immediately when searching by dong/gu or keyword in `단지 찾기` and `지도로 찾기` → `지역 찾기`. Root cause: consecutive in-page Playwright fetches from a `QThread` slot raised a native access violation. Fetch execution moved to a daemon plain-thread queue pump that owns the browser session outright; results cross back through queued signals. Reproduced and verified with a live session.
- Fixed the dialog wedging on `검색 중...` when the API answers explicit null lists (`"complexes": null`), and late autocomplete failures overwriting the search status (search status now wins).

## Real-address and map-link search

- Full addresses now resolve: `서울특별시 서초구 반포동` → `서초구 반포동` → `반포동`, trailing bunji numbers stripped, road-name numbers stripped. The first variant with results wins and stays active for `더 보기` pagination. Rate limits (429) never burn through variants.
- Pasted map links: `new.land`/`fin.land` links carrying complex IDs resolve to checkable rows with looked-up names; `ms=lat,lon,zoom` links become a region row directly. Viewport-only links with neither (fin.land `map?center=`) show guidance instead of failing silently.

## Build and verification

- 22 new regression tests (address variants, fallback fetch, null payloads, map-link rows, mid-flight shutdown, late-suggest guard, fin patterns, `ms=` extraction).
- `compileall` clean, Pyright 0 errors, pytest subset 411 passed, preflight clean.
