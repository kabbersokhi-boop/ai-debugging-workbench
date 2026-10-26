# G4 — Patch Audit product and release readiness

Tested implementation: `ca56acfb9120aa42aef70b794b995008d4b42ca2`.
Stacked [PR #16](https://github.com/kabbersokhi-boop/ai-debugging-workbench/pull/16)
targets `feature/generalized-patch-audit-g03-compatibility` at accepted
`9c025a37cc4a01d86ce0af599776a73a07b2bc16` (#12 → #13 → #14 → #15).
All dependencies remain unmerged. [Frozen scope](../plans/GENERALIZED-PATCH-AUDIT-G04.md).

**Recommendation: PASS for independent engineering review.** Final report/evidence-head CI must
also pass before handoff; its exact SHA/run URLs are recorded on PR #16 after this commit.
The [implementation fingerprint](assets/generalized-patch-audit-g04/implementation-fingerprint.json)
binds all runtime, test, workflow and frozen-evidence Git objects to the tested implementation.

## Product scope and actual changes

The existing evaluator, admission policy, plan/approval contracts, verifier definitions, runtime
images and restart correction are reused. No parallel audit backend or research campaign.

| Before | G4 candidate |
| --- | --- |
| Prepared-task entry, generalized intake behind a selector | Obvious **Audit a completed patch** action, cohesive product header and six-step workflow |
| Research panels precede source intake | Source/patch journey first; historical campaign/addendum remain a separate research section |
| Requirement authoring starts with a JSON document | Guided provenance and finite behavior-example forms; advanced JSON retained without changing requirement semantics |
| Approval foregrounds a raw plan dump | Command, environment, budget and independent scope first; exact identities/payloads remain inspectable |
| Outcome context buried in raw evidence | Separate ordinary/independent cards, immutable source/patch/test context, readable expected/observed values and direct download/history |
| Recorded viewer opens directly into historical results | Product explanation, authentic case-study context and separate study accounting; recorded-only boundary remains explicit |
| README foregrounds the earlier four-task workflow | Ordinary-English product explanation, practical Python/Node walkthrough, actual interface screenshots and Mermaid trust boundaries |

New backend authority is limited to local-only public PR **metadata preview**. The recorded server,
source admission, evaluator, evidence validator, recovery manager and database schemas are unchanged.
Modified legacy browser assertions follow updated visible wording/editor selection; the original
restart scenario, its assertions and its 90-second readiness budget remain intact.

## GitHub PR preview: deliberately bounded

`POST /api/repository-audits/github-preview` inherits the existing local-owner and origin gate.
It accepts only canonical `https://github.com/owner/repository/pull/123` URLs. It constructs two
fixed `api.github.com` requests, sends no credentials/cookies, ignores environment proxies,
follows no redirects, limits response bytes (100/300 KB), applies five-second HTTP and
12-second AnyIO level-cancellation total budgets, and uses the existing single intake lock.

It displays observed repository/PR/base/head identities and change counts. Results explicitly say
`not_admitted` and `execution_authorized: false`. There is no source archive, diff, file import,
candidate creation, command inference or execution. No preview record enters scientific evidence.
Mutable PR heads cannot replace admitted bytes because metadata is never used to create a snapshot
or candidate. Manual immutable source admission still recomputes archive/tree/blob identities;
patch admission still applies every existing policy and content identity check.

A full importer is excluded: a PR's base tip need not be its diff's merge-base, and PRs commonly
change tests/configuration or add/delete files outside the admitted policy. Private/deleted heads,
redirects, rate limits, oversized/invalid responses, timeouts and transport failures are unsupported
states with a manual-intake explanation. Every upstream error maps to a preview-specific bounded
failure. This is a convenience for inspection, not a complete PR evaluator.

## Independent requirements, approval and outcomes

Guided authoring edits the same requirement/assertion payloads as Advanced JSON. It starts with
blank expectations and no assertions: the application never invents an expected answer. Exact
excerpt hashes are recomputed; provenance, domains, assumptions and ambiguities remain accessible.
Controls must pass before exact independent approval. Expected values are withheld from the scored candidate’s observation container and compared by
the trusted broker. Synthetic controls necessarily encode their authored outputs;
ordinary tests, controls and candidate observations retain their fresh, separate environments.

Requirement/assertion/module/setup/timeout edits clear validation, exact independent approval and
parent execution confirmation. Historical results remain persisted and reopenable. Loading saved
history grants no new execution approval. Current Node execution uses fresh current-verifier
validation; retained validation IDs are not reused as authorization.

The result summary uses both phases: it distinguishes ordinary failures, an additional independent
failure, both failures, successful declared checks and no configured independent checks. Invalid,
unsupported, incomplete, interrupted, cancelled and infrastructure outcomes retain their actual
status/reason and never become a passing conclusion. Generalized command test counts remain
**unknown**, since the runner contract retains exit status/output rather than parsed counts.
Multiple failed observations are not labeled multiple unique bugs.

## Browser evidence

Actual execution evidence, screenshots and exact totals are retained in
[assets/generalized-patch-audit-g04](assets/generalized-patch-audit-g04/).

The deterministic CI journeys replay only the previously accepted public source transport into
the real database. Patch admission, requirement/plan creation, controls, explicit approval,
execution, saved evidence and downloads use the actual API/PostgreSQL/broker/Docker path. The
transport substitution is explicit in every journey record; it is not claimed as live upstream
source retrieval. Separate local live-source journeys exercise the actual GitHub adapter when
available. G2 positive examples are product acceptance, not new G3 campaign observations.

The Boltons journey replays authentic immutable AI-generated evidence. It makes no new submission,
model call, execution or discovery. The rejected production-scope case uses actual admission and
asserts unchanged run history. Response-race and combined-failure fixtures are UI contract tests,
explicitly separate from scientific results.

| Required journey | Actual evidence | Screenshots |
| --- | --- | --- |
| Python bounded audit | Live GitHub admission of accepted G2 `hynek/first`; fresh controls/approval/execution, ordinary and independent success; exact download/history. Audit `557dce6b-8353-43ef-a1b4-ae734970c0ec`. [Journal](assets/generalized-patch-audit-g04/live-source/python-positive/journey.json) · [Evidence](assets/generalized-patch-audit-g04/live-source/python-positive/evidence.json) | [Intake desktop](assets/generalized-patch-audit-g04/intake-desktop.png) / [mobile](assets/generalized-patch-audit-g04/intake-mobile.png) · [Requirements](assets/generalized-patch-audit-g04/python-requirements.png) · [Result desktop](assets/generalized-patch-audit-g04/python-result-desktop.png) / [mobile](assets/generalized-patch-audit-g04/python-result-mobile.png) |
| Genuine Node support | Live GitHub admission of accepted G2 `component/escape-html`; correct pinned Node 22/Mocha environment, fresh current-verifier controls/approval and successful separate outcomes. Audit `20fc8e4b-453e-4484-a9ca-1be0fd1a21e9`. [Journal](assets/generalized-patch-audit-g04/live-source/node-positive/journey.json) · [Evidence](assets/generalized-patch-audit-g04/live-source/node-positive/evidence.json) | [Desktop](assets/generalized-patch-audit-g04/node-result-desktop.png) / [mobile](assets/generalized-patch-audit-g04/node-result-mobile.png) |
| Independent detection | Authentic saved Boltons AI missed-copy evidence; ordinary pass, independent failure; one incomplete repair, separate earlier study. Replay only. [Journal](assets/generalized-patch-audit-g04/recorded-journey.json) | [Desktop](assets/generalized-patch-audit-g04/boltons-desktop.png) / [mobile](assets/generalized-patch-audit-g04/boltons-mobile.png) |
| Rejected/incomplete input | Actual API rejects a test-file patch with HTTP 422; no candidate/result, unchanged run history. Unsafe preview URL also fails visibly. [Rejection](assets/generalized-patch-audit-g04/rejected-patch.json) | [Rejected patch desktop](assets/generalized-patch-audit-g04/rejected-patch-desktop.png) / [mobile](assets/generalized-patch-audit-g04/rejected-patch-mobile.png) |
| Recorded boundary | Actual local release container, three browser journeys, immutable evidence downloads and zero mutation requests. [Boundary log](assets/generalized-patch-audit-g04/recorded-boundary.log) | [Introduction desktop](assets/generalized-patch-audit-g04/recorded-intro-desktop.png) / [mobile](assets/generalized-patch-audit-g04/recorded-intro-mobile.png) |

The actual public PR #15 metadata preview resolved accepted head `9c025a37…`, reported 157
changed files and explicitly admitted nothing. [Response](assets/generalized-patch-audit-g04/live-pr-preview.json) ·
[desktop](assets/generalized-patch-audit-g04/github-preview-desktop.png) /
[mobile](assets/generalized-patch-audit-g04/github-preview-mobile.png).
Its metadata is not evidence that this large PR satisfies production-only patch admission.

[Post-restart browser proof](assets/generalized-patch-audit-g04/post-restart/proof.json) additionally
reopens both earlier G4 live-source audits after the complete-suite restarts and smoke. Full
saved evidence remains exact. Each had one original execution submission and **zero submissions
after container recreation**. Reopening creates no new execution.

## Public boundary, accessibility and documentation

The actual recorded image is checked for non-root/read-only configuration, resource limits, no
host mounts, Docker socket, workbench/evaluator/agent modules, provider/database credentials or
privileged routes. Preview, source, candidate, approval, execution, cancellation and recovery
requests remain unavailable. Browser journeys allow GET/HEAD only. The public deployment is not
changed by G4; these are local release-candidate checks.

Keyboard skip navigation, visible focus, labeled controls, text statuses, semantic headings and
390px mobile overflow are exercised. Desktop captures are 1440px wide. Evidence is progressively
disclosed; large diffs/logs remain scrollable. This is not a full screen-reader or WCAG certification.
The browser title, description, social metadata and favicon identify Patch Audit without adding
unsupported claims. [README](../../README.md), [first-audit guide](../PATCH-AUDIT-QUICKSTART.md) and
[Mermaid architecture](../ARCHITECTURE.md#patch-audit-trust-boundaries) explain the two deployment
surfaces, local prerequisites, genuine defect case, Python/Node scope and honest G3 findings.

## Retained development failures

The first exploratory browser run failed four tests: a new assertion incorrectly expected
`checks_passed` instead of the established saved status `completed`; a concurrent image rebuild
interrupted later validation/navigation. The summary and assertion now use the existing contract;
subsequent execution uses a stable, ready stack. No backend verdict or readiness timeout changed.

A later focused run passed seven cases and failed two test assertions: keyboard input was sent
before the asynchronous application had mounted, and rejection expected an internal underscore
status rather than the existing human-readable text. Waiting for the visible application heading
and checking the actual rejection wording corrected those assumptions. Both targeted cases passed.
Original failure logs are retained; failed attempts are not reported as passes or scientific trials.

The first complete implementation CI runs at `1a18b23` failed: **387 offline passed; 98
integration/browser passed, two failed, four existing opt-ins skipped**. The failures were the
omitted existing **Agent Evaluation** navigation link and the prepared-task browser's obsolete
`Patch Audit` heading assertion after the intended introduction change. Restore the existing link;
update only the heading assertion, retaining the complete real import/execution/download/reopen
scenario. Original restart and subsequent API-scenario tests passed in both failed workflows.
Later smoke/release gates were skipped because integration failed, not claimed as passing.

- [Initial push failure 40408801629](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/runs/40408801629)
- [Initial PR failure 40408844672](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/runs/40408844672)

The local full-suite helper was once invoked using system Python instead of the project virtual
environment and failed to import Docker before collecting tests. It was launched through the
existing project environment; no package installation or test changes were needed.

The intermediate navigation-fix workflows correctly reduced the failure to the obsolete heading
assertion: **99 passed, one failed, four skipped**. [Push](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/runs/40410204469) /
[PR](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/runs/40410210403).
The unchanged complete journeys both passed after correction ([focused log](assets/generalized-patch-audit-g04/restored-existing-journeys.log)).
No workflow reruns, removed scenarios, skipped regressions or increased timeouts were used.

## Final verification and CI

| Gate at tested implementation | Actual result |
| --- | --- |
| `./scripts/check` | Ruff/format/Pyright/frontend build passed; **387 offline passed, 104 deselected**, 24.45s. [Log](assets/generalized-patch-audit-g04/check.log) |
| `./scripts/e2e` | **100 passed, four pre-existing opt-ins skipped, 387 deselected**, 592.78s. All nine G4 cases, restored earlier journeys and original restart/API scenarios passed. [Full log](assets/generalized-patch-audit-g04/e2e.log) |
| Focused boundaries | **29 new preview security/error cases** and **13 unchanged recovery regressions** included in offline totals. **Nine G4 browser cases** included in full e2e, not extra totals. [Browser subset](assets/generalized-patch-audit-g04/focused-browser-summary.json) |
| Actual GitHub source transport | **Two passed**, 37.82s; fresh Python/Node UI journeys. [Log](assets/generalized-patch-audit-g04/live-source.log) |
| `./scripts/recovery-smoke` | Passed: completed history unchanged, fresh post-recovery run reproduced, cleanup errors false. [Log](assets/generalized-patch-audit-g04/recovery-smoke.log) |
| Actual recorded boundary | Passed: non-root/read-only, bounded resources, no authority modules/socket/mounts/credentials, privileged GET 404 / POST 405. [Log](assets/generalized-patch-audit-g04/recorded-boundary.log) |
| Actual recorded browsers | **Three passed**, 7.13s; desktop/mobile, authentic failure/pass evidence, no mutations. [Log](assets/generalized-patch-audit-g04/recorded-browser.log) |
| [Implementation push CI](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/runs/40411229304) | Passed: 387 offline (19.02s), 100 integration/browser + four skips (400.88s), recovery, recorded boundary, three browsers (5.33s). |
| [Implementation PR CI](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/runs/40411237325) | Passed: 387 offline (23.94s), 100 integration/browser + four skips (500.86s), recovery, recorded boundary, three browsers (6.59s). |

Four existing opt-ins remain explicit: `LIVE_NVIDIA_E2E`, `LIVE_NVIDIA_REPAIR`, `LIVE_NVIDIA_M4`
(real inference) and `M4_SAVED_REOPEN` (requires a prior saved live demonstration). None was enabled.
No paid/live model inference occurred. The Node compatibility addendum, original G3 campaign and
separate earlier Boltons study remain distinct; there was no new benchmark campaign.

The original repository restart became usable in **18.636s**; completed evidence was exact, the
missing result became interrupted after **37 broker 404s**, with one completed execution submission
and one successful terminal fetch. [Observation](assets/generalized-patch-audit-g04/repository-recovery.json).
The original scenario's function is byte-identical; its readiness remains **90 seconds** and CI
remains **20 minutes**. The accepted recovery implementation and its per-audit budgets are unchanged.

Logs were read, not just exit codes. Both originally failing recovery/API tests passed in both
successful implementation CI runs. Local service review found only the expected database
immutability rejections from negative tests; no unhandled API exception. One intentional legacy
debugger preview (600-second TTL) was cleaned via its existing private broker endpoint, preserving
its saved verified record. No execution containers/volumes remain. The legacy default-broker
precondition was explicit, its source hash checked and original stopped state restored. Unrelated project services were untouched. [Cleanup](assets/generalized-patch-audit-g04/cleanup.json) ·
[Service review](assets/generalized-patch-audit-g04/service-log-review.json).

The final report/evidence commit changes no runtime, tests or workflows. Exact final head and final
push/PR run URLs are recorded on [PR #16](https://github.com/kabbersokhi-boop/ai-debugging-workbench/pull/16),
whose final-head checks must also pass before handoff. The self-referential commit/run IDs are
recorded there after creating this report. [Fingerprint](assets/generalized-patch-audit-g04/implementation-fingerprint.json)
provides independent Git-tree/blob equality verification against `ca56acfb…`.

## Historical preservation and release decisions

[Preservation proof](assets/generalized-patch-audit-g04/preservation.json): **1,643 protected files**
match accepted PR #15 byte-for-byte, including all pre-existing backend source except the extended
route module. All **19 existing route functions are AST-identical**. All **28 original campaign**
and **12 addendum records** validate; all **12 prior private Node records and downloads** remain
exact. Source admission, candidate application, requirements/verifiers, candidate runtime images,
approval/evidence identities and engine digest `9bc99b9a…` are unchanged. No historical result hash
or frozen study input was rewritten. Served frontend bytes and recovery/preview modules match the
tested checkout ([served identities](assets/generalized-patch-audit-g04/served-implementation.json)).

| Decision | Status |
| --- | --- |
| Ready for independent engineering review | **PASS** at tested implementation; final documentation-head CI is a mandatory handoff gate. |
| Ready to integrate the stacked chain | Technically reviewable; independent review and a separate integration decision remain pending. PRs #12–#16 remain unmerged. |
| Ready to publish a release | Validated candidate only. No release/tag created; integration, release review and owner authorization remain separate. |
| Ready to deploy updated recorded content | Local recorded candidate validated. Existing public viewer not republished; deployment review and authorization remain separate. |

Remaining limits: PR metadata is not full PR import; source/network availability and API rate limits
can reject intake. Python/Node and finite declarative checks remain deliberately bounded. Owner
approval does not prove a specification true; controls do not establish broad oracle accuracy.
Containers share the host kernel; use an isolated disposable VM for adversarial source. Recovery
budgets are per running audit, not constant for an arbitrary backlog. Accessibility checks cover
semantics/focus/responsiveness, not full screen-reader certification. Large lazy Monaco assets retain
the existing build warning; no production-scale performance claim is made. Project licensing is
unchanged. Public production availability is not a new release certification: the GET-only check
returned HTTP 200 and recorded mode with zero execution slots/provider budget, with no deployment.

**Recommended verdict: PASS for independent engineering review after both final-head CI gates pass.**
No merge, deployment, release, inference, historical G3 rerun or new research milestone occurred.
Stop for independent review.
