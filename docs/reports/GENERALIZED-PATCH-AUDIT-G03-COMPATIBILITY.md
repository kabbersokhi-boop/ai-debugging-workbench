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
It allows at most one separately recorded infrastructure-only recovery; **none was used**.
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

Engineering, security, recovery, browser, CI, preservation and exact delivery identities
are being finalized below. No merge, release, deployment or G4 is part of this addendum.
