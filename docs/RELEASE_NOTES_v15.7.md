## Data integrity and collection reliability

- Mark incomplete API, pagination, parsing, and Selenium DOM runs as partial or failed. Keep successful rows visible while preventing incomplete runs from being cached as complete, marking listings as disappeared, or replacing full-day price statistics.
- Refresh observation timestamps for already-known listings before applying display filters so a price or area filter does not make an active listing look removed.
- Replace a target's same-day price snapshot rows transactionally after a complete, unfiltered collection. Preserve prior statistics on cancellation, filtered or cached results, partial collection, and persistence errors.
- Include PRE mode and the collection contract version in cache fingerprints.
- Record per-run collection diagnostics and data-quality counts in crawl history.

## Naver page and data handling

- Read supported JSON records from Next.js Flight (`__next_f`) frames on listing detail pages, with bounded parsing and existing fallback paths retained.
- Keep supply area, exclusive area, and area precision separate; use structured detail values when available and expose the provenance fields in exports.
- Update the site survey notes with the observed `fin.land` map-layer detail route and current list/API contract observations.

## Build and verification

- Add collection-integrity, site-contract, response-normalization, geo-marker, crawler-regression, and lock tests to the CI suite. Isolate test settings and history files under temporary directories.
- The audit follow-up recorded 512 passing tests and one environment pin failure on local Windows ARM64 (installed `cryptography` 46.0.3 versus the declared `>=50.0.2`), plus zero Pyright errors. The release workflow separately installs declared dependencies and validates the signed frozen build on GitHub-hosted Windows x64.

See [the audit follow-up](AUDIT_FIXES_2026-10-18.md) for implementation details and the complete validation scope.
