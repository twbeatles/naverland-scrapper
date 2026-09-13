# Repository Rename Impact Analysis

Updated: 2026-09-13

## Decision

The repository name remains `naverland-scrapper`. No rename was performed. A repository rename changes public clone and release URLs and therefore requires the repository owner's explicit approval.

The GitHub description and Topics were updated separately so the current name does not prevent the repository from being discovered for its intended terms.

## Current references that a rename would affect

| Surface | Current dependency | Rename work required |
|---|---|---|
| Git remote | `https://github.com/twbeatles/naverland-scrapper.git` | Update clone instructions and external integrations that retain the old remote. |
| Update manifest endpoint | `src/utils/version.py` → `raw.githubusercontent.com/twbeatles/naverland-scrapper/...` | Change, ship, and test the endpoint in a new application release. |
| Release artifact URL | `.github/workflows/release.yml` builds the repository name into the GitHub Releases URL and EXE filename. | Update the URL template and artifact naming; verify signed-manifest download and rollback flow. |
| Release tests | `tests/test_update_manifest.py` uses a repository release URL fixture. | Update fixtures without weakening the HTTPS/signature assertions. |
| Build specification | `naverland-scrapper.spec` and README build commands use the current filename. | Rename only if a new artifact/application name is intended; otherwise keep compatibility names. |
| Existing public links | GitHub redirects may preserve many old URLs, but this must not be the only compatibility measure. | Verify releases, raw manifest delivery, badges, external bookmarks, and updater behavior after the rename. |

No README clone URL or repository-owned badge URL currently needs changing. The UI-framework badge points to its upstream project, not this repository.

## Naming options

| Option | SEO and branding | Compatibility impact |
|---|---|---|
| Keep `naverland-scrapper` | Keeps the existing URL and release/update channel intact, but retains the uncommon `scrapper` spelling. | None. |
| `naverland-scraper` | Corrects the technical spelling while retaining the recognizable product name. | Moderate: update channel, release URLs, tests, and public references must be verified. |
| `naver-real-estate-scraper` | Strongest direct match for English GitHub searches such as “naver real estate scraper.” | Highest branding and compatibility cost; it is longer and changes the established product name. |

## Recommendation

Use `naverland-scraper` if a rename is approved later: it corrects the spelling with the least branding disruption. Before approving it, create a release/update migration checklist covering the rows above and test a staged upgrade from an existing installed build.
