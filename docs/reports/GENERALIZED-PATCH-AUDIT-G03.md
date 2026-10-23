# Generalized Patch Audit — G3 real change case study

## Result and recommendation

**FIX before G4.** The bounded investigation produced **zero additional independently
supported defects**. Three of four formally evaluated genuine candidates pass both
layers. One accepted historical upstream patch has a reproducible compatibility
regression, already caught by the unchanged ordinary tests. No new upstream discovery
or population accuracy claim is made.

**Intended coverage was not achieved:** six patches / three repositories / Python and
Node were frozen; four patches / two repositories / Python completed formal scoring.
One Node reference had unsupported ordinary dependencies; the other source was rejected
before admission. These cases remain visible, with their original failures preserved.
This is a deliverable for review under the prompt's bounded-subset provision, not a claim
that full intended G3 coverage passed. No G4 work is started.

## Procedure and selection

The [selection rules](../../evaluation/repository-examples/g3/SELECTION.md) were committed
at `fa81245` before screening. Six repositories and eight task/patch pairs were inspected,
within ceilings of eight repositories and twelve pairs. The immutable
[screening log](../../evaluation/repository-examples/g3/screening.json) records the initial
inclusions/exclusions. It is not overwritten to conceal the two later compatibility misses.

- `jaraco/inflect`: environment-only exclusion (unavailable runtime dependencies).
- `jpvanhal/inflection`: two repairs selected.
- `okunishinishi/python-stringcase`: two repairs selected.
- `vercel/ms`: two patches excluded because unchanged tests require unavailable `expect.js`.
- `jonschlinkert/arr-flatten`: two performance refactors selected, then unsupported in preflight.
- `davidchambers/string-format`: metadata/environment screen only; current test workflow needs
  unavailable `sanctuary-scripts`. No task screened. The final two shortlisted repositories
  were not screened; no replacement search followed candidate observations.

This is a convenience sample of historical, dependency-light functions. Codex read public
fixes and discussions before preparing specifications; it is **retrospective, not blind or
held out**, and there was no separate human semantic review or captured model generation.
The owner authorized the workflow, not the truth of every assertion. All six candidates are
upstream developer submissions; no AI-generated authorship is claimed.

The campaign was committed at **`4dcbdc4` before any execution**:
[declaration](../../evaluation/repository-examples/g3/campaign.json), SHA-256
`7d521577539d910c9a86b546bf775a56b0d0f200c9da477c36140a055f4df161`.
It fixes patches, requirements, assertions, runtime images, policy, commands, order,
interpretation and finite execution/recovery limits. Named assertion rationales, exact
source excerpts/hashes, original diffs, admitted projections, licenses, base documents
and relevant upstream issue material are in [the case material](../../evaluation/repository-examples/g3/cases.json).

All original production hunks are retained; submitted test hunks are consistently excluded.
The ordinary baseline is the unchanged existing test file at each candidate's own parent.
The two flattening revisions address performance at different bases, share one contract,
and do not establish a speed improvement. The four Python revisions address distinct fixes;
the later inflection title fix's base includes the earlier inflection plural fix.

### Immutable candidates and actual outcomes

Every row has the full base/revision and original/admitted hashes in its linked provenance.
Counts below come from actual framework output, not inferred from exit status.

| Genuine upstream candidate | Parent base | Ordinary result per formal trial | Independent result per formal trial | Repeats |
|---|---|---|---|---|
| [inflection plural](../../evaluation/repository-examples/g3/inflection-plural/provenance.json), `1969b3a06a9ff06d023863e388cf8af01978d297` | `2d2d37951f6c8871d27a1c74a2c0c1fe6a9354fb` | 450 passed | 5 / 5 passed | 2 / 2 agree |
| [inflection title](../../evaluation/repository-examples/g3/inflection-title/provenance.json), `e32443bb7dc1ba91a15336b5baab908d25f4b93a` | `1969b3a06a9ff06d023863e388cf8af01978d297` | 453 passed | 6 / 6 passed | 2 / 2 agree |
| [stringcase alphanumeric](../../evaluation/repository-examples/g3/stringcase-alpha/provenance.json), `fdf27a6734482564747138bdf7a351d482a20ea9` | `cc7d5eb58ff4a959a508c3f2296459daf7c3a1f2` | 13 passed | 5 / 5 passed | 2 / 2 agree |
| [stringcase camel case](../../evaluation/repository-examples/g3/stringcase-camel/provenance.json), `f79de04e856be5661208ff5360f183815f8ae760` | `50fe41d3c9bebf001f24fc49b89fe023b5eba12c` | 12 passed / 1 failed | 5 passed / 1 failed | 2 / 2 agree |
| [flatten recursive optimization](../../evaluation/repository-examples/g3/flatten-recursive/provenance.json), `1597ea90072a2eaff8e523523e0105cac0bf195c` | `280845c6f384fab8ff07a1395de9568270636528` | No formal trial; reference cannot load `array-flatten`; test count unknown | Reference and authored alternative each 5 / 5 passed | Formal pair missing |
| [flatten loop optimization](../../evaluation/repository-examples/g3/flatten-for/provenance.json), `8953ce8522ee6da8a467286c9bce23fc03b7f38e` | `966022a4a9190ddf8c8936daa80d1a7f9f77ecb3` | No admission/execution | No observation | Formal pair missing |

### Requirements and check validation

The inflection plural task uses upstream PR #40's explicit formal `passersby` requirement;
colloquial `passerby` is acknowledged by that source. This plan fixes the formal-output
interpretation; exact JSON equality cannot accept both legitimate variants. A colloquial
implementation would need a different approved plan and must not be called generally wrong
from this formal-only check. No such genuine candidate was evaluated here. Issue #33 explicitly requests `Ana Índia` capitalization. Base docstrings,
ordinary test context and standard possessive spelling justify the compatibility cases.
The stringcase base README gives exact camel-case and ASCII alphanumeric examples;
issue #23 adds joining capitalized words. The flattening READMEs promise recursive,
ordered flattening; empty arrays contribute no leaves, objects/scalars remain leaves,
and duplicates stay duplicated. Expected outputs were derived from these rules, not
copied from candidate observations. Unicode alphanumeric policy, acronym policy,
sparse arrays, alternate encodings and arbitrary object coercions are outside these plans.

For five admitted tasks, a credible accepted upstream implementation was exercised as a
reference. **It is the same implementation later scored**, not an independent oracle or
proof that the spec is right. A separately authored implementation using a different
procedure was also exercised per task: a word exception, word-initial transformation,
ASCII regex filtering, separator-aware camel joining, or Node's native recursive flatten.
These alternatives are explicit controls, not genuine candidate submissions. All five
alternatives satisfy their named assertions; four have runnable ordinary baselines.

Ten positive/negative validation audits passed (20 synthetic control environments), within
the frozen twelve-audit ceiling. Literal-return controls establish comparison mechanics
only. Specification checks exposed **one semantic reference disagreement out of five**:
the camel patch lowercases the entire input, changing documented `FooBarBaz` → `fooBarBaz`
into `foobarbaz`. The unchanged baseline independently fails on `FooBar` → `foobar`.
Both formal trials reproduce it. The alternative retains capitals and satisfies the newly
requested spaced-word behavior. This is one historical compatibility root cause,
**zero additional independent detections**, and not a checker false alarm.

No requirement or expected value was changed after observations. No observed check error,
unresolved semantic ambiguity, or suspected false alarm remains in these declared domains;
this small set does not establish a general false-positive rate.

### Preserved failures and versioned procedure

[Original preflight output](../../evaluation/repository-examples/g3/results/preflight-v1.log)
retains all twenty original runs and the terminal source rejection. The recursive flatten
ordinary test imports `array-flatten`, absent offline. Both reference and alternative fail
before any test runs, while their independent checks pass. This is unsupported test setup,
not a candidate defect. The later base contains
`benchmark/code/arr-flatten-0.1.0 (do-while).js`, rejected by the accepted path contract.
No path restriction, test, dependency or sandbox limit was weakened to make these fit.
The screen inspected a newer dependency-free test file too early; failing to verify each
historical base's entire environment was a selection mistake, now documented.

A driver review also found that re-fetching source would change the snapshot's `fetched_at`
and invalidate the earlier controls. Before formal scoring,
[procedure v1.1](../../evaluation/repository-examples/g3/procedure-v1.1.json), committed at
`5068d5f`, changed orchestration to reuse the exact prepared identities and skip explicitly
blocked cases. There was no failed formal run from that orchestration issue. The original
campaign, expectations, observer and preflight evidence remain intact. No evaluator defect
was found, no initial outcome was rescored, and no semantic retries were performed.

## Counts, reproducibility and effort

The UI/report accounting is generated from the **28 validated application downloads** in
[the evidence index](../../evaluation/repository-examples/g3/results/index.json), with
[additive explanations](../../evaluation/repository-examples/g3/results/adjudications.json).
It is not a manually entered scorecard. Hash manifests bind retained files; they are content
identities, not signatures or proof of semantic truth.

| Measure | Actual denominator and result |
|---|---|
| Screening | 6 repositories; 8 task/patch pairs considered; 6 provisionally selected / 2 excluded pairs |
| Final compatibility | 4 eligible formal cases / 6 selected; 2 unsupported; 5 admitted patches |
| Formal scoring | 8 / 12 intended audits; 4 / 6 candidates, 2 / 3 repositories, Python only |
| Ordinary pass + independent pass | 3 / 4 evaluated candidates (6 / 8 formal runs) |
| Ordinary failures | 1 / 4 evaluated candidates (2 / 8 formal runs) |
| Additional supported independent defects | **0 / 3 ordinary-passing candidates** |
| Missing planned formal evaluations | 4 / 12 audits, both unsupported Node cases |
| Repeated-run disagreements | 0 / 4 completed candidate pairs; statuses and exact observations agree |
| Semantic reference disagreements | 1 / 5 reference executions; ordinary tests also fail |
| Authored alternative acceptance | 5 / 5 independent plans; 4 / 4 runnable ordinary baselines |
| Check errors / unresolved semantic disagreements | 0 observed / 5 exercised check plans; sixth never exercised |
| Campaign infrastructure execution errors | 0 / 28 admitted API runs; one unsupported intake rejection retained separately |
| Controls / specification runs | 10 validation audits + 5 reference + 5 alternative; separate from 8 formal audits |
| Recovery retries / new model calls | 0 / 0 |

The [specification trace audit](assets/generalized-patch-audit-g03/specification-trace-audit.json)
checks all six exact excerpts/hashes. The [production projection audit](assets/generalized-patch-audit-g03/projection-audit.json)
compares all five admitted genuine implementations with the exact upstream revision bytes;
all match. Baseline test files, modules, documentation and licenses also match retained base material.

The measured interval from first control start to last formal completion was **243.884
seconds**. Summed environment execution durations were **85.484 seconds**, excluding
intake, control orchestration, analysis and application/tooling development. These are
measured timestamps, not estimated onboarding labor or dollar costs. Manual historical
base/dependency and specification review was the main practical effort; no claim of
one-click arbitrary repository support is justified.

Reproduction (private local stack, existing pinned Python/Node images). The fresh-execution
recipe is for a separately versioned reproduction, not permission to exceed the completed
campaign limits. The retained-evidence commands do not execute target code:

```bash
# Inert freeze verification and deterministic retained-evidence replay:
uv run --project backend pytest backend/tests/test_repository_campaign.py \
  backend/tests/test_campaign_replay.py -q
# Fresh local executions are opt-in, in a NEW output directory; preserve original results:
mkdir -p artifacts/repository-audit-g3/reproduction
cp evaluation/repository-examples/g3/results/blocked.json \
  artifacts/repository-audit-g3/reproduction/blocked.json
uv run --project backend python scripts/repository_campaign_g3.py --phase preflight \
  --output artifacts/repository-audit-g3/reproduction --confirm-local-execution
uv run --project backend python scripts/repository_campaign_g3.py --phase score \
  --output artifacts/repository-audit-g3/reproduction --confirm-local-execution
# Review summary of the retained campaign without executing target code:
uv run --project backend python scripts/repository_campaign_g3.py --phase summary \
  --output evaluation/repository-examples/g3/results \
  --adjudications evaluation/repository-examples/g3/results/adjudications.json
```

Exact ordinary commands are frozen per case: Python runs `python -m pytest -q -p
no:cacheprovider test_inflection.py` or `stringcase_test.py`; Node runs pinned Mocha on
`test.js`. These are the complete selected unchanged files, **not full upstream CI suites**.
The declaration binds exact local image IDs; a fresh build on another machine can have a
different image ID. Reproduction requires those captured images or a separately versioned
procedure declaring the rebuilt images; the driver deliberately refuses silent substitution.
Fixed independent commands and adapter hashes are unchanged from accepted G2. Ordinary and
independent phases use identical candidate source in different fresh environments. Every
approval, command/output, expected/observed value, source/image identity, timing and cleanup
record is retained in the compressed JSON downloads; `gzip -dc FILE.json.gz` opens one.

## Review integration, safety and verification

The existing local Patch Audit view now has one campaign selector and a compact evidence
table. It distinguishes formal candidate/repeat/reference/alternative/control roles,
shows incomplete coverage, and opens the existing requirement/outcome view. Downloads and
saved links revalidate registered evidence; no execution starts when opening it. The public
recorded server remains separate, without campaign intake or execution routes.

Safety restrictions remain unchanged: no candidate network, host bind, credentials or
Docker socket; non-root, read-only source/verifier and bounded resources/output. Downloaded
project code was executed only in the broker's restricted environments. Original licenses
and attribution remain in source evidence and the minimal retained material.

### Verification and delivery identities

Tested G3 implementation: **`679e3e739d172a83a8ccb8a085006c99392012de`**.
[Stacked PR #14](https://github.com/kabbersokhi-boop/ai-debugging-workbench/pull/14) targets
accepted G2 at `a9e9eceefc567a5eee3c86f7d736973fafff629d`; PRs #12 and #13 remain
unmerged. Final review head is `refs/pull/14/head`, resolved to its exact SHA in the PR
body and handoff. The final report/evidence commit changes no runtime code after the
tested implementation.

Campaign execution used the unchanged accepted G2 engine and `json-observer-v2` material
at `c96449dd3b14513cb53601ba21ca4754a77fb3f4`. G3 adds orchestration, evidence accounting
and review integration, not a second scorer. The final runtime audit matches backend files
and every served frontend asset to the tested worktree.

| Gate | Actual result and evidence |
|---|---|
| `./scripts/check` | **309 passed**, Ruff/Pyright/frontend build passed; [log](assets/generalized-patch-audit-g03/check.log). Existing Monaco chunk-size warning retained. |
| Focused campaign offline replay | **19 passed**, including freeze, identity, tampering, controls/repeats, unsupported/infrastructure classification, exact downloads and all 28 saved records; [log](assets/generalized-patch-audit-g03/focused-offline.log). |
| Full local `./scripts/e2e` | **89 passed / 4 existing live opt-ins skipped**, 656.35 seconds; [log](assets/generalized-patch-audit-g03/e2e.log). This used `3328fd8` application bytes; the sole later implementation change reuses existing form/table CSS classes. |
| Final local campaign browser | **1 passed** at `679e3e7`, exact download/reopen and no new execution; [log](assets/generalized-patch-audit-g03/campaign-browser.log). |
| Exact implementation CI | [Full workflow passed](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/runs/39841085657) on **`679e3e739d172a83a8ccb8a085006c99392012de`**: 309 offline, 89 integration, 4 skips, recovery, recorded authority boundary and 2 recorded browser tests; [exact CI summaries](assets/generalized-patch-audit-g03/ci-implementation.json). |
| `./scripts/recovery-smoke` | Completed history unchanged, interrupted work reconciled, fresh reproduction succeeded, no runner cleanup errors; [log](assets/generalized-patch-audit-g03/recovery-smoke.log). Existing G1/G2 cancellation/recovery integration checks also passed. |
| Actual saved G2/G3 history after recovery | **36 exact original records and downloads unchanged**: 28 G3 + 8 original G2; zero new executions from reopening; [audit](assets/generalized-patch-audit-g03/api-history-audit.json). |
| Rebuilt local recorded server | `scripts/check_release.py` passed: non-root/read-only, no authority modules/socket/credentials/mounts and zero execution slots; [proof](assets/generalized-patch-audit-g03/recorded-boundary.json). Both new G3 routes return GET 404 / POST 405; [route proof](assets/generalized-patch-audit-g03/recorded-campaign-boundary.json). **2 recorded browser tests passed**; [log](assets/generalized-patch-audit-g03/recorded-browser.log). This is loopback review, not a deployment. |
| Runtime and preservation | [Runtime byte audit](assets/generalized-patch-audit-g03/runtime-audit.json); [completion audit](assets/generalized-patch-audit-g03/completion-audit.json): 28 validated records, 56 distinct environments, **150 actual Docker resources confirmed absent**, **1,275 historical files unchanged**, accepted observer/engine/archive unchanged. |

The [generated summary](assets/generalized-patch-audit-g03/summary.json) and
[SHA256 artifact manifest](assets/generalized-patch-audit-g03/manifest.json) make the
report material inspectable. Original G1/G2 evidence, the v1 archive, frozen earlier
experiments and public release assets remain intact. Two superseded duplicate CI runs
were cancelled; successful checks are cited by exact implementation SHA. No failed
campaign outcome was deleted or replaced.

## Remaining product limits and G4 decision

**FIX**: first verify the complete immutable base and its ordinary dependencies during
screening, then establish genuinely supported cross-language coverage in a separately
approved bounded milestone. Also assess prospective specification quality on changes not
already read in public history. The current case study shows repeatability, appropriate
acceptance of several legitimate changes, and one accurate but redundant warning. It does
not demonstrate additional value beyond ordinary tests on genuine changes or broad
repository compatibility. No leaderboard, model benchmark, deployment, merge, film,
visibility change or G4 implementation was performed.

### Retained browser captures

Actual local browser captures (public upstream code and local synthetic data only):

- [Passing Unicode title case](assets/generalized-patch-audit-g03/inflection-title.png).
- [Ordinary and independent camel regression](assets/generalized-patch-audit-g03/stringcase-camel.png).
- [Unsupported ordinary dependency](assets/generalized-patch-audit-g03/flatten-recursive.png).
- [Rejected source with no execution](assets/generalized-patch-audit-g03/unsupported-source.png).

These are saved evidence views of the declared executions, not new campaign trials.
The browser test checks navigation, exact downloads, saved-link reload and an unchanged
execution-history list. Source/patch/requirement details remain inspectable in the existing
view and validated JSON; no new dashboard, confidence score or benchmark was added.
