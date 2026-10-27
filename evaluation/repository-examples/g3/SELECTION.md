# G3 selection procedure (before screening)

This is a retrospective case study prepared by Codex from public upstream
material, not a blind, held-out benchmark or independent human review.

## Eligibility

- Public, licensed repository not used in G1/G2; inert intake must fit existing limits.
- A completed, identifiable upstream production change with an immutable parent/base.
- Python 3.12 or Node 22; offline tests using the existing pytest/Mocha images.
- Observable behavior through the existing finite JSON function-call contract.
- An issue, documented API, or public contract that justifies exact expected values
  independently of the scored implementation. Ambiguous tasks are excluded or disputed.
- Preserve the full original diff; consistently project only existing production files,
  excluding tests/docs. Never omit a production dependency/configuration hunk to fit.
- Up to four existing production files, no new dependencies or writable-source setup.
- Prefer two distinct upstream fixes per repository; two valid patches are acceptable.

## Bound and order

Screen at most eight repositories and twelve task/patch pairs, stopping when six
eligible candidates from three repositories cover Python and Node and at least two
behavior categories. Initial shortlist, in order: `jaraco/inflect` (compatibility
screen only), `jpvanhal/inflection`, `okunishinishi/python-stringcase`, `vercel/ms`,
`jonschlinkert/arr-flatten`, `davidchambers/string-format`, `mahmoud/glom`,
`python-humanize/humanize`. No search for failures or minimum finding count.

Record each screened repository and pair, inclusion/exclusion reason, source and
provenance uncertainty. No candidate code runs during screening. Specification
validation uses restricted application containers and is bounded separately from
formal scoring. Freeze all selected patches, requirements, assertions, images,
commands, run order, controls and retry rules in a committed declaration before
formal scoring. Preserve every attempt and any procedure correction additively.

## Interpretation

An ordinary failure is not an additional independent detection. A semantic mismatch
needs specification investigation; adapter errors, insufficient evidence and ambiguous
contracts cannot be labeled candidate defects. Repeats and controls do not increase
the genuine-candidate or finding denominator. Zero additional findings is valid.
