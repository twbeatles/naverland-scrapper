## Naverland Scrapper v15.11

v15.11 includes the (never-tagged) v15.10 changes below plus the fixes on top.
See [`RELEASE_NOTES_v15.10.md`](./RELEASE_NOTES_v15.10.md) for the fin.land switch
and updater hardening details.

## New in v15.11

- **Collection gap shortened:** the wait between complexes is now 1 second after a
  clean fast-path pair instead of 3–5 seconds. Measured on the live site: the same
  3 complexes went from 30.7 s to 19.9 s wall time with identical listing counts
  and no rate limits. Legacy/DOM paths and failed pairs keep the previous pacing.
- **Villa search fix:** complexes of type A07 (도시형생활주택) were labeled as
  apartments in `단지 찾기` results and collected through the wrong endpoint
  (empty results). They are now correctly treated as villas.
- **Browser identity refreshed:** desktop user agent updated to Chrome/158 to
  match current stable (the site collects the user-agent signal for bot
  detection). Verified with headless live smoke: all probes ok.

## Verified

- Live collection with the real engine on a separate database: 헬리오시티 sale
  2,025 listings, villa 매매 47 listings, 헬리오시티 전세 719 listings — all
  complete, no fallbacks, no 429s, 6/6 detail enrichment success.
- New regression tests (`A07` asset mapping, fast-path pair gap) added; engine and
  collection suites green, ruff clean.
- Docs: `docs/NAVER_LAND_SURVEY_2026-11-25.md` (re-check: site contract unchanged),
  `docs/README.md` (new document index).
