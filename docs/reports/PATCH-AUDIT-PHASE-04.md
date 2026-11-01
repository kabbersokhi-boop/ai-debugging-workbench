# Patch Audit Phase 4: bounded generation and reproducible failure reduction

## Prior-phase review

Before extending execution, rechecked the current worktree and previous engineering
reports. Thirty-one prepared-example, project-checklist and verifier-history tests passed.
Both real Python and Node browser/CLI checklist parity and second-patch journeys passed
again on the prior normal local image. This supports the implemented Phases 1–3 within
their declared limits; it is not unfamiliar-developer usability research.

## Implementation

- Added `json-generated-v3` with separate `generated-plan-v1` and
  `repository-generated-result-v1` contracts, a pinned Python observer archive,
  and a separate dispatch layer. Existing v1/v2 implementations, adapters, named
  check workflows, checklist v1 declarations, evaluations and results are retained.
- Added owner-approved built-in reference properties for first truthy element,
  integer sum and integer sort on bounded JSON lists. Requirements retain independent
  provenance, justification and approved input domains. Arbitrary oracle programs
  and candidate-derived expectations are not accepted.
- Added deterministic seeded case generation, domain-preserving simplification,
  bounded reduction, original-input replay and two final fresh reproductions.
  Cases/rounds/proposals, list/scalar sizes, per-observer execution time and total
  environments are bounded. Input generation and expected values stay on the host;
  candidate code uses only the existing restricted execution broker.
- Bound property interpretation, stateless-function declaration, domain, seed,
  budgets, host implementation and observer hashes to exact plan identity. Require
  fresh synthetic controls and exact execution approval. Changing a plan requires
  review and approval again. No model calls are involved.
- Added semantic evidence replay: regenerated inputs, each proposal set, observed
  selection, reduction trajectory and final confirmations are recomputed from
  retained command evidence. All runtime material hashes, bindings and fresh
  container identities are checked. Missing or fabricated reduction evidence is
  rejected, even if a client recomputes its result hash.
- Added a browser Python generation mode and an input/expected/actual result with
  the requirement's justification, original input, reduction limits and full trace.
  Added readable report sections and CLI generation/reproduction preparation using
  the same approval, execution and evidence services. Exact reduced inputs can be
  rerun through a newly approved plan, not just read as saved playback.
- Published a schema and a search example. Updated the quickstart with supported
  inputs, approval steps, budgets, scope limits and terminal replay instructions.

## Verification

- `./scripts/check` passed: **424 offline tests**, lint, formatting, Python type
  checks and the production TypeScript/Vite build. The existing large diff-editor
  chunk warning remains. Twenty new offline cases cover authored positive/negative
  behavior, generation/replay determinism, bounded reduction, unstable observations,
  timeout/cancellation/infrastructure classification, exact plan/material bindings,
  unsupported domains, schema parity and the local/recorded-server boundary.
- The real generated-verifier journey passed both independently and in the full
  suite. Source fetching replayed a retained accepted Python snapshot; admission,
  database, controls, approvals, Docker execution and evidence validation were real.
  It exercised the browser positive path, mobile layout and keyboard approval,
  approval invalidation after an edit, CLI negative execution and an explicit fresh
  CLI replay. It also rejected forged reduction summaries and missing execution
  evidence after their outer hashes were recomputed.
- The accepted **authored negative** passed ordinary tests and failed the approved
  first-truthy property. Reduction retained `["a"]`: expected `"a"`, observed
  `null`, confirmed in two fresh environments. The explicit replay used a newly
  approved plan and again confirmed that exact failure twice. All run environments
  were distinct. This demonstrates the mechanism on an authored control, not a new
  defect discovered in the wild.
- The full `./scripts/e2e` run finished with **105 passed, 1 failed, 4 skipped**
  across 110 selected cases. The older Node shared-array observation test reported
  `infrastructure_error` from its ordinary execution. The failed result's full
  diagnostic was not retained by that test, so the underlying cause is unproven.
  The affected case and the nested-array case passed together on immediate retry;
  the complete six-case Node observation family then passed. No assertion, timeout,
  verifier or runtime code was changed to obtain those passes.
- Across that full run and the focused rerun, **all 106 distinct non-skipped
  integration/end-to-end cases passed**. This is combined coverage, not a clean
  single full-suite invocation. The four existing live-model gates remained skipped.
  The full run also covered both prior Python/Node checklist parity journeys,
  prepared examples, saved Boltons playback, older verifiers, source/patch admission,
  sandbox restrictions, cancellation, timeout, cleanup and restart recovery.
- `./scripts/recovery-smoke` passed on the normal final Docker image: forced API
  termination preserved the interrupted state and completed history; a fresh run
  reproduced successfully, with no runner cleanup errors. The normal image has no
  development source/frontend bind mounts. Final saved generated evidence was
  independently revalidated from its retained execution trace.
- React component review, desktop/mobile and keyboard journey checks completed.
  The recorded server still has no Patch Audit or generalized intake/execution
  routes. Release dependency-file comparison and `git diff --check` passed. Existing
  v1/v2 verifier/observer source, frozen evaluations and recordings have no worktree
  modifications.
- Local runtime evidence is retained under `artifacts/generated-verifier-v3/`
  (excluded from commits): authored-negative JSON/Markdown, replay JSON, a synthetic
  mobile screenshot and verification logs. No release, merge or deployment was made.

## Limits

The starting domain is one positional list of approved JSON scalars, for deterministic
stateless Python functions, against three explicitly approved built-in properties.
Generation is bounded and may miss defects. Passing covers only those checks. Reduction
retains a simpler witnessed failure when found; it does not prove a globally smallest
input. Inconsistent fresh observations are marked non-reproducible; infrastructure errors
remain separate from a confirmed reduced counterexample. Authored controls are controls,
not genuine new discoveries. No accuracy campaign, unfamiliar-user observation, public
execution, deployment, release, recording or social post is included. Those remain future
work or separate decisions.
