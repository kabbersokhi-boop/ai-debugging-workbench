# Patch Audit Phase 3: repeated local audits

This phase adds reusable project checklists, a local CLI, and readable reports to the
existing local workflow. Historical evaluations and verifier implementations are retained.

## Implementation

- Added strict `project-checklist-v1` declarations with a name/revision, repository,
  supported immutable commits and file hashes, production scope, runtime/command
  limits, independently justified requirements, supported input domains, and named
  JSON function checks. Download declarations from the configured browser workflow
  and reload them for another patch; approvals are excluded from portable files.
  A checked-in JSON Schema documents the contract, and Python/Node example
  checklists allow terminal use without a prior browser export.
- Added local-only syntax validation, compatibility, and plan compilation endpoints.
  Source, repository, scope and hashes are checked explicitly. Unsupported source
  revisions and retired verifiers display an outdated state. Plans use the existing
  ordinary and independent admission services and current trusted adapters.
- Added immutable checklist application records via additive migration 011. Saved
  evidence includes the full checklist plus its hash/revision and exact source,
  candidate and plan binding. Reopening validates that binding. Historical checklist
  evidence can still be checked against archived supported verifier versions.
- Added a CLI for preparation, controls, execution, and evidence export. Browser and
  CLI use the same local API. Execution requires an explicitly supplied fingerprint
  of the complete preparation and a candidate-bound control validation. Every
  invocation requires exact approval; there is no reusable execution authorization.
- Added readable Markdown report downloads and terminal exports alongside complete
  JSON evidence and the exact patch. Reports include scope limitations, source and
  patch identity, approvals, checker requirements, observations, controls and command
  output. Untrusted content stays inside escaped evidence blocks.
- Added browser checklist review/import/export, compatibility messages, explicit
  requirement review and existing fresh controls/approval flow. Added a report link.

## Verification

- Applied migration 011 to the local PostgreSQL database and confirmed the
  checklist application table has its immutability trigger.
- `./scripts/check` passed with 404 offline tests, lint, formatting, Python type
  checks, and the production TypeScript/Vite build. The existing large editor
  chunk warning remains.
- Sixteen focused contract/integrity tests cover reuse across patches, incompatible
  repositories/source hashes/scopes, outdated commits/verifiers, prohibited embedded
  approvals, tampered bindings, historical verifier reopening, published schema
  parity, changed CLI approval fingerprints, forged broker bindings, missing saved
  checklist references, and escaped report evidence.
- Both real browser/CLI parity journeys passed for Python and Node. Each exported
  a checklist from the browser, reviewed compatibility on mobile and by keyboard,
  ran browser checks, ran the same patch via CLI with identical exact inputs and
  observations, and reused the checklist on an authored negative patch. The latter
  passed ordinary tests and failed independent assertions. Validation from the
  earlier candidate was rejected. Evidence JSON, Markdown reports, and patches
  were checked against the shared API; source transport replayed retained accepted
  public snapshots, while admission, storage, approvals, Docker controls and
  candidate execution were real.
- The first parity attempt exposed an omitted broker request field for checklist
  references. Added broker-side exact binding validation and reran both journeys
  successfully. The failed local attempt remains retained as infrastructure evidence.
- The recorded hosting entrypoint has no generalized intake, checklist, report or
  execution routes. Release dependency-file comparison and whitespace checks passed.
- Early local verification used the built frontend and current backend source
  mounted read-only into the API/evaluator containers. A final normal Docker image
  was then built and started with the default Compose file and no development
  source/frontend mounts. Both parity journeys and the final human-readable report
  renderer passed against that image. Runtime captures and an example readable report
  are retained under `artifacts/project-checklists/`, excluded from commits.
- `./scripts/e2e`: **104 passed, 1 failed, 4 skipped** in the full run. The
  failure was an older retained Patch Audit browser journey waiting only five
  seconds for its initial asynchronously loaded candidate review. A repeated final
  image run reproduced that readiness timeout; direct inspection confirmed the
  region subsequently loads without alerts. Increased only the initial readiness
  wait to 20 seconds, matching the existing editor wait. The entire older browser
  journey then passed from a fresh API start.
- Across the full run and focused rerun, **all 105 distinct non-skipped integration
  and end-to-end tests passed**. The four existing live-model gates stayed skipped.
  This is combined coverage, not a claim of one clean full-suite invocation. Both
  new parity journeys also passed again against the normal final image after the
  final report rendering changes.
- `./scripts/recovery-smoke` passed against the normal final image. A forced
  API crash preserved the interrupted state, left completed history unchanged,
  and allowed a fresh successful reproduction with no runner cleanup errors.
- Final `./scripts/check` passed again: **404 offline tests**, lint, formatting,
  Python type checks, and production frontend build. Final image health, explicit
  readable-report labels, both checked-in example declarations, recorded-route
  isolation, dependency-file comparison, and `git diff --check` passed. Historical
  evaluation/configuration/recording files have no worktree modifications.

## Boundaries

No generalized execution endpoints were added to the recorded server. No generation,
reduction, inference, public hosting, release or deployment is included. Checklist revision
numbers are owner-managed; portable files do not query a central latest-version registry.
Compatibility proves the declared source/patch constraints, not specification completeness
or universal correctness. Native dependency availability and actual function behavior are
still established through local execution and its retained evidence.
