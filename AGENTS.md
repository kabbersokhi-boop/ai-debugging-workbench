# Contributor guidance

Patch Audit checks completed code changes against selected tests and independently justified behavior. Favor complete, understandable user journeys and reproducible results.

## Implementation

Use Python 3.12, typed async services, Pydantic, SQLAlchemy and Alembic. The interface uses React and TypeScript. Persist execution state and evidence. Report infrastructure errors separately from a detected defect.

Repository content is untrusted. Reading or importing it must never execute it. Patches may change only approved production files, never trusted checks, infrastructure or secrets. Setup and tests require restricted containers and approval tied to the exact source, patch, commands and requirements. Check the checking setup with passing and failing examples before evaluating a patch.

Keep browser responses and approvals tied to the current selection. Editing inputs must invalidate dependent plans, approvals and displayed results. Reopening saved results must not rerun code.

## Evidence and compatibility

Preserve accepted commits, source snapshots, historical reports and release tags. Do not change frozen evaluation data or retune against held-out results. In particular, retain `evals/experiment-v2.json`, `evals/final_checks.py`, `evaluation/` and `recordings/` with their original results.

Retain existing verifier implementations and evidence interpretations. Behavior or scoring changes require explicit versioning and continued readability of old records. Expected results must be justified independently of the patch. Keep deliberately faulty test examples separate from genuine historical findings.

A passing result covers only the declared checks. Do not claim universal correctness, measured usability improvements, automatic discovery of specifications or model superiority without supporting evidence.

## Public interface and documentation

Use plain language in the README, getting-started guide and interface. Keep internal phase names, workstation paths, account configuration and review instructions out of product copy. Keep detailed technical reference material separate from first-use instructions. Preserve the source and meaning of archived evidence.

The public application uses only `compose.release.yaml` and the recorded server. It must have no new-code execution, local repository intake, provider credentials, private history or Docker access. Keep the full execution application private.

## Verification and delivery

Run `./scripts/check` and the relevant `./scripts/e2e` journeys. Use the full established CI pipeline before integration. Retain bounded, sanitized CI evidence and describe actual results accurately; preserve failed attempts rather than presenting combined retries as one clean run.

Never commit credentials, environment files, private runtime artifacts or secret-bearing traces. Only sanitized images from approved public or synthetic examples may be committed. Keep money values in integer cents in the retail examples.

Merging, changing repository visibility, publishing a release, deploying and running paid inference require explicit task authorization. Authorization for one action does not authorize the others. Do not force-push or rewrite accepted history.
