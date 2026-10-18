# Agent Evaluator M2 — Producer reliability correction

## Decision

**Readiness failed. No eight-trial formal experiment was started. M3 remains on hold.**
Four fixed calibration runs yielded one explicit final submission; Nemotron 3.5 submitted 0/2.
That genuine development patch passed ordinary tests but failed the existing independent checks.
This is a useful additional observation on a known calibration task, not evidence of a reliable
stream on the newer tasks or a successful formal comparison. No further producer calls were made.

One focused correction pass, on the existing M2 branch and PR #7.
The original 24-trial `m02-v1` is unchanged and is not pooled with this procedure.
Formal validation is conditional on a fixed, bounded calibration preflight; results below distinguish
protocol usability, submitted candidates, patch correctness and independent discoveries.

## Diagnosis from actual v1 evidence

| Representative retained trial | Observation | Interpretation |
| --- | --- | --- |
| `more-seekable-nemotron35-r01` | First response: finish `length`, content null, 3,000 completion and 3,000 reasoning tokens | Output allowance exhausted before an actionable decision; not a code failure |
| `boltons-addlist-nemotron3-r03` | Request 7 timed out after roughly 60 seconds after a passing ordinary tool | Latency/deadline failure; the normalized provider timeout also raced the outer 60-second cancellation |
| `boltons-indexedset-nemotron3-r01` | Request 8 returned HTTP 502 in 68 ms | Provider transient, not candidate behavior |
| `boltons-indexedset-nemotron35-r01` | Edited tree passed ordinary checks; six calls reserved 176,963 units, leaving too little for explicit submission | Conservative cumulative accounting/context interaction; no retrospective promotion |
| `boltons-indexedset-nemotron3-r02` | Nine bare tool objects were rejected; other reads exceeded the inclusive line limit; 12 requests, no edit | Protocol/model compliance friction, not a demonstrated inability to implement the repair |
| `more-bucket-nemotron35-r02` | Three calls, 51,980 reservations, edited/tested/submitted, both final procedures passed | A genuine completed lifecycle; repeated calibration correction, not a new independent discovery |

Trial names above have prefix `m02-v1-`. Exact metadata and raw paths are in
[`diagnosis.json`](../../evaluation/experiments/m02-v2/diagnosis.json) and the unchanged v1 journals.
These are separate failure modes. V1 remains six both-pass finals, eight no submissions, ten provider
failures, and **0/6** incremental detections. Two ordinary-passing unsubmitted trees remain unscored.

## Corrections and supported provider behavior

The historical producer directly calls `NvidiaProvider.request`, bypassing the standard chat method,
which already requests reasoning off. The new `json-source-tools-v3` path uses explicit
`chat_template_kwargs: {enable_thinking: false}`, JSON-object responses, temperature 1/top-p .95,
and 4,096 output tokens. Both official model cards support configurable reasoning and recommend
those sampling settings for text. References:
[Nemotron 3 Super](https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b/modelcard),
[Nemotron 3.5 Super](https://build.nvidia.com/nvidia/nemotron-3.5-super-vl-120b-a12b/modelcard).

The hosted service must demonstrate usable outputs in preflight; documentation alone is not proof
that a parameter takes effect. No unsupported OpenAI-style `reasoning_effort` or separate reasoning
budget is assumed. No `force_nonempty_content` setting is inferred to be supported by this endpoint.
A truncated/content-null response remains a recorded invalid output and executes no action.

The new path accepts a direct tool object or an explicit single-action wrapper. One action per turn
makes ordinary feedback precede submission. Source inspection must succeed before editing; denied
reads do not satisfy that requirement. Exact edits, path allowlists, fixed ordinary tools and explicit
submission remain mandatory. Passing intermediate trees are never auto-promoted. The final two
requests are signposted for test/submission, without an automatic patch or submit fallback.

Context is rebuilt deterministically from current source excerpts/hashes, all edit/error/test feedback
and the last two read/search outputs. Ordinary output keeps up to 6,000 bytes per stream, split between head and tail, with explicit omission counts and a full-log hash; full raw evidence is retained. Repeated
container policy/resource fields and older successful reads are not resent. Syntax-invalid edits
retain current source hashes and parse errors, allowing ordinary testing and subsequent revision.
No second LLM summarizes feedback. Compaction is itself a changed experimental condition and may
lose useful conversational continuity; it is not asserted to be universally better.

The per-request deadline is 90 seconds (was 60); an outer deadline allows five seconds for the
provider's normalized timeout unless the trial deadline intervenes. At most one transient timeout or
HTTP 429/500/502/503/504 retry is allowed per trial, with identical payload, no repeated tool side
effects, original error retained and a fresh full request/reservation charge. Other provider errors and malformed/truncated
decision envelopes terminate; tool errors receive bounded feedback. Every unknown-usage request retains its conservative reservation.

Limits per run: 12 actual attempts including retry, 360,000 input-content-UTF-8-byte-plus-output
reservations, 48,000 input content bytes/request, 720 generation seconds, four edit revisions,
twelve exact edits, four ordinary runs, sixteen source read/search actions. A fixed ordinary tool
is admitted only with 30 seconds remaining for the inherited 25-second executor. The global ledger
covers development and formal work together: **12 runs, 144 attempts, 4,320,000 reservations and
8,640 allocated generation seconds**. Docker daemon/cleanup responsiveness remains an inherited
limit, not a hard real-time sandbox guarantee. Monetary cost is unknown; no new service was bought.

V1 modules remain byte-for-byte unchanged. The versioned path reuses its approved task loader,
Workspace admission helpers, journal, candidate builder, Docker executor, independent verifier and
PostgreSQL schema. New replay logic reconstructs every model-facing request and tool action;
source/trial/configuration/result bindings are validated before aggregation. Exclusive run/charge
files reject concurrent reuse. An interrupted raw generation is not restarted; later delivery would
report an incomplete campaign rather than silently rerun it. This pass does not add a public endpoint.

Offline review caught and fixed three new implementation weaknesses before live calls: current-source
AST parsing could abort on a syntax-invalid edit; denied inspection could otherwise satisfy an edit
precondition; and replay needed the same per-request context limit as generation. Draft preflight
freezes are retained explicitly; no live request used either draft.

## Actual preflight and gate result

The preflight was frozen at commit `c140b3b` before all new provider calls, hash
`fb064c086e74ff10c8396a6c5ca3235add8f53e09a794a0b672dcc5b0ae3a2df`.
The order was bucket/Nemotron 3, bucket/Nemotron 3.5, addlist/Nemotron 3.5, addlist/Nemotron 3.
Both configurations received the same task material, source namespace, fixed ordinary commands,
tools and budgets. No independent feedback entered generation. Each began with fresh source/state.

| Configuration / calibration task | Actual requests | Final result | Read/search attempts / admitted revisions / ordinary runs | Reported tokens | Reservations |
| --- | --- | --- | --- | --- | --- |
| Nemotron 3 / bucket | 12 | Request ceiling; no submission | 10 / 1 / 1 (9 tests passed) | 50,974 | 180,843 |
| Nemotron 3.5 / bucket | 12 | Request ceiling; no submission | 6 / 1 / 0 | 96,253 | 275,931 |
| Nemotron 3.5 / addlist | 12 | Request ceiling; no submission | 10 / 0 / 0 | 64,978 | 200,772 |
| Nemotron 3 / addlist | 7 | Explicit submitted final | 4 / 1 / 1 (155 tests passed) | 33,131 | 102,808 |

Requested / actual returned identities:

- Nemotron 3: `nvidia/nemotron-3-super-120b-a12b` / same.
- Nemotron 3.5: `nvidia/nemotron-3.5-super-vl-120b-a12b` / `private/nvidia/nemotron-3.5-super-120b-a12b`.
- Harness: `json-source-tools-v3`; exact prompt, parameters, source and harness hashes are in the
  development freeze and per-request records. Immutable weights, provider hardware/load, training
  exposure, model RNG seed and monetary cost are unavailable. Model behavior is not deterministic.

All **43 requests returned responses**, each with nonempty parseable JSON content, finish `stop` and reported
reasoning tokens **0**. No new truncation, provider failure or retry occurred. One response took
**81.465 seconds**, demonstrating why a 90-second bound was technically useful for that request;
this is not a causal comparison of provider reliability. The retry policy is tested by deterministic
fixtures and was not exercised against a real transient in this pass.

Total reported usage is **245,336 tokens**, unknown usage **0 requests**, reservations **760,354**.
Generation wall totals **179.695 s**, with **6.816 s** of recorded ordinary-tool phase durations
inside that interval. The separate final ordinary/independent phase durations sum to **32.343 s**;
reproduction phases sum to **2.636 s**. Container setup/daemon overhead and concurrent local build
load affect these timings; they are not model compute times or a speed ranking. Maximum request
content was **23,737 bytes**, below 48,000. No run hit the new reservation ceiling. Monetary cost
remains **unknown**. The unused eight formal runs and remaining budget were not replenished or spent.

The N3 bucket run spent ten actions inspecting, then edited and tested on its last two requests;
its ordinary-passing unsubmitted tree remains unscored. N3.5 bucket supplied an extra `command`
field to the fixed `test` tool twice, retried already-applied edits twice and exceeded read bounds
once. N3.5 addlist inspected ten times and supplied invalid edit contracts twice. Ordinary testing
was available equally but N3.5 never admitted a valid test action. These are model/harness workflow
failures, not observed code correctness failures or evidence that the provider service was unavailable.

Generic inherited tool-error text and rebuilding a compact state without recent assistant turns
remain weaknesses. One-action turns cost more requests than batching; reasoning-off can also affect
multi-step planning. This pass does not isolate those effects or establish compaction as an improvement.
Live preflight did not demonstrate correcting a failed ordinary test: the two admitted live tests
passed. Failure-feedback/revision behavior is covered by deterministic fixtures, not claimed as a
measured live-agent capability. No prompt or harness was tuned after these outcomes; the two-run/configuration cap was respected.

The real `freeze` command returned exit 1 with `Preflight readiness gate failed`; no formal freeze,
generation claim, newer-task candidate or formal score exists. The proposed conditional maximum
was the two newer tasks × two configurations × two trials, alternating configuration order with
seed 20261017 and unchanged task/verifier identities. It was **not frozen or executed** after the
failed gate. No replacement models or runs were tried. Development is not an experiment-success claim.

## Separate independent observation on the explicit development final

After **all four generations ended**, every explicit development submission (one) received fresh
ordinary and independent execution using the unchanged preflight-bound verifier. This adds no model
requests and is kept outside formal comparison storage/denominators. The already frozen rule permits
scoring only after generation; neither the behavioral tests nor expectations changed after the patch.
The dedicated local helper retains a separate source/trial/freeze/result binding and exclusive claim.
No unsubmitted tree was promoted.

Candidate `m02-v2-development-boltons-addlist-nemotron3-r02`, source identity
`5cab12b5c1b25239d4418e84aae45f166041390a6895d24f2a6ae1d1d85d6246`, changes only
`boltons/dictutils.py`. Fresh ordinary execution passed **155 tests**. The package implementations
passed the independent observations, but all five standalone vendored `urlutils` cases failed.

**Empty input leaves inconsistent state: `len() == 1`, while keys and items are empty.** Iterator
and generator inputs also lose their values; repeated list/tuple appends expose stale values and
length inconsistencies. The standalone implementation was not repaired. This is a known behavioral
coverage gap that ordinary package tests miss, observed here on an unmodified genuine model patch.
It is not a novel upstream defect or a supplied negative control. Both source paths were available
to the producer, and no historical patch, reference or independent feedback was supplied.

The development observation is **1/1 ordinary-passing explicit development finals failing independent
checks**; all-attempt development outcomes are one such final and three no submissions out of four.
Formal-validation detection is **not measured (0 submitted formal candidates)**. Original M1 and
`m02-v1` retain their original zero additional detections, including v1 **0/6**. Do not pool these
conditions or report 1/7 as a common experiment. A separate fresh reproduction confirmed the same
failure with new containers; it is not another candidate, trial or defect discovery.

## Answers and investment decision

1. **More usable final candidates?** One excluded development final, not a demonstrated improvement:
   conditions/tasks differ, there is no new formal result, and both configurations did not pass preflight.
2. **Resolved mechanisms?** The supported reasoning-off request produced zero reported reasoning tokens
   in 43 responses; no truncation occurred. Bare tool syntax works. Bounded context and reservations
   did not cause a terminal failure. These observations do not prove general reliability.
3. **Remaining failures?** Repeated inspection, incorrect tool contracts, weak error recovery and request
   exhaustion. N3.5 did not demonstrate edit/test/feedback/submit. Provider transients remain possible.
4. **Comparable opportunities?** Same two calibration tasks, tools, budgets and reversed configuration
   order. Actual test use differed because of tool decisions; untested outputs are not called
   equivalent to tested submissions. No vendor or quality winner is claimed.
5. **Ordinary pass / independent fail?** Yes, one explicitly labeled development final; no formal case.
6. **Additional behavior?** Standalone vendored addlist state and one-shot input preservation, above.
7. **What can be concluded?** Independent evidence can expose an omitted implementation that ordinary
   package tests miss. One known calibration case does not establish general defect yield or accuracy.
8. **Enough for M3?** **No.** The revised producer does not provide a sufficiently reliable two-configuration
   stream, and neither newer task received a formal candidate. The one development discovery does not
   overcome the failed readiness gate. Stop this correction pass; no further tuning, roadmap or M3.

## Verification, preservation and review references

Commands from repository root (Python 3.12, Docker/uv/Node/PostgreSQL as in the main report):

```sh
./scripts/check
uv run --project backend pytest backend/tests/test_evaluator_reliability.py -q
docker compose up --build -d --wait api
./scripts/e2e
./scripts/recovery-smoke
docker compose -f compose.release.yaml up --build -d --wait
uv run --project backend python scripts/check_release.py
E2E_BASE_URL=http://127.0.0.1:8020 ./scripts/e2e -k recorded_explorer_first
```

| Check | Actual result |
| --- | --- |
| Offline / static / frontend | **98 passed, 66 deselected**, Ruff/format/Pyright/build passed; inherited Monaco chunk warning. [Log](assets/agent-evaluator-m02-reliability/check.log) |
| Focused reliability file | **21 passed**, deterministic fixtures and retained actual evidence, no model calls. [Log](assets/agent-evaluator-m02-reliability/focused.log) |
| Full local integration/browser | **62 passed, 4 opt-in skipped, 97 deselected**, 313.16 s. The final added evidence test is offline and passed above. [Log](assets/agent-evaluator-m02-reliability/e2e.log) |
| Recovery smoke | Preserved terminal history, interrupted work recovered, fresh run reproduced, no runner cleanup errors. [Log](assets/agent-evaluator-m02-reliability/recovery.log) |
| Recorded-container boundary | Passed; no credentials/authority modules or live evaluation routes. [Log](assets/agent-evaluator-m02-reliability/release-boundary.log) |
| Recorded browser | **1 passed, 163 deselected**. [Log](assets/agent-evaluator-m02-reliability/release-browser.log) |

Targeted tests cover reasoning-only/null/truncated output, supported parameters, exact reservations,
charged timeout/502 retry without duplicate tools, context compaction, syntax-invalid source recovery,
inspection/edit admission, feedback/revision, passing-but-unsubmitted trees, campaign limits, frozen
v1/v2-development compatibility, stored source/trial/score identities and the actual failed readiness
gate. Synthetic failures are explicitly fixtures; the 43 NVIDIA responses are separate actual evidence.

Historical live commands (do not rerun this closed pass):

```sh
uv run --project backend python -m workbench.evaluator.reliability prepare
uv run --project backend python -m workbench.evaluator.reliability preflight --live
```
They now reject reusing the existing ledger/claims; do not delete claims or rerun this pass.
`uv run --project backend python -m workbench.evaluator.reliability freeze` **must fail** at the
readiness gate and makes no provider call. Inference-free scoring/reproduction commands were:

```sh
uv run --project backend python scripts/evaluate_reliability_preflight.py
uv run --project backend python scripts/evaluate_reliability_preflight.py --reproduce
```

The first command retains the one-time development observation; it refuses an existing claim.
On a fresh checkout the second writes separate ignored reproduction evidence; it also refuses to
overwrite an existing local reproduction claim. Both returned operational exit 0 after recording
**candidate status failed** (ordinary passed / independent failed). They never regenerate source.
[Original scoring log](assets/agent-evaluator-m02-reliability/development-independent.log),
[reproduction log](assets/agent-evaluator-m02-reliability/reproduction.log), and
[fresh-container proof](assets/agent-evaluator-m02-reliability/reproduction-proof.json).

[Implementation CI](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/runs/38979322452)
**passed** on `1c701de16eb1918ad8ede74b5897c03033b8bbc8` without model credentials: offline checks,
retained v1 import, full integration/browser suite, recovery and recorded-server checks. The push
workflow also passed. [Job summary](assets/agent-evaluator-m02-reliability/ci-implementation.json) ·
[sanitized transcript](assets/agent-evaluator-m02-reliability/ci-implementation.log).
Final documentation-head CI and its exact head SHA are recorded in the PR description and handoff.

The byte-hash preservation manifest covers all **552** original `m02-v1` files. The original freeze
and all 24 outcomes validate against the original implementation-file identities. Original M1/M2
reports/assets and evaluator modules remain unchanged; no integrity assertion was weakened. A scoped
before/after PostgreSQL row-hash audit also checks all captured history, including prior comparison
snapshots: **153 runs, 25 investigations, 23 repairs, 12 source snapshots, 37 evaluations and
25 comparison snapshots**. The audit checks those captured rows, not every database table or ignored
runtime file. Existing tests append their own history. No new formal trial or development observation was inserted into the comparison tables.

The comparison UI and original debugger remain unchanged. Raw development diffs and observations are
linked below; they do not appear as a new completed formal comparison. Execution remains private,
local, approved-source-only, with coordinator credentials excluded from candidate containers and no
shell/reference/independent-test access through producer tools. **In-process Python observations
are not a complete anti-tampering boundary against malicious candidates.** Docker/kernel and finite
historical-task contamination limits remain. No deployment, visibility change or merge occurred.

Evidence:

- [Exact development freeze](../../evaluation/experiments/m02-v2/development/freeze.json),
  [all four raw journeys](../../evaluation/experiments/m02-v2/development/trials),
  [actual preflight accounting and gate failure](../../evaluation/experiments/m02-v2/preflight-summary.json),
  [campaign ledger](../../evaluation/experiments/m02-v2/accounting).
- [Exact genuine patch](../../evaluation/experiments/m02-v2/development/independent/m02-v2-development-boltons-addlist-nemotron3-r02.patch)
  and [source-bound independent evidence](../../evaluation/experiments/m02-v2/development/independent/m02-v2-development-boltons-addlist-nemotron3-r02.json).
- [V1 byte-hash baseline](../../evaluation/experiments/m02-v2/preservation-v1.json),
  [final preservation audit](assets/agent-evaluator-m02-reliability/preservation.json),
  [fresh reproduction](assets/agent-evaluator-m02-reliability/reproduction.json), and
  [asset hashes](assets/agent-evaluator-m02-reliability/manifest.json).

The producer used commit `c140b3bfe07700ac4cecfff11e56fdbdba39710a`; neither producer nor verifier changed
after the first new call. Tested implementation: `1c701de16eb1918ad8ede74b5897c03033b8bbc8`.
Final review head: `refs/pull/7/head`; its exact SHA and final CI URL are in the
[updated PR #7 description](https://github.com/kabbersokhi-boop/ai-debugging-workbench/pull/7).
The final report/evidence commit cannot include its own SHA. No source changes follow the tested
implementation. PR #7 remains stacked on `feature/agent-evaluator-m01`; PR #6 is untouched and unmerged.
