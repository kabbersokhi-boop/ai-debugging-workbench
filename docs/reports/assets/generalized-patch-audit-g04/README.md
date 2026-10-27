# G4 retained acceptance evidence

Implementation: `ca56acfb9120aa42aef70b794b995008d4b42ca2`.

Screenshots are unedited Playwright captures from the actual interface at 1440px desktop and
390px mobile widths. Root Python/Node images copy the final **live GitHub source** journeys;
their JSON/evidence is in `live-source/`. The `fixture-transport/` directory separately records
the deterministic CI procedure: only source response transport is replayed from accepted public
snapshots; admission, plans, controls, approval, execution, downloads and history are real.
These are G4 product checks of accepted G2 examples, not a new G3 campaign.

`boltons-*`/`recorded-*` capture the actual local recorded release container. The Boltons case
replays authentic retained AI-generated evidence; no inference or fresh execution. Original
recordings and campaign records remain untouched. `post-restart/` preserves the earlier G4 live
records exactly after the full-suite restarts and smoke; original execution submission = 1,
submissions after container recreation = 0 for each audit.

`check.log`, `e2e.log`, `recovery-smoke.log`, `recorded-browser.log` and `recorded-boundary.log`
are actual final implementation checks. The nine focused cases in `focused-browser-summary.json`
are a subset of the full e2e run, not additional test totals. `implementation-ci.json` records
both successful implementation workflows; final report/evidence-head CI is recorded on PR #16.
`implementation-fingerprint.json` identifies complete source/test/workflow Git objects that must
match the final review head. `served-implementation.json` verifies the served frontend files and
coordinator recovery/preview modules against the tested checkout.

`development/` retains earlier failed browser/full-suite runs and CI links. They are not omitted,
replaced, or counted as successful. The unchanged legacy harness resolves a default broker by
fixed name: its source was checked and its original stopped state restored after the complete
suite. The final private G4 stack was isolated from prior G3 history. One intentional 600-second
legacy debugger preview was cleaned through its existing private broker endpoint; saved evidence
remains. No candidate execution resources remain (`cleanup.json`).

The only matched service ERRORs are the expected database immutability rejections from negative
tests (`service-log-review.json`). Recovery smoke recreates the API container, so final API logs
retain its post-smoke startup; evaluator logs and `repository-recovery.json` retain the earlier
restart journey. `preservation.json` validates 1,643 protected files, 19 unchanged existing route
handlers, both retained campaign collections, the unchanged original restart scenario and all
12 prior private Node records/downloads. `public-read-only-check.json` is GET-only inspection of
the existing deployed viewer; it is not a deployment or production acceptance campaign.

All upstream source in the JSON records is already accepted public evidence, with original
license/attribution material preserved. No private repository, provider credential or environment
file is included. SHA256SUMS covers every retained file in this directory except itself.
