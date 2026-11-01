# Phase 5 preparation: local demonstration and observation readiness

Phase 5 remains incomplete. No unfamiliar-developer sessions, participant completion
times, independent participant reproductions or participant-reported friction have been
supplied. The observation protocol is in
[PATCH-AUDIT-USABILITY-SESSION.md](../PATCH-AUDIT-USABILITY-SESSION.md).

## Prepared artifacts

- Created a script-free, offline HTML evidence report for the retained **authored
  negative control** from Phase 4. It shows what passed, what failed, why it matters,
  input/expected/observed values, scope limitations and complete evidence downloads.
- Packaged the full saved JSON, readable Markdown, exact patch, fresh replay evidence,
  portable checklist, original search and exact-input replay search. Instructions
  distinguish replay on the original installation from preparation on another compatible
  private local installation, which needs fresh controls and exact approval.
- Recorded **11.88 seconds** of actual automated interaction with the local application's
  saved-evidence UI at 1280 × 900: inspect the result, open the original failure details
  and download the readable report. This is saved playback of an authored control,
  not a new audit recording, an unfamiliar person's session or a usability measurement.
- Added asset SHA-256 checksums and a ZIP for local transfer. These are integrity checks,
  not an independent attestation. The files remain runtime artifacts excluded from commits.

Local artifacts:

- `artifacts/phase5-preparation/index.html`
- `artifacts/phase5-preparation/automated-saved-playback.webm`
- `artifacts/phase5-preparation/README.txt`
- `artifacts/phase5-preparation/inspection.json`
- `artifacts/phase5-preparation/SHA256SUMS.json`
- `artifacts/patch-audit-authored-control-demo.zip`

## Verification

- Revalidated the source saved evidence through the current semantic evidence validator
  before exporting. The retained case is `["a"]`, expected `"a"`, observed `null`, with
  two fresh confirmations. No new candidate execution was needed for this export.
- Browser interception allowed only read requests during the application recording;
  there were no mutating requests or browser errors. The downloaded report matched
  the retained report byte for byte.
- Opened the report directly with `file:` and checked desktop and 390-pixel mobile
  widths, keyboard disclosure activation, no horizontal overflow, and no external
  requests. Visually inspected the mobile capture. The document contains no scripts,
  forms, embedded frames, event-handler attributes or execution endpoints; its content
  security policy denies network/content loading except its inline presentation styles.
- Checked every HTML download target exists, validated the portable checklist and replay
  search contracts, checked the ZIP's integrity, and rehashed every packaged asset.
  Video metadata confirms a VP8 recording at 1280 × 900 lasting 11.88 seconds.
- An initial inspection assertion matched two different report sections and failed its
  locator uniqueness check. Scoped the inspection locator to the intended disclosure
  and repeated successfully. This was an automation error; no product change or
  participant friction claim follows from it. Both diagnostic logs remain local.
- No runtime application code changed in this preparation. The engineering verification
  results remain those recorded in [the Phase 4 report](PATCH-AUDIT-PHASE-04.md).

## Remaining evidence and decisions

The next required input is an actual unfamiliar developer's session, or genuine session
notes and timings. Setup, audit wait and interpretation/export time must be measured
separately; unsupported cases, assistance and failures must remain visible. Fixes should
address observed friction and retain the initial and follow-up evidence.

The local package is ready for inspection or private transfer; no public report URL has
been created. A final X post linking directly to evidence awaits actual observations and
a publication decision. No participant results, public sharing, deployment, merge or
release are claimed. Automated inspection does not satisfy the unfamiliar-developer
completion check.
