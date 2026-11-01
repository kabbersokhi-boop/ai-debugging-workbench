# Your first Patch Audit

Use the recorded viewer to inspect evidence without installing anything:
<https://ai-debugging-workbench-recorded.vercel.app/>. It cannot import or execute new code.
The public viewer presents the released interface and historical examples; fresh audits stay local.

## Start the private local application

Prerequisites: Git, Docker with Compose, sufficient space for the pinned browser/Python/Node
images, and a local environment you control. Image building and the trusted API’s repository intake/PR
preview require outbound network access to their package sources and GitHub respectively. Candidate
execution containers remain network-disabled. Linux is the tested environment. No model key is needed for Patch Audit.

Use current `main` for the prepared workflow, reusable checklists and generated Python checks.
The older published v1.2.1 tag does not include these features. From the repository root:

```sh
docker compose up --build -d --wait api
```

Open <http://127.0.0.1:8010/> and choose **Audit a completed patch**. This is a privileged local
execution stack. Do not expose it to the internet. Use a disposable isolated VM for adversarial
source; container isolation is not a complete hostile-code sandbox.

## Run a prepared example locally

Choose **Run a prepared example locally** from the local home page. The Python example
is prefilled; use **Prepared example** to switch to the accepted Node HTML escaping example.
These inputs come directly from the accepted [example definitions](../evaluation/repository-examples/g2/examples.json).
The patches are historical developer changes, with their original sources shown in the interface.

1. Review the pinned repository and commit. Select **Fetch source for review** and inspect
   its source identities and attribution. Fetching never runs repository code.
2. Review the prefilled production file scope and exact patch. Select **Validate patch for review**.
3. Review the runtime, offline setup, selected tests and timeout. Select **Prepare exact plan for approval**.
4. Review the prepared requirement, supporting excerpt, justification, assumptions, target,
   input arguments and expected results. Explicitly approve the requirement and its supporting source,
   then select **Prepare independent plan**.
5. Approve the positive and negative synthetic controls, then **Validate independent checker**.
   This starts restricted local execution. Successful controls validate the checker;
   they do not establish the truth of the specification. Inspect the validation evidence
   and approve the exact independent plan.
6. Approve the exact source, patch and existing-test plan, then **Run existing tests and independent checks**.
7. Inspect the separate existing-test and independent-check results. Download the evidence
   and exact patch. Reopening the saved audit reads evidence without executing it again.

No JSON editing is needed. Expand the advanced configuration sections for custom inputs.
Editing bound inputs invalidates their existing plans and approvals. Both prepared examples
still use the normal source admission, patch admission and exact execution approval services.
Runtime images must be built locally before a plan can be prepared.

The interface measures setup from example selection until the run request, including review
and control validation. Actual command durations remain separately recorded in audit evidence.
These local timings are session measurements, not observations of unfamiliar developers.

## PR links and unsupported inputs

Expand **Start from a public GitHub pull request** and enter a canonical URL such as
`https://github.com/owner/repository/pull/123`. The local preview reads public metadata only,
shows observed base/head SHAs and counts, and admits no source or patch. Private/deleted heads,
redirects, rate limits and invalid URLs fail visibly. The PR can change after preview. Its base
tip may differ from its diff's merge-base; deliberately choose the immutable source and a
compatible production-only patch for manual intake. Preview values are not recomputed source
or candidate identities, and never authorize execution.

Tests/configuration changes, new/deleted files, unsupported paths, excessive source budgets,
missing offline dependencies and incompatible runtime behavior remain unsupported. Intake
restrictions apply equally to manual and PR-inspired workflows. No green result substitutes
for rejected, invalid, interrupted or infrastructure evidence.

## Inspect rather than execute

For the authentic AI missed-copy case, open **Recorded examples** and select the retained
Boltons development repair. Ordinary checks passed; the standalone copy failed independent
checks. Related assertion failures describe one defect. The historical patch study panels in the private
repository workspace retain separate original/addendum evidence and their honest zero-additional-
discovery result. Neither replay starts execution.

Stop local services with `docker compose down`; saved volumes remain. `down -v` deletes local
history. For contributor checks see [README](../README.md) and the
[historical engineering report](reports/GENERALIZED-PATCH-AUDIT-G04.md).

## Reuse a project checklist

After configuring the existing-test plan and independent requirements, name the checklist,
choose its revision, and select **Download reusable project checklist**. This exports
`project-checklist-v1`: source compatibility declarations, production scope, commands,
justified requirements, supported inputs, and named checks. It contains no execution
approval. Keep this file under your own project's version control.

For a subsequent patch, fetch its immutable source and admit the patch, then load the
file in **Reuse a project checklist**. Review the compatibility result and declarations.
Approve the requirements, select **Prepare checklist plans for review**, validate fresh
positive/negative controls, and approve the exact plans before executing. The new run
retains the checklist's content hash, revision, and exact application binding in its evidence.

Supported commits and required file hashes are explicit. A different repository, missing
source, changed hashes or unsupported patch scope is incompatible. An undeclared revision
or retired verifier is outdated. Review the contract before adding supported revisions,
update source hashes deliberately, and increment the checklist revision when declarations
change. Portable files do not consult a central registry for a newer revision of the same
name. Historical evidence retains the checklist bytes that actually applied.

Use **Download readable report** beside the complete JSON evidence download. The Markdown
report includes source and patch identities, existing-test and independent-check results, requirements,
inputs and observations, command output, approval, and inspection/reproduction instructions.

## Use the same local workflow from a terminal

The local stack must be running. Start with the checked-in
[Python checklist](../examples/checklists/python-first-v1.json) or
[Node checklist](../examples/checklists/node-escape-html-v1.json), or export your own from the
browser. These example checklists reuse the accepted historical example definitions.
The CLI talks only to the local API on `127.0.0.1:8010`; it uses the same intake,
admission, plan preparation, control validation, approval, execution and evidence services.
No model key is needed.

```sh
uv run --project backend python -m workbench.repository_audit.cli prepare \
  --checklist examples/checklists/python-first-v1.json \
  --patch evaluation/repository-examples/g2/python-positive.patch \
  --commit 106ee3cf389cf2bb76f2816bf22a845c44275f94 \
  --approve-requirements --out preparation.json
```

Preparation admits the inputs and prints the exact plans plus an approval fingerprint;
it never starts execution. Review the entire preparation and substitute that fingerprint
for `REVIEWED_FINGERPRINT` below. A changed preparation has a different fingerprint.

```sh
uv run --project backend python -m workbench.repository_audit.cli controls \
  --preparation preparation.json --approve-exact REVIEWED_FINGERPRINT \
  --out-dir audit-evidence

uv run --project backend python -m workbench.repository_audit.cli run \
  --preparation preparation.json --approve-exact REVIEWED_FINGERPRINT \
  --validation VALIDATION_AUDIT_ID --out-dir audit-evidence

uv run --project backend python -m workbench.repository_audit.cli evidence \
  EXECUTION_AUDIT_ID --out-dir audit-evidence
```

`controls` prints its validation audit ID after successful controls. `run` requires that
candidate-bound validation plus new exact approval. Both commands export JSON evidence,
a readable Markdown report, and the exact patch. `evidence` only reads saved evidence.
Exit status 0 means the selected operation passed its declared checks, 1 means a completed
non-passing or incomplete audit, and 2 means admission, request or local I/O failure.
An observation deadline reports the existing audit ID and never starts a retry.

Use `prepare --snapshot-id ADMITTED_SOURCE_ID` with the same `--commit` to reuse an already
admitted local snapshot. Reusing declarations or source never reuses execution approval.

The checked-in [project-checklist-v1 JSON Schema](../schemas/project-checklist-v1.schema.json)
is the portable format contract. Unknown fields (including saved approvals) are rejected.
The browser validates exports against the same backend model before downloading them.

## Generate and simplify Python failures

The Python independent-scope section offers **Generate bounded Python inputs and simplify
failures**. Start with the prepared Python example, or configure your own immutable source,
production patch and existing-test plan. Review a separately justified requirement, target file
and public function. Choose one of the trusted built-in reference behaviors:

- `first_truthy`: first Python-truthy scalar in a list, or `None`.
- `integer_sum`: sum a list of integers.
- `integer_sort`: return integers in ascending order.

Generation supports a single positional list containing values from an explicitly approved
palette of at most eight scalars. Scalars are null, booleans, integers from -32 to 32, or
strings of at most 16 characters; integer properties require integer-only palettes. Lists
have at most eight elements. These are deterministic, stateless function checks, with
bounded JSON outputs. Other call shapes, reference programs, arbitrary expected-result programs,
stateful behavior and unsupported values are outside this verifier.

Review the source excerpt, justification and input domain. Explicitly approve the selected
property as an executable interpretation of that requirement and approve the budgets.
Prepare the generated plan, inspect its exact source/patch/test-plan identities,
property, domain, seed, case/reduction limits, host implementation hash and observer bytes.
Approve and validate its positive/negative synthetic controls; then approve the exact
validated generated plan and final existing-test plan before execution. Editing inputs clears
approval and controls. Control validation checks the adapter and generated assertions;
it does not establish that a specification is true.

The host creates inputs and expectations. Candidate code runs in restricted containers,
with existing tests and observer runs separate. Up to 32 initial cases and four reduction
rounds of up to 16 proposals are allowed. Every observer batch gets a fresh environment.
The original failure must replay, and the final retained input must fail consistently in
two further fresh environments. The per-observer timeout is at most 15 seconds (five by
default). A complete execution uses at most eight observer environments plus existing tests.
A timeout, invalid observation or inconsistent replay does not become a confirmed reduced
counterexample. Passing covers only the declared generated cases. Reduction is a bounded
search for a simpler example, never a globally smallest-input claim.

The result shows **input → expected behavior → actual observation**, its requirement's
justification, original failing input, limits, complete execution trace and reproduction
declaration. Download JSON evidence and the readable report as in the existing workflow.
Previous named checks remain available under verifier v2; historical v1/v2 evidence stays
readable. Generated v3 uses the separate [generated-plan-v1 schema](../schemas/generated-plan-v1.schema.json).

### Terminal generation and exact replay

First use `prepare` with the Python checklist and selected patch as described above. It
produces a candidate-bound `preparation.json` without executing. Then explicitly approve
the generated property and budgets from the example search declaration:

```sh
uv run --project backend python -m workbench.repository_audit.cli generated-prepare \
  --preparation preparation.json --search examples/generation/first-truthy-v3.json \
  --approve-property --out generated-preparation.json
```

Use `controls` and `run` with this new preparation's reviewed fingerprint. They use the same
exact approval and evidence services as named checks. The prepared source's existing
requirement must justify the property; generation requires exactly one approved requirement
and the same Python runtime image as the existing-test plan.

For a retained counterexample, create a new plan that explicitly replays its reduced input:

```sh
uv run --project backend python -m workbench.repository_audit.cli generated-prepare \
  --preparation preparation.json --search examples/generation/first-truthy-v3.json \
  --replay-audit FAILING_AUDIT_ID --approve-property --out replay-preparation.json
```

This loads and semantically validates the original generated-v3 failure. The original source,
candidate, existing-test plan, requirement, target, runtime, property, domain, seed, case budget
and verifier material must match; conflicting preparation/search files are rejected.
The local replay-plan endpoint repeats the identity check against saved evidence. It derives
the plan from the original, sets `replay_inputs` to the retained input and disables further
reduction. The supplied search may retain its original reduction setting or set it to zero;
it may retain the original replay list or contain only that exact retained input. These are
the only replay-specific substitutions. To change the property or domain, omit
`--replay-audit` and prepare a new experiment, which is not an exact reproduction.

Review the new fingerprint,
run fresh controls, and approve a new execution. Reopening a saved audit or downloading its
reproduction declaration performs no execution. Replay execution carries the original audit
reference and rejects controls created before that audit completed, including replay of an
already reduced replay whose plan hash happens to be unchanged. The original audit remains
intact and each new execution is saved separately. The algorithm and observer belong to the
new v3 verifier; future behavior changes must use a new version and retain v3 history.
