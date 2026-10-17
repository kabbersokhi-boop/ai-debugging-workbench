# Completed Patch Audit workflow

## What a user can do

**Patch Audit is the default local and recorded experience.** It accepts a completed patch for an
approved historical Python task, runs the selected ordinary repository checks and evaluator-owned
behavioral checks, explains disagreements and preserves source-bound execution evidence. It makes
no model calls. The original debugger is available at `/?workspace=debugger`; Agent Evaluation and
its original comparison remain at `/?workspace=evaluation`.

The local journey supports:

1. Select an approved task; load a retained genuine candidate or an explicitly authored control.
2. Alternatively paste a unified diff or upload a UTF-8 `.patch`/`.diff` file.
3. Review the exact submitted text, affected files, pinned base and provenance before execution.
4. Confirm authority to execute this exact candidate locally. Importing alone starts no audit.
5. Run ordinary and independent phases in separate fresh restricted containers.
6. Inspect the outcome, deterministic explanation, detailed observations, logs and execution IDs.
7. Download the exact patch and evidence, reopen a saved audit, or explicitly start another run.

Supported existing adapters: more-itertools bucket (9 selected ordinary tests), Boltons addlist
(155), more-itertools seekable (14) and Boltons IndexedSet (5). Task requirements, upstream bases,
source snapshots, licenses, selected tests and behavioral expectations are unchanged. No new task,
language, execution platform or database was added; migration 008 adds two tables to existing PostgreSQL.

## The genuine introductory case

The default recorded example is
`m02-v2-development-boltons-addlist-nemotron3-r02`, source identity
`5cab12b5c1b25239d4418e84aae45f166041390a6895d24f2a6ae1d1d85d6246`.
The model repaired `boltons/dictutils.py` but omitted the required standalone copy in
`boltons/urlutils.py`. Normal package imports exercise the repaired class; standalone execution uses
the unchanged vendored class. **The selected 155 ordinary tests passed.** Existing independent checks
exercise the missed implementation and observe **empty input with length 1, although keys and items
are empty; expected length is 0**. Iterator/generator values and repeated appends expose related state
errors. Five failed observation groups describe **one incomplete repair**, not five discoveries.

The passing example for exactly the same task/base is
`m02-v1-boltons-addlist-nemotron35-r02`, source identity
`ad55f9039233a94d71447bbf043e94537de73ca0aa7d2b5174b9753abcb90f29`.
It changes both production implementations and passed the selected ordinary and independent checks.
Neither patch was regenerated or manually improved.

Original evidence: [development patch](../../evaluation/experiments/m02-v2/development/independent/m02-v2-development-boltons-addlist-nemotron3-r02.patch),
[source-bound independent observation](../../evaluation/experiments/m02-v2/development/independent/m02-v2-development-boltons-addlist-nemotron3-r02.json),
[passing generation/scoring journal](../../evaluation/experiments/m02-v1/trials/m02-v1-boltons-addlist-nemotron35-r02),
and [explicit recorded export manifest](../../recordings/patch-audit-manifest.json).

Both examples are validated against their actual generation journals, event heads, frozen procedure,
source/candidate identities and scoring bindings before loading/export. Recorded exports retain the
original trial binding and result hash, not just a manually entered verdict. They package the
necessary source, exact patch, selected ordinary transcript, independent observations, runtime
identities, provenance and upstream license, without copying whole model conversations.

These are different model/harness procedures: the incomplete patch is development evidence on a
known calibration task; the passing patch belongs to the older controlled experiment. They are
**not a fair vendor ranking or held-out accuracy estimate**. Original M1 conclusions and `m02-v1`
**0/6** additional detections remain unchanged. The separate development observation remains **1/1**,
with three other journeys producing no submission. Fresh audits here repeat executions of existing
code; they add no producer trials or distinct defect discoveries.

The inherited development freeze's top-level temperature 0 differs from actual request temperature
1. An additive provenance note displays this discrepancy. Actual serialized request parameters are
the authority for what was sent; no historical artifact was edited. New provenance has one
`request_settings` location and reports captured returned model identities.

## Import and execution scope

Imports are a deliberately limited unified-diff subset: LF/UTF-8 text, maximum **64 KiB**, at most
four existing approved production files and 64 hunks/file; total admitted source is limited to
1.5 MB. Each old hunk must match its declared position and exact context. Git independently checks
and applies the diff in a temporary directory; its output must equal the exact-context reconstruction.
There is no fuzzy application, automatic repair, checkout, hook, shell interpolation or Python import.
Git is installed at trusted image build time; candidates cannot install dependencies.

Traversal/absolute/unauthorized paths, tests/verifiers/policies/dependencies/manifests, duplicate file
sections, create/delete headers, renames, modes, symlinks/submodules, binary patches, CRLF/no-newline
markers and malformed/stale/oversized patches are rejected. Unsupported format is a rejection, not
an invitation to rewrite the patch. Rejection returns an admission error and creates no execution.

An admitted candidate is immutable in `patch_audit_candidates`, enforced by a database trigger. It
retains original patch text/hash, canonical software identity, resulting source hashes, exact task
base and provenance. Same patch plus same metadata deduplicates to the same import record. Different
metadata can produce another immutable import record for the **same software hash**. Every execution
has its own UUID in `patch_audit_runs`. Imported records never enter frozen historical catalogs.

Provenance categories distinguish captured model evidence, user-declared model/tool metadata,
unknown authorship, declared human authorship and deliberately authored controls. Import cannot claim
the captured-model category; a label such as “Codex” is a declaration, not proof. Labels and source
references are stored as text and never fetched. Authorship does not affect behavioral scoring.
Controls have separate selection groups and explicit history/result labels; no agent metrics are
computed from imported audits or controls.

The API stores/reviews text; it has no candidate execution path. The private broker independently
rebuilds the admitted record before claiming a run UUID. It shares the existing one-run execution
capacity and cancellation/cleanup machinery. Both API start routes use a common admission lock;
legacy evaluation and Patch Audit cannot race into spurious occupied-broker executions.

The two M1 tasks call the frozen evaluator directly. The two M2 adapters needed cancellation support:
a small versioned bridge reuses the same fixed executor, probes and comparison functions. Its verifier
identity also includes the new adapter source. Validation checks the original binding hash and the
verifier captured at run admission, then uses an in-memory projection for the unchanged inherited
phase/observation validator. Retained results are never rewritten or relabeled as old experiment runs.

Only trusted local owner mode supports import/execution. Guest mode and foreign origins are rejected;
the supplied Compose file binds the API to loopback. Do not expose or reverse-proxy this privileged
stack. Confirmation declares authority, not safety. Existing candidate containers have no provider
credentials, Docker socket, host bind mounts or network; trusted test/source volumes and rootfs are
read-only, with existing CPU/memory/PID/log/file limits and a 25-second phase deadline. Docker daemon
responsiveness/cleanup is an inherited limitation. **Local containers and in-process Python observations
are not a complete anti-tampering system for deliberately malicious programs.** Expected values and
scoring remain outside candidate modification authority.

## Result and persistence semantics

The page leads with task/candidate, ordinary outcome, independent outcome and the principal observed
mismatch. Repeated detailed observations, manifests, identities and raw logs are expandable. The
specific omitted-copy explanation requires recorded package success, an unchanged standalone file
and the observed empty-state mismatch; arbitrary imported failures do not inherit that story.
A pass says **“Passed these checks for this task and environment.”** There is no trust score or claim
of universal correctness/security.

Admission rejection, ordinary failure, additional independent failure, both-pass, timeout,
execution/infrastructure error, cancellation/interruption and invalid/missing evidence remain distinct.
Missing evidence never becomes a pass. Invalid broker responses remain explicitly unvalidated and
are downloadable without being used as a displayed verdict. Startup/collection failures retain the
inherited execution/infrastructure classification; inspect logs rather than inferring a provider fault.

A saved run is revalidated against candidate/task/source, verifier, image/policy, phase commands,
actual initialized files and recomputed observations before display. Candidate edits/imports clear
previous verdicts and confirmation. Request epochs reject delayed selections; serialized polling
prevents stale running responses replacing terminal evidence.

Cancellation records the request and stops the broker. Restart reconciles validated terminal broker
evidence; otherwise it requests cancellation and records interruption without inventing checks.
Terminal publication uses an exclusive execution claim and atomic artifact write. A bounded eight-second
reconciliation wait accommodates cancellation cleanup. No interrupted run automatically restarts.
History shows the latest 100 audits; older records remain available by saved ID/URL.

## Recorded experience and boundary

`/recorded/` in the local application and `/` in the restricted release open the two curated audits.
Visitors can switch failing/passing examples, inspect the requirement, exact diff, omitted file,
ordinary/independent evidence, provenance, licenses and reproduction instructions, and download evidence.
Every execution is labeled saved/historical; browsing starts no fresh audit, inference or animation
pretending to execute. Existing recorded debugger runs remain linked and unchanged.

The exporter names **only the two selected historical IDs**. It never scans local imported candidates
or attached transcripts. The recorded server checks manifest SHA-256 identities and serves GET-only
saved assets. It imports no evaluator/database/provider/Docker authority and has no import/live audit
routes. New auditing requires the local application. The recorded build was prepared/tested locally;
no hosting, visibility change or public execution was activated.

## Verification and preservation

Tested implementation: `f5ab0e74ea7b159bafcfe5f176f48169e31ec565`.
The live API and broker source hashes were compared with this worktree before final process tests.
The final report/evidence commit changes only README, this report and selected sanitized assets.
Final review head: `refs/pull/8/head`; its exact SHA and CI URLs are recorded in
[review PR #8](https://github.com/kabbersokhi-boop/ai-debugging-workbench/pull/8) and the handoff, since a
commit cannot embed its own SHA. PR #8 is stacked on `feature/agent-evaluator-m02`; PRs #6/#7 are unmerged.

Commands from repository root, with Python 3.12, uv, Node and local Docker:

```sh
./scripts/check
uv run --project backend pytest backend/tests/test_patch_audit.py -q
docker compose up --build -d --wait api
./scripts/e2e
./scripts/recovery-smoke
uv run --project backend python scripts/export_patch_audits.py
docker compose -f compose.release.yaml up --build -d --wait
uv run --project backend python scripts/check_release.py
E2E_BASE_URL=http://127.0.0.1:8020 ./scripts/e2e -k recorded_explorer_first
```

A new execution of a saved local candidate, with explicit authority:

```sh
uv run --project backend python -m workbench.patch_audit.cli <saved-candidate-id> --confirm-local-execution
```

| Check | Actual result |
| --- | --- |
| `./scripts/check` | **124 passed, 71 deselected**; Ruff/format/Pyright/frontend build passed. Inherited Monaco chunk warning. [Log](assets/patch-audit-workflow/check.log) |
| Focused admission/evidence tests | **26 passed**; deterministic checks, no model calls. [Log](assets/patch-audit-workflow/focused.log) |
| Full integration/browser suite | **67 passed, 4 skipped, 124 deselected**, 349.48 s. All five Patch Audit process/browser tests passed. Four live-model opt-in tests stayed disabled. [Log](assets/patch-audit-workflow/e2e.log) |
| Recovery smoke | Completed history unchanged; interrupted browser work recovered; fresh reproduction and cleanup passed. [Log](assets/patch-audit-workflow/recovery.log) |
| Audit cancellation/restart | Real cancellation, terminal broker reconciliation and missing-terminal interruption passed. [Proof](assets/patch-audit-workflow/audit-recovery.json) |
| CLI reproduction | Completed operationally (exit 0), with candidate **failed**: ordinary passed / independent failed. Same binding and four distinct phase containers across original/reproduction. [Log](assets/patch-audit-workflow/cli.log), [proof](assets/patch-audit-workflow/reproduction-proof.json), [evidence](assets/patch-audit-workflow/cli-reproduction.json) |
| Restricted recorded container | Nonroot/read-only, no mounts/socket/provider/database authority; new live routes absent. [Actual container proof](assets/patch-audit-workflow/recorded-boundary.json) |
| Recorded-server browser suite | **2 passed, 193 deselected**; new audit and old debugger explorer, no mutation requests. [Log](assets/patch-audit-workflow/recorded-browser.log) |
| Implementation CI | [Run 39049922675 passed](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/runs/39049922675), head `f5ab0e74ea7b159bafcfe5f176f48169e31ec565`, without model credentials. [Summary](assets/patch-audit-workflow/ci-implementation.json), [transcript](assets/patch-audit-workflow/ci-implementation.log) |

Final documentation-head CI and its exact SHA are listed in PR #8 and the review handoff. No runtime
source follows the tested implementation. The earlier implementation CI was cancelled after the
local full-suite test-lifecycle defect was found; its replacement above passed.

Focused self-review corrected overlapping polling, missing original scoring-wrapper export, a verifier
identity that omitted the new M2 bridge, asymmetric API capacity admission and early terminal lookup.
Initial browser verification found unstable implicit form labels, corrected with explicit accessible
labels. A subsequent test locator matched two Monaco editors; it now selects the opened visible editor.
The first full suite also exposed the new test reusing a database pool across pytest event loops; a test-scoped engine fixes that without altering runtime code or assertions. These earlier failed checks are retained as verification history, not hidden producer trials.

[Preservation evidence](assets/patch-audit-workflow/preservation.json) verifies **1,097** protected
files against accepted head `df525f5f1b2cd7bbe213c84314bb6ad6dd51c063`: all existing evaluation artifacts,
fixtures, evals, recordings, reports/assets and frozen evaluator modules remain byte identical.
The original 24 outcomes and development gate/observation still validate. Deterministic re-export
of the two selected recordings produces identical bytes.

The scoped PostgreSQL audit checks every captured pre-pass application row: **163 runs, 752 events,
26 investigations, 24 repairs, 12 repository indexes, 1,008 source chunks, 12 source snapshots,
43 evaluations and 25 comparison snapshots** (guest/usage tables were empty). Every prior row hash
remains present and unchanged after regression/recovery checks. New validation records append to
history; the audit excludes migration version metadata and makes no claim about ignored runtime files.

All **20 local development/test audit records** remain available: five candidate failures, five
passes, three cancellations, three interruptions and four invalid-evidence views. The latter are
provisional M2 adapter executions made before run-admission verifier snapshots were added; their raw
results remain downloadable as unvalidated evidence. They are not asserted code defects. Final
implementation runs retain the admitted verifier identity for reopening. These are engineering
executions of known patches, not new agent trials or independent defect samples.
[Retained run index](assets/patch-audit-workflow/local-validation-runs.json).

The earlier [form-label failures](assets/patch-audit-workflow/initial-form-label-failure.log),
[editor-locator failures](assets/patch-audit-workflow/initial-editor-locator-failure.log) and
[full-suite pool failure](assets/patch-audit-workflow/initial-e2e-pool-failure.log) are retained separately.
No model calls, generation campaigns, historical rescoring, merges or visibility changes occurred.

[SHA-256 hashes for the selected evidence assets](assets/patch-audit-workflow/manifest.json).

Screenshots from actual supported-source executions (no provider inference):

- [Fresh incomplete repair: ordinary passed, independent failed](assets/patch-audit-workflow/fresh-missed.png).
- [Fresh complete repair: passed the named checks](assets/patch-audit-workflow/fresh-complete.png).
- [Recorded audit on mobile: saved execution clearly labeled](assets/patch-audit-workflow/recorded-mobile.png).

## Short code tour

- [Import boundary](../../backend/src/workbench/patch_audit/admission.py): exact context, Git application,
  finite limits, immutable software/import identities and source reconstruction.
- [Local API](../../backend/src/workbench/patch_audit/routes.py) and
  [persistence/lifecycle](../../backend/src/workbench/patch_audit/service.py): owner boundary, explicit
  confirmation, deduplication, history, cancellation and restart reconciliation.
- [Private broker](../../backend/src/workbench/patch_audit/broker.py) and
  [evaluator adapter/result validation](../../backend/src/workbench/patch_audit/execution.py): second
  admission, exclusive execution identities, frozen executor/scorers and versioned M2 cancellation.
- [Patch Audit UI](../../frontend/src/PatchAudit.tsx): review, fresh versus saved labels, deterministic
  explanations, protected selection/polling, evidence downloads and history.
- [Curated validation](../../backend/src/workbench/patch_audit/curated.py),
  [explicit export](../../scripts/export_patch_audits.py) and
  [recorded server](../../backend/src/workbench/release.py): selected genuine evidence with no runtime authority.

No known blocking defect remains within the verified local scope after these checks. Unsupported
diff forms and arbitrary repositories/languages remain outside the workflow. This delivery does not
change the hold on broad comparison-platform release/M3, authorize adversarial public execution, or
establish general independent-check accuracy. Stop this product pass for review.
