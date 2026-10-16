# Publication audit — v1.0.0

Performed locally on 2026-10-16 while the repository remained private. Accepted application baseline: `d43d8164f3e8f9f3ead402bcd26d1994376726bb`, retained by `review/milestone-04-guest-auth`.

## Scope and findings

- Fetched every remote branch and review tag. Scanned all 26 pre-integration commits and 387 unique retained blobs, plus all 299 tracked files at the accepted head. No committed environment credentials, database backups, private keys or runtime dumps were found. `.env.example` and Compose contain explicitly disposable local database defaults; the real provider environment file is ignored and excluded from Docker builds.
- Gitleaks **8.30.1**, downloaded from the official project release with its published archive checksum checked locally, scanned Git history (`--log-opts=--all`) and an exported tracked tree with full redaction. Four matches in each scan were source SHA-256 digest fields for `api.py` and `access.py`, verified against exact JSON field structure. They are provenance, not secrets. No scanner suppression was added.
- A separate local scan checked retained blobs and downloaded GitHub material for NVIDIA/GitHub token patterns, the exact locally configured provider credential, private-key headers, literal authorization credentials and signed download URLs. No matches were found. Secret values were never emitted.
- Downloaded and scanned all four PR descriptions/reviews/comments, issue comments and current authored repository metadata. Downloaded **28/28 workflow log archives and 28/28 retained artifact bundles** available before integration; none were expired or unavailable. Existing failures were included. The GitHub-content scanner found one genuine temporary clone token automatically supplied by the authenticated metadata API. It was confined to an ignored local API-response download, never authored repository content, committed history or a public artifact. Raw audit downloads are not published.
- Inspected synthetic evidence, recordings and metadata; visually reviewed the README comparison and sampled captioned walkthrough frames. Both committed walkthrough copies have identical SHA-256 `0e7bc5522ed8e522da1fc6829aa149b1233704648d2a7c61de81885df189cbd0`. No customer data is used. This is a bounded audit, not a claim that regex scanning or sampled visual inspection proves the absence of every possible disclosure.
- Ordinary CI uses GitHub-hosted ephemeral runners, `contents: read`, no provider secret inputs, no privileged contributor trigger and no persistent privileged runner. Checkout credentials are not persisted. Offline fixtures, live opt-in skips and recorded evidence remain distinct.
- There is **no project license file**. No license or attribution was replaced or invented. Public availability is not an open-source license grant.

No publication-blocking sensitive-data exposure was found in the material to be published. Local environment files, raw API responses and audit working files remain ignored. Subsequent release documentation and verification outputs are checked again before visibility changes.

## Integration provenance

All four accepted PRs were checked for their expected heads, clean mergeability and successful checks, retargeted to `main` where needed, then merged normally:

| PR | Merge commit |
| --- | --- |
| [#1](https://github.com/kabbersokhi-boop/ai-debugging-workbench/pull/1) | `7a042aa2ea47ba92c017fc3e8eecca3c916e72c7` |
| [#2](https://github.com/kabbersokhi-boop/ai-debugging-workbench/pull/2) | `4d2d1aac03c3da06d2de24e3e98102bf048e3613` |
| [#3](https://github.com/kabbersokhi-boop/ai-debugging-workbench/pull/3) | `d1e7daaf4ff9b507843cd9e9c95013e8a90b3246` |
| [#4](https://github.com/kabbersokhi-boop/ai-debugging-workbench/pull/4) | `e93054ed50890723741b1a75010a86e2b2fce21c` |

The application tree at PR #4's merge exactly matches the accepted baseline. All milestone branches, source commits, review tags, historical reports and retained failures are preserved. The release-preparation change is documentation plus CI checkout credential handling; no application or evaluation code changes.

## Verification and activation gates

The final delivery and GitHub release identify the exact tested main commit and CI runs, without embedding a document's own commit hash recursively. The gates are `scripts/check`, offline integration/browser acceptance including guest UUID authorization, crash recovery, recorded-image build/health, actual-container `scripts/check_release.py`, recorded desktop/mobile acceptance, documentation links, and unauthenticated repository/release/asset/clone checks after publication. No NVIDIA experiment is rerun for release.

Branch-protection and ruleset inspection returned the account-plan restriction (HTTP 403) while private. No protection was disabled or bypassed; inspection is repeated after publication. Hosting remains inactive. [Deployment boundary and separate activation requirements](RELEASE.md).
