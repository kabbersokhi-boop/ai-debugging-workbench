# G3 Node compatibility addendum

## Result

Both originally unsupported Node candidates now complete their two formal repetitions.
Each run passes the **same 2 unchanged ordinary tests and 5 original independent assertions**.
There are **zero additional independent findings**, repeat disagreements, disputed checks,
or remaining compatibility blockers in this declared scope.

Recommendation: **PASS for this narrow compatibility completion; G4 remains on hold.**
No performance improvement, broad false-positive rate, general superiority or AI-agent
accuracy is established by this retrospective sample. No new candidates or repositories
were selected and no completed Python candidate was rerun for this study.

The [original G3 report](GENERALIZED-PATCH-AUDIT-G03.md), declaration, outcomes, audit IDs,
adjudications and logs remain byte-identical. Its historical result stays **4/6 evaluated,
two unsupported, zero additional findings**. This separate addendum completes the two
missing candidates under new, explicitly declared execution conditions.

## Corrections

### Historical dependency

At immutable base `280845c6f384fab8ff07a1395de9568270636528`, the unchanged `test.js`
imports `array-flatten`. Its `package.json` requires **`^1.0.0`**, without a lockfile.
The import is retained even though that variable is unused in the selected assertions.
We explicitly pin compatible **1.0.0**, not an unknowable historical installed resolution.

The [dependency capsule](../../docker/node-compat/manifest.json) binds the registry
[version metadata](https://registry.npmjs.org/array-flatten/1.0.0), SHA-512 integrity,
archive SHA-1/SHA-256, upstream git revision and four exact file hashes. Registry archive
integrity was checked before copying only regular, allowlisted package files; no package
code, install hook or target code ran on the host. MIT permission and attribution are
retained with the capsule. It has no runtime dependencies.

`node22_compat` is a **new** runtime, `patch-audit-node:22-compat-v1`, with the same pinned
Node 22.22.0 base and locked Mocha 11.7.5 as the original preset. A trusted build verifier
checks capsule bytes without importing the library. Both dependency material and root
filesystem are read-only. The preset excludes writable `/work/node_modules` from
`NODE_PATH`; ordinary tests resolve the pinned image material. The original Node preset,
lockfile and historical image identity are preserved.

### Literal safe filenames

The exact historical path `benchmark/code/arr-flatten-0.1.0 (do-while).js` is now accepted
under **`relative-ascii-spaces-v2`**, captured in new source metadata and snapshot/plan
identities. The policy adds ASCII spaces and parentheses, preserves names exactly, and
rejects leading/trailing component spaces, trailing dots and case aliases of `.git`.
There is no trimming, separator rewriting, Unicode normalization or shell interpolation.

Absolute paths, traversal, repeated separators, `.` components, backslashes, drive prefixes,
control characters, invalid encodings and shell metacharacters remain rejected. Archive
symlinks/hardlinks, duplicates, file/directory collisions and non-directory trailing-slash
aliases are rejected before source initialization. Existing path/file/archive limits remain
unchanged. Docker receives an archive of validated regular files; commands and working
directories use argument arrays and Docker APIs. Actual initialized file hashes must match
the entire immutable Git tree before tests execute.

Legacy stored snapshots retain the original v1 policy in memory and on disk. The sandbox
policy is unchanged. This expands source intake, not the existing production-diff grammar:
both selected changes still modify only `index.js`.

## Preflight and freeze

Before formal scoring, both **unchanged** bases were fetched through the real local intake,
checked against GitHub tree/blob identities and executed in fresh restricted preflight
containers. No candidate patch or test edit was applied. The owner-only CLI prepares a
concrete source/runtime/command review and requires its exact plan hash before execution;
it exposes no HTTP route. Approval records state that Codex acted under the owner's
current delegated task authorization, not a captured human UI approval. Old G3 approvals
and controls were not reused.

| Case | Exact unchanged base | Git tree | Selected command/result |
|---|---|---|---|
| `flatten-recursive` | `280845c6f384fab8ff07a1395de9568270636528` | `594c69fb62dbf616a7b118b7ac085eec203d0e5d` | `node /opt/test-tools/node_modules/mocha/bin/mocha.js test.js` — exit 0, 2 passing |
| `flatten-for` | `966022a4a9190ddf8c8936daa80d1a7f9f77ecb3` | `057ed246be77c9da5564874694df9b5eaecbaddb` | Same unchanged command — exit 0, 2 passing |

[Preflight source snapshots, exact reviews, approvals and full Docker/output evidence](../../evaluation/repository-examples/g3-node-compatibility/base-preflights)
are frozen with the addendum. The images and capsule were verified, the actual initialized
source matched every base file, restrictions were inspected, and cleanup was confirmed.

Freeze commit: **`615b290`**. [Addendum declaration](../../evaluation/repository-examples/g3-node-compatibility/campaign.json):
**`166219b9c4b188e90c7f48ebadf757e27246929eba5a5ba140ff516383c6ba36`** (SHA-256).
Runtime image: `sha256:b6d2d1152ed7dd9ce3fbc96290799b1903f75bfe3054d32df649bf3d691a63e4`.
The declaration freezes exact prepared application plans, source/candidate/requirement
identities, original patches/assertions, adapter hashes, new engine/intake identities,
commands, order, acceptance criteria and limits before scoring.

The bounded procedure permits 4 formal audits, 4 control validations, 2 references and
2 authored alternatives: **12 planned API audits**, plus the two unchanged-base preflights.
It allows at most one separately recorded campaign infrastructure recovery; **none was used**.
The separate engineering-suite setup recovery below did not repeat any campaign audit.
No semantic result was retried outside the two declared repetitions. Any unknown attempt
must be inspected rather than automatically restarted.

## Exact candidate outcomes

| Genuine candidate | Upstream revision | Formal audit IDs | Ordinary / independent, each repeat |
|---|---|---|---|
| Recursive optimization | `1597ea90072a2eaff8e523523e0105cac0bf195c` | `3f04cfa7-4232-4274-b952-eaa464535f37`, `ab9011ae-320c-40b5-89b5-4381e01432ff` | 2 tests passed / 5 assertions passed |
| Loop optimization | `8953ce8522ee6da8a467286c9bce23fc03b7f38e` | `6556c1a8-a99e-4b20-a99b-d14106bee727`, `b8b787d9-0141-4f90-89ea-f0c338830a72` | 2 tests passed / 5 assertions passed |

Both original full diffs and production-only projections are retained unchanged. Newly
submitted upstream tests remain excluded consistently, and the selected baseline file is
unchanged. These are selected test files, not full upstream CI suites or performance tests.

Fresh positive/negative controls passed for each of the four new exact plans. The two
upstream references and two Codex-authored alternatives each passed 2 ordinary tests and
all 5 assertions **before formal scoring**. References overlap the genuine candidates;
alternatives are controls, not additional submissions. The requirement is still recursive,
ordered flattening of dense JSON arrays with leaf values and duplicates retained. No
expected value or supported domain changed after observations.

## Accounting and visible evidence

| Scope | Distinct formal candidates | Formal audits | Ordinary-passing candidates | Ordinary failures | Additional findings |
|---|---:|---:|---:|---:|---:|
| Original G3, frozen historical result | 4/6 | 8 | 3/4 evaluated | 1 known historical Python regression | 0/3 ordinary-passing |
| Separate Node addendum | 2/2 | 4 | 2/2 | 0 | 0/2 ordinary-passing |
| Combined distinct coverage | 6/6 | 12 | 5/6 | 1 | **0/5 ordinary-passing** |

There are no unsupported/incomplete addendum cases, invalid/disputed independent checks,
or repeat disagreements. Combined identity uses repository, immutable base and admitted
patch hash; controls, references, authored alternatives and repetitions do not increase the
unique candidate denominator. The Node image and intake policy differ explicitly from
original G3; combined coverage describes these fixed requirements under declared runtime
conditions, not a single unmodified experiment or a population estimate.

All twelve [application downloads, approval intents, plan hashes, observations and logs](../../evaluation/repository-examples/g3-node-compatibility/results)
are retained and revalidated with the same application evidence validator. Summaries are
generated from validated records. The original UI remains at 4/6; a separate labelled
Node addendum panel uses the existing result, provenance, download and saved-link view.
Reopening is read-only and starts no new execution.

## Verification and delivery

The implementation tested locally and in both CI events is
**`98a57bd3f91116e6cd3f18ef986e2301543195d7`**. The following delivery commit adds only
this report and its review evidence. Its exact final SHA and final-head CI URLs are
recorded in [PR #15](https://github.com/kabbersokhi-boop/ai-debugging-workbench/pull/15),
whose head is also available as `refs/pull/15/head`. This avoids embedding a commit's own
hash in its contents. The PR is stacked on unmerged
[PR #14](https://github.com/kabbersokhi-boop/ai-debugging-workbench/pull/14) at
`4c73c9d125617bc82195e759da267aee5d24606c`; accepted G3 implementation
`679e3e739d172a83a8ccb8a085006c99392012de` is unchanged.

The [review evidence index](assets/generalized-patch-audit-g03-compatibility/README.md)
contains logs, identity checks and public-case screenshots. These engineering checks
are distinct from the twelve frozen application audits.

| Check | Actual result and evidence |
|---|---|
| `./scripts/check` at tested implementation | Ruff, Pyright, frontend build and **345 offline tests passed**; 95 integration/opt-in tests deselected. [Log](assets/generalized-patch-audit-g03-compatibility/check.log). |
| Complete standard-topology CI | **91 integration tests passed, 4 existing live opt-ins skipped**; 345 offline tests separately passed. Recovery smoke, release-server check and **2 recorded browser tests** passed. [Job steps, durations and result lines](assets/generalized-patch-audit-g03-compatibility/ci-tested.json). |
| First isolated local `./scripts/e2e` | **18 failed, 73 passed, 4 skipped**, 450.09s. Seventeen failures followed Docker address-pool exhaustion; one was the inherited harness topology precondition below. [Retained failures](assets/generalized-patch-audit-g03-compatibility/development/e2e-initial-failure.log), [Docker errors](assets/generalized-patch-audit-g03-compatibility/development/docker-pool-failure.log). |
| One full isolated local rerun | **1 failed, 90 passed, 4 skipped**, 532.93s, after relocating only this task's four control networks to checked, non-overlapping explicit /26 subnets. [Full log](assets/generalized-patch-audit-g03-compatibility/e2e-local-isolated.log). |
| Remaining unchanged harness test | **1 passed**, 21.85s, in its expected broker topology. [Log](assets/generalized-patch-audit-g03-compatibility/legacy-harness-test.log), [source identity and original stopped-state restoration](assets/generalized-patch-audit-g03-compatibility/legacy-harness-check.json). |
| Local `./scripts/recovery-smoke` | Passed, no cleanup errors; [log](assets/generalized-patch-audit-g03-compatibility/recovery-smoke.log). All **12 saved records and downloads** remained exact after restart/recovery, with no new execution. [Runtime and history check](assets/generalized-patch-audit-g03-compatibility/history-runtime-audit.json). |
| Actual compatibility sandbox | Passed capsule version/import, literal historical filename, denied source/dependency writes, no Docker socket and immutable dependency search path. [Inspection](assets/generalized-patch-audit-g03-compatibility/capsule-security-regression.json), [test](assets/generalized-patch-audit-g03-compatibility/capsule-security-test.log). |
| Separate addendum browser | Passed both saved candidates, downloads, reload and candidate/audit synchronization. Original panel remains 4/6; addendum 2/2 and labelled combined 6/6. Passed again within the full local rerun and standard CI. [Original/addendum view](assets/generalized-patch-audit-g03-compatibility/separate-addendum.png), [recursive](assets/generalized-patch-audit-g03-compatibility/flatten-recursive.png), [loop](assets/generalized-patch-audit-g03-compatibility/flatten-for.png). |
| Actual recorded image | Server boundary passed; **2 browser tests passed**. Source/addendum routes return GET 404 / POST 405. No privileged import/execution service, database, Docker socket or provider credentials added. [Server](assets/generalized-patch-audit-g03-compatibility/recorded-boundary.json), [new routes](assets/generalized-patch-audit-g03-compatibility/recorded-addendum-boundary.json), [browser](assets/generalized-patch-audit-g03-compatibility/recorded-browser.log). |
| Preservation and cleanup | **1,419 protected historical files byte-identical**; observer/v1 and original runtime unchanged. **26 preflight/audit execution environments**, including two base preflights; **70 recorded Docker resources actually absent**. [Completion audit](assets/generalized-patch-audit-g03-compatibility/completion-audit.json). |

The isolated local full suite was **not wholly green**. The frozen legacy harness resolves
`ai-debugging-workbench-repair-broker-1` and `ai-debugging-workbench_repair-control` by name.
That default broker was stopped while the task used project `patch-audit-g3c`; its empty
IP produced `http://:8012` and `httpx.UnsupportedProtocol`. We temporarily started only
that existing broker, checked its unchanged source hash and absence of active repair
sandboxes, ran the unchanged test once, and restored its stopped state. No frozen script,
test, timeout or sandbox permission was changed. The complete CI uses the expected
default topology and passes all 91 integration tests.

The [engineering recovery record](assets/generalized-patch-audit-g03-compatibility/engineering-recovery.json)
separates address-pool recovery, one full-suite rerun and one targeted legacy precondition
check from **zero campaign retries**. Task data volumes were retained; unrelated networks
were not pruned and their prior IDs remained present. Infrastructure failures remain
visible and are not described as reproduced candidate defects. CI's tested PR job took
**9m27s**, including **6m14s** for the integration step, below the unchanged 20-minute
workflow limit. No timeout increase, removed test or cancellation retry was needed.
The earlier original G3 parallel-watch cancellation remains a cancellation, not an
assertion failure.

Implementation CI history, all successful:

| Implementation SHA | Push | Pull request |
|---|---|---|
| `22738a0df78fadf81dfa45b8024db4e82d8a9c05` | [40222391064](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/runs/40222391064) | [40222508233](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/runs/40222508233) |
| `98a57bd3f91116e6cd3f18ef986e2301543195d7` | [40223718820](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/runs/40223718820) | [40223722707](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/runs/40223722707) |

Final-head CI must be checked at PR #15 after this report-only commit is pushed; the
handoff includes those final run URLs and statuses, rather than treating this earlier
implementation CI as final-head verification.

## Replay and limits

From the repository root, `uv run --project backend pytest backend/tests/test_node_compatibility.py
backend/tests/test_node_compatibility_replay.py` validates retained evidence and tamper
rejections without candidate execution. The checked-in SHA-256 manifests identify bytes;
they are not external signatures. The full application validator rejects forged run IDs,
changed plans, patch/source claims, capsules and mismatched engine identities. Legacy
snapshots still replay under their original path policy. Fresh runtime approval and
positive/negative controls are required; an old approval cannot authorize the new runtime.

The completed campaign budget is exhausted. Do not rerun its candidate execution command
as an evidence replay. A new experiment would require its own declaration and exact
approval. Local security/browser fixtures and the offline repair provider used in engineering
tests are synthetic and are excluded from the genuine candidate denominator; no model
inference was performed.

This remains two previously selected optimizations from one historical Node repository,
with known upstream outcomes and independently authored but retrospective requirements.
The assertions cover dense JSON arrays, ordered recursive flattening, leaf values and
duplicates; they do not establish sparse-array, cyclic/shared-identity or performance
behavior. Version 1.0.0 is an explicit compatible dependency resolution, not proof of the
original installation. Runtime/intake changes are declared; the original unsupported
observations are preserved. No additional independent defects were found among the
five combined ordinary-passing candidates. This sample supports no broad detection,
false-positive or AI-agent accuracy claim.

**PASS**: both narrow blockers are resolved, unchanged bases preflighted, all four genuine
audits and separate controls verified, original history preserved, security boundaries
retained, and complete implementation CI passed. No Node compatibility blocker remains.
Final report-head CI and identities are supplied in the PR handoff for independent review.
**G4 stays on hold. No merge, release, deployment or further experiment is authorized here.**

## API Restart / Recovery Reliability Correction

The accepted Node outcomes above are unchanged. This correction addresses the engineering
FIX identified at reviewed head `41c1bb0f00e7f27e62da48fc07af658741eebc5d`.
Tested implementation: **`dbc59678289e9b772605206a14839253273954eb`**. The final delivery
head adds report/evidence only; its exact SHA and both final-head CI URLs/statuses are in
[PR #15](https://github.com/kabbersokhi-boop/ai-debugging-workbench/pull/15), also resolvable
as `refs/pull/15/head`. No stacked base change, merge, deployment, inference or G4 work.

### Reconstructed failure and causal evidence

The original [push run 40226794051](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/runs/40226794051)
passed 345 offline tests but failed two integration tests: the repository restart's
existing 90-second readiness wait, then a scenario request with `httpx.ReadError`
(89 integration passes, four opt-in skips). This was **not a cancelled workflow or overall
workflow timeout**. The parallel [PR run 40226797453](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/runs/40226797453)
passed all 91 integration tests and subsequent gates on the same submitted SHA.

[Both retained service logs and the machine-readable comparison](assets/generalized-patch-audit-g03-compatibility/restart-recovery/workflow-comparison.json)
support this lifecycle:

| Stage | Failed push workflow | Successful PR workflow |
|---|---|---|
| Before restart | Synthetic audit `c55b7e9d-be82-45e5-8d6f-e9b68578ac9c` finished; the test removed its DB terminal update and inserted a separate missing-result row | Same test procedure, completed audit `79e6319f-c335-44df-b9e3-c77dae4781e7` |
| Shutdown/restart | API shutdown completed; next startup began | Startup recovery began |
| Completed evidence | Broker returned HTTP 200 for the completed audit; exactly one original execution submission | Broker returned HTTP 200; exactly one original execution submission |
| Missing result | `4340e5a7-e904-4878-bc23-9266effac52b`: **439 HTTP 404 responses**, then API log still at startup pending | `2b15d537-e723-49a7-9da9-b40bd4c5fea3`: **37 HTTP 404 responses**, then startup completed and test verified reconciliation |
| Client observation | Restart test failed at 19:46:40 UTC; later scenario request failed at 19:47:29 UTC | Restart test passed at 19:45:26 UTC; later scenario request passed at 19:46:23 UTC |

The historical artifacts contain no DB dump or per-request timestamps. DB mutations are
reconstructed from the unchanged test and observed requests, not claimed as independently
captured snapshots. Within-service log order is usable; cross-service line position is
not a timestamp. At the declared 0.3-second polling interval, 439 separate polls exceed
the intended 12-second window. They demonstrate continued polling, rather than one stuck
HTTP request, a Docker call or DB operation at that point. Recovery awaits rows serially,
so this loop prevents application lifespan startup from yielding.

**Reproduced mechanism:** a single native `asyncio.timeout` cancellation can be consumed
when it coincides with AnyIO's connection task-group cancellation. The installed locked
AnyIO 4.15.1 source has this documented [native-cancellation race](https://github.com/agronholm/anyio/issues/1214),
later corrected upstream in [PR #1330](https://github.com/agronholm/anyio/pull/1330).
HTTPX's TCP connection path uses that task-group cancellation pattern. The bounded
[causal harness](assets/generalized-patch-audit-g03-compatibility/restart-recovery/causal-reproduction.py)
uses real asyncio/AnyIO scopes and the original polling body, controlling only their
scheduling through public APIs. Its [observation](assets/generalized-patch-audit-g03-compatibility/restart-recovery/causal-result.json)
shows an **expired timeout, three polls, a task still running, and one pending native
cancellation**, followed by explicit harness cleanup. The regression suite exercises
the actual corrected manager with the same connection-cancellation schedule.

This establishes a controlled causal model matching the historical symptom, **not a
claim that the exact original CI instruction interleaving was captured or naturally
reproduced**. The secondary read error is consistent with the same API remaining in
startup; the old log provides no packet-level proof of that individual transport error.
There is no evidence of a separate scenario defect. The corrected full journey also
checks subsequent API usability.

### Narrow correction and recovery semantics

`repository_audit/service.py` now uses AnyIO's [level cancellation](https://anyio.readthedocs.io/en/stable/cancellation.html)
for the unchanged **12-second terminal-result budget**, plus an absolute monotonic check
between attempts. Pending native cancellation is explicitly re-raised after an HTTP call;
a swallowed shutdown signal cannot turn into another poll or a fabricated DB outcome.
No detached polling task is created. Transport failures retry only inside that same
deadline, permitting a later valid result after an earlier request timeout. Non-object
JSON and invalid terminal evidence are rejected.

Startup recovery separately bounds cancel delivery to **10 seconds**, terminal lookup to
**12 seconds**, and DB reconciliation to **5 seconds**: **27 seconds per selected running
audit**, plus a 5-second initial DB query budget. Rows remain serial; this is a per-row
budget, not a fixed total for an arbitrary historical backlog. A failed cancel request
still permits terminal lookup. Valid evidence follows the existing validator and exact
result-hash persistence path; missing evidence becomes `interrupted`, malformed/forged
evidence becomes `invalid_evidence`, and no pass is inferred. Existing terminal rows
remain excluded, and the locked terminal-update guard preserves idempotence. A database
integrity/availability failure is bounded and raised; startup is not falsely released.
Migrations and the single-coordinator advisory lock are unchanged.

`repository_audit/recovery.py` emits start, cancel, poll summary, persistence and final
classification events with audit/attempt IDs, monotonic elapsed time, declared budget,
attempt/404/error counters, cancellation count and an explicit no-execution flag. It logs
no patch, source, credentials or response body. API startup logs release only after all
required recovery returns. There is no application log per poll. No new HTTP route or
public authority is added. Dependency versions, execution engines, verifier identities,
container policies, candidate requirements and approval rules are unchanged.

### Focused and actual restart validation

**13 focused regressions passed**: permanently absent evidence, delayed valid evidence
after a request timeout and several 404s, hung/slow requests, connection failure, malformed
JSON, non-object and forged evidence, shutdown cancellation, native/AnyIO cancellation
collision, level deadline expiry, cancel-delivery timeout with valid evidence, and bounded
DB failure. They invoke the actual recovery, persistence and validator code; only broker
responses and DB storage are controlled. They also check idempotence, unchanged terminal
history and absence of orphan request tasks. [Focused log](assets/generalized-patch-audit-g03-compatibility/restart-recovery/focused.log).

The [predeclared procedure](assets/generalized-patch-audit-g03-compatibility/restart-recovery/restart-plan.json)
capped fresh stress trials at **five**, stopping on any failure without replacements.
All five ran the original Docker/PostgreSQL/evaluator integration scenario at the tested
implementation SHA. Its assertions and 90-second readiness wait are unchanged; only
timing and evidence-hash observation fields were added.

| Trial | API usable after restart | Missing-row recovery | Missing polls | Completed re-executions | Outcome |
|---|---:|---:|---:|---:|---|
| 1 | 17.668s | 12.039s | 37 | 0 | PASS |
| 2 | 17.786s | 12.041s | 37 | 0 | PASS |
| 3 | 17.719s | 12.042s | 37 | 0 | PASS |
| 4 | 17.634s | 12.029s | 37 | 0 | PASS |
| 5 | 17.681s | 12.035s | 37 | 0 | PASS |

[All five attempt records](assets/generalized-patch-audit-g03-compatibility/restart-recovery/trials.json)
retain exact commit/service/image/audit IDs, evidence hashes and actual resource-absence
checks. Per-trial test output and timestamped API/evaluator logs are alongside them.
Every completed result was byte-equivalent after recovery, every missing row became
`interrupted`, and each completed audit had exactly one original execution submission.
There were **no failed or replaced trials**. The required full suite's inherited restart
checks and recovery smoke are separate engineering gates, not additional stress trials
or G3 campaign executions.

### Full regression, preservation and delivery

| Gate at `dbc59678289e9b772605206a14839253273954eb` | Actual local result |
|---|---|
| `./scripts/check` | **358 passed**, 95 deselected; Ruff, formatting, Pyright and frontend build passed. [Log](assets/generalized-patch-audit-g03-compatibility/restart-recovery/check.log). |
| `./scripts/e2e` | **91 passed, 4 existing live opt-ins skipped**, 358 deselected, 541.49s. Both originally failing tests passed. [Complete log](assets/generalized-patch-audit-g03-compatibility/restart-recovery/e2e.log). |
| `./scripts/recovery-smoke` | Passed: completed history unchanged, a fresh post-recovery run succeeded, no runner cleanup errors. [Log](assets/generalized-patch-audit-g03-compatibility/restart-recovery/recovery-smoke.log). |
| Actual recorded image | Boundary check passed; **2 browser journeys passed**, 451 deselected, 4.62s. [Server inspection](assets/generalized-patch-audit-g03-compatibility/restart-recovery/recorded-boundary.json), [browser log](assets/generalized-patch-audit-g03-compatibility/restart-recovery/recorded-browser.log). |
| Recovery/private routes in recorded service | GET 404 / POST 405. No workbench package, Docker socket, DB/provider credentials, writable host mounts or privileged authority. [New-route checks](assets/generalized-patch-audit-g03-compatibility/restart-recovery/recorded-recovery-boundary.json). |
| Historical and served evidence | **1,522 protected reviewed files byte-identical**; accepted G3/addendum validator replay passed; all **12 accepted saved records and downloads exact** after restarts/full suite/smoke. Served coordinator source hashes match the implementation. [Proof](assets/generalized-patch-audit-g03-compatibility/restart-recovery/preservation.json). |

The complete local suite explicitly supplied the unchanged legacy harness's hard-coded
default broker precondition, verified its source hash, and restored its original stopped
state afterward. [Recorded setup/restoration](assets/generalized-patch-audit-g03-compatibility/restart-recovery/legacy-harness-precondition.json).
No test assertion or timeout changed. A restricted-harness offline invocation stalled in
an ASGI fixture and was precisely interrupted; its partial log is retained separately.
The complete passing check used the required local async/socket permissions. Development
lint/type errors were corrected before committing the tested implementation.

Both original workflow outcomes remain retained, with [artifact identities and exact job
result lines](assets/generalized-patch-audit-g03-compatibility/restart-recovery/original-workflow-metadata.json).
No workflow was rerun to replace a failure. The final report/evidence commit changes no
runtime, test, workflow, dependency or container bytes after the tested implementation.
Its exact head and **both actual push/PR CI links and outcomes** are recorded in the
PR #15 handoff after submission; earlier successful CI is not substituted for those runs.

Local correction gates: **PASS**. Engineering recommendation for independent re-review:
**PASS only when both final-head CI workflows also pass**, as confirmed in the PR handoff;
any remaining failed required check means FIX, not unconditional success. The controlled
cancellation mechanism is demonstrated; the exact historical scheduling remains inferred.
Budgets require a responsive event loop and apply per running audit, so a larger backlog
has a proportionally larger startup bound. Required DB/integrity failures still fail
startup explicitly. Other coordinator subsystems retain their existing behavior.

No historical result hash, approval, patch, requirement, runtime image declaration or
versioned verifier was rewritten. **Zero G3 campaign reruns; no merge, deployment, release,
real inference or G4.** The accepted Node compatibility and G3 coverage remain PASS.
