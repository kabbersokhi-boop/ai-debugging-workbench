# Case study: a passing test suite missed half of a repair

## The question

Selected test suites can pass while a changed behavior remains incomplete. Patch Audit explores a
narrow question: can a developer make the expected behavior explicit, justify it independently of
the candidate patch, and retain enough evidence for another person to inspect what was checked?

This is a workbench for declared checks, not an automatic specification-discovery system or a
general proof of correctness.

## The retained Boltons example

The source is a pinned public revision of Boltons. In one separate development run, an AI-generated
patch updated the `Remap` implementation in `boltons/dictutils.py` but missed a standalone copy in
`boltons/urlutils.py`. The retained patch and generation record are available in the
[original development evidence](../evaluation/experiments/m02-v2/README.md).

The selected upstream test command passed **155 tests**. The independent requirement came from the
upstream documented `Remap` behavior, not from the candidate. A separately approved check exercised
the standalone implementation with empty input. It observed length `1` where the declared behavior
required `0`; keys and items were empty as expected. These observations describe **one incomplete
repair**: the missed implementation copy. A separate retained complete patch covers both copies,
but came from a different procedure and is not a controlled model comparison.

The [saved public record](https://ai-debugging-workbench-recorded.vercel.app/?recordedAudit=m02-v2-development-boltons-addlist-nemotron3-r02)
reopens the actual evidence without re-execution. Inspect the [exact patch](../evaluation/experiments/m02-v2/development/independent/m02-v2-development-boltons-addlist-nemotron3-r02.patch),
[generation provenance](../evaluation/experiments/m02-v2/development/independent/m02-v2-development-boltons-addlist-nemotron3-r02.json),
and [independent observations](../recordings/patch-audit-missed.json).

## From one example to a local workbench

The retained case exposed a useful product question, not a performance claim. The project evolved
from a prepared example into a local workflow for bounded public Python and Node repositories:

1. Pin and inspect an immutable source snapshot. Intake does not execute repository code.
2. Admit and review an exact, production-only patch.
3. Declare the runtime and selected ordinary test command explicitly.
4. Optionally add requirements whose provenance is reviewed independently of the patch, with named
   finite inputs and expected values.
5. Validate positive and negative controls, then approve the exact source, patch and plans.
6. Run separate restricted local environments and retain the ordinary and independent outcomes,
   observations, logs and downloadable evidence.

The [quickstart](PATCH-AUDIT-QUICKSTART.md) walks through a real accepted example. This workflow
does not infer correct requirements from code or a model. A passing result applies only to the
declared checks and environment.

## A separate retrospective study (G3)

G3 examined **six genuine historical developer candidate patches**, using its separately frozen
method and requirements. Five passed the selected ordinary tests; one regression was already
detected by those tests. Independent checks produced **zero additional findings**. G3 therefore
does not show added detection value on its sample, and does not estimate accuracy or false-positive
rates. The Boltons AI-generated development example above is a distinct study with different
provenance and is not part of that denominator.

See the [G3 report](reports/GENERALIZED-PATCH-AUDIT-G03.md) and its
[Node compatibility addendum](reports/GENERALIZED-PATCH-AUDIT-G03-COMPATIBILITY.md) for the
method, candidate accounting, and limitations. The earlier producer comparison is another
separate evidence set; its outcomes are summarized in the [final review](reports/PATCH-AUDIT-FINAL-REVIEW.md).

## What proved difficult

The hard part is not adding another test runner. It is deciding where expected behavior comes from,
keeping candidate code away from the oracle and its expected values, binding approval to exact
inputs, separating ordinary and independent outcomes, and preserving evidence through interruption
and restart. The product also has to make an absent or unsupported check visible without presenting
it as a pass. The [architecture](ARCHITECTURE.md), [code tour](CODE_TOUR.md), and
[G1–G4 reports](reports/GENERALIZED-PATCH-AUDIT-G04.md) document those decisions and their tests.

## What is available today

- The public site replays genuine saved evidence, diffs, observations and downloads. It cannot
  import a repository or execute a patch.
- The local application supports explicitly approved Python 3.12 and Node 22 audit plans under
  bounded container restrictions.
- Saved history can be reopened without rerunning a candidate; interrupted execution and
  infrastructure failure remain distinct outcomes.
- The project has not established universal correctness, broad defect-detection rates, or a
  complete sandbox for hostile code. Containers share the host kernel; adversarial work belongs in
  an isolated disposable VM.

## Provenance and ownership

Repository artifacts establish the retained inputs, code, tests, execution records and release
history. They do not by themselves establish who made each design or implementation decision, what
anyone learned, or which work was completed unaided. **This presentation review and its copy, UI and
media edits were prepared with Codex assistance.** No unaided-authorship claim is made. Personal
ownership, motivation and learning statements should be added only after the project owner confirms
them.
