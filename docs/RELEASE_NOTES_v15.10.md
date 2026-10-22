## Naver Pay Real Estate (fin.land) switch

Naver Land is moving to `fin.land.naver.com`. Live checks on 2026-10-22 showed `m.land` already redirecting there and `new.land` still up but changing. Collection, complex search, and map links now use the new site first; the old `new.land` paths stay as a fallback.

- **Listings:** apartment and villa listings come from the new site (`complex/article/list`, villa: `complex/villa/article/list`). Same-listing groups are expanded to one row per ad, as before, so saved data, exports, and price history keep the same shape. If the new site has nothing for a complex, the old path takes over.
- **Map search (`지도로 찾기`):** discovery now asks the new site for the complexes in each map area (most listings first, only complexes with listings) instead of dragging a map around. It is faster, and it works again for villas, where the old map flow no longer found complexes. The area pause setting replaces the old "wait after moving the map".
- **Complex search (`단지 찾기`):** searches the new site first, finds full addresses (`서울특별시 송파구 가락동` → `가락동`), shows the district and a complex-number tooltip, and keeps `더 보기` paging. Pasted links work for new map links, complex links (apartment and villa), article links, and map-position links (the position is named by its district).
- **Detail (broker, phone, previous deposit):** fetched through the new site's API first and only opens the article page when the API gave nothing. The same 56 listings took 101 s before and 14 s now. Fixed the complex management-office phone number being saved as the broker phone.
- **Blocking:** the site answers 429 to `HeadlessChrome` user agents and to requests made outside a browser page. All browsers the app starts now send a normal Chrome user agent, and API calls run inside a page on the site.
- **Opening links:** complex links open on the new site (`isVilla=true` for villas).

## Updater hardening (WinError 5 fix)

- Windows could not overwrite or delete a running (or just-exited, AV-scanned) EXE, so the old copy-then-overwrite installer failed with WinError 5 and its rollback failed the same way, leaving a backup behind.
- The installer now swaps with two renames: installed EXE -> backup, then staged EXE -> installed. A rename succeeds where overwrite/delete does not. If the first rename fails the installed build is untouched.
- A stale backup never blocks the next attempt: it is overwritten by the next rename. If a run dies between the two renames, the next run restores backup -> installed before swapping.
- Rollback after a failed smoke also avoids in-place overwrite: the failed build is renamed aside first, then the backup is renamed home.
- Helper, restarted app, and `--preflight` smoke children now run with a cleaned environment (PyInstaller `_MEI*` / `_PYI*` / `_PYINSTALLER*` removed) so a stale `_MEIPASS` from the parent cannot break the child.

## Things to know

- Villa numbers saved by older versions came from `new.land` and do not exist on the new site. The log says so; add those villas again with `지도로 찾기` or `단지 찾기`.
- In one map area the app reads up to 300 complexes (most listings first). Raise the zoom for a finer sweep.
- Collection caches from earlier versions are not reused (the cache version changed with the data source).

## Build and verification

- Verified on the live site with the real collection thread and a separate database: three complexes (two apartments, one villa) × sale/lease, 4,069 listings, no errors; a second run found 0 new listings (same ads recognized). Map discovery around Gongdeok: 320 complexes (117 apartments, 203 villas), 5,772 listings, all complete.
- Live smoke (`--live-smoke --smoke-headless --live-smoke-detail-fields`): all 11 steps ok, including the new `fin-contract` step (search, listings, map list).
- New tests in `tests/test_fin_land.py` (codec, group expansion, paging, 429 handling, villa, geo discovery, search fallbacks) added to the CI subset; Pyright 0 errors, full pytest and preflight clean.
- Updater regression tests in `tests/test_update_installer.py` (rename order, stale-backup overwrite, interrupted-swap recovery, locked-overwrite rollback, clean child env) stay in the CI subset guard.
- Docs: `docs/NAVER_LAND_SURVEY_2026-10-22.md` (measured contract) and `docs/FIN_LAND_MIGRATION_PLAN_2026-10-22.md`.
