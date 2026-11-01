# Patch Audit: first implementation increment

Scope: Phases 1–2 of the improvement plan. This is product maintenance, not a new
release, research campaign, or change to retained evaluation results.

## Implemented

- Added a guided Boltons saved-evidence walkthrough: selected passing tests,
  the patch's omitted standalone implementation, then expected versus observed
  empty-input behavior. Only one step is displayed at a time, with keyboard
  controls and an explicit saved-playback label. Full evidence, provenance,
  logs, source and downloads remain available below.
- Added a local-only prepared-example catalog reading the existing frozen G2
  Python and Node positive declarations and exact patch bytes. Requirements
  enter the UI unapproved. The recorded application has no catalog or execution
  routes.
- Added a local first-use entry point with Python prefilled and a Node selector.
  Source, production scope, patch, runtime, commands, requirement provenance,
  assumptions, function target and named checks are supplied without copying JSON.
  Custom source, patch, command and checker editors remain under expandable
  advanced configuration.
- Preserved the normal source/patch admission services, runtime identity checks,
  explicit requirement approval, fresh synthetic-control validation, independent
  plan approval and final exact-plan execution approval. Changing bound inputs
  continues to invalidate approval. Modified source or patch input loses its
  prepared-example provenance label.
- Displayed session setup time separately from execution durations. Setup begins
  at prepared-example selection and ends when execution is requested; it includes
  review and control validation. Command durations remain in the saved evidence.
- Updated the local quickstart to document the complete prepared journey.
- Mounted review diff editors only while their disclosure is open, and wrapped
  prepared requirement provenance on narrow screens. Added coverage for keyboard
  opening/closing and mobile layout.

## Verification

- `./scripts/check`: passed on the final source, including lint, formatting,
  Python type checks, **388 offline tests**, and the production TypeScript/Vite
  build. Vite retains its existing warning about large editor chunks.
- `./scripts/e2e`: the full run recorded **87 passed, 16 failed, 4 skipped**.
  Three failures were the prepared-page URL wrapping issue and the previous
  featured-link navigation expectation. The final UI rerun passed all four
  selected checks (both prepared journeys, guided playback, and existing viewer
  navigation). The other 13 failures came from Docker refusing new candidate
  networks with `all predefined address pools have been fully subnetted`.
  After removing eight unattached networks from earlier G1/G2 local Compose
  projects, the executor rerun passed all 15 selected checks. Attached networks,
  application records, source snapshots and volumes were preserved.
- Across the full run and focused reruns, **all 103 distinct non-skipped
  end-to-end/integration tests passed**. Four existing live-model gates remained
  skipped. This is combined coverage, not a claim of a single clean full-suite run.
- The final four UI checks exercised desktop (1440 pixels), mobile (390 pixels),
  keyboard navigation, exact frozen requirement/assertion contents, fresh
  synthetic-control approval and execution for Python and Node, evidence
  downloads matching the API, approval invalidation, and saved-history reopening.
  Public source transport used retained accepted snapshots; admission, database,
  broker and execution were real. No paid model call was made.
- The final production frontend bundle was mounted read-only into the existing
  local API image for the final UI rerun; backend source was unchanged from that
  built image. Local screenshots and fresh machine evidence are retained in
  `artifacts/prepared-workflow/`, excluded from commits.
- The recorded hosting entrypoint exposes no `/api/patch-audits` or
  `/api/repository-audits` routes. Release dependency-file comparison and
  `git diff --check` passed.
- `./scripts/recovery-smoke`: passed using the same read-only frontend mount.
  A forced API crash retained an interrupted result, preserved completed history,
  and allowed a fresh successful reproduction with no runner cleanup errors.

## Limits and subsequent phases

The examples remain accepted historical developer changes; the Boltons case is
retained model output. Automated browser journeys are engineering checks, not
observations of unfamiliar developers. No new detection-rate or usability claim
is established. Setup timing is local session state, not persisted telemetry.

Reusable versioned project checklists, a shared browser/CLI workflow, report
exports, generated/reduced failing inputs, observed usability sessions, new
recordings, social posts, public sharing, deployment and releases are subsequent
work under Phases 3–5 or separate decisions. The existing historical recordings
and evaluation evidence are retained.
