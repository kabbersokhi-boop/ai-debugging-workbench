# Patch Audit — final release review

Review date: 2026-10-27. This is an independent engineering assessment of the artifact,
not an official OpenAI review, endorsement, recruiter study or inference about its owner's ability.

## Source, scope and bounded plan

Started from actual public main `c8ab8ee5c3038e1dde59502a6ec843770842e946` in a clean
worktree, preserving the owner's G4 checkout and every accepted merge. Its Git tree matches
accepted G4 `bf081f28431c931025c5227b6e5b55c661fd8e42`.

Plan: inspect implementation and hosting; classify findings; make one small implementation
pass; run complete isolated checks and user journeys; publish one focused PR and a traceable
release; stage, test and promote the same recorded artifact; assess and stop. No new milestone,
model inference, candidate campaign, license change or infrastructure upgrade is included.

Reviewed AGENTS, README, release/architecture/code-tour/quickstart, G1–G4 reports and the
G3 compatibility/recovery correction. Followed source admission, exact patch application,
requirement/control material, runtime inspection, approval/result binding, persisted recovery,
frontend onboarding and the physically separate recorded server. Earlier reports retain their
historical branch/authorization statements; they are not current publication instructions.

## Findings and changes

| Class | Finding | Resolution |
|---|---|---|
| A — blocker | None established by completed verification | Publication still requires final integrated CI and actual production checks. |
| B — public clarity | README and quickstart described merged G4 as an unmerged candidate | Use released workflow, pin the first-audit instructions to `v1.2.0`, and explain the retained repository name. |
| B — onboarding | README local instructions foregrounded prepared historical tasks | Point directly to generalized Python/Node source, plan, controls and approval walkthrough. |
| B — traceability | Historical deploy recipe blindly archived `v1.1.0` | Resolve the tested release commit, stage production configuration without aliasing, verify and promote the same artifact; retain rollback identity. |
| B — presentation | No visible current release link; older walkthrough lacked version context | Add `v1.2.0` navigation, a real main-workflow badge and an explicit earlier-version video label. |
| C — future | Repeated-use value, manual specification effort and compatibility friction | Exactly three optional opportunities below; none implemented. |

No execution engine, dependency, verifier, historical evidence, test assertion, timeout,
database schema or admission/security policy changed. Existing accurate screenshots remain.
There is no project license grant; the README discloses that, and upstream notices remain.
Repository description, topics and homepage were already accurate and need no churn.

## Actual verification and limits

Final verification receipts are summarized here before publication; exact merge/tag/deployment
identities and subsequent production receipts are recorded in the release notes to avoid a
self-referential commit loop.

| Gate performed in this review | Actual result |
|---|---|
| `./scripts/check` | 387 offline passed, 104 deselected (33.55s); lint, formatting, Pyright and frontend build passed. |
| Initial `./scripts/e2e` | 87 passed, 13 failed, four skipped (548.28s). Broker logs prove Docker default address-pool exhaustion during candidate network creation. |
| Focused environment correction | Moved only this task's recorded network to explicit `10.243.45.0/26`; five unchanged verifier cases passed (62.86s). No network pruning, assertion or timeout change. |
| Complete corrected `./scripts/e2e` | 100 passed, four skipped, 387 deselected (772.67s). All nine G4 cases included, not extra totals. |
| Actual GitHub intake | Two passed, seven deselected (37.97s): real GitHub source verification, fresh Python/Node controls/approval/execution/download/history. |
| `./scripts/recovery-smoke` | Passed: interrupted run classified correctly, completed history unchanged, fresh reproduction succeeded, no runner cleanup errors. Four completed Python/Node downloads remained exact after restart, with exactly one original execution submission each and zero additional submissions. |
| Recorded image and `scripts/check_release.py` | Non-root/read-only, bounded local resources, no mounts/credentials/socket/authority modules, absent privileged routes; passed. |
| Established recorded browsers | Three passed, 488 deselected (9.15s), authentic failure/pass, exact diff/download, earlier debugger and mobile browsing. |
| Additional served-artifact/console checks | Both audit records, all three debugger recordings and all nine frontend assets exact; 23 privileged/private paths GET 404 / POST 405. Two desktop/mobile navigation/diff journeys had no page/console/HTTP/transport errors; benign media cancellations are recorded separately. |
| Documentation/preservation | 74 local links resolve; 1,776 protected paths unchanged; accepted main/G4 trees identical. |

Full logs, failed-run evidence, helper corrections and SHA-256 receipts accompany the release
as a bounded verification archive; CI's own artifacts retain its complete service logs.

The four existing opt-ins remain disabled: `LIVE_NVIDIA_E2E`, `LIVE_NVIDIA_REPAIR`,
`LIVE_NVIDIA_M4`, and `M4_SAVED_REOPEN` (requires a previous saved live run). No live provider call
was made. Deterministic UI response fixtures and source transport replay are labeled as such;
fresh ordinary/independent execution still uses real PostgreSQL, broker and Docker containers.
Actual GitHub intake is verified separately rather than inferred from those fixtures.
The extra console observer was corrected to open a collapsed comparison before checking it and
to report intentional navigation/media aborts separately from material errors; its failed
observations are retained. A focused command initially used a root-relative path although
`scripts/e2e` changes to `backend`; zero tests ran, and the invocation was corrected.

Isolation: project `patch-audit-final`, loopback ports 18210/18213/55439, separate named volumes
and explicit unused `10.243.44.0/24` subdivisions. Existing G4/G3c databases had only terminal
records and no candidate resources before testing. The frozen earlier offline harness resolves
the default broker by name; that existing idle broker was temporarily started and its original
stopped state is restored afterward. No owner database, volume or unrelated service is removed.
Ordinary and independent candidate phases have fresh separate restricted environments.

Coverage follows actual assertions: first startup/migrations; Python and Node admission,
requirements, synthetic controls, exact approvals, execution, downloads/history; editing clears
approval; missing checks remain not configured; unsupported production scope creates no run;
restart reconciles completed evidence without a duplicate execution; authentic recorded Boltons
failure, passing example, debugger, desktop/mobile navigation and exact diffs/downloads.
This uses a clean worktree and fresh task volumes, with existing host build caches and pinned
runtime images; it is not a clean-VM installation test. This is bounded Linux verification,
not universal compatibility, hostile-code security or
screen-reader certification. The existing large Monaco bundle warning is a performance limit.

## Evidence integrity and publication boundary

The featured Boltons patch is one genuine retained AI-generated incomplete repair: 155 selected
ordinary tests passed, while the standalone implementation failed independent checks. Multiple
failed assertions do not create multiple discoveries. The separately generated passing example
is not a controlled model ranking. G3 plus its Node addendum evaluated six genuine historical
developer candidates, five ordinary-passing and one regression already caught ordinarily:
zero additional independent findings. Reruns, controls and product acceptance are not candidates.

Historical freezes, old verifier versions, unsuccessful trials, provenance, logs and result
hashes remain unchanged. Replay/tamper tests validate their mechanical integrity; content hashes
do not authenticate a specification's truth. Controls test the authored mechanism, not semantic
correctness or coverage. Owner justification and finite JSON function examples remain essential.

Bounded local history scan: 2,919 reachable Git objects, 2,106 blobs, 47,938,537 bytes after fetch.
Six credential-URL pattern matches occur in upstream `test_urlutils.py` URL/userinfo fixtures;
inspection establishes synthetic parser examples, not real credentials. No tracked environment,
private-key or authentication-state file and no confirmed secret was found. This targeted scan
is not proof of absence; new public artifacts and the deployment allowlist are checked separately.
All 42 current compressed evaluation evidence files also passed a decompressed high-confidence
credential/private-key pattern scan. No repository content was uploaded to an external scanning service.

Existing hosting was resolved before pushing: team `mogging20202020`, Hobby,
project `prj_FIHQuwz4M2D2Jm8UMEMQ747p1td2`, no Git link/deploy hook, no password/SSO protection,
and only `RELEASE_SECURE_COOKIES` configured. Previous healthy production deployment:
`dpl_AmPBLGxg632KVXBjywFQMxskLESX`, source `c3bb3df5d6727ec36b837c3510f70ff60b1d41ae`.
Its unauthenticated HTTPS health and security headers were checked before replacement.

Only the documented Git-archive allowlist may be uploaded: recorded server/entrypoint, pinned
release requirements, frontend, curated recordings and build configuration. No normal application,
database, evaluator, private history, provider key, socket or execution fallback belongs there.
The actual recorded container is inspected, not merely its buttons. Local Compose memory/CPU/PID,
read-only-root and capability restrictions are not claimed as Vercel platform restrictions.
Vercel functions recycle and rate windows are process-local. Final receipts bind version, source
SHA, upload/file identities and deployment ID; metadata alone is insufficient source proof.

## Portfolio assessment

Subjective anchors: **5** competent with limited distinction/usability; **7** strong, working and
interview-worthy; **9** unusually compelling depth, usability and demonstrated value;
**10** exceptional evidence across the rubric, not framework quantity.

| Dimension | Weight | Score | Implemented evidence | Main limit; what would raise it |
|---|---:|---:|---|---|
| Immediate clarity and demonstrability | 20% | 8.2 | README genuine Boltons case, recorded viewer, guided `AuditGuide.tsx`, desktop/mobile journeys | First-time local setup still requires Docker and considerable spec input; observed successful unaided use would strengthen this. |
| Engineering depth and architecture | 20% | 8.5 | `repository_audit/intake.py`, `execution.py`, `service.py`: recomputed source, runtime inspection, exact approval, durable recovery | Trusted Docker broker/host authority and serial per-row startup recovery; demonstrated operational ownership under realistic load would justify more. |
| Reliability, testing and evaluation integrity | 20% | 8.3 | Complete regression journeys, recovery deadline regressions, tamper/replay validation, preserved G3 failures and honest denominator | Finite checks, retrospective convenience samples and in-process observation trust; prospective external review and measured operational reliability would strengthen the evidence. |
| Applied AI / agent-evaluation relevance | 15% | 7.6 | Genuine AI missed-copy evidence; separated producer/evaluator roles, versioned oracle material, retained model failures | Primary path uses no model; G3 finds no additional defect beyond ordinary tests; a prospective useful evaluation use case would raise this. |
| Practical usefulness and differentiation | 15% | 6.8 | Exact source/patch/approval/runtime/result chain, independent requirement provenance, recoverable downloadable evidence | Human specification work and narrow function/dependency scope; repeated voluntary use with measured useful outcomes is missing. |
| Reproducibility and explanation | 10% | 8.0 | Pinned environments, quickstart, source tour, frozen inputs and failure logs, separate recorded deployment | Heavy setup and machine-specific captured image IDs complicate exact historical reproduction; independent successful setup and spec reuse would improve it. |

Weighted overall: **7.955 → 8.0/10**. Recruiter first impression: **7.5/10**; immediate demo and
clear case earn attention, but the original repository name and broad legacy stack can obscure
the product. Technical hiring-manager assessment: **8.3/10**; traceable execution, honest oracle
limits and causal recovery work reward inspection, while practical adoption remains unproven.
These are judgments, not hiring probabilities, measured recruiter feedback or candidate rankings.

**Would it earn a closer look for AI engineering? Yes**, especially AI evaluation/tooling,
backend infrastructure for agents, reliability and developer-tool roles. It is weaker evidence
for model training, novel ML research, broad autonomous coding or production-scale operations.
A recruiter could dismiss it as another framework showcase if they miss the immediate recorded
case; lack of a project license can also limit trying/reusing it in an organization.

A senior engineer should challenge specification independence after public fixes were read,
in-process observation spoofing, exact JSON semantics, dependency compatibility, owner approval
authenticity, hash-versus-authenticity claims and recovery bounds across a larger backlog.
The biggest weakness is **evidence of product value**: one authentic additional historical repair
failure is compelling, but the separate six-candidate G3 study contributes zero new detections.
The scope and usability costs constrain how often the mechanism will be worth using.

The primary workflow uses deterministic source/diff validation, explicit owner-authored finite
contracts and isolated observation/comparison; **no active LLM, RAG, LangGraph or MCP is required**.
Those techniques remain real implementations in the earlier NVIDIA diagnosis/repair subsystem:
hybrid lexical/vector retrieval and reranking, typed model decisions, MCP tools and graph checkpoints.
Recorded playback executes none of those models. Listing them is not evidence of primary-path AI.

Beyond conventional pytest/CI, the stronger part is separately justified behavioral expectations
bound to exact artifacts and approvals, fresh phase isolation, explicit missing/error states and
durable evidence reconciliation. Pytest/CI can implement the checks themselves. Patch Audit does
not automatically discover the right requirement, establish complete correctness, defeat malicious
code or demonstrate broad detection superiority. Assessment of this repository cannot establish
the owner's personal authorship, unaided ability or interview readiness.

## Exactly three optional future improvements

1. **Test repeated-use value with a small prospective user exercise.** Problem: there is no evidence
   that intended users choose this over their existing CI workflow. Recruit two or three willing
   engineers, each with one supported real change and a requirement fixed before seeing the result;
   record setup/specification effort, supported/rejected outcomes and whether they voluntarily return.
   Effort: **small** for the study. Risks: private-code disclosure, post hoc oracle tuning and conflating
   assertions with defects; obtain consent, keep code local, freeze expectations and preserve failures.
   Acceptance: at least two users complete an audit unaided, all outcomes/effort are reported, and
   at least one returns for a second task. A negative result is still useful. This outranks more code
   because it tests whether the product's central cost/value tradeoff deserves further investment.

2. **Reuse reviewed requirement packs with explicit invalidation.** Problem: repeatedly authoring
   provenance and JSON examples costs more than rerunning tests. Smallest implementation: export/import
   one versioned declarative pack, bound to a source contract and domain, with a readable diff; import
   grants no approval and still requires current controls and owner review. Effort: **medium**.
   Risks: stale/poisoned specifications, leaked private excerpts and accidental approval inheritance;
   allow no executable checker uploads and validate every binding. Acceptance: reuse a pack on two
   supported changes, reject mismatched source/domain, and prove edits/import invalidate prior approval.
   It ranks ahead of new languages/frameworks because it reduces the main recurring human cost.

3. **Explain compatibility before requirement authoring.** Problem: a user may spend time on a spec
   before discovering an unsupported dependency or runtime. Smallest implementation: inert source/runtime
   inspection followed, only with exact approval, by a bounded ordinary-test preflight; show concrete
   unsupported reasons and preserve its evidence. Effort: **medium**. Risks: setup hooks executing too
   early, dependency fetching and confusing preflight with correctness; retain offline restricted
   execution and separate outcomes. Acceptance: accepted Python/Node examples get an actionable result,
   a missing-dependency example is rejected before independent authoring, and intake alone executes
   nothing. It outranks another dashboard or broader language support because it avoids wasted user work.

## Owner interview preparation

Be able to explain or debug these five areas without AI assistance:

1. Git blob/tree recomputation, archive/path rejection and exact patch admission; trace one byte change.
2. Requirement provenance and JSON oracle semantics; why controls cannot establish specification truth.
3. Docker broker authority, separate read-only inputs, actual resource inspection and observation spoofing limits.
4. Approval/plan/runtime/result identities, database terminal guards and invalidation after an edit.
5. AnyIO level cancellation versus the historical swallowed native timeout; restart reconciliation and why reopening is not rerunning.

## Release readiness

Local release gates passed after the documented host-subnet correction. The complete required
checks, actual GitHub journeys, recorded-image inspection and recovery evidence support release
readiness within the stated scope. No unresolved product blocker was found. Final integrated
main CI, annotated tag, production-configured staged artifact checks, same-artifact promotion,
unauthenticated production verification and deployed-file/source binding must all succeed before
the release operation is declared complete. Their receipts belong in the `v1.2.0` release notes.
Branch protection/rulesets were inspected; none were configured. No protection or review is bypassed.

**Recommendation: Use this version now** for the documented bounded local workflow and recorded
portfolio demonstration, once the release-note production receipts confirm publication. This is
not a recommendation to expose the execution stack or claim universal correctness.
