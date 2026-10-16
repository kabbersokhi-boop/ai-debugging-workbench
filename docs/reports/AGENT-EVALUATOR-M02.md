# Agent Evaluator · Milestone 2

## Executive summary

A genuine, frozen **4 tasks × 2 NVIDIA model/harness configurations × 3 trials** comparison has
completed. Both configurations could inspect the same approved source, edit production files,
run ordinary upstream tests and revise within equal limits. All 24 attempts and intermediate
outputs are retained. Six final candidates were explicitly submitted and scored in fresh ordinary
and independent containers; all six passed both procedures.

**Incremental detection: 0/6 genuine ordinary-passing final candidates failed independent checks.**
This is six completed final evaluations out of 24 attempted trials, not 24 successful repairs.
Eight trials had no final submission and ten ended in provider failure. Neither newly added task
produced a submitted final candidate. Five scored trials repeat the same bucket correction; the
remaining scored trial repairs Boltons addlist. The evidence is inconclusive about comparative
coding quality and does not demonstrate unique independent detection on genuine producer outputs.

**Recommendation: do not proceed to release polish or broader product investment on this evidence.**
Generation completion was 25%, and every completed score comes from an M1 calibration task. Keep
this as a bounded local reviewable experiment. Further investment needs reliable producer completion
and genuine value evidence under a newly reviewed procedure. No additional trial budget was issued.

M1 remains intact: its single-turn experiment found one genuine patch passing both procedures and
one failing both. **M1 did not find a genuine ordinary-pass/independent-fail patch.** Its historical
results are not pooled with the new interactive comparison. Milestone 3 has not been started.

## Actual user-facing capabilities

The existing Agent Evaluation workspace links to a **Controlled producer comparison** at
`http://127.0.0.1:8010/?workspace=evaluation&comparison=m02-v1`.

A visitor can inspect the frozen conditions and four task specifications, filter the 24-trial
matrix by task, open each genuine submitted or incomplete trial, inspect source context, model
decisions, exact tool actions, ordinary-test transcripts and provider errors, download complete
trial evidence, and reopen the corresponding PostgreSQL evaluation. Submitted patches include exact
unified diffs, the existing Monaco comparison, source/runtime identities and an inference-free
reproduction command. Generation and evaluation are not restarted by viewing or downloading.

The page leads with 0/6 incremental detections, 6/24 completed finals, eight unsubmitted and ten
provider failures. It shows measured usage separately from unknown usage/cost, and generation wall,
ordinary tools within that wall, and separate final evaluation. Authored controls have their own
expandable section and contribute zero agent trials. Ties, zero denominators and provisional
incomplete imports have deterministic rendering coverage; there is no winner or composite score.

Failure pages lead with a deterministic evidence-grounded explanation. The existing genuine M1
Boltons failure now first explains that empty addlist input reports `len() == 1` while `keys()` and
`items()` are empty. Repeated observations and detailed logs are collapsed. The accepted debugger
remains available; its application, runner and repair workflow were not replaced.

## Complete results and denominators

The tables below are derived from validated retained records, not entered scorecards. The complete
machine-readable matrix and persisted evaluation IDs are linked in the final evidence section.

| Configuration | Attempted | Completed finals | Both passed | Ordinary failed | Additional independent failure | No submission | Provider failure | Incremental numerator / denominator |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nemotron 3 Super / JSON source tools v2 | 12 | 3 | 3 | 0 | 0 | 1 | 8 | 0/3 |
| Nemotron 3.5 Super / JSON source tools v2 | 12 | 3 | 3 | 0 | 0 | 7 | 2 | 0/3 |

Completed-trial outcomes are **6/6 both passed** (3/3 per configuration). All-attempt outcomes are
**6 both passed, 0 ordinary failures, 0 additional independent failures, 8 no submission, 10 provider
failures**, totaling 24. No incomplete trial is dropped. Provider failures affect completion and do
not demonstrate candidate code defects. The incremental denominator includes only genuine submitted
ordinary-passing finals with completed independent evaluation. Controls and unsubmitted working
trees are excluded.

| Task | Nemotron 3 trials 1 / 2 / 3 | Nemotron 3.5 trials 1 / 2 / 3 |
| --- | --- | --- |
| `more-bucket` | both passed / both passed / both passed | both passed / both passed / provider failure |
| `boltons-addlist` | provider failure / provider failure / provider failure | token ceiling; no submission / both passed / token ceiling; no submission |
| `more-seekable` | provider failure / provider failure / provider failure | truncated output / provider failure / truncated output |
| `boltons-indexedset` | provider failure / request ceiling; no submission / provider failure | token ceiling; no submission / truncated output / truncated output |

The provider failures comprise nine request timeouts and one HTTP 502. Nemotron 3 had seven timeouts
and the 502; Nemotron 3.5 had two timeouts. No provider request or trial was retried after failure.
The eight other incomplete trials comprise four truncated outputs, three conservative token ceilings
and one 12-request ceiling. Every response and intermediate revision remains in its trial directory.

Two unsubmitted working trees passed ordinary tests: Nemotron 3 Boltons trial 3 ended in provider
failure, and Nemotron 3.5 IndexedSet trial 1 reached its token ceiling before explicit submission.
They were not promoted or independently scored. Their independent behavior is unknown. Another
unsubmitted Boltons trial's ordinary tool exited 2 during collection before the token ceiling; that
transcript remains visible. No completed trial demonstrates correction after an ordinary-test
failure, so iteration benefits cannot be inferred from this study.

Independent evaluation supplied additional finite observations for five bucket submissions and one
Boltons submission, including the standalone urlutils implementation, one-shot inputs, empty state,
ordering and iterator consumption. It found no additional genuine failure. The sixteen authored
controls still establish the verifier's ability to reject known defects and meaningful incomplete
fixes. That is control validation, not an AI failure-discovery claim.

Neither new task has a submitted final, so this study cannot compare genuine independent behavior
on either new defect. Identical bucket source hashes across five trials are repeated observations,
not five distinct repairs. M1's single-turn conditions differ from M2; the new passing Boltons patch
does not establish a causal benefit from tools or iteration relative to M1.

## Requests, usage and time

| Configuration | Requests | Successful responses | Reported tokens | Requests with unknown usage | Generation wall | Ordinary tools within wall | Separate final evaluation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Nemotron 3 Super / JSON source tools v2 | 60 | 52 | 212,905 | 8 | 1022.770 s | 4.370 s | 7.313 s |
| Nemotron 3.5 Super / JSON source tools v2 | 47 | 45 | 380,519 | 2 | 543.585 s | 12.582 s | 4.913 s |

Comparison totals: **107 requests, 97 responses with usage, 593,424 reported tokens**, with usage
unknown for ten failed requests. Total conservative reservations were 1,795,268 against the frozen
4,320,000 ceiling. Token totals include successful responses from incomplete trials. Monetary cost
is **unknown**, not zero. The different failure mixes and provider conditions prevent a clean speed
comparison; these are measured local totals, not a vendor performance ranking.

Development is separately accounted: 21 request intents/attempts (five availability, sixteen
capability), seventeen responses and 51,125 reported tokens; four attempts have unknown usage.
One interrupted in-flight development request may or may not have completed at the provider. A
model-catalog GET produced no inference usage. Development and M1 historical requests do not enter
the 24-trial denominators. No further producer calls were made to improve these outcomes.

## Task validity and provenance

Four approved tasks share the existing Python/Docker platform. Ordinary files are byte-for-byte
upstream snapshots from the defective base, without later regression tests. The first two remain
known M1 calibration cases; they are not new discoveries.

| Task | Exact base | Public defect / reference | Ordinary scope |
| --- | --- | --- | --- |
| more-itertools `bucket` false-valued validators | `1ea82a711c69f590054987b5cb194157f8ce8ac4` | [issue 1308](https://github.com/more-itertools/more-itertools/issues/1308), [67fcf64](https://github.com/more-itertools/more-itertools/commit/67fcf640477c78605580f5ee703a54c73c1e7a8a) | 9 existing BucketTests |
| Boltons one-shot `addlist` inputs | `d45cc414e33aa4e08a73e0993574df4397e2e9db` | [PR 458](https://github.com/mahmoud/boltons/pull/458), [a1ea103](https://github.com/mahmoud/boltons/commit/a1ea1030ed85137e999c0bd9b11d16368d3ab241) | 155 existing dictutils/urlutils tests |
| more-itertools zero-cache `seekable` observation | `ca711220a6657a22655f6fa497524d006a735c5f` | [issue 1268](https://github.com/more-itertools/more-itertools/issues/1268), [6b1907d](https://github.com/more-itertools/more-itertools/commit/6b1907de293a655fb77881bf81948f95fd15bd7c) | 14 existing SeekableTest tests |
| Boltons `IndexedSet` slices after removals | `979fa9b613fa8c0a455ae16ea6f2ec91c11ecafe` | [PR 423](https://github.com/mahmoud/boltons/pull/423), [609cabe](https://github.com/mahmoud/boltons/commit/609cabe932a1ea1423b24568644945abb1b8bb84) | 5 existing setutils tests |

more-itertools is MIT licensed; Boltons is BSD 3 clause. Both licenses are retained. The two new
snapshots were independently compared with `git show <base>:<path>`; exact hashes appear in the
manifests and upstream-verification evidence. No task was chosen after observing a compared
producer fail it. No task was excluded after generation.

The new iterator task exercises interactions among `peek`, truth testing, `next`, exhaustion,
source pulls and cache views, including false-valued values. It also preserves positive/default
cache regressions. It does not claim bounded memory under arbitrarily many repeated peeks: the
initial upstream reference was later optimized to avoid nested-chain growth.

The set task observes four removal histories and ten slices each, plus scalar indexing, visible
order, length, return type and nonmutation. Boltons' established negative-step convention is
explicitly preserved: normalize negative bounds against visible length, reverse the stream, then
apply forward bounds with absolute step. Python list negative-step semantics are not imposed.

Before generation, all sixteen authored controls were actually executed. For every task, baseline
and meaningful negative passed ordinary tests and failed independent checks; reference and
alternative passed both. The seekable negative fixes truth testing alone; peek/iteration still
loses values. The IndexedSet negative removes physical-index mapping but misses negative-bound
normalization. A peekable-based alternative and a materialized-live-sequence slice alternative
both pass. These controls validate finite task behavior and are excluded from agent denominators.

## Producer configurations and access

Both configurations are genuine NVIDIA-hosted model calls through the same trusted JSON source-tool
harness, `json-source-tools-v2`. They are model/harness configurations, not Codex, Claude Code, or
another named coding-agent product.

Both use prompt identity `b123a523c93b720063e928e77fd94e2a6fcdc940c3878f634465fdbd36e78f87`
and harness identity `e2f602b074b4da013d03433b9bbce6d1d5198391748a8f2b2a8609af9267a086`.
The full frozen configuration and source-context hashes are retained in the freeze manifest.

| Configuration | Requested model | Available returned model identity |
| --- | --- | --- |
| Nemotron 3 Super / JSON source tools v2 | `nvidia/nemotron-3-super-120b-a12b` | `nvidia/nemotron-3-super-120b-a12b` |
| Nemotron 3.5 Super / JSON source tools v2 | `nvidia/nemotron-3.5-super-vl-120b-a12b` | `private/nvidia/nemotron-3.5-super-120b-a12b` |

The returned strings are provider metadata; immutable weight revisions, training exposure, provider
hardware/load, RNG seed and monetary prices/costs are unavailable. These are two related model
families through one provider, not a cross-vendor study. Actual returned identities are retained in
each response. Temperature is zero; deterministic model behavior is not claimed. No model seed is
provided by the service.

Availability used five small development-only requests: initial Nemotron 3.5 returned HTTP 500;
Qwen Coder returned 410; Kimi K2.6 returned 404; Nemotron 3 and a bounded Nemotron 3.5 recheck succeeded.
This was not an exhaustive model search. An initial capability run exposed ambiguous edit-schema
feedback and was interrupted. Its raw prefix is retained. A revised development fixture let each
selected configuration inspect source, apply its own unmodified correction, run the same ordinary
test successfully and submit. Development requests are separately accounted and never enter the
24-trial matrix. Later prefreeze changes strengthened accounting and failed-test feedback gates;
they did not change the accepted source-tool protocol or execution platform.

Each comparison starts with the same public problem, expected behavior, relevant source excerpts,
full approved file inventory/hashes, fixed ordinary command, environment and budget. Producers can
read any approved source/test file in bounded ranges, perform literal search, make exact unique
production edits, run the fixed ordinary tests, and submit. File-level edit spelling is normalized
mechanically; replacement source text is never manually repaired. Tests are readable and executable
but cannot be edited. Each trial starts with fresh source and conversation state. Statistical
independence of repeated provider outputs is not assumed.

The producer has a virtual source namespace rather than a host working directory. It contains only
pinned upstream source, ordinary tests and license. It exposes no evaluator repository, `.git`,
reference correction, authored control, prior candidate, independent program, expected matrix,
freeze/scoring records, shell, external retrieval, Docker socket or provider credential. Source reads
and edits run as trusted dictionary operations. Only the trusted coordinator reads existing NVIDIA
credentials. Ordinary execution uses a fresh restricted M1 container. Access-denial unit tests and
an actual Docker filesystem/network/credential boundary probe are retained.

## Frozen experimental procedure

[Freeze m02-v1](../../evaluation/experiments/m02-v1/freeze.json) was committed at
`050dc6adea6993aabcc22a91f36f51cacc3df0ea` before comparison requests. Its identity is
`aaf36a066a50e463e1a28a912353dec2c210ce887a439e54089183ffa547cdf4`.
It binds source specifications, initial contexts, producer/prompt/harness versions, generation and
scoring code, retained control evidence, runtime image, policy, trial counts, accounting and order.
The sixteen frozen raw controls are in `validation-final-v2/`; earlier folders are retained
prefreeze iterations. M1's four identity-bearing core source files and every old freeze/result remain
unchanged. The new task adapters reuse M1's Docker executor and policy.

The fixed design is **4 tasks × 2 configurations × 3 trials = 24**. Seed `20261016` pre-randomizes
adjacent configuration pairs across task/repeat blocks. Generation is sequential. All generation
must terminate before any final independent scoring. Independent output never enters a producer
conversation. Invalid output, provider error, truncation, timeout, intermediate revision and
unsuccessful attempt remain retained. No configuration replacement, automatic provider retry,
budget replenishment, selective rerun, regeneration after scoring or discarded trial is allowed.

Per trial ceilings:

- 12 provider requests, maximum 3,000 output tokens per request.
- 180,000 cumulative conservative token reservations: UTF-8 message bytes plus reserved maximum output,
  charged before each request including failures.
- 420 seconds of generation wall time; each provider request has at most 60 seconds.
- Four admitted edit revisions, twelve exact edits total, four ordinary test runs, sixteen read/search
  actions; reads at most 120 lines/12,000 characters, searches at most twenty hits.
- At most four actions in a response. A failed ordinary test gates later edits/tests/submission in
  that response until the producer sees its feedback on the next decision turn.

Global comparison ceilings are 288 requests, 4,320,000 conservative token reservations and 10,080
seconds of generation. Docker calls/cleanup depend on daemon responsiveness, as in M1. The
coordinator makes no new subscription purchase. Monetary cost remains unknown.

A usable candidate requires explicit submission after a valid edit and ordinary execution of that
last working tree. A passing intermediate tree without submission is retained but not automatically
promoted or scored. Budget exhaustion therefore can produce no usable candidate. This rule is
frozen and applies equally to both configurations. Completed scores can be reused only after
validation; interrupted scoring claims become infrastructure failures without rerunning execution.
Interrupted generation IDs are never restarted or silently replaced; a final comparison requires
all scheduled coordinates.

Each submitted final candidate runs fresh ordinary and independent phases with identical per-task
procedures for both configurations. M1 calibration tasks retain their existing verifier IDs. New
tasks have separate frozen adapter identities. Runtime uses Python 3.12.14/pytest 8.3.5 and actual
image `sha256:379d13f7b91f63995b9aaa143204149ead633755d19fb093599717ded5574301`.
Source volumes are initialized and hashed outside candidate authority, then mounted read-only.

## Evidence integrity and safety limits

Trial IDs are append-only and fixed before calls. Exclusive claims reject concurrent reuse;
individual event files form a trial-specific hash chain. Validation replays model actions, source
changes and tool replies, reconstructs semantic request hashes, verifies provider model/status/usage,
checks terminal accounting and rejects omitted/reordered actions. Candidate identity binds source;
a separate scoring binding ties each execution to the trial, configuration, freeze and transcript.
Identical source patches cannot exchange scoring evidence. Final container identities must be
unique. Every stored snapshot is validated before aggregation, with complete-matrix enforcement
for final reports. Scores are recomputed from saved observations rather than entered manually.

Migration 007 adds immutable comparison snapshots, unique trial coordinates and database triggers
rejecting updates/deletion. Final evaluations reuse existing `agent_evaluations` PostgreSQL history.
Imports are idempotent for identical retained evidence and reject conflicting content. CI uses
retained genuine evidence and explicitly labeled deterministic provider fixtures; it performs no
model requests and needs no model credential.

Execution remains local, networkless and allowlisted, with M1's read-only root/source, uid 1000,
dropped capabilities, no-new-privileges, one CPU, 256 MiB memory/swap, 32 PIDs and bounded logs/tmp.
No new public execution, upload, arbitrary URL/repository/command endpoint or automatic PR publishing
was added. The trusted private Docker coordinator has host-level authority and is not a public
execution service. **In-process Python observations are not a complete anti-tampering boundary
against malicious candidates.** Candidates can introspect their interpreter/probe and Docker shares
the host kernel. Trusted hashes/scoring do not establish adversarial benchmark immunity.

Public historical issues/fixes may be in training data. Finite controls do not prove all input
behavior. The JSON protocol, cumulative context and conservative byte reservations make this a
comparison of the declared model/harness configurations. Protocol errors and context ceilings are
completion limits; they cannot establish intrinsic model coding ability. Local sequential timing
also includes provider conditions and container overhead. Resource samples can miss short processes.
M1 single-turn evidence remains historical and is never combined with these controlled interactive
trials. No uncontrolled external candidate import is presented as a controlled experiment.

## Reproduction and verification

Run from the repository root with Python 3.12, uv, Node/npm, Docker and PostgreSQL available.
The existing evaluator image is built by the integration test when absent; ordinary and independent
execution share the declared pinned image. Import and inspection never make a model request.

```sh
uv sync --project backend --frozen
npm ci --prefix frontend
./scripts/check
uv run --project backend playwright install --with-deps chromium
docker compose up --build -d --wait api
uv run --project backend python -m workbench.evaluator.experiment_cli import
uv run --project backend python -m workbench.evaluator.experiment_cli summary
./scripts/e2e
./scripts/recovery-smoke
docker compose -f compose.release.yaml up --build -d --wait
uv run --project backend python scripts/check_release.py
E2E_BASE_URL=http://127.0.0.1:8020 ./scripts/e2e -k recorded_explorer_first
```

The original generation invocation was `uv run --project backend python -m
workbench.evaluator.experiment_cli generate --live`, followed after all 24 terminal records by
`... experiment_cli score`. Generation is historical: it refuses to reuse the retained campaign
claim. Do not delete claims or regenerate these IDs. The comparison UI was implemented around
these actual outcomes after scoring. A new procedure needs a distinct frozen version.

Fixed ordinary commands inside each approved task environment:

| Task | Command |
| --- | --- |
| bucket | `python -m pytest -q -p no:cacheprovider tests/test_more.py::BucketTests` |
| addlist | `python -m pytest -q -p no:cacheprovider tests/test_dictutils.py tests/test_urlutils.py` |
| seekable | `python -m pytest -q -p no:cacheprovider tests/test_more.py::SeekableTest` |
| IndexedSet | `python -m pytest -q -p no:cacheprovider tests/test_setutils.py` |

Independent commands, probe programs, exact expected observations, verifier hashes and source hashes
are in the frozen task definitions and each execution record. They are not producer inputs.

These three approved reproductions were run concurrently without inference:

```sh
uv run --project backend python -m workbench.evaluator.experiment_cli reproduce m02-v1-boltons-addlist-nemotron35-r02 --output artifacts/evaluator-m02/reproduced-genuine.json
uv run --project backend python -m workbench.evaluator.experiment_cli reproduce boltons-indexedset-negative --output artifacts/evaluator-m02/reproduced-control-failure.json
uv run --project backend python -m workbench.evaluator.cli boltons-addlist-nvidia-01 --output artifacts/evaluator-m02/reproduced-historical-m1-failure.json
```

Expected exit codes are respectively **0, 1, 1**. The new genuine submission passes both procedures;
the authored IndexedSet negative passes ordinary and fails independent; historical M1 Boltons fails
both. The six phase containers are distinct, their ordinary intervals overlap, and source/result
bindings remain correct. Reproductions are additional executions, not new producer trials or
replacement comparison scores. A different locally rebuilt image is recorded as such.

### Focused coverage and observed implementation corrections

Offline fixtures exercise namespace denial, immutable claims and candidate identities, request and
revision ceilings, no automatic retries, unavailable usage, configuration fairness, failed-test
feedback before further action, omitted or reordered events, provenance and score swaps for
identical patches. Aggregation tests include ordinary failures, independent discoveries, provider
failures, no submissions, missing finals and control exclusion. API fixtures test guest denial,
read-only routes and stored-evidence mutation rejection before aggregation.

Docker tests exercise the actual producer boundary, both new task control sets, all retained actual
trials, generation-before-scoring and fresh environments. Browser tests navigate the actual matrix,
patch, transcript, evidence download, saved PostgreSQL evaluation and reload paths, plus failures,
controls and mobile presentation. Separate labeled mocked responses cover ties, zero denominators
and pending evaluation; they are deterministic fixtures, not additional producer evidence. Existing
M1 and debugger integration/browser workflows remain in the full regression suite.

Prefreeze validation caught text-mode CRLF normalization in a new source loader. It was corrected
to preserve bytes and all controls were rerun before freezing. Later verification corrected an
isolation assertion that mistook the base image's public `GPG_KEY` for a provider credential, and a
browser assertion that treated empty Monaco accessibility regions as app errors. Visual inspection
caught a trial-title loading race; the fallback title and capture readiness were fixed. None of
these changed a frozen scoring rule, producer output or comparison result. The first browser
attempt preceded stack readiness and was rerun after the correct build/start sequence.

### Preservation and restricted execution

The before/after row-hash audit verifies all previously captured rows unchanged in five existing
PostgreSQL tables: **135 runs, 23 investigations, 21 repairs, 12 source snapshots and 19 agent
evaluations**. This is a scoped preservation audit, not a claim about every database table or ignored
runtime file. New regression runs append history. Migration 007 is additive; real update/delete
attempts against a separate `development` comparison fixture are rejected by database triggers.
Its fixture row is excluded from the frozen experiment.

The audit also verifies unchanged M1 task/candidate/generation records, freezes, report/assets,
accepted evaluator catalog/runner/behavior/service files, and the previous frozen product experiment.
The original debugger application and repair execution implementation remain intact. The recorded
server has no evaluator/comparison routes, model or database credentials, Docker mount or authority
modules. Its local boundary was checked without public activation. PR #6 remains unmerged,
repository visibility remains private, and no deployment, public execution or Milestone 3 was started.

## Review references and retained evidence

- Accepted M1 final head: `1d49caec6accbb7d640d4e3a90a5978983a42076` ([PR #6](https://github.com/kabbersokhi-boop/ai-debugging-workbench/pull/6)).
- Pre-generation freeze commit: `050dc6adea6993aabcc22a91f36f51cacc3df0ea`.
- Tested implementation: **`5939dcae313c0800335636b816353ce85c54f8ab`**.
- Stacked review: [PR #7](https://github.com/kabbersokhi-boop/ai-debugging-workbench/pull/7), base `feature/agent-evaluator-m01`, head `feature/agent-evaluator-m02`.
- Final review head: `refs/pull/7/head`, resolvable through the [PR commit list](https://github.com/kabbersokhi-boop/ai-debugging-workbench/pull/7/commits). The final evidence/report commit cannot contain its own SHA; the exact final SHA is recorded in the PR description and delivery handoff. Changes after the tested implementation are confined to this report and evidence assets.

### Actual verification results

| Command / check | Actual result |
| --- | --- |
| `./scripts/check` | Ruff, formatting, Pyright and production frontend build pass; **77 passed, 66 deselected**. Existing Monaco chunk-size warning remains. [Log](assets/agent-evaluator-m02/check.log) |
| `./scripts/e2e` | **62 passed, 4 skipped, 77 deselected**, 348.61 s; skips are opt-in live/video scenarios. [Log](assets/agent-evaluator-m02/e2e.log) |
| Focused M2 Docker integration | **4 passed**. [Log](assets/agent-evaluator-m02/focused-integration.log) |
| Focused recorded-server unit checks | **7 passed**. [Log](assets/agent-evaluator-m02/release-unit.log) |
| `./scripts/recovery-smoke` | Interrupted run recovered; completed history unchanged; fresh run reproduced; no runner cleanup errors. [Log](assets/agent-evaluator-m02/recovery.log) |
| `python scripts/check_release.py` through uv | Actual restricted recorded container audit passed; evaluator/comparison paths absent. [Log](assets/agent-evaluator-m02/release-boundary.log) |
| Recorded-server browser command above | **1 passed, 142 deselected**. [Log](assets/agent-evaluator-m02/release-browser.log) |
| Frozen retained-evidence and preservation audit | 24 trial snapshots, six persisted evaluations, all source/trial bindings and previously captured rows verified. [Log](assets/agent-evaluator-m02/audit.log) |

[GitHub Actions on the tested implementation](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/runs/38951904609)
**passed** with no model credentials. It ran the offline checks, retained-trial import, full end-to-end
suite, recovery smoke, recorded-container boundary and recorded browser workflow. See the
[CI job summary](assets/agent-evaluator-m02/ci-implementation.json) and
[sanitized CI transcript](assets/agent-evaluator-m02/ci-implementation.log).
The final report/evidence-only head is also checked by the PR workflow; its exact SHA and CI link
are recorded in the PR description and final delivery handoff.

Retained evidence (all paths are relative to this report):

- [Validated complete matrix](assets/agent-evaluator-m02/comparison.json) and [PostgreSQL-backed matrix with six exact evaluation IDs](assets/agent-evaluator-m02/comparison-persisted.json).
- [Actual immutable trial event streams, final candidates and score bindings](../../evaluation/experiments/m02-v1/trials), [candidate patches](../../evaluation/experiments/m02-v1/candidates), [freeze](../../evaluation/experiments/m02-v1/freeze.json), [new task source/manifests](../../evaluation/experiments/m02-v1/tasks), [frozen controls](../../evaluation/experiments/m02-v1/validation-final-v2), and [development raw evidence](../../evaluation/experiments/m02-v1/smoke).
- [Evidence and preservation audit](assets/agent-evaluator-m02/audit.json), [upstream byte verification](assets/agent-evaluator-m02/upstream-verification.json), [development accounting](assets/agent-evaluator-m02/development-accounting.json), [migration protection](assets/agent-evaluator-m02/migration.json), [actual producer boundary](assets/agent-evaluator-m02/producer-isolation.json), and [recorded release boundary](assets/agent-evaluator-m02/release-boundary.json).
- [Genuine reproduction](assets/agent-evaluator-m02/reproduced-genuine.json), [negative-control reproduction](assets/agent-evaluator-m02/reproduced-control-failure.json), [historical M1 reproduction](assets/agent-evaluator-m02/reproduced-historical-m1-failure.json), and [concurrent source/container bindings](assets/agent-evaluator-m02/concurrent-reproduction.json).
- [Asset SHA-256 manifest](assets/agent-evaluator-m02/manifest.json). Hashes and event chains detect accidental corruption; repository authors can alter code/evidence together, so this is not a cryptographic external attestation.

### Screenshots

These local captures show synthetic upstream task material and retained actual trial evidence.
They contain no production/customer data or credential values.

| View | Capture |
| --- | --- |
| Actual comparison, all 24 trials | [Desktop](assets/agent-evaluator-m02/comparison.png) |
| Submitted genuine patch and code comparison | [Trial](assets/agent-evaluator-m02/genuine-trial.png) |
| Provider failure without a code-defect claim | [Provider failure](assets/agent-evaluator-m02/provider-failure.png) |
| Exhausted generation without automatic promotion | [No submission](assets/agent-evaluator-m02/no-submission.png) |
| Control excluded from agent metrics; empty state first | [Control](assets/agent-evaluator-m02/control-empty-state.png) |
| Historical genuine M1 Boltons failure; empty state first | [M1 failure](assets/agent-evaluator-m02/historical-boltons-result.png) |
| Narrow viewport with the same complete denominators | [Mobile](assets/agent-evaluator-m02/comparison-mobile.png) |

## Investment decision

**Do not proceed to release polish on this evidence.** The evaluator supplies independently observed
behavior and reproducible source-bound evidence, but the measured incremental genuine defect yield
is zero in six completed calibration submissions. Eighteen incomplete attempts, no submitted new-task
results, related model families, historical task contamination and protocol constraints prevent a
useful coding-quality ranking. The equal 3/12 completion counts are a tie with different failure
causes, not a winner. M2 is delivered as the requested small, honest case study; additional product
features would not resolve these evidentiary limits.
